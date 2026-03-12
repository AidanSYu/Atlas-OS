"""Executor Agent — Script generation sandbox for Discovery OS (Phase 5).

Implements transparent Python script execution:
  1. Plan next task based on research goals
  2. Generate Python script using deterministic tools (RDKit, pandas, etc.)
  3. Save script to discovery/{session_id}/generated/
  4. Optional: interrupt() for human approval
  5. Execute script in subprocess sandbox
  6. Save outputs (logs.txt, results.csv, plots.png)
  7. Loop until all goals satisfied or max iterations

Uses MemorySaver checkpointing with thread_id = f"executor-{session_id}".

Living .md Knowledge Substrate
-------------------------------
Session root (.md files the agents read and write):
  SESSION_INIT.md    — written by coordinator after initialization
  FINDINGS.md        — appended by executor after every successful run
  HYPOTHESES.md      — user or agent writes; guides iteration direction
  CONSTRAINTS.md     — user drops domain constraints here
  RESEARCH_NOTES.md  — any background knowledge the user wants agents to know

Agents read ALL .md files at the start of each run so knowledge accumulates.
"""
import asyncio
import logging
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command

from app.services.discovery_llm import DiscoveryLLMService
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Living .md Knowledge Helpers
# ============================================================

# Priority order for .md files — most important context first
_MD_PRIORITY = [
    "SESSION_INIT.md",
    "FINDINGS.md",
    "HYPOTHESES.md",
    "CONSTRAINTS.md",
    "RESEARCH_NOTES.md",
]


def _read_session_notes(session_id: str, max_chars: int = 3000) -> str:
    """Read all .md files from the session root folder.

    Returns a concatenated string that is injected into every agent prompt,
    giving agents awareness of: coordinator output, prior findings, user
    hypotheses/constraints, and any background notes the user dropped in.

    This is the core mechanism for the "living knowledge substrate" —
    agents accumulate understanding across iterations via these files.
    """
    session_path = Path(settings.DATA_DIR) / "discovery" / session_id
    if not session_path.exists():
        return ""

    parts: list[str] = []
    seen: set[str] = set()

    # Priority files first (trimmed to preserve context budget)
    for fname in _MD_PRIORITY:
        fpath = session_path / fname
        if fpath.exists():
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")[:1500]
                parts.append(f"=== {fname} ===\n{text}")
                seen.add(fname)
            except OSError as exc:
                logger.warning("Failed to read session note %s: %s", fpath, exc)

    # Any other .md files the user may have dropped in the session folder
    for fpath in sorted(session_path.glob("*.md")):
        if fpath.name not in seen:
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")[:400]
                parts.append(f"=== {fpath.name} ===\n{text}")
            except OSError as exc:
                logger.warning("Failed to read session note %s: %s", fpath, exc)

    combined = "\n\n".join(parts)
    return combined[:max_chars]


