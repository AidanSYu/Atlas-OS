"""
Atlas 3.0: MoE Supervisor Agent (Navigator/Orchestrator).

The Supervisor analyzes user intent, breaks down complex queries, and
delegates sub-tasks to Expert Agents. It aggregates expert outputs and
decides when the research satisfies the user's prompt.

Architecture:
    User Query -> Supervisor -> [Hypothesis Expert, Retrieval Expert, Writer Expert]
                             -> Grounding Auditor (Critic)
                             -> Final Synthesis or Revision Loop
"""
import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from app.core.config import settings
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


# ============================================================
# STATE TYPES
# ============================================================

class MoEState(TypedDict, total=False):
    """Shared state for the MoE agent graph."""
    # Input
    query: str
    project_id: str

    # Supervisor planning
    intent: str                           # "deep_analysis", "broad_research", "hypothesis_testing", "synthesis"
    sub_tasks: List[str]                  # Decomposed sub-tasks
    current_round: int                    # Current expert delegation round
    max_rounds: int                       # Max rounds before forcing synthesis

    # Hypothesis Expert output
    hypotheses: List[Dict[str, Any]]      # [{text, confidence, reasoning}]
    selected_hypothesis: str              # User-selected or auto-selected hypothesis

    # Retrieval Expert output
    retrieved_evidence: List[Dict[str, Any]]  # [{text, source, page, score, doc_id}]
    retrieval_queries: List[str]              # Queries issued by retrieval expert

    # Writer Expert output
    draft: str                            # Current draft text
    draft_version: int                    # Draft revision number

    # Grounding Auditor output
    grounding_results: List[Dict[str, Any]]   # [{claim, status, confidence, source}]
    ungrounded_claims: List[str]              # Claims that failed grounding
    audit_verdict: str                        # "PASS", "REVISE", "NEEDS_MORE_EVIDENCE"

    # Final output
    final_answer: str
    evidence: List[Dict[str, Any]]
    reasoning_trace: List[str]
    confidence_score: float
    status: str


# ============================================================
# SUPERVISOR NODE
# ============================================================

async def supervisor_plan(state: MoEState, llm_service: LLMService) -> MoEState:
    """Supervisor: Analyze query intent and create a research plan.

    This is the entry point. The Supervisor classifies the query type
    and decomposes it into sub-tasks for the expert agents.
    """
    query = state["query"]
    trace = state.get("reasoning_trace", [])

    prompt = f"""You are a research team supervisor. Analyze this query and create a plan.

QUERY: {query}

Classify the intent as one of:
- deep_analysis: Requires following chains of reasoning through connected documents
- broad_research: Requires surveying many documents for a comprehensive answer
- hypothesis_testing: Requires generating and testing specific hypotheses
- synthesis: Requires combining findings from multiple sources into a cohesive answer

Then decompose the query into 2-4 specific sub-tasks that expert agents can execute.

Return ONLY valid JSON:
{{
    "intent": "deep_analysis|broad_research|hypothesis_testing|synthesis",
    "sub_tasks": ["task 1 description", "task 2 description"],
    "reasoning": "why this plan"
}}

JSON:"""

    try:
        response = await llm_service.generate(prompt=prompt, temperature=0.1, max_tokens=512)
        plan = _parse_json(response)
    except Exception as e:
        logger.warning(f"Supervisor planning failed: {e}")
        plan = {"intent": "broad_research", "sub_tasks": [query], "reasoning": "fallback"}

    intent = plan.get("intent", "broad_research")
    sub_tasks = plan.get("sub_tasks", [query])

    trace.append(f"[Supervisor] Intent: {intent}")
    trace.append(f"[Supervisor] Sub-tasks: {sub_tasks}")

    return {
        **state,
        "intent": intent,
        "sub_tasks": sub_tasks,
        "current_round": 0,
        "max_rounds": settings.MOE_MAX_EXPERT_ROUNDS,
        "reasoning_trace": trace,
    }


async def supervisor_decide(state: MoEState, llm_service: LLMService) -> str:
    """Supervisor: Decide the next step based on current state.

    Routes to:
    - "hypothesis" if we need hypotheses
    - "retrieve" if we need more evidence
    - "write" if we have enough evidence to draft
    - "audit" if we have a draft to verify
    - "synthesize" if audit passed or max rounds reached
    """
    current_round = state.get("current_round", 0)
    max_rounds = state.get("max_rounds", settings.MOE_MAX_EXPERT_ROUNDS)
    audit_verdict = state.get("audit_verdict", "")
    hypotheses = state.get("hypotheses", [])
    retrieved_evidence = state.get("retrieved_evidence", [])
    draft = state.get("draft", "")

    # Force synthesis if max rounds reached
    if current_round >= max_rounds:
        return "synthesize"

    # If audit passed, we're done
    if audit_verdict == "PASS" and draft:
        return "synthesize"

    # If no hypotheses yet and intent requires them
    intent = state.get("intent", "")
    if not hypotheses and intent in ("hypothesis_testing", "deep_analysis"):
        return "hypothesis"

    # If we don't have enough evidence
    if len(retrieved_evidence) < 3:
        return "retrieve"

    # If we have evidence but no draft
    if not draft and retrieved_evidence:
        return "write"

    # If we have a draft but it hasn't been audited
    if draft and audit_verdict not in ("PASS",):
        return "audit"

    # If audit says revise
    if audit_verdict in ("REVISE", "NEEDS_MORE_EVIDENCE"):
        if audit_verdict == "NEEDS_MORE_EVIDENCE" and current_round < max_rounds:
            return "retrieve"
        return "write"

    return "synthesize"


