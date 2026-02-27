"""Discovery OS ReAct Agent - LangGraph StateGraph implementation.

Implements the two-layer architecture:
  Layer 1 (Semantic): LLM generates TOOL_CALL_SCHEMA JSON via GBNF grammar
  Layer 2 (Deterministic): PluginManager dispatches to CPU-only tools

The loop: think -> decide -> execute -> observe -> think -> ... -> final_answer
"""
import asyncio
import json
import logging
import os
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from langgraph.graph import StateGraph, END

from app.services.llm import LLMService
from app.services.plugins import get_plugin_manager
from app.services.agents.discovery_state import DiscoveryState
from app.services.agents.tool_schemas import (
    PHASE1_TOOLS,
    PHASE2_TOOLS,
    PHASE_TOOLS,
    TOOL_INPUT_SPECS,
    validate_tool_input,
)
from app.core.config import settings
from app.services.synthesis_memory import get_synthesis_memory

logger = logging.getLogger(__name__)


# ============================================================
# SYSTEM PROMPT BUILDER
# ============================================================

def _build_system_prompt(
    available_tools: List[str], phase: str, spectrum_file: str = ""
) -> str:
    """Build the system prompt with dynamic tool availability.

    Includes per-tool input specifications and few-shot examples so that
    both small local models (7B) and SOTA cloud models produce correct
    tool calls reliably.
    """
    pm = get_plugin_manager()

    tool_lines = []
    for tool_name in available_tools:
        plugin = pm.get_plugin(tool_name)
        if plugin:
            spec = TOOL_INPUT_SPECS.get(tool_name, {})
            required = spec.get("required", [])
            desc = plugin.description
            req_str = ", ".join(f'"{k}"' for k in required) if required else "none"
            tool_lines.append(f"- **{tool_name}**: {desc}  Required keys: {req_str}")

    if "search_literature" in available_tools:
        tool_lines.append(
            '- **search_literature**: Search uploaded research papers for relevant passages.  '
            'Required keys: "query"'
        )
    if "final_answer" in available_tools:
        tool_lines.append(
            '- **final_answer**: Provide the final answer to the user.  '
            'Required keys: "query_answer"'
        )

    tool_block = "\n".join(tool_lines)

    phase_context = ""
    if phase == "verification" and spectrum_file:
        phase_context = (
            f'\n\n**Verification mode active.** An NMR spectrum file "{spectrum_file}" '
            "has been uploaded. The file_path will be injected automatically when you call "
            "verify_spectrum — you only need to provide the SMILES string of the expected molecule."
        )

    return f"""You are Atlas Discovery OS, a scientific reasoning agent. You answer chemistry and biology questions by calling deterministic tools. You NEVER generate molecular data yourself — you always use tools.

Current workflow phase: {phase}{phase_context}

## Available Tools

{tool_block}

## Output Format

For each step you MUST output a single JSON object with exactly three fields:

```json
{{"thought": "your reasoning", "action": "tool_name", "action_input": {{...}}}}
```

When you have enough information, use action "final_answer":
```json
{{"thought": "I have all the data I need.", "action": "final_answer", "action_input": {{"query_answer": "your complete answer citing tool results"}}}}
```

## Examples

User: "What are the properties of aspirin?"
```json
{{"thought": "I need to predict molecular properties for aspirin. Its SMILES is CC(=O)OC1=CC=CC=C1C(=O)O.", "action": "predict_properties", "action_input": {{"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"}}}}
```

User: "Is caffeine toxic?"
```json
{{"thought": "I should check caffeine for structural toxicity alerts. Caffeine SMILES: CN1C=NC2=C1C(=O)N(C(=O)N2C)C.", "action": "check_toxicity", "action_input": {{"smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"}}}}
```

User: "What do my papers say about Lipinski's rule of five?"
```json
{{"thought": "I should search the user's uploaded literature for information about Lipinski's rule of five.", "action": "search_literature", "action_input": {{"query": "Lipinski rule of five drug-likeness"}}}}
```

User: "Verify this NMR spectrum against aspirin"  (verification phase, .jdx file attached)
```json
{{"thought": "I have an uploaded .jdx file. I should verify the spectrum against aspirin's SMILES.", "action": "verify_spectrum", "action_input": {{"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"}}}}
```

## Rules

1. NEVER invent SMILES strings, molecular weights, or property values — always call predict_properties.
2. Always provide the "smiles" key (not "molecule" or "name") when calling predict_properties or check_toxicity.
3. Check toxicity before recommending any molecule.
4. Use search_literature to find relevant context from the user's uploaded papers.
5. Cite tool results (exact numbers, scores) in your final answer.
6. If a tool returns an error, explain the error and try an alternative approach.
7. If the user asks about a named molecule (e.g. "aspirin"), you MUST know or look up its SMILES. Common molecules: aspirin=CC(=O)OC1=CC=CC=C1C(=O)O, ibuprofen=CC(C)CC1=CC=C(C=C1)C(C)C(=O)O, caffeine=CN1C=NC2=C1C(=O)N(C(=O)N2C)C, paracetamol=CC(=O)NC1=CC=C(O)C=C1."""