def _read_key_artifacts(session_id: str, max_chars: int = 1500) -> str:
    """Read the tail of execution_log.txt and head of any CSV in generated/.

    Gives plan_task actual result data from prior runs so it can make
    intelligent decisions about what to do next (not just see filenames).
    """
    generated = Path(settings.DATA_DIR) / "discovery" / session_id / "generated"
    if not generated.exists():
        return ""

    parts: list[str] = []

    # Last 40 lines of execution log (most recent run output)
    log_path = generated / "execution_log.txt"
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = "\n".join(lines[-40:])
            parts.append(f"=== execution_log.txt (last 40 lines) ===\n{tail}")
        except OSError:
            pass

    # First 20 lines of the most recently modified CSV
    csv_files = sorted(generated.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if csv_files:
        try:
            lines = csv_files[0].read_text(encoding="utf-8", errors="replace").splitlines()
            preview = "\n".join(lines[:20])
            parts.append(f"=== {csv_files[0].name} (first 20 lines) ===\n{preview}")
        except OSError:
            pass

    combined = "\n\n".join(parts)
    return combined[:max_chars]


def _append_findings(
    session_id: str,
    task: str,
    iteration: int,
    output: str,
    artifacts: list,
) -> None:
    """Append execution results to FINDINGS.md for persistent learning.

    This file is re-read at the start of every subsequent plan_task call,
    so the agent continuously builds on what it has already discovered.
    User can also read and annotate this file between runs.
    """
    session_path = Path(settings.DATA_DIR) / "discovery" / session_id
    findings_path = session_path / "FINDINGS.md"

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    header_needed = not findings_path.exists()

    try:
        with open(findings_path, "a", encoding="utf-8") as f:
            if header_needed:
                f.write(
                    "# Research Findings\n\n"
                    "Auto-updated log of all execution results. "
                    "Agents read this file before planning each next step.\n\n"
                )
            f.write(f"## Iteration {iteration} — {timestamp}\n\n")
            f.write(f"**Task**: {task}\n\n")
            if artifacts:
                f.write(f"**Artifacts generated**: {', '.join(artifacts)}\n\n")
            if output:
                # Keep the most informative portion (tail of stdout usually has summaries)
                summary = output[-800:] if len(output) > 800 else output
                f.write(f"**Output**:\n```\n{summary.strip()}\n```\n\n")
    except OSError as exc:
        logger.warning("Failed to append to FINDINGS.md: %s", exc)


# ============================================================
# State
# ============================================================

class ExecutorState(TypedDict, total=False):
    session_id: str
    project_id: str
    extracted_goals: List[str]  # from coordinator

    # Script generation
    current_task: str
    generated_script: str
    script_filename: str
    script_description: str
    required_packages: List[str]
    script_status: str  # "draft" | "approved" | "rejected" | "executed"

    # Execution
    execution_output: str
    execution_error: Optional[str]
    artifacts_generated: List[str]

    # Loop control
    iteration: int
    max_iterations: int
    status: str  # "planning" | "scripting" | "awaiting_approval" | "executing" | "complete"
    auto_approve: bool


# ============================================================
# LLM Constrained Output Schemas
# ============================================================

TASK_PLANNING_SCHEMA = {
    "type": "object",
    "properties": {
        "assessment": {
            "type": "string",
            "description": "Analysis of current progress and remaining goals"
        },
        "next_task": {
            "type": "string",
            "description": "The specific next task to accomplish (or 'complete' if all goals satisfied)"
        },
        "reasoning": {
            "type": "string",
            "description": "Why this task is the logical next step"
        },
    },
    "required": ["assessment", "next_task", "reasoning"],
}

SCRIPT_GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "script_code": {
            "type": "string",
            "description": "Complete Python script with imports, error handling, and output saving"
        },
        "filename": {
            "type": "string",
            "description": "Script filename (e.g., generate_candidates.py)"
        },
        "description": {
            "type": "string",
            "description": "Plain English summary of what the script does"
        },
        "required_packages": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of required Python packages"
        },
    },
    "required": ["script_code", "filename", "description", "required_packages"],
}


# ============================================================
# Graph Builder
# ============================================================

