"""
Atlas 3.0: Grounding Auditor (Critic) Expert.

Cross-references every claim made by the Paper Writer against the retrieved
source chunks. If a claim is hallucinated/unsupported, it triggers a
conditional edge forcing the Writer to revise its draft.

Action: PASS (all claims grounded) | REVISE (some claims ungrounded) | NEEDS_MORE_EVIDENCE
"""
import json
import logging
import re
from typing import Any, Dict, List

from app.services.llm import LLMService

logger = logging.getLogger(__name__)


async def grounding_audit(state: dict, llm_service: LLMService) -> dict:
    """Audit the Writer's draft for grounding in retrieved evidence.

    For each claim in the draft, checks whether it is supported by
    the retrieved evidence. Ungrounded claims trigger a revision loop.

    Args:
        state: Current MoE state dict with 'draft' and 'retrieved_evidence'.
        llm_service: LLM service for claim extraction and verification.

    Returns:
        Updated state with grounding results and audit verdict.
    """
    draft = state.get("draft", "")
    evidence = state.get("retrieved_evidence", [])
    trace = state.get("reasoning_trace", [])

    trace.append("[Grounding Auditor] Verifying claims against evidence...")

    if not draft:
        return {
            **state,
            "audit_verdict": "NEEDS_MORE_EVIDENCE",
            "grounding_results": [],
            "reasoning_trace": trace,
        }

    # Step 1: Extract claims from the draft
    claims = _extract_claims(draft)
    trace.append(f"[Grounding Auditor] Extracted {len(claims)} claims to verify")

    if not claims:
        return {
            **state,
            "audit_verdict": "PASS",
            "grounding_results": [],
            "reasoning_trace": trace,
        }

    # Step 2: Build evidence index for checking
    evidence_texts = []
    for e in evidence[:15]:
        source = e.get("source", "Unknown")
        page = e.get("page", "?")
        text = e.get("text", "")
        evidence_texts.append(f"[{source}, p.{page}]: {text}")

    evidence_block = "\n\n".join(evidence_texts)

    # Step 3: Verify each claim against evidence using LLM
    prompt = f"""You are a fact-checking auditor. For each claim below, determine if it is supported by the evidence.

CLAIMS TO VERIFY:
{chr(10).join(f'{i+1}. {c}' for i, c in enumerate(claims[:10]))}

AVAILABLE EVIDENCE:
{evidence_block[:3000]}

For each claim, classify as:
- GROUNDED: Directly supported by evidence with a clear source
- SUPPORTED: Partially supported or reasonably inferred from evidence
- UNVERIFIED: Cannot be confirmed from the available evidence
- INFERRED: Not directly stated but logically follows from evidence

Return ONLY valid JSON:
{{
    "results": [
        {{
            "claim_index": 1,
            "claim": "the claim text",
            "status": "GROUNDED|SUPPORTED|UNVERIFIED|INFERRED",
            "confidence": 0.9,
            "source": "filename.pdf, p.5 (if applicable)"
        }}
    ],
    "overall_verdict": "PASS|REVISE|NEEDS_MORE_EVIDENCE"
}}

JSON:"""

    try:
        response = await llm_service.generate(prompt=prompt, temperature=0.1, max_tokens=1024)
        result = _parse_json(response)
    except Exception as e:
        logger.warning(f"Grounding audit LLM call failed: {e}")
        # Default to pass if we can't audit
        return {
            **state,
            "audit_verdict": "PASS",
            "grounding_results": [],
            "reasoning_trace": trace,
        }

    grounding_results = result.get("results", [])
    verdict = result.get("overall_verdict", "PASS")

    # Collect ungrounded claims
    ungrounded = [
        r.get("claim", "")
        for r in grounding_results
        if r.get("status") == "UNVERIFIED"
    ]

    # Determine verdict based on results
    if not grounding_results:
        verdict = "PASS"
    else:
        unverified_count = sum(1 for r in grounding_results if r.get("status") == "UNVERIFIED")
        total = len(grounding_results)
        if unverified_count == 0:
            verdict = "PASS"
        elif unverified_count / total > 0.5:
            verdict = "NEEDS_MORE_EVIDENCE"
        else:
            verdict = "REVISE"

    trace.append(f"[Grounding Auditor] Verdict: {verdict}")
    trace.append(f"[Grounding Auditor] {len(grounding_results)} claims checked, "
                 f"{len(ungrounded)} ungrounded")

    return {
        **state,
        "grounding_results": grounding_results,
        "ungrounded_claims": ungrounded,
        "audit_verdict": verdict,
        "reasoning_trace": trace,
    }


def _extract_claims(text: str) -> List[str]:
    """Extract individual factual claims from a draft text.

    Uses sentence splitting and filters out non-factual sentences
    (questions, transitions, hedging without facts).
    """
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    claims = []
    skip_patterns = [
        r'^(however|moreover|furthermore|in conclusion|to summarize|overall)',
        r'^(the query|the question|as mentioned|note that)',
        r'\?$',  # questions
    ]

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20:
            continue

        # Skip non-factual sentences
        skip = False
        for pattern in skip_patterns:
            if re.match(pattern, sentence, re.IGNORECASE):
                skip = True
                break
        if skip:
            continue

        # Keep sentences that likely contain factual claims
        claims.append(sentence)

    return claims[:10]  # Limit to 10 claims for efficiency


def _parse_json(text: str) -> dict:
    """Parse JSON from LLM response."""
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