def _get_progress_message(node_name: str) -> str:
    """Human-readable progress messages for discovery nodes."""
    return {
        "think": "Reasoning about next step...",
        "execute": "Executing tool...",
    }.get(node_name, f"Processing: {node_name}...")


def _format_prompt(llm_service: LLMService, system: str, user: str) -> str:
    """Format system+user into the correct chat template for the active model.

    Handles local models (qwen, phi3, llama3) and API models transparently.
    """
    if llm_service._model_source == "api":
        return f"{system}\n\n{user}"

    model_type = getattr(llm_service, "_model_type", "llama3")
    formatters = {
        "qwen": "_format_qwen_prompt",
        "phi3": "_format_phi3_prompt",
    }
    formatter = formatters.get(model_type, "_format_llama3_prompt")
    return getattr(llm_service, formatter)(system, user)


# ============================================================
# GRAPH BUILDER
# ============================================================

def _build_discovery_graph(
    llm_service: LLMService,
    retrieval_service: Any,
) -> StateGraph:
    """Build the ReAct StateGraph for discovery workflows.

    Nodes:
        think:   LLM generates a ToolCall JSON via GBNF-constrained generation
        execute: Dispatches to PluginManager or RetrievalService

    Edges:
        think -> (conditional) -> execute | END
        execute -> think
    """
    pm = get_plugin_manager()

    async def think_node(state: DiscoveryState) -> DiscoveryState:
        """LLM generates next action via constrained JSON generation."""
        messages = state.get("messages", [])
        # Phase 2 tools provide synthesis planning in addition to predictions
        available_tools = state.get("available_tools", PHASE2_TOOLS)
        phase = state.get("phase", "hit_identification")
        iteration = state.get("current_iteration", 0)

        history_lines = []
        for msg in messages:
            if msg["role"] == "assistant":
                history_lines.append(f"Thought: {msg.get('thought', '')}")
                history_lines.append(f"Action: {msg.get('action', '')}")
                if msg.get("action_input"):
                    history_lines.append(f"Action Input: {json.dumps(msg['action_input'])}")
            elif msg["role"] == "tool":
                output_str = json.dumps(msg["output"])
                if len(output_str) > 800:
                    output_str = output_str[:800] + "..."
                history_lines.append(f"Observation [{msg['name']}]: {output_str}")

        history_text = "\n".join(history_lines)

        spectrum_path = state.get("spectrum_file_path", "")
        spectrum_basename = os.path.basename(spectrum_path) if spectrum_path else ""
        system_prompt = _build_system_prompt(available_tools, phase, spectrum_basename)
        user_prompt = f"User query: {state['query']}"
        if history_text:
            user_prompt += f"\n\nPrevious steps:\n{history_text}"
        user_prompt += "\n\nWhat is your next step? Respond with JSON only."

        dynamic_schema = {
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "The agent's reasoning about what to do next",
                },
                "action": {
                    "type": "string",
                    "enum": available_tools,
                },
                "action_input": {
                    "type": "object",
                    "description": "Arguments for the selected tool",
                },
            },
            "required": ["thought", "action", "action_input"],
        }

        prompt = _format_prompt(llm_service, system_prompt, user_prompt)

        try:
            raw = await llm_service.generate_constrained(
                prompt=prompt,
                schema=dynamic_schema,
                temperature=0.1,
                max_tokens=512,
            )
        except Exception as e:
            logger.error(f"Constrained generation failed: {e}")
            raw = {
                "thought": f"Generation error: {e}. Providing final answer.",
                "action": "final_answer",
                "action_input": {"query_answer": "I encountered an error during reasoning. Please try again."},
            }

        if not isinstance(raw, dict) or not raw:
            raw = {
                "thought": "Failed to parse model output.",
                "action": "final_answer",
                "action_input": {"query_answer": str(raw) if raw else "No response from model."},
            }

        thought = raw.get("thought", "")
        action = raw.get("action", "final_answer")
        action_input = raw.get("action_input", {})

        if not isinstance(action_input, dict):
            action_input = {}

        if action not in available_tools:
            logger.warning(f"LLM selected invalid tool '{action}', forcing final_answer")
            action = "final_answer"
            action_input = {"query_answer": f"Could not determine correct tool. {thought}"}

        # Validate and repair tool inputs
        if action not in ("final_answer", "search_literature"):
            valid, error_msg, repaired = validate_tool_input(action, action_input)
            if not valid:
                logger.warning(f"Invalid input for {action}: {error_msg}. Attempting repair.")
                if repaired:
                    action_input = repaired
                else:
                    # Let the tool handle the error; it will return a descriptive message
                    pass

        new_msg = {
            "role": "assistant",
            "thought": thought,
            "action": action,
            "action_input": action_input,
        }
        messages = list(messages) + [new_msg]

        trace = list(state.get("reasoning_trace", []))
        trace.append(f"[Step {iteration}] Thought: {thought[:200]}")
        trace.append(f"[Step {iteration}] Action: {action}")

        return {
            **state,
            "messages": messages,
            "reasoning_trace": trace,
            "current_iteration": iteration,
        }

    async def execute_node(state: DiscoveryState) -> DiscoveryState:
        """Execute the tool selected by the LLM."""
        messages = state.get("messages", [])
        if not messages:
            return {**state, "status": "error"}

        last_msg = messages[-1]
        action = last_msg.get("action", "")
        action_input = last_msg.get("action_input", {})
        iteration = state.get("current_iteration", 0)

        if not isinstance(action_input, dict):
            action_input = {}

        try:
            if action == "search_literature":
                search_query = action_input.get(
                    "query",
                    action_input.get("query_text", state.get("query", "")),
                )
                result = await retrieval_service.query_atlas(
                    user_question=search_query,
                    project_id=state.get("project_id"),
                )
                raw_chunks = result.get("context", {}).get("vector_chunks", [])
                output = {
                    "chunks": [
                        {
                            "text": c.get("text", "")[:500],
                            "source": c.get("metadata", {}).get("filename", c.get("source", "Unknown")),
                            "page": c.get("metadata", {}).get("page", c.get("page", 0)),
                            "score": round(c.get("relevance_score", c.get("score", 0)), 3),
                        }
                        for c in raw_chunks[:5]
                    ],
                    "total_results": len(raw_chunks),
                }
            elif action == "final_answer":
                output = action_input
            elif action == "verify_spectrum":
                # Inject file_path from state — the LLM only provides smiles
                spectrum_path = state.get("spectrum_file_path", "")
                if "file_path" not in action_input and spectrum_path:
                    action_input["file_path"] = spectrum_path
                output = await pm.invoke(action, **action_input)
            else:
                output = await pm.invoke(action, **action_input)
        except Exception as e:
            logger.error(f"Tool execution failed ({action}): {e}")
            output = {"error": str(e), "tool": action}

        obs_msg = {"role": "tool", "name": action, "output": output}
        messages = list(messages) + [obs_msg]

        trace = list(state.get("reasoning_trace", []))
        output_summary = json.dumps(output)
        if len(output_summary) > 300:
            output_summary = output_summary[:300] + "..."
        trace.append(f"[Step {iteration}] {action} result: {output_summary}")

        candidates = list(state.get("candidates", []))
        if action == "predict_properties" and output.get("valid"):
            smiles = output.get("smiles", "")
            existing = next((c for c in candidates if c.get("smiles") == smiles), None)
            if existing:
                existing["properties"] = output
            else:
                candidates.append({"smiles": smiles, "properties": output})
        elif action == "check_toxicity" and output.get("valid"):
            smiles = output.get("smiles", "")
            existing = next((c for c in candidates if c.get("smiles") == smiles), None)
            if existing:
                existing["toxicity"] = output
            else:
                candidates.append({"smiles": smiles, "toxicity": output})

        # ─── Phase 4: stash synthesis route on the matching candidate ───
        elif action == "plan_synthesis" and not output.get("error"):
            smiles = action_input.get("smiles", "")
            routes = output.get("routes", [])
            if smiles and routes:
                existing = next((c for c in candidates if c.get("smiles") == smiles), None)
                if existing:
                    existing["synthesis_route"] = routes[0] if routes else {}
                else:
                    candidates.append({"smiles": smiles, "synthesis_route": routes[0] if routes else {}})

        evidence = list(state.get("evidence", []))
        if action == "search_literature":
            for chunk in output.get("chunks", []):
                evidence.append({
                    "source": chunk.get("source", ""),
                    "page": chunk.get("page", 0),
                    "excerpt": chunk.get("text", "")[:200],
                    "relevance": chunk.get("score", 0),
                })

        # ─── Phase 4: persist to knowledge graph after spectrum verification ───
        experiment_node_id = state.get("experiment_node_id", "")
        if action == "verify_spectrum" and not output.get("error"):
            match_score = output.get("match_score")
            # Find the best SMILES candidate from state (the one we were verifying)
            best_candidate = candidates[0] if candidates else {}
            smiles = best_candidate.get("smiles", action_input.get("smiles", ""))
            route = best_candidate.get("synthesis_route", {})
            assay_result = state.get("assay_result", {})

            if smiles:
                mem = get_synthesis_memory()
                try:
                    node_id = await mem.record_experiment(
                        project_id=state.get("project_id", ""),
                        smiles=smiles,
                        route=route,
                        match_score=match_score,
                        assay_result=assay_result,
                    )
                    experiment_node_id = node_id
                    asyncio.ensure_future(
                        mem.embed_experiment(
                            project_id=state.get("project_id", ""),
                            experiment_node_id=node_id,
                            smiles=smiles,
                            route=route,
                            match_score=match_score,
                            assay_result=assay_result,
                        )
                    )
                    trace = list(state.get("reasoning_trace", []))
                    trace.append(
                        f"[Phase 4] SynthesisAttempt recorded in knowledge graph: "
                        f"node_id={node_id}, match_score={match_score}"
                    )
                    logger.info(f"Phase 4: experiment persisted, node_id={node_id}")
                except Exception as mem_exc:
                    logger.warning(f"Phase 4 memory write failed (non-blocking): {mem_exc}")

        return {
            **state,
            "messages": messages,
            "reasoning_trace": trace,
            "current_iteration": iteration + 1,
            "candidates": candidates,
            "evidence": evidence,
            "experiment_node_id": experiment_node_id,
        }

    def should_continue(state: DiscoveryState) -> str:
        """Conditional edge: decide whether to continue or end."""
        messages = state.get("messages", [])
        if not messages:
            return "end"

        last_msg = messages[-1]
        action = last_msg.get("action", "")
        iteration = state.get("current_iteration", 0)

        if action == "final_answer":
            return "end"
        if iteration >= settings.MAX_TOOL_ITERATIONS:
            logger.info(f"Hit max iterations ({settings.MAX_TOOL_ITERATIONS}), forcing end")
            return "end"
        return "execute"

    sg = StateGraph(DiscoveryState)
    sg.add_node("think", think_node)
    sg.add_node("execute", execute_node)

    sg.set_entry_point("think")
    sg.add_conditional_edges("think", should_continue, {
        "execute": "execute",
        "end": END,
    })
    sg.add_edge("execute", "think")

    return sg