def _build_executor_graph(
    llm_service: DiscoveryLLMService,
    auto_approve: bool = False,
) -> StateGraph:
    """Build the Executor StateGraph with optional HITL for script approval."""

    async def plan_task(state: ExecutorState) -> dict:
        """Node 1: Analyze goals, session notes, and prior results — plan next task."""
        session_id = state.get("session_id", "")
        goals = state.get("extracted_goals", [])
        iteration = state.get("iteration", 0)

        # Check existing artifacts in generated/ folder
        generated_folder = Path(settings.DATA_DIR) / "discovery" / session_id / "generated"
        generated_folder.mkdir(parents=True, exist_ok=True)

        existing_files = [f.name for f in generated_folder.iterdir() if f.is_file()]
        existing_summary = ", ".join(existing_files) if existing_files else "None yet"

        # Read living .md knowledge substrate (SESSION_INIT.md, FINDINGS.md, user notes)
        session_notes = _read_session_notes(session_id)
        # Read actual content of prior run outputs (log tail + latest CSV preview)
        artifact_content = _read_key_artifacts(session_id)

        notes_section = f"\n=== SESSION KNOWLEDGE (from .md files) ===\n{session_notes}" if session_notes else ""
        artifacts_section = f"\n=== PRIOR RUN RESULTS ===\n{artifact_content}" if artifact_content else ""

        prompt = f"""You are a research automation planner for a chemistry discovery session.

=== RESEARCH GOALS ===
{chr(10).join(f"- {g}" for g in goals) if goals else "None specified"}

=== ARTIFACT FILES IN SESSION ===
{existing_summary}
{notes_section}{artifacts_section}

=== CURRENT ITERATION ===
Iteration {iteration + 1}

Based on the research goals, prior run outputs, and any notes/findings above:
- Determine the NEXT specific, actionable task.
- If prior results show candidates were generated, the next step should screen/filter them.
- If screening is done, the next step might be to analyze top candidates or generate variants.
- Only set next_task to "complete" if ALL research goals are meaningfully satisfied.

Respond with the required JSON schema."""

        try:
            result = await llm_service.generate_constrained(
                prompt=prompt,
                schema=TASK_PLANNING_SCHEMA,
                temperature=0.3,
                max_tokens=512,
            )
        except Exception as exc:
            logger.error("Executor planning failed: %s", exc)
            raise RuntimeError(
                f"Executor planning failed — Discovery OS requires DeepSeek and MiniMax "
                f"API keys to be configured. Check your .env file. Original error: {exc}"
            ) from exc

        next_task = result.get("next_task", "complete")

        if next_task.lower() == "complete":
            return {
                "status": "complete",
                "current_task": "All goals satisfied",
            }

        return {
            "current_task": next_task,
            "status": "scripting",
        }

    async def generate_script(state: ExecutorState) -> dict:
        """Node 2: Generate Python script for current task."""
        task = state.get("current_task", "")
        goals = state.get("extracted_goals", [])
        session_id = state.get("session_id", "")

        # Check existing artifacts again for context
        generated_folder = Path(settings.DATA_DIR) / "discovery" / session_id / "generated"
        existing_files = [f.name for f in generated_folder.iterdir() if f.is_file()]
        existing_summary = ", ".join(existing_files) if existing_files else "None yet"

        # Read session notes for domain constraints and prior findings
        session_notes = _read_session_notes(session_id)
        notes_section = f"\n=== SESSION KNOWLEDGE (constraints, findings, notes) ===\n{session_notes}" if session_notes else ""

        prompt = f"""You are a scientific computing agent generating Python scripts for chemistry research.

=== RESEARCH GOALS ===
{chr(10).join(f"- {g}" for g in goals) if goals else "None specified"}

=== EXISTING ARTIFACTS ===
{existing_summary}
{notes_section}

=== CURRENT TASK ===
{task}

Generate a complete, executable Python script that:
1. Uses deterministic tools (RDKit, NumPy, Pandas — NO LLM calls, NO external APIs that require auth)
2. Saves all outputs to the current directory (logs.txt, results.csv, plots.png)
3. Includes error handling and progress logging to stdout
4. Is fully self-contained (no external file dependencies except RDKit data)
5. Writes structured output (CSV or JSON) for machine readability

Available packages: rdkit, pandas, numpy, matplotlib, pathlib, csv, json

IMPORTANT: The script will execute in the directory where it's saved.
Use relative paths only. Print progress messages.

Example template:
```python
import sys
from pathlib import Path
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors

def main():
    print("Starting task: {task}")

    # Your logic here
    results = []

    # Save results
    df = pd.DataFrame(results)
    df.to_csv("results.csv", index=False)
    print(f"Saved {{len(results)}} results to results.csv")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {{e}}", file=sys.stderr)
        sys.exit(1)
```

Respond with the required JSON schema."""

        try:
            result = await llm_service.generate_constrained(
                prompt=prompt,
                schema=SCRIPT_GENERATION_SCHEMA,
                temperature=0.4,
                max_tokens=2048,
            )
        except Exception as exc:
            logger.error("Script generation failed: %s", exc)
            raise RuntimeError(
                f"Script generation failed — Discovery OS requires DeepSeek and MiniMax "
                f"API keys to be configured. Check your .env file. Original error: {exc}"
            ) from exc

        script_code = result.get("script_code", "")
        raw_filename = result.get("filename", "script.py")
        description = result.get("description", "Generated script")
        packages = result.get("required_packages", [])

        # Sanitize filename to prevent directory traversal
        filename = os.path.basename(raw_filename) or "script.py"

        # Save script to generated/ folder
        generated_folder = Path(settings.DATA_DIR) / "discovery" / session_id / "generated"
        script_path = (generated_folder / filename).resolve()
        if not script_path.is_relative_to(generated_folder.resolve()):
            logger.error("Rejected script filename with path traversal: %s", raw_filename)
            return {"status": "complete", "execution_error": "Invalid script filename rejected."}

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_code)
        except Exception as exc:
            logger.error("Failed to save script: %s", exc)
            return {
                "status": "complete",
                "execution_error": f"Failed to save script: {exc}"
            }

        return {
            "generated_script": script_code,
            "script_filename": filename,
            "script_description": description,
            "required_packages": packages,
            "script_status": "draft",
            "status": "awaiting_approval" if not state.get("auto_approve") else "executing",
        }

    async def await_approval(state: ExecutorState) -> dict:
        """Node 3: HITL — wait for human approval/rejection/edit."""
        script_code = state.get("generated_script", "")
        filename = state.get("script_filename", "")
        description = state.get("script_description", "")
        packages = state.get("required_packages", [])

        approval_payload = {
            "script_code": script_code,
            "filename": filename,
            "description": description,
            "required_packages": packages,
        }

        # interrupt() pauses graph, surfaces payload to frontend
        user_decision = interrupt(approval_payload)

        # --- Execution resumes here after Command(resume=...) ---

        session_id = state.get("session_id", "")
        decision_str = str(user_decision).lower()

        if decision_str == "reject":
            return {
                "script_status": "rejected",
                "status": "complete",
            }

        if decision_str.startswith("edit:"):
            # Extract edited code
            edited_code = str(user_decision)[5:].strip()
            # Save edited version
            generated_folder = Path(settings.DATA_DIR) / "discovery" / session_id / "generated"
            script_path = generated_folder / filename
            try:
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(edited_code)
                return {
                    "generated_script": edited_code,
                    "script_status": "approved",
                    "status": "executing",
                }
            except Exception as exc:
                logger.error("Failed to save edited script: %s", exc)
                return {"status": "complete", "execution_error": str(exc)}

        # Default: approve
        return {
            "script_status": "approved",
            "status": "executing",
        }

    async def execute_script(state: ExecutorState) -> dict:
        """Node 4: Execute Python script in sandboxed subprocess."""
        session_id = state.get("session_id", "")
        raw_filename = state.get("script_filename", "")
        iteration = state.get("iteration", 0)

        # Sanitize filename to prevent directory traversal
        filename = os.path.basename(raw_filename) or ""
        generated_folder = Path(settings.DATA_DIR) / "discovery" / session_id / "generated"
        script_path = (generated_folder / filename).resolve()
        if not script_path.is_relative_to(generated_folder.resolve()):
            logger.error("Rejected script_filename with path traversal: %s", raw_filename)
            return {"status": "complete", "execution_error": "Invalid script filename rejected."}

        if not script_path.exists():
            return {
                "execution_error": f"Script not found: {filename}",
                "status": "complete"
            }

        try:
            # Execute with timeout
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(generated_folder),
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes
                env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent.parent)},
            )

            # Append to execution log
            log_file = generated_folder / "execution_log.txt"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Script: {filename} (Iteration {iteration + 1})\n")
                f.write(f"{'='*60}\n")
                f.write(f"STDOUT:\n{result.stdout}\n")
                if result.stderr:
                    f.write(f"STDERR:\n{result.stderr}\n")
                f.write(f"Exit Code: {result.returncode}\n")

            if result.returncode != 0:
                return {
                    "execution_error": result.stderr or "Script failed with non-zero exit code",
                    "execution_output": result.stdout,
                    "script_status": "executed",
                    "iteration": iteration + 1,
                    "status": "complete",  # Stop on error (or could retry with plan_task)
                }

            # List all artifacts
            artifacts = [f.name for f in generated_folder.iterdir() if f.is_file()]

            # Append findings to FINDINGS.md — this is how the agent "learns" across iterations
            task = state.get("current_task", "")
            _append_findings(
                session_id=session_id,
                task=task,
                iteration=iteration + 1,
                output=result.stdout,
                artifacts=artifacts,
            )

            return {
                "execution_output": result.stdout,
                "execution_error": None,
                "artifacts_generated": artifacts,
                "script_status": "executed",
                "iteration": iteration + 1,
                "status": "planning",  # Loop back to plan next task
            }

        except subprocess.TimeoutExpired:
            return {
                "execution_error": "Script execution timeout (5 minutes)",
                "status": "complete"
            }
        except Exception as exc:
            logger.exception("Script execution failed")
            return {
                "execution_error": str(exc),
                "status": "complete"
            }

    def should_await_approval(state: ExecutorState) -> str:
        """Route: auto-approve or wait for human?"""
        if state.get("auto_approve"):
            return "execute"
        return "await"

    def should_continue(state: ExecutorState) -> str:
        """Route: loop back or end?"""
        status = state.get("status", "complete")
        iteration = state.get("iteration", 0)
        max_iterations = state.get("max_iterations", 10)

        if status == "complete" or iteration >= max_iterations:
            return "end"
        return "continue"

    # Assemble graph
    sg = StateGraph(ExecutorState)
    sg.add_node("plan_task", plan_task)
    sg.add_node("generate_script", generate_script)
    sg.add_node("await_approval", await_approval)
    sg.add_node("execute_script", execute_script)

    sg.set_entry_point("plan_task")
    sg.add_edge("plan_task", "generate_script")

    sg.add_conditional_edges("generate_script", should_await_approval, {
        "await": "await_approval",
        "execute": "execute_script",
    })

    sg.add_edge("await_approval", "execute_script")

    sg.add_conditional_edges("execute_script", should_continue, {
        "continue": "plan_task",
        "end": END,
    })

    return sg


