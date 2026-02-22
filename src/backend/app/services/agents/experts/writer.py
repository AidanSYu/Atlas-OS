"""
Atlas 3.0: Paper Writer / Synthesizer Expert.

Drafts cohesive research papers, summaries, or domain reports. Operates
STRICTLY on the structured evidence JSON outputted by the Retrieval Expert.
The Writer is allowed to write, but NOT allowed to retrieve.

Constraint: Every claim must be backed by a citation from retrieved evidence.
"""
import json
import logging
from typing import Any, Dict, List

from app.services.llm import LLMService

logger = logging.getLogger(__name__)


async def writer_draft(state: dict, llm_service: LLMService) -> dict:
    """Draft a synthesis from the retrieved evidence.

    The Writer takes the retrieved evidence and produces a well-structured,
    citation-rich answer. It does NOT retrieve new information.

    Args:
        state: Current MoE state dict with 'retrieved_evidence'.
        llm_service: LLM service for generation.

    Returns:
        Updated state with 'draft' and incremented 'draft_version'.
    """
    query = state["query"]
    evidence = state.get("retrieved_evidence", [])
    hypotheses = state.get("hypotheses", [])
    ungrounded_claims = state.get("ungrounded_claims", [])
    previous_draft = state.get("draft", "")
    draft_version = state.get("draft_version", 0)
    trace = state.get("reasoning_trace", [])

    trace.append(f"[Writer Expert] Drafting synthesis (v{draft_version + 1})...")

    # Build evidence context
    evidence_blocks = []
    for i, e in enumerate(evidence[:15], 1):
        source = e.get("source", "Unknown")
        page = e.get("page", "?")
        text = e.get("text", "")[:500]
        evidence_blocks.append(f"[E{i}] Source: {source}, Page: {page}\n{text}")

    evidence_text = "\n\n".join(evidence_blocks)

    # Build hypothesis context
    hypothesis_text = ""
    if hypotheses:
        hypothesis_text = "\nHYPOTHESES UNDER INVESTIGATION:\n"
        for i, h in enumerate(hypotheses[:5], 1):
            hypothesis_text += f"H{i}: {h.get('text', '')}\n"

    # Build revision instructions if this is a revision
    revision_context = ""
    if previous_draft and ungrounded_claims:
        revision_context = f"""
REVISION REQUIRED: The previous draft had ungrounded claims that must be fixed.
PREVIOUS DRAFT (DO NOT COPY UNGROUNDED CLAIMS):
{previous_draft[:1000]}

UNGROUNDED CLAIMS TO REMOVE OR FIX:
{chr(10).join(f'- {c}' for c in ungrounded_claims)}

Revise the draft to remove or properly cite all ungrounded claims.
"""

    prompt = f"""You are a research synthesis writer. Write a comprehensive, well-cited answer.

QUERY: {query}
{hypothesis_text}
{revision_context}

EVIDENCE (cite as [Source: filename, Page: N]):
{evidence_text}

RULES:
1. Every factual claim MUST have a citation from the evidence above.
2. Use the format [Source: filename.pdf, Page: N] for all citations.
3. If the evidence is insufficient to answer part of the query, explicitly state what is unknown.
4. Do NOT make up facts or cite sources not listed above.
5. Structure the answer with clear paragraphs.
6. Start with a direct answer to the query, then provide supporting details.

SYNTHESIS:"""

    try:
        draft = await llm_service.generate_chat(
            system_message="You are a precise research writer. Every claim must be cited from the provided evidence.",
            user_message=prompt,
            temperature=0.1,
            max_tokens=2048,
        )
    except Exception as e:
        logger.error(f"Writer draft generation failed: {e}")
        draft = previous_draft or "Unable to generate synthesis from available evidence."

    trace.append(f"[Writer Expert] Draft v{draft_version + 1} complete ({len(draft)} chars)")

    return {
        **state,
        "draft": draft,
        "draft_version": draft_version + 1,
        "reasoning_trace": trace,
    }