# ============================================================
# EXTRACT FINAL ANSWER
# ============================================================

def _extract_final_answer(state: dict) -> str:
    """Extract the final answer from the state's message history."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("action") == "final_answer":
            ai = msg.get("action_input", {})
            return ai.get("query_answer", ai.get("answer", str(ai)))
    for msg in reversed(messages):
        if msg.get("role") == "tool":
            return f"Tool result: {json.dumps(msg.get('output', {}))[:500]}"
    return state.get("final_answer", "No answer generated.")


def _build_initial_state(
    query: str, project_id: str, spectrum_file_path: Optional[str] = None
) -> DiscoveryState:
    """Construct the initial DiscoveryState for a new query.

    If a spectrum_file_path is provided, auto-transitions to the
    'verification' phase with verify_spectrum available.
    """
    if spectrum_file_path:
        phase = "verification"
        tools = PHASE_TOOLS.get(phase, PHASE2_TOOLS)
    else:
        phase = settings.DISCOVERY_DEFAULT_PHASE
        tools = PHASE_TOOLS.get(phase, PHASE2_TOOLS)

    state: DiscoveryState = {
        "query": query,
        "project_id": project_id,
        "messages": [],
        "current_iteration": 0,
        "available_tools": tools,
        "candidates": [],
        "phase": phase,
        "reasoning_trace": [f"Router: Classified as DISCOVERY (phase={phase})"],
        "status": "running",
        "final_answer": "",
        "evidence": [],
        "confidence_score": 0.5,
    }
    if spectrum_file_path:
        state["spectrum_file_path"] = spectrum_file_path
    return state


# ============================================================
# NON-STREAMING EXECUTION
# ============================================================

async def run_discovery_query(
    query: str,
    project_id: str,
    llm_service: LLMService,
    retrieval_service: Any,
    spectrum_file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Non-streaming discovery execution. Returns final result dict."""
    from app.core.memory import get_memory_saver

    sg = _build_discovery_graph(llm_service, retrieval_service)
    memory = await get_memory_saver()
    compiled = sg.compile(checkpointer=memory)

    initial_state = _build_initial_state(query, project_id, spectrum_file_path)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    try:
        final_state = await compiled.ainvoke(initial_state, config=config)
    except Exception as e:
        logger.exception("Discovery graph execution failed")
        raise RuntimeError(f"Discovery execution failed: {e!s}") from e

    answer = _extract_final_answer(final_state)

    return {
        "brain_used": "discovery",
        "hypothesis": answer,
        "evidence": final_state.get("evidence", []),
        "reasoning_trace": final_state.get("reasoning_trace", []),
        "status": "completed",
        "confidence_score": final_state.get("confidence_score"),
        "candidates": final_state.get("candidates", []),
        "iterations": final_state.get("current_iteration", 0),
        "session_id": thread_id,
    }