# ============================================================
# Streaming Execution
# ============================================================

async def run_executor_streaming(
    session_id: str,
    project_id: str,
    extracted_goals: Optional[List[str]] = None,
    llm_service: Optional[DiscoveryLLMService] = None,
    auto_approve: bool = False,
    cancel_event: Optional[asyncio.Event] = None,
    resume_command: Optional[str] = None,
) -> AsyncGenerator[Tuple[str, dict], None]:
    """Stream executor events. Yields (event_type, event_data) tuples.

    Args:
        session_id: Discovery session ID
        project_id: Project ID
        extracted_goals: Research goals (if None, loads from session memory)
        llm_service: Discovery LLM service
        auto_approve: If True, skip approval interrupts
        cancel_event: Cancellation signal
        resume_command: Command to resume graph execution (e.g. "approve", "reject", "edit:...")

    Event types:
        executor_thinking:          {"content": "..."}
        executor_script_generated:  {"filename": "...", "code": "...", "description": "..."}
        executor_awaiting_approval: {"filename": "...", "preview": "..."}
        executor_executing:         {"filename": "...", "iteration": ...}
        executor_artifact:          {"filename": "...", "type": "log|csv|py"}
        executor_complete:          {"artifacts": [...], "summary": "..."}
        error:                      {"message": "..."}
    """
    from app.core.memory import get_memory_saver
    from app.services.discovery_session import SessionMemoryService

    # Load session memory for multi-agent coordination
    session_memory = SessionMemoryService.load_session_memory(session_id)

    if extracted_goals is None:
        # Bootstrap from session memory (coordinator already ran)
        if session_memory is None:
            yield ("error", {"message": "Session not initialized. Run coordinator first."})
            return

        extracted_goals = session_memory.research_goals
        if not extracted_goals:
            yield ("error", {"message": "No research goals found in session memory."})
            return

        yield ("executor_thinking", {
            "content": f"Loaded {len(extracted_goals)} goals from session memory. Domain: {session_memory.domain}"
        })
    else:
        # Goals provided explicitly (legacy path)
        yield ("executor_thinking", {"content": f"Starting with {len(extracted_goals)} provided goals..."})

    memory = await get_memory_saver()
    sg = _build_executor_graph(llm_service, auto_approve)
    compiled = sg.compile(checkpointer=memory)

    thread_id = f"executor-{session_id}"
    config = {"configurable": {"thread_id": thread_id}}

    # Check if resuming (approval decision) or initial trigger
    snapshot = await compiled.aget_state(config)
    is_resume = bool(snapshot.next)

    if is_resume:
        if resume_command:
            # We are resuming execution with the user's decision
            yield ("executor_thinking", {"content": "Resuming execution with your decision..."})
            input_value = Command(resume=resume_command)
        else:
            # Graph is paused but no resume command provided
            yield ("executor_thinking", {"content": "Graph is paused waiting for approval."})
            return
    else:
        # Initial trigger
        yield ("executor_thinking", {"content": "Planning first task..."})
        input_value = {
            "session_id": session_id,
            "project_id": project_id,
            "extracted_goals": extracted_goals,
            "iteration": 0,
            "max_iterations": 10,
            "status": "planning",
            "auto_approve": auto_approve,
        }

    try:
        async for event in compiled.astream(input_value, config=config, stream_mode="updates"):
            if cancel_event and cancel_event.is_set():
                return

            for node_name, update in event.items():
                if not isinstance(update, dict):
                    continue

                if node_name == "plan_task":
                    task = update.get("current_task", "")
                    status = update.get("status", "")
                    if status == "complete":
                        artifacts = update.get("artifacts_generated", [])
                        yield ("executor_complete", {
                            "artifacts": artifacts,
                            "summary": f"Execution complete. Task: {task}",
                        })
                    else:
                        yield ("executor_thinking", {"content": f"Task planned: {task}"})

                elif node_name == "generate_script":
                    filename = update.get("script_filename", "")
                    code = update.get("generated_script", "")
                    desc = update.get("script_description", "")
                    yield ("executor_script_generated", {
                        "filename": filename,
                        "code": code,
                        "description": desc,
                        "required_packages": update.get("required_packages", []),
                    })

                elif node_name == "execute_script":
                    filename = update.get("script_filename", "")
                    iteration = update.get("iteration", 0)
                    error = update.get("execution_error")

                    if error:
                        yield ("error", {"message": f"Execution failed: {error}"})
                    else:
                        yield ("executor_executing", {
                            "filename": filename,
                            "iteration": iteration,
                        })

                        # Yield artifacts
                        artifacts = update.get("artifacts_generated", [])
                        for artifact in artifacts:
                            ext = Path(artifact).suffix.lstrip(".")
                            yield ("executor_artifact", {
                                "filename": artifact,
                                "type": ext or "txt",
                            })

    except Exception as exc:
        logger.exception("Executor streaming failed")
        yield ("error", {"message": str(exc)})
        return

    # Check final state
    try:
        final_snapshot = await compiled.aget_state(config)

        if not final_snapshot.next:
            # Completed
            final_state = final_snapshot.values or {}
            if final_state.get("status") == "complete":
                artifacts = final_state.get("artifacts_generated", [])
                yield ("executor_complete", {
                    "artifacts": artifacts,
                    "summary": f"Execution complete after {final_state.get('iteration', 0)} iterations.",
                })
            return

        # Graph is paused — extract interrupt payload
        for task in (final_snapshot.tasks or []):
            if hasattr(task, "interrupts") and task.interrupts:
                approval_data = task.interrupts[0].value
                if isinstance(approval_data, dict):
                    yield ("executor_awaiting_approval", {
                        "filename": approval_data.get("filename", ""),
                        "preview": approval_data.get("script_code", "")[:500] + "...",
                        "description": approval_data.get("description", ""),
                    })
                return

    except Exception as exc:
        logger.warning("Failed to read executor snapshot: %s", exc)
        yield ("error", {"message": f"State read error: {exc}"})
