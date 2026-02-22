"""
Atlas 3.0: Hypothesis Generator Expert.

Given a broad research question, traverses the Knowledge Graph and proposes
3-5 distinct, testable hypotheses. Each hypothesis includes confidence,
reasoning, and suggested evidence paths.

Tools: query_graph, search_documents
"""
import json
import logging
from typing import Any, Dict, List

from app.services.llm import LLMService
from app.core.config import settings

logger = logging.getLogger(__name__)


async def hypothesis_generate(
    state: dict,
    llm_service: LLMService,
    graph_service: Any,
) -> dict:
    """Generate research hypotheses from the query and knowledge graph.

    Examines the knowledge graph for relevant entities and connections,
    then proposes testable hypotheses the retrieval expert can investigate.

    Args:
        state: Current MoE state dict.
        llm_service: LLM service for generation.
        graph_service: Graph service for knowledge graph queries.

    Returns:
        Updated state with 'hypotheses' populated.
    """
    query = state["query"]
    project_id = state.get("project_id", "")
    trace = state.get("reasoning_trace", [])
    num_hypotheses = settings.MOE_HYPOTHESIS_COUNT

    trace.append("[Hypothesis Expert] Generating research hypotheses...")

    # Step 1: Query the knowledge graph for relevant entities
    graph_context = ""
    try:
        graph_data = await graph_service.get_full_graph_cached(project_id=project_id)
        nodes = graph_data.get("nodes", [])[:30]
        edges = graph_data.get("edges", [])[:30]

        if nodes:
            entity_lines = []
            for n in nodes:
                props = n.get("properties", {})
                name = props.get("name", n.get("label", "Unknown"))
                entity_lines.append(f"- {name} ({n.get('label', 'entity')})")
            graph_context = "KNOWN ENTITIES IN KNOWLEDGE GRAPH:\n" + "\n".join(entity_lines[:20])

        if edges:
            edge_lines = []
            node_map = {n.get("id"): n.get("properties", {}).get("name", "?") for n in nodes}
            for e in edges:
                src = node_map.get(e.get("source_id"), "?")
                tgt = node_map.get(e.get("target_id"), "?")
                edge_lines.append(f"- {src} --[{e.get('type', '?')}]--> {tgt}")
            graph_context += "\n\nKNOWN RELATIONSHIPS:\n" + "\n".join(edge_lines[:15])
    except Exception as e:
        logger.debug(f"Graph query for hypothesis generation failed: {e}")

    # Step 2: Generate hypotheses using LLM
    prompt = f"""You are a hypothesis generator for a research team. Given the query and available knowledge,
propose {num_hypotheses} distinct, testable hypotheses.

QUERY: {query}

{graph_context}

For each hypothesis, provide:
1. A clear, testable statement
2. Your confidence (0.0-1.0) based on available evidence
3. Brief reasoning for why this hypothesis is worth investigating
4. What evidence would confirm or deny it

Return ONLY valid JSON:
{{
    "hypotheses": [
        {{
            "text": "Hypothesis statement",
            "confidence": 0.6,
            "reasoning": "Why this is plausible",
            "evidence_needed": "What to look for"
        }}
    ]
}}

JSON:"""

    try:
        response = await llm_service.generate(prompt=prompt, temperature=0.3, max_tokens=1024)
        result = _parse_json(response)
        hypotheses = result.get("hypotheses", [])
    except Exception as e:
        logger.warning(f"Hypothesis generation failed: {e}")
        hypotheses = [{
            "text": query,
            "confidence": 0.5,
            "reasoning": "Direct investigation of the original query",
            "evidence_needed": "Relevant document passages",
        }]

    # Select highest-confidence hypothesis by default (user can override in Phase 4)
    if hypotheses:
        hypotheses.sort(key=lambda h: h.get("confidence", 0), reverse=True)
        selected = hypotheses[0].get("text", query)
    else:
        selected = query

    trace.append(f"[Hypothesis Expert] Generated {len(hypotheses)} hypotheses")
    for i, h in enumerate(hypotheses):
        trace.append(f"  H{i+1} ({h.get('confidence', '?')}): {h.get('text', '')[:100]}")

    return {
        **state,
        "hypotheses": hypotheses,
        "selected_hypothesis": selected,
        "reasoning_trace": trace,
    }


def _parse_json(text: str) -> dict:
    """Parse JSON from LLM response."""
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