# ============================================================
# STREAMING EXECUTION
# ============================================================

async def run_discovery_query_streaming(
    query: str,
    project_id: str,
    session_id: Optional[str],
    llm_service: LLMService,
    retrieval_service: Any,
    cancel_event: Optional[asyncio.Event] = None,
    spectrum_file_path: Optional[str] = None,
) -> AsyncGenerator[Tuple[str, dict], None]:
    """Streaming discovery execution. Yields (event_type, event_data) tuples.

    Event types:
        routing:     {"brain": "discovery", "intent": "DISCOVERY"}
        progress:    {"node": "think"|"execute", "message": "..."}
        thinking:    {"content": "Thought: ..."}
        tool_call:   {"tool": "predict_properties", "input": {...}}
        tool_result: {"tool": "predict_properties", "output": {...}}
        evidence:    {"items": [...], "count": N}
        complete:    {full response}
        error:       {"message": "..."}
    """
    from app.core.memory import get_memory_saver

    yield ("routing", {"brain": "discovery", "intent": "DISCOVERY"})

    if cancel_event and cancel_event.is_set():
        return

    sg = _build_discovery_graph(llm_service, retrieval_service)
    memory = await get_memory_saver()
    compiled = sg.compile(checkpointer=memory)

    initial_state = _build_initial_state(query, project_id, spectrum_file_path)

    thread_id = session_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    try:
        async for event in compiled.astream_events(initial_state, config=config, version="v2"):
            if cancel_event and cancel_event.is_set():
                logger.info("Discovery streaming cancelled by user")
                return

            kind = event["event"]

            if kind == "on_chain_start":
                node_name = event.get("name", "")
                if node_name in ("think", "execute"):
                    yield ("progress", {
                        "node": node_name,
                        "message": _get_progress_message(node_name),
                    })

            elif kind == "on_chain_end":
                node_name = event.get("name", "")
                output = event.get("data", {}).get("output", {})

                if not isinstance(output, dict):
                    continue

                messages = output.get("messages", [])
                if not messages:
                    continue

                last = messages[-1]

                if node_name == "think" and last.get("role") == "assistant":
                    yield ("thinking", {"content": f"Thought: {last.get('thought', '')}"})
                    action = last.get("action", "")
                    if action and action != "final_answer":
                        yield ("tool_call", {
                            "tool": action,
                            "input": last.get("action_input", {}),
                        })

                if node_name == "execute" and last.get("role") == "tool":
                    tool_name = last.get("name", "")
                    tool_output = last.get("output", {})
                    yield ("tool_result", {
                        "tool": tool_name,
                        "output": tool_output,
                    })

                    if tool_name == "search_literature":
                        evidence = output.get("evidence", [])
                        if evidence:
                            yield ("evidence", {
                                "items": evidence,
                                "count": len(evidence),
                            })

    except Exception as e:
        logger.exception("Discovery streaming failed")
        yield ("error", {"message": str(e)})
        return

    if cancel_event and cancel_event.is_set():
        logger.info("Discovery cancelled before final result emission")
        return

    try:
        final_snapshot = await compiled.aget_state(config)
    except AttributeError:
        final_snapshot = None
    final_state = final_snapshot.values if (final_snapshot and hasattr(final_snapshot, "values")) else {}

    answer = _extract_final_answer(final_state)

    yield ("complete", {
        "hypothesis": answer,
        "evidence": final_state.get("evidence", []),
        "confidence_score": final_state.get("confidence_score"),
        "reasoning_trace": final_state.get("reasoning_trace", []),
        "brain_used": "discovery",
        "status": final_state.get("status", "completed"),
        "candidates": final_state.get("candidates", []),
        "iterations": final_state.get("current_iteration", 0),
        "session_id": thread_id,
    })