async def supervisor_synthesize(state: MoEState, llm_service: LLMService) -> MoEState:
    """Supervisor: Produce the final answer from the draft and evidence."""
    trace = state.get("reasoning_trace", [])
    draft = state.get("draft", "")
    evidence = state.get("retrieved_evidence", [])
    grounding = state.get("grounding_results", [])

    # If we have a grounded draft, use it as the final answer
    if draft:
        final = draft
    else:
        # Emergency fallback: synthesize directly from evidence
        evidence_text = "\n".join(
            f"- [{e.get('source', 'Unknown')}, p.{e.get('page', '?')}]: {e.get('text', '')[:300]}"
            for e in evidence[:10]
        )
        prompt = f"""Synthesize a comprehensive answer based on this evidence.

QUERY: {state['query']}

EVIDENCE:
{evidence_text}

Write a clear, well-cited answer. Cite sources as [Source: filename, Page: N]."""

        final = await llm_service.generate_chat(
            system_message="You are a precise research synthesizer.",
            user_message=prompt,
            temperature=0.1,
            max_tokens=2048,
        )

    # Calculate confidence from grounding results
    if grounding:
        grounded = sum(1 for g in grounding if g.get("status") in ("GROUNDED", "SUPPORTED"))
        confidence = grounded / len(grounding) if grounding else 0.5
    else:
        confidence = 0.5

    trace.append(f"[Supervisor] Final synthesis complete. Confidence: {confidence:.2f}")

    # Phase 4: Automatically save draft to Workspace
    project_id = state.get("project_id")
    if project_id:
        try:
            from app.services.workspace import WorkspaceService
            ws = WorkspaceService()
            # EditorPane uses Tiptap JSON format
            draft_content = {
                "type": "doc",
                "content": [
                    {
                        "type": "heading",
                        "attrs": {"level": 1},
                        "content": [{"type": "text", "text": "MoE Research Synthesis"}]
                    },
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": final}]
                    }
                ]
            }
            ws.save_draft(project_id, "moe_synthesis", draft_content)
            trace.append("[Supervisor] Saved full synthesis to workspace as 'moe_synthesis'")
        except Exception as e:
            logger.warning(f"Failed to auto-save thesis to workspace: {e}")

    return {
        **state,
        "final_answer": final,
        "confidence_score": confidence,
        "status": "complete",
        "reasoning_trace": trace,
    }


# ============================================================
# GRAPH BUILDER
# ============================================================

def build_moe_graph(
    llm_service: LLMService,
    graph_service: Any,
    qdrant_client: Any,
    collection_name: str,
) -> StateGraph:
    """Build the MoE LangGraph StateGraph with Supervisor + Experts.

    The graph routes through:
    Supervisor -> Hypothesis Expert -> Retrieval Expert -> Writer Expert -> Grounding Auditor
    with conditional loops for revision.
    """
    from app.services.agents.experts.hypothesis import hypothesis_generate
    from app.services.agents.experts.retrieval_expert import retrieval_search
    from app.services.agents.experts.writer import writer_draft
    from app.services.agents.experts.critic import grounding_audit

    graph = StateGraph(MoEState)

    # --- Node definitions ---
    async def _plan(state):
        return await supervisor_plan(state, llm_service)

    async def _hypothesis(state):
        return await hypothesis_generate(state, llm_service, graph_service)

    async def _retrieve(state):
        return await retrieval_search(state, llm_service, qdrant_client, collection_name, graph_service)

    async def _write(state):
        return await writer_draft(state, llm_service)

    async def _audit(state):
        return await grounding_audit(state, llm_service)

    async def _synthesize(state):
        return await supervisor_synthesize(state, llm_service)

    graph.add_node("plan", _plan)
    graph.add_node("hypothesis", _hypothesis)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("write", _write)
    graph.add_node("audit", _audit)
    graph.add_node("synthesize", _synthesize)

    # --- Edges ---
    graph.set_entry_point("plan")

    # After planning, supervisor decides next step
    async def _decide(state):
        return await supervisor_decide(state, llm_service)

    graph.add_conditional_edges("plan", _decide, {
        "hypothesis": "hypothesis",
        "retrieve": "retrieve",
        "write": "write",
        "audit": "audit",
        "synthesize": "synthesize",
    })

    # After hypothesis, go to retrieval
    graph.add_edge("hypothesis", "retrieve")

    # After retrieval, supervisor decides (write or retrieve more)
    async def _post_retrieve(state):
        return await supervisor_decide(state, llm_service)

    graph.add_conditional_edges("retrieve", _post_retrieve, {
        "hypothesis": "hypothesis",
        "retrieve": "retrieve",
        "write": "write",
        "audit": "audit",
        "synthesize": "synthesize",
    })

    # After writing, go to audit
    graph.add_edge("write", "audit")

    # After audit, supervisor decides (revise, retrieve more, or synthesize)
    async def _post_audit(state):
        return await supervisor_decide(state, llm_service)

    graph.add_conditional_edges("audit", _post_audit, {
        "retrieve": "retrieve",
        "write": "write",
        "synthesize": "synthesize",
        "hypothesis": "hypothesis",
        "audit": "synthesize",  # prevent audit loop
    })

    # Synthesize is terminal
    graph.add_edge("synthesize", END)

    return graph


# ============================================================
# HELPERS
# ============================================================

def _parse_json(text: str) -> dict:
    """Parse JSON from LLM response, handling code blocks."""
    import re
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}
