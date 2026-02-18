"""
Two-Brain Swarm - Agentic RAG using LangGraph.

Architecture:
  Router -> classifies query as DEEP_DISCOVERY or BROAD_RESEARCH
  
  Brain 1: Navigator (Deep/Sequential)
    - Walks the knowledge graph (NetworkX subgraph from SQLite)
    - Reads relevant text chunks from Qdrant (embedded)
    - Synthesizes a hypothesis using the LLM
    - Best for: "How does X connect to Y?", cross-domain discovery

  Brain 2: Cortex (Broad/Simulated Parallel via Map-Reduce)
    - Breaks query into 5 sub-tasks
    - Executes tasks sequentially (RTX 3050 4GB VRAM constraint)
    - Reduces/summarizes all results
    - Best for: patent landscape, regulatory scan, literature survey

Hardware constraint: RTX 3050 (4GB VRAM).
  - No parallel GPU execution.
  - Async serial execution via LangGraph StateGraph.
"""


import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, TypedDict

import networkx as nx
from langgraph.graph import StateGraph, END

from app.services.graph import GraphService
from app.services.llm import LLMService
from qdrant_client import QdrantClient
# Phase A3: Import prompt templates and validation
from app.services import prompt_templates
# Phase B: Import RerankService
from app.services.rerank import get_rerank_service
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# STATE TYPES
# ============================================================

class SwarmState(TypedDict, total=False):
    """Shared state for the swarm graph."""
    query: str
    project_id: str
    brain: str  # "navigator" or "cortex"
    # Navigator state
    subgraph_summary: str
    chunks: List[Dict[str, Any]]
    hypothesis: str
    # Cortex state
    sub_tasks: List[str]
    sub_results: List[Dict[str, Any]]
    cortex_summary: str
    # Common
    evidence: List[Dict[str, Any]]
    reasoning_trace: List[str]
    status: str


class NavigatorState(TypedDict, total=False):
    """Enhanced Navigator state with reflection loop support (Phase A1)."""
    # Input
    query: str
    project_id: str
    brain: str

    # Planning phase (NEW)
    reasoning_plan: str
    identified_gaps: List[str]
    search_terms: List[str]

    # Graph exploration
    graph_summary: str
    key_paths: List[Dict[str, Any]]
    entity_clusters: List[Dict[str, Any]]

    # Multi-turn retrieval (NEW)
    chunks: List[Dict[str, Any]]
    retrieval_round: int
    retrieval_history: List[str]

    # Reasoning
    hypothesis: str
    reasoning_trace: List[str]
    evidence_map: str  # NEW: Claim → Evidence mapping

    # Reflection & verification (NEW)
    verification_result: str  # "PASS" | "REFINE" | "RETRIEVE_MORE"
    identified_contradictions: List[str]
    confidence_score: float  # 0.0-1.0
    iteration_count: int

    # Output
    final_answer: str
    evidence: List[Dict[str, Any]]
    status: str


class CortexState(TypedDict, total=False):
    """Enhanced Cortex state with cross-checking support (Phase A2)."""
    # Input
    query: str
    project_id: str
    brain: str

    # Decomposition phase (ENHANCED)
    aspects: List[str]  # Key aspects identified in query
    sub_tasks: List[str]
    task_coverage_check: str  # "COMPLETE" | "PARTIAL - missing [X]"

    # Execution phase (ENHANCED with CoT)
    sub_results: List[Dict[str, Any]]  # Each has: task, answer, reasoning, confidence, sources

    # Cross-checking phase (NEW in Phase A2)
    contradictions: List[Dict[str, Any]]  # Each has: between, issue, severity
    coverage_gaps: List[str]
    verification_result: str  # "PASS" | "HAS_CONFLICTS"

    # Conflict resolution (optional)
    resolutions: List[Dict[str, Any]]

    # Final synthesis
    hypothesis: str
    reasoning_trace: List[str]
    evidence: List[Dict[str, Any]]
    confidence_score: float  # NEW: Overall confidence
    status: str


# ============================================================
# HELPER FUNCTIONS - Prompt utilities (Phase A1 + A3)
# ============================================================

async def generate_with_validation(
    llm_service: 'LLMService',
    prompt: str,
    temperature: float,
    max_tokens: int,
    validator=None,
    node_name: str = "unknown",
    max_retries: int = 2,
) -> str:
    """Generate LLM response with optional validation and retry logic (Phase A3).

    Args:
        llm_service: LLM service instance
        prompt: The prompt to send
        temperature: Temperature for generation
        max_tokens: Max tokens for response
        validator: Optional validation function
        node_name: Name of the calling node (for logging)
        max_retries: Maximum number of retries for malformed outputs

    Returns:
        LLM response text
    """
    from app.core.config import settings

    response = await llm_service.generate(
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens
    )

    # If validation is disabled or no validator provided, return immediately
    if not settings.ENABLE_OUTPUT_VALIDATION or validator is None:
        return response

    # Validate output
    retries = 0
    while not validator(response) and retries < max_retries:
        logger.warning(
            f"{node_name}: Malformed LLM output detected, retrying... "
            f"(attempt {retries + 1}/{max_retries})"
        )
        retries += 1
        response = await llm_service.generate(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

    if not validator(response):
        logger.error(
            f"{node_name}: Failed validation after {max_retries} retries, "
            "proceeding with potentially malformed output"
        )

    return response

def extract_xml_tag(text: str, tag: str) -> str:
    """Extract content from <tag>...</tag> in LLM output.

    Args:
        text: LLM response text
        tag: Tag name (without brackets)

    Returns:
        Content within tags, or empty string if not found
    """
    # 1. Strip markdown code blocks if present
    code_block_match = re.search(r"```(?:\w+)?\s*(.*?)```", text, re.DOTALL)
    if code_block_match:
        text = code_block_match.group(1)

    # 2. Extract content
    # Matches <tag ...> content </tag>
    # \b ensures we don't match <tagfoo>
    pattern = f"<{tag}\\b[^>]*>(.*?)</{tag}\\s*>"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response (handles markdown code blocks).

    Args:
        text: LLM response that may contain JSON

    Returns:
        Parsed JSON dict, or empty dict if parsing fails
    """
    # Try to find JSON in markdown code block first
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)

    # Try to find raw JSON
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        json_str = text[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parsing failed: {e}")
            pass

    return {}


def format_chunks(chunks: List[Dict[str, Any]], max_chunks: int = 5) -> str:
    """Format chunks with citations for LLM prompts.

    Args:
        chunks: List of chunk dicts with text and metadata
        max_chunks: Maximum number of chunks to include

    Returns:
        Formatted string with citations
    """
    if not chunks:
        return "[No evidence available]"

    formatted_parts = []
    for i, chunk in enumerate(chunks[:max_chunks], 1):
        metadata = chunk.get("metadata", {})
        filename = metadata.get("filename", "Unknown")
        page = metadata.get("page", "?")
        text = chunk.get("text", "")[:500]  # Limit to 500 chars per chunk

        formatted_parts.append(
            f"[Source {i}: {filename}, Page {page}]\n{text}"
        )

    return "\n\n".join(formatted_parts)


# ============================================================
# ROUTER - decides which brain to use
# ============================================================

async def route_intent(query: str, llm_service: LLMService) -> str:
    """Classify query as DEEP_DISCOVERY or BROAD_RESEARCH.

    DEEP_DISCOVERY: Synthesis, connection-finding, hypothesis generation.
    BROAD_RESEARCH: Patent search, regulatory scan, literature survey.
    """
    prompt = f"""Classify this research query into exactly ONE category:

DEEP_DISCOVERY - The user wants to find hidden connections, synthesize across domains,
generate hypotheses, or discover relationships between concepts.
Examples: "How might polymer X relate to drug delivery method Y?",
          "What connections exist between these two papers?"

BROAD_RESEARCH - The user wants a broad survey, patent landscape, regulatory overview,
or comprehensive literature scan across many sources.
Examples: "What patents exist for carbon nanotube synthesis?",
          "Survey the regulatory landscape for gene therapy in the EU"

Query: {query}

Respond with ONLY the category name (DEEP_DISCOVERY or BROAD_RESEARCH):"""

    try:
        response = await llm_service.generate(prompt=prompt, temperature=0.0, max_tokens=20)
        response = response.strip().upper()
        if "BROAD" in response:
            return "BROAD_RESEARCH"
        return "DEEP_DISCOVERY"
    except Exception as e:
        logger.warning(f"Router classification failed: {e}, defaulting to DEEP_DISCOVERY")
        return "DEEP_DISCOVERY"


# ============================================================
# BRAIN 1: NAVIGATOR (Deep/Sequential)
# ============================================================

def _build_navigator_graph(
    graph_service: GraphService,
    llm_service: LLMService,
    qdrant_client: QdrantClient,
    collection_name: str,
) -> StateGraph:
    """Build the Navigator StateGraph.

    Nodes:
      navigator - Fetch NetworkX subgraph, find relevant clusters/paths
      analyst   - Read text chunks from Qdrant for context
      synthesizer - Generate hypothesis using LLM
    """

    async def navigator_node(state: SwarmState) -> SwarmState:
        """Walk the knowledge graph to find relevant structure."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("Navigator: Fetching knowledge graph subgraph...")



        # Phase B: Use cached async method
        G = await graph_service.get_networkx_subgraph(project_id=state["project_id"])
        trace.append(f"Navigator: Graph has {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        if G.number_of_nodes() == 0:
            trace.append("Navigator: Empty graph - no entities found")
            return {**state, "subgraph_summary": "No graph data available.", "reasoning_trace": trace}

        # Find the most connected components and central nodes
        summary_parts = []

        # Degree centrality for key entities
        if G.number_of_nodes() > 0:
            centrality = nx.degree_centrality(G)
            top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:10]
            summary_parts.append("Key entities (by connectivity):")
            for node_id, score in top_nodes:
                attrs = G.nodes[node_id]
                summary_parts.append(
                    f"  - {attrs.get('name', node_id)} ({attrs.get('type', 'unknown')}) "
                    f"[centrality: {score:.3f}]"
                )

        # Connected components
        undirected = G.to_undirected()
        components = list(nx.connected_components(undirected))
        trace.append(f"Navigator: Found {len(components)} connected components")
        if len(components) > 1:
            summary_parts.append(f"\nGraph has {len(components)} clusters of concepts.")
            for i, comp in enumerate(sorted(components, key=len, reverse=True)[:5]):
                names = [G.nodes[n].get("name", n) for n in list(comp)[:5]]
                summary_parts.append(f"  Cluster {i+1}: {', '.join(names)}{'...' if len(comp) > 5 else ''}")

        # Shortest paths between highly central nodes (look for bridges)
        if len(top_nodes) >= 2:
            try:
                src = top_nodes[0][0]
                tgt = top_nodes[1][0]
                path = nx.shortest_path(undirected, src, tgt)
                path_names = [G.nodes[n].get("name", n) for n in path]
                summary_parts.append(f"\nKey path: {' -> '.join(path_names)}")
            except nx.NetworkXNoPath:
                summary_parts.append("\nNo path between top entities (separate clusters)")

        subgraph_summary = "\n".join(summary_parts) if summary_parts else "Graph structure analyzed."
        trace.append("Navigator: Subgraph analysis complete")

        return {**state, "subgraph_summary": subgraph_summary, "reasoning_trace": trace}

    async def analyst_node(state: SwarmState) -> SwarmState:
        """Read text chunks from Qdrant relevant to the query."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("Analyst: Searching vector store for relevant text...")

        try:
            query_embedding = await llm_service.embed(state["query"])
            results = qdrant_client.query_points(
                collection_name=collection_name,
                query=query_embedding,
                limit=8,
            ).points

            chunks = []
            for r in results:
                payload = r.payload or {}
                chunks.append({
                    "text": payload.get("text", ""),
                    "doc_id": payload.get("doc_id", ""),
                    "metadata": payload.get("metadata", {}),
                    "score": r.score,
                })

            trace.append(f"Analyst: Found {len(chunks)} relevant text chunks")
            return {**state, "chunks": chunks, "reasoning_trace": trace}
        except Exception as e:
            trace.append(f"Analyst: Vector search failed: {e}")
            return {**state, "chunks": [], "reasoning_trace": trace}

    async def synthesizer_node(state: SwarmState) -> SwarmState:
        """Synthesize a hypothesis from graph structure + text chunks."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("Synthesizer: Generating hypothesis...")

        subgraph = state.get("subgraph_summary", "")
        chunks = state.get("chunks", [])

        chunk_texts = "\n\n".join(
            [f"[Chunk from {c['metadata'].get('filename', '?')}, p.{c['metadata'].get('page', '?')}]\n{c['text'][:500]}"
             for c in chunks[:5]]
        )

        prompt = f"""You are a research synthesis agent. Based on the knowledge graph structure
and document evidence below, generate a hypothesis or insight that answers the user's query.
Look for non-obvious connections across domains.

USER QUERY: {state["query"]}

KNOWLEDGE GRAPH STRUCTURE:
{subgraph}

DOCUMENT EVIDENCE:
{chunk_texts}

Generate a clear, evidence-based hypothesis. Cite specific entities and documents.
If the evidence is insufficient, say what additional data would be needed.

HYPOTHESIS:"""

        try:
            hypothesis = await llm_service.generate(prompt=prompt, temperature=0.3, max_tokens=1024)
            trace.append("Synthesizer: Hypothesis generated")

            evidence = [
                {
                    "source": c["metadata"].get("filename", "Unknown"),
                    "page": c["metadata"].get("page", 1),
                    "excerpt": c["text"][:200],
                    "relevance": c.get("score", 0),
                }
                for c in chunks[:5]
            ]

            return {
                **state,
                "hypothesis": hypothesis.strip(),
                "evidence": evidence,
                "reasoning_trace": trace,
                "status": "completed",
            }
        except Exception as e:
            trace.append(f"Synthesizer: LLM generation failed: {e}")
            return {
                **state,
                "hypothesis": "Hypothesis generation failed - LLM unavailable.",
                "evidence": [],
                "reasoning_trace": trace,
                "status": "error",
            }

    # Build the graph
    graph = StateGraph(SwarmState)
    graph.add_node("navigator", navigator_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("synthesizer", synthesizer_node)

    graph.set_entry_point("navigator")
    graph.add_edge("navigator", "analyst")
    graph.add_edge("analyst", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph


# ============================================================
# BRAIN 1.5: NAVIGATOR 2.0 (Deep Discovery with Reflection - Phase A1)
# ============================================================

def _build_navigator_2_graph(
    graph_service: GraphService,
    llm_service: LLMService,
    qdrant_client: QdrantClient,
    collection_name: str,
) -> StateGraph:
    """Build Navigator 2.0 with multi-turn reflection loops (SOTA 2026).

    Architecture:
      Plan → Graph Explore → Retrieve → Reason (CoT) → Critic → Decision
                                ↑                                   ↓
                                └────────── LOOP (max 3x) ←─────────┘
                                         (if gaps/errors found)

    Nodes:
      planner      - Plan reasoning strategy before retrieval
      graph_explorer - Enhanced graph analysis with centrality
      retriever    - Multi-turn adaptive retrieval
      reasoner     - Chain-of-thought reasoning with self-explanation
      critic       - Self-verification and gap detection
      synthesizer  - Final answer synthesis
    """
    from app.core.config import settings

    async def planner_node(state: NavigatorState) -> NavigatorState:
        """Plan reasoning strategy before retrieval (NEW in Phase A1, enhanced in A3)."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("=== PLANNING PHASE ===")
        trace.append(f"Query: {state['query']}")

        # Phase A3: Use prompt template if enabled
        if settings.USE_PROMPT_TEMPLATES:
            template = prompt_templates.NAVIGATOR_PLANNER
            prompt = template.format(query=state["query"])
            temperature = template.temperature
            max_tokens = template.max_tokens
            validator = prompt_templates.get_validator_for_node("planner")
        else:
            # Legacy prompt (Phase A1)
            prompt = f"""You are a research planning agent. Analyze this query step-by-step:

USER QUERY: {state["query"]}

Think through:
1. What is the user REALLY asking? (rephrase in clear terms)
2. What types of information do we need to answer this?
3. What entities or concepts should we look for in the knowledge graph?
4. What potential gaps or ambiguities might exist in our knowledge base?

Return your analysis as JSON:
{{
  "understanding": "Your clear interpretation of what the user wants",
  "information_needs": ["type 1: description", "type 2: description"],
  "search_terms": ["search term 1", "search term 2", "search term 3"],
  "potential_gaps": ["potential gap 1", "potential gap 2"]
}}
"""
            temperature = 0.1
            max_tokens = 1024
            validator = None

        try:
            plan_json = await generate_with_validation(
                llm_service=llm_service,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                validator=validator,
                node_name="Planner",
                max_retries=settings.MAX_VALIDATION_RETRIES if hasattr(settings, 'MAX_VALIDATION_RETRIES') else 2,
            )
            plan = parse_json_response(plan_json)

            understanding = plan.get("understanding", state["query"])
            search_terms = plan.get("search_terms", [state["query"]])
            gaps = plan.get("potential_gaps", [])

            trace.append(f"Understanding: {understanding[:100]}...")
            trace.append(f"Planned {len(search_terms)} targeted searches")
            trace.append(f"Identified {len(gaps)} potential knowledge gaps")

            return {
                **state,
                "reasoning_plan": understanding,
                "search_terms": search_terms if search_terms else [state["query"]],
                "identified_gaps": gaps,
                "reasoning_trace": trace,
                "iteration_count": 0,
                "retrieval_round": 1,
                "retrieval_history": [],
            }
        except Exception as e:
            logger.error(f"Planner failed: {e}", exc_info=True)
            trace.append(f"Planning failed, using direct query: {e}")
            return {
                **state,
                "reasoning_plan": state["query"],
                "search_terms": [state["query"]],
                "identified_gaps": [],
                "reasoning_trace": trace,
                "iteration_count": 0,
                "retrieval_round": 1,
                "retrieval_history": [],
            }

    async def graph_explorer_node(state: NavigatorState) -> NavigatorState:
        """Enhanced graph exploration (reuses existing logic)."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("=== GRAPH EXPLORATION ===")



        # Phase B: Use cached async method
        G = await graph_service.get_networkx_subgraph(project_id=state["project_id"])
        trace.append(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        if G.number_of_nodes() == 0:
            return {
                **state,
                "graph_summary": "No graph data available.",
                "reasoning_trace": trace,
            }

        # Enhanced analysis with multiple centrality measures
        summary_parts = []

        # Degree centrality
        centrality = nx.degree_centrality(G)
        top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:10]

        summary_parts.append("Key entities (by connectivity):")
        for node_id, score in top_nodes:
            attrs = G.nodes[node_id]
            name = attrs.get('name', node_id)
            node_type = attrs.get('type', 'unknown')
            summary_parts.append(f"  - {name} ({node_type}) [centrality: {score:.3f}]")

        # Connected components
        undirected = G.to_undirected()
        components = list(nx.connected_components(undirected))
        if len(components) > 1:
            summary_parts.append(f"\nGraph has {len(components)} concept clusters:")
            for i, comp in enumerate(sorted(components, key=len, reverse=True)[:5]):
                names = [G.nodes[n].get("name", n) for n in list(comp)[:5]]
                summary_parts.append(f"  Cluster {i+1}: {', '.join(names)}")

        # Key paths
        if len(top_nodes) >= 2:
            try:
                src, tgt = top_nodes[0][0], top_nodes[1][0]
                path = nx.shortest_path(undirected, src, tgt)
                path_names = [G.nodes[n].get("name", n) for n in path]
                summary_parts.append(f"\nKey path: {' → '.join(path_names)}")
            except nx.NetworkXNoPath:
                summary_parts.append("\nTop entities are in separate clusters")

        graph_summary = "\n".join(summary_parts)
        trace.append("Graph analysis complete")

        return {
            **state,
            "graph_summary": graph_summary,
            "reasoning_trace": trace,
        }

    async def retriever_node(state: NavigatorState) -> NavigatorState:
        """Multi-turn adaptive retrieval (NEW - retrieves more if gaps found)."""
        trace = list(state.get("reasoning_trace", []))
        round_num = state.get("retrieval_round", 1)
        trace.append(f"=== RETRIEVAL ROUND {round_num} ===")

        # Determine what to search for
        if round_num == 1:
            # Initial search: use planned search terms
            search_queries = state.get("search_terms", [state["query"]])
            trace.append(f"Initial retrieval with {len(search_queries)} planned searches")
        else:
            # Follow-up search: target identified gaps
            gaps = state.get("identified_gaps", [])
            search_queries = gaps[:3] if gaps else [state["query"]]
            trace.append(f"Follow-up retrieval targeting {len(search_queries)} knowledge gaps")

        # Track existing chunks to avoid duplicates
        all_chunks = list(state.get("chunks", []))
        existing_ids = {c.get("metadata", {}).get("chunk_id") for c in all_chunks}
        new_chunks_count = 0

        # Phase B: Parallel Retrieval & Reranking
        
        # 1. Execute vector searches in parallel
        search_tasks = []
        for query_text in search_queries:
             async def _single_search(q):
                q_embed = await llm_service.embed(q)
                # Fetch more candidates for reranking (Top-K * 3)
                resp = await asyncio.to_thread(
                    qdrant_client.query_points,
                    collection_name=collection_name,
                    query=q_embed,
                    limit=settings.RERANK_TOP_N * 3 if settings.ENABLE_RERANKING else 5
                )
                return resp.points
             search_tasks.append(_single_search(query_text))
        
        search_results_list = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        raw_candidates = []
        for res_list in search_results_list:
            if isinstance(res_list, Exception):
                logger.error(f"Search failed: {res_list}")
                continue
            for r in res_list:
                payload = r.payload or {}
                raw_candidates.append({
                    "text": payload.get("text", ""),
                    "metadata": {
                        **payload.get("metadata", {}),
                        "chunk_id": str(r.id),
                    },
                    "score": r.score,
                    "doc_id": payload.get("doc_id", ""),
                })
        
        # 2. De-duplicate candidates
        unique_candidates = {}
        for c in raw_candidates:
            cid = c["metadata"]["chunk_id"]
            if cid not in unique_candidates:
                unique_candidates[cid] = c
                
        candidate_list = list(unique_candidates.values())
        trace.append(f"Retrieved {len(candidate_list)} unique candidates before reranking")
        
        # 3. Rerank if enabled (Phase B)
        if settings.ENABLE_RERANKING and candidate_list:
            trace.append("Reranking candidates with FlashRank...")
            rerank_service = get_rerank_service()
            # Rerank against the original query (or the first search term which is usually the best proxy)
            rerank_query = search_queries[0] if search_queries else state["query"]
            
            top_docs = await rerank_service.rerank(
                query=rerank_query, 
                documents=candidate_list, 
                top_n=settings.RERANK_TOP_N
            )
            trace.append(f"Reranking complete. Kept top {len(top_docs)} chunks.")
        else:
            top_docs = candidate_list[:5]

        # 4. Integrate into state
        for doc in top_docs:
            chunk_id = doc["metadata"]["chunk_id"]
            if chunk_id not in existing_ids:
                all_chunks.append({
                    **doc,
                    "retrieved_in_round": round_num,
                })
                existing_ids.add(chunk_id)
                new_chunks_count += 1

        trace.append(f"Retrieved {len(all_chunks)} total chunks ({new_chunks_count} new this round)")

        # Track retrieval history
        history = list(state.get("retrieval_history", []))
        history.extend(search_queries)

        return {
            **state,
            "chunks": all_chunks,
            "retrieval_round": round_num,
            "retrieval_history": history,
            "reasoning_trace": trace,
        }

    async def reasoner_node(state: NavigatorState) -> NavigatorState:
        """Generate hypothesis with explicit chain-of-thought (DeepSeek R1 style, enhanced in A3)."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("=== REASONING PHASE ===")

        chunks = state.get("chunks", [])
        graph_summary = state.get("graph_summary", "")

        if not chunks and not graph_summary:
            trace.append("Warning: No evidence available for reasoning")

        chunks_text = format_chunks(chunks, max_chunks=5)

        # Phase A3: Use prompt template if enabled
        if settings.USE_PROMPT_TEMPLATES:
            template = prompt_templates.NAVIGATOR_REASONER
            prompt = template.format(
                query=state["query"],
                evidence=chunks_text,
                graph=graph_summary
            )
            temperature = template.temperature
            max_tokens = template.max_tokens
            validator = prompt_templates.get_validator_for_node("reasoner")
        else:
            # Legacy prompt (Phase A1)
            prompt = f"""You are a research synthesis agent with deep analytical capabilities.

USER QUERY: {state["query"]}

EVIDENCE FROM DOCUMENTS:
{chunks_text}

KNOWLEDGE GRAPH STRUCTURE:
{graph_summary}

FORMAT YOUR RESPONSE WITH EXPLICIT REASONING:

<thinking>
Wait, let me think through this carefully...

Step 1: What does the evidence actually tell us?
[Analyze the evidence systematically...]

Step 2: How does this connect to the query?
[Make explicit connections...]

Step 3: Are there any contradictions or gaps in the evidence?
[Self-check your reasoning...]

Step 4: What can we confidently conclude?
[Synthesize your findings...]
</thinking>

<hypothesis>
[Your clear, evidence-based answer to the query. Include specific citations like: "According to [Source.pdf, p.X], ..."]
</hypothesis>

<evidence_mapping>
Claim 1: [specific claim] → Evidence: [Source.pdf, p.X]
Claim 2: [specific claim] → Evidence: [Source.pdf, p.Y]
...
</evidence_mapping>

<confidence>HIGH/MEDIUM/LOW because [brief justification]</confidence>

CRITICAL: If evidence is insufficient, explicitly state "I cannot find sufficient evidence for [specific aspect]."
"""
            temperature = 0.2
            max_tokens = 2048
            validator = None

        try:
            response = await generate_with_validation(
                llm_service=llm_service,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                validator=validator,
                node_name="Reasoner",
                max_retries=settings.MAX_VALIDATION_RETRIES if hasattr(settings, 'MAX_VALIDATION_RETRIES') else 2,
            )

            # Extract structured parts
            thinking = extract_xml_tag(response, "thinking")
            hypothesis = extract_xml_tag(response, "hypothesis")
            evidence_map = extract_xml_tag(response, "evidence_mapping")
            confidence_str = extract_xml_tag(response, "confidence")

            # Parse confidence
            confidence_score = 0.5  # default
            if "HIGH" in confidence_str.upper():
                confidence_score = 0.85
            elif "MEDIUM" in confidence_str.upper():
                confidence_score = 0.6
            elif "LOW" in confidence_str.upper():
                confidence_score = 0.3

            trace.append(f"Generated hypothesis ({len(thinking.split('Step'))} reasoning steps)")
            trace.append(f"Confidence: {confidence_score:.2f}")

            # Append thinking to trace for transparency
            reasoning_with_thinking = list(state.get("reasoning_trace", [])) + trace + [f"[THINKING]\n{thinking}"]

            return {
                **state,
                "hypothesis": hypothesis.strip() if hypothesis else "No hypothesis generated.",
                "evidence_map": evidence_map,
                "confidence_score": confidence_score,
                "reasoning_trace": reasoning_with_thinking,
            }
        except Exception as e:
            logger.error(f"Reasoner failed: {e}", exc_info=True)
            trace.append(f"Reasoning failed: {e}")
            return {
                **state,
                "hypothesis": f"Error generating hypothesis: {str(e)}",
                "evidence_map": "",
                "confidence_score": 0.0,
                "reasoning_trace": trace,
            }

    async def critic_node(state: NavigatorState) -> NavigatorState:
        """Self-verification and gap detection (NEW in A1, enhanced in A3)."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("=== VERIFICATION PHASE ===")

        hypothesis = state.get("hypothesis", "")
        evidence_map = state.get("evidence_map", "")
        query = state["query"]

        # Phase A3: Use prompt template if enabled
        if settings.USE_PROMPT_TEMPLATES:
            template = prompt_templates.NAVIGATOR_CRITIC
            prompt = template.format(
                query=query,
                hypothesis=hypothesis,
                evidence_map=evidence_map
            )
            temperature = template.temperature
            max_tokens = template.max_tokens
            validator = prompt_templates.get_validator_for_node("critic")
        else:
            # Legacy prompt (Phase A1)
            prompt = f"""You are a critical reviewer. Your job is to find flaws, gaps, and contradictions.

ORIGINAL QUERY: {query}

GENERATED HYPOTHESIS:
{hypothesis}

EVIDENCE USED:
{evidence_map}

CRITICAL ANALYSIS:

1. COVERAGE: Does the hypothesis answer ALL parts of the query? What's missing?
2. CONTRADICTIONS: Do any evidence sources contradict each other?
3. EVIDENCE GAPS: Which claims lack supporting evidence?
4. CLARITY: Is the answer clear and well-structured?

Based on your analysis, return JSON:
{{
  "verdict": "PASS" | "REFINE" | "RETRIEVE_MORE",
  "issues_found": ["issue 1", "issue 2"],
  "missing_aspects": ["aspect 1", "aspect 2"],
  "contradictions": ["contradiction 1"],
  "confidence_assessment": "HIGH" | "MEDIUM" | "LOW"
}}

PASS = Hypothesis is well-supported and complete
REFINE = Minor issues, can fix with current evidence
RETRIEVE_MORE = Major gaps, need additional evidence
"""
            temperature = 0.1
            max_tokens = 1024
            validator = None

        try:
            response = await generate_with_validation(
                llm_service=llm_service,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                validator=validator,
                node_name="Critic",
                max_retries=settings.MAX_VALIDATION_RETRIES if hasattr(settings, 'MAX_VALIDATION_RETRIES') else 2,
            )
            critique = parse_json_response(response)

            verdict = critique.get("verdict", "PASS")
            issues = critique.get("issues_found", [])
            missing = critique.get("missing_aspects", [])
            contradictions = critique.get("contradictions", [])

            trace.append(f"Verification verdict: {verdict}")
            trace.append(f"Issues found: {len(issues)}")
            trace.append(f"Missing aspects: {len(missing)}")
            if contradictions:
                trace.append(f"Contradictions detected: {len(contradictions)}")

            return {
                **state,
                "verification_result": verdict,
                "identified_gaps": missing if missing else [],
                "identified_contradictions": contradictions if contradictions else [],
                "reasoning_trace": trace,
            }
        except Exception as e:
            logger.error(f"Critic failed: {e}", exc_info=True)
            trace.append(f"Verification failed, defaulting to PASS: {e}")
            return {
                **state,
                "verification_result": "PASS",  # Fail gracefully
                "identified_gaps": [],
                "identified_contradictions": [],
                "reasoning_trace": trace,
            }

    def should_refine(state: NavigatorState) -> str:
        """Decide whether to loop back or finalize (conditional edge logic)."""
        verdict = state.get("verification_result", "PASS")
        iteration = state.get("iteration_count", 0)
        confidence = state.get("confidence_score", 0.5)

        # Get settings for max iterations and confidence threshold
        max_iterations = getattr(settings, "MAX_REFLECTION_ITERATIONS", 3)
        confidence_threshold = getattr(settings, "NAVIGATOR_CONFIDENCE_THRESHOLD", 0.75)

        # Hard limit: max iterations reached
        if iteration >= max_iterations:
            logger.info(f"Navigator: Max iterations ({max_iterations}) reached, finalizing")
            return "synthesize"

        # High confidence pass - we're done
        if verdict == "PASS" and confidence >= confidence_threshold:
            logger.info(f"Navigator: High confidence ({confidence:.2f}), finalizing")
            return "synthesize"

        # Acceptable confidence after at least one iteration
        if verdict == "PASS" and iteration >= 1:
            logger.info(f"Navigator: Acceptable result after {iteration} iteration(s)")
            return "synthesize"

        # Need more evidence - loop back to retriever
        if verdict == "RETRIEVE_MORE" and iteration < max_iterations - 1:
            logger.info(f"Navigator: Retrieving more evidence (iteration {iteration+1})")
            return "retrieve"

        # Need refinement - loop back to reasoner
        if verdict == "REFINE":
            logger.info(f"Navigator: Refining hypothesis (iteration {iteration+1})")
            return "reason"

        # Default: finalize
        return "synthesize"

    async def increment_iteration(state: NavigatorState) -> NavigatorState:
        """Increment iteration counter and retrieval round for loops."""
        return {
            **state,
            "iteration_count": state.get("iteration_count", 0) + 1,
            "retrieval_round": state.get("retrieval_round", 1) + 1,
        }

    async def synthesizer_node(state: NavigatorState) -> NavigatorState:
        """Synthesize final answer with confidence and evidence."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("=== SYNTHESIS PHASE ===")

        iterations = state.get("iteration_count", 0)
        if iterations > 0:
            trace.append(f"Refined through {iterations} reflection cycle(s)")

        # Final answer is the last hypothesis
        final_answer = state.get("hypothesis", "")
        confidence = state.get("confidence_score", 0.5)

        # Build evidence list from chunks
        chunks = state.get("chunks", [])
        evidence = []
        for chunk in chunks[:10]:
            metadata = chunk.get("metadata", {})
            evidence.append({
                "source": metadata.get("filename", "Unknown"),
                "page": metadata.get("page", 1),
                "excerpt": chunk.get("text", "")[:200],
                "relevance": chunk.get("score", 0),
                "retrieved_round": chunk.get("retrieved_in_round", 1),
            })

        trace.append(f"Final confidence: {confidence:.2f}")
        trace.append(f"Evidence sources: {len(evidence)}")

        return {
            **state,
            "final_answer": final_answer,
            "evidence": evidence,
            "reasoning_trace": trace,
            "status": "completed",
        }

    # ============================================================
    # Build the LangGraph with reflection loops
    # ============================================================

    graph = StateGraph(NavigatorState)

    # Add all nodes
    graph.add_node("planner", planner_node)
    graph.add_node("graph_explorer", graph_explorer_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("reasoner", reasoner_node)
    graph.add_node("critic", critic_node)
    graph.add_node("increment", increment_iteration)
    graph.add_node("synthesizer", synthesizer_node)

    # Linear flow for first pass
    graph.set_entry_point("planner")
    graph.add_edge("planner", "graph_explorer")
    graph.add_edge("graph_explorer", "retriever")
    graph.add_edge("retriever", "reasoner")
    graph.add_edge("reasoner", "critic")

    # Conditional edges based on verification result
    graph.add_conditional_edges(
        "critic",
        should_refine,
        {
            "synthesize": "synthesizer",  # Done - go to final synthesis
            "retrieve": "increment",      # Need more evidence
            "reason": "increment",        # Need to refine reasoning
        }
    )

    # Loop back after incrementing iteration
    graph.add_conditional_edges(
        "increment",
        lambda state: "retrieve" if state.get("verification_result") == "RETRIEVE_MORE" else "reason",
        {
            "retrieve": "retriever",  # Loop to retriever
            "reason": "reasoner",     # Loop to reasoner
        }
    )

    # Final exit
    graph.add_edge("synthesizer", END)

    return graph


# ============================================================
# BRAIN 2.5: CORTEX 2.0 (Broad Research with Cross-Checking - Phase A2)
# ============================================================

def _build_cortex_2_graph(
    llm_service: LLMService,
    qdrant_client: QdrantClient,
    collection_name: str,
) -> StateGraph:
    """Build Cortex 2.0 with verification and cross-checking (SOTA 2026).

    Architecture:
      Decompose → Execute (5 tasks w/ CoT) → Cross-Check → [Resolve if conflicts] → Synthesize
                                                  ↓
                                          Detect contradictions
                                          Identify coverage gaps

    Nodes:
      decomposer    - Break query into sub-tasks with coverage validation
      executor      - Execute each sub-task with chain-of-thought reasoning
      cross_checker - Detect contradictions and coverage gaps
      synthesizer   - Final synthesis with conflict awareness
    """
    from app.core.config import settings

    async def decomposer_node(state: CortexState) -> CortexState:
        """Break query into sub-tasks with coverage validation (ENHANCED)."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("=== DECOMPOSITION PHASE ===")
        trace.append(f"Query: {state['query']}")

        num_subtasks = settings.CORTEX_NUM_SUBTASKS

        # Phase A3: Use prompt template if enabled
        if settings.USE_PROMPT_TEMPLATES:
            template = prompt_templates.CORTEX_DECOMPOSER
            prompt = template.format(
                query=state["query"],
                num_subtasks=num_subtasks
            )
            temperature = template.temperature
            max_tokens = template.max_tokens
            validator = prompt_templates.get_validator_for_node("decomposer")
        else:
            # Legacy prompt (Phase A2)
            prompt = f"""Break this research query into {num_subtasks} focused sub-questions.
Each sub-question should cover a different aspect or angle of the original query.

USER QUERY: {state["query"]}

STEP 1 - IDENTIFY KEY ASPECTS:
What are the different aspects of this query that need to be researched?
- Aspect 1: ...
- Aspect 2: ...
- ...

STEP 2 - DESIGN SUB-TASKS:
Create {num_subtasks} sub-questions (one per aspect):
1. [Sub-question for aspect 1]
2. [Sub-question for aspect 2]
...

STEP 3 - VALIDATION:
Do these {num_subtasks} sub-questions FULLY cover the original query?
Are there any important aspects missing?

Return your analysis as JSON:
{{
  "aspects": ["aspect 1", "aspect 2", "aspect 3", ...],
  "sub_tasks": ["sub-question 1", "sub-question 2", "sub-question 3", "sub-question 4", "sub-question 5"],
  "coverage_check": "COMPLETE" or "PARTIAL - missing [describe what's missing]"
}}
"""
            temperature = 0.15
            max_tokens = 1024
            validator = None

        try:
            response = await generate_with_validation(
                llm_service=llm_service,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                validator=validator,
                node_name="Decomposer",
                max_retries=settings.MAX_VALIDATION_RETRIES if hasattr(settings, 'MAX_VALIDATION_RETRIES') else 2,
            )
            decomp = parse_json_response(response)

            aspects = decomp.get("aspects", [])
            sub_tasks = decomp.get("sub_tasks", [state["query"]])
            coverage = decomp.get("coverage_check", "UNKNOWN")

            # Ensure we have the right number of sub-tasks
            if len(sub_tasks) < num_subtasks:
                # Pad with the original query if needed
                while len(sub_tasks) < num_subtasks:
                    sub_tasks.append(state["query"])
            elif len(sub_tasks) > num_subtasks:
                sub_tasks = sub_tasks[:num_subtasks]

            trace.append(f"Identified {len(aspects)} key aspects")
            trace.append(f"Created {len(sub_tasks)} sub-tasks")
            trace.append(f"Coverage: {coverage}")

            return {
                **state,
                "aspects": aspects,
                "sub_tasks": sub_tasks,
                "task_coverage_check": coverage,
                "reasoning_trace": trace,
            }
        except Exception as e:
            logger.error(f"Decomposer failed: {e}", exc_info=True)
            trace.append(f"Decomposition failed, using direct query: {e}")
            return {
                **state,
                "aspects": [],
                "sub_tasks": [state["query"]] * num_subtasks,
                "task_coverage_check": "ERROR",
                "reasoning_trace": trace,
            }

    async def executor_node(state: CortexState) -> CortexState:
        """Execute each sub-task with chain-of-thought reasoning (ENHANCED)."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("=== EXECUTION PHASE ===")

        sub_tasks = state.get("sub_tasks", [])
        sub_results = []

        for i, task in enumerate(sub_tasks):
            trace.append(f"Executing sub-task {i+1}/{len(sub_tasks)}: {task[:60]}...")

            try:
                # 1. Retrieve evidence for this sub-task
                embedding = await llm_service.embed(task)
                results = qdrant_client.query_points(
                    collection_name=collection_name,
                    query=embedding,
                    limit=4,
                ).points

                chunks_text = format_chunks([
                    {
                        "text": r.payload.get("text", ""),
                        "metadata": r.payload.get("metadata", {})
                    }
                    for r in results if r.payload
                ], max_chunks=3)

                if chunks_text == "[No evidence available]":
                    sub_results.append({
                        "task": task,
                        "answer": "No relevant documents found for this sub-task.",
                        "reasoning": "No evidence available",
                        "confidence": 0.0,
                        "sources": [],
                    })
                    continue

                # 2. Reason with chain-of-thought (Phase A3: use template if enabled)
                if settings.USE_PROMPT_TEMPLATES:
                    template = prompt_templates.CORTEX_EXECUTOR
                    prompt = template.format(task=task, evidence=chunks_text)
                    temperature = template.temperature
                    max_tokens = template.max_tokens
                    validator = prompt_templates.get_validator_for_node("executor")
                else:
                    # Legacy prompt (Phase A2)
                    prompt = f"""Answer this sub-question with step-by-step reasoning.

SUB-QUESTION: {task}

EVIDENCE:
{chunks_text}

FORMAT YOUR RESPONSE:

<thinking>
Step 1: What does the evidence actually say about this question?
Step 2: How confident can we be in this evidence?
Step 3: What's the clearest answer we can provide?
</thinking>

<answer>
[Your clear, evidence-based answer with specific citations]
</answer>

<confidence>HIGH/MEDIUM/LOW</confidence>
"""
                    temperature = 0.2
                    max_tokens = 1024
                    validator = None

                response = await generate_with_validation(
                    llm_service=llm_service,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    validator=validator,
                    node_name=f"Executor[{i+1}]",
                    max_retries=settings.MAX_VALIDATION_RETRIES if hasattr(settings, 'MAX_VALIDATION_RETRIES') else 2,
                )

                # Extract structured parts
                thinking = extract_xml_tag(response, "thinking")
                answer = extract_xml_tag(response, "answer")
                confidence_str = extract_xml_tag(response, "confidence")

                # Parse confidence
                confidence = 0.5  # default
                if "HIGH" in confidence_str.upper():
                    confidence = 0.85
                elif "MEDIUM" in confidence_str.upper():
                    confidence = 0.6
                elif "LOW" in confidence_str.upper():
                    confidence = 0.3

                # Build sources list
                sources = []
                for r in results[:3]:
                    if r.payload:
                        metadata = r.payload.get("metadata", {})
                        sources.append({
                            "source": metadata.get("filename", "Unknown"),
                            "page": metadata.get("page", 1),
                            "excerpt": r.payload.get("text", "")[:150],
                            "relevance": r.score,
                        })

                sub_results.append({
                    "task": task,
                    "answer": answer.strip() if answer else "No answer generated.",
                    "reasoning": thinking,
                    "confidence": confidence,
                    "sources": sources,
                })

                trace.append(f"  Completed with confidence: {confidence:.2f}")

            except Exception as e:
                logger.error(f"Executor sub-task {i+1} failed: {e}", exc_info=True)
                trace.append(f"  Sub-task {i+1} failed: {e}")
                sub_results.append({
                    "task": task,
                    "answer": f"Error processing: {str(e)}",
                    "reasoning": "",
                    "confidence": 0.0,
                    "sources": [],
                })

        trace.append(f"Completed all {len(sub_results)} sub-tasks")
        return {**state, "sub_results": sub_results, "reasoning_trace": trace}

    async def cross_checker_node(state: CortexState) -> CortexState:
        """Detect contradictions and coverage gaps (NEW in Phase A2)."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("=== CROSS-CHECKING PHASE ===")

        sub_results = state.get("sub_results", [])
        query = state["query"]

        # Format results for analysis
        results_text = "\n\n".join([
            f"Task {i+1}: {r['task']}\n"
            f"Answer: {r['answer']}\n"
            f"Confidence: {r['confidence']:.2f}"
            for i, r in enumerate(sub_results)
        ])

        # Phase A3: Use prompt template if enabled
        if settings.USE_PROMPT_TEMPLATES:
            template = prompt_templates.CORTEX_CROSS_CHECKER
            prompt = template.format(query=query, results=results_text)
            temperature = template.temperature
            max_tokens = template.max_tokens
            validator = prompt_templates.get_validator_for_node("cross_checker")
        else:
            # Legacy prompt (Phase A2)
            prompt = f"""You are a consistency validator. Analyze these sub-task results for contradictions and gaps.

ORIGINAL QUERY: {query}

SUB-TASK RESULTS:
{results_text}

ANALYSIS:

1. CONTRADICTIONS: Do any answers conflict with each other?
   - Look for direct contradictions (A says X, B says not-X)
   - Look for inconsistent claims across sub-tasks

2. COVERAGE: Do these answers FULLY address the original query?
   - Are all aspects of the query covered?
   - What important information is missing?

3. CONFIDENCE: Which findings are well-supported vs. speculative?
   - Which sub-tasks have low confidence?
   - Do low-confidence tasks create uncertainty in the overall answer?

Return your analysis as JSON:
{{
  "contradictions": [
    {{"between": ["task 1", "task 3"], "issue": "description of contradiction", "severity": "HIGH or LOW"}}
  ],
  "coverage_gaps": ["gap 1", "gap 2"],
  "overall_verdict": "PASS" or "HAS_CONFLICTS"
}}

PASS = No major contradictions, coverage is acceptable
HAS_CONFLICTS = Significant contradictions or major coverage gaps detected
"""
            temperature = 0.1
            max_tokens = 1024
            validator = None

        try:
            response = await generate_with_validation(
                llm_service=llm_service,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                validator=validator,
                node_name="Cross-Checker",
                max_retries=settings.MAX_VALIDATION_RETRIES if hasattr(settings, 'MAX_VALIDATION_RETRIES') else 2,
            )
            check = parse_json_response(response)

            contradictions = check.get("contradictions", [])
            gaps = check.get("coverage_gaps", [])
            verdict = check.get("overall_verdict", "PASS")

            trace.append(f"Verification verdict: {verdict}")
            trace.append(f"Contradictions found: {len(contradictions)}")
            trace.append(f"Coverage gaps: {len(gaps)}")

            # Log contradictions
            for contr in contradictions:
                severity = contr.get("severity", "UNKNOWN")
                between = contr.get("between", [])
                issue = contr.get("issue", "")
                trace.append(f"  [{severity}] Conflict between {between}: {issue[:80]}...")

            return {
                **state,
                "contradictions": contradictions,
                "coverage_gaps": gaps,
                "verification_result": verdict,
                "reasoning_trace": trace,
            }
        except Exception as e:
            logger.error(f"Cross-checker failed: {e}", exc_info=True)
            trace.append(f"Cross-checking failed, defaulting to PASS: {e}")
            return {
                **state,
                "contradictions": [],
                "coverage_gaps": [],
                "verification_result": "PASS",
                "reasoning_trace": trace,
            }

    async def synthesizer_node(state: CortexState) -> CortexState:
        """Synthesize final answer with conflict awareness (ENHANCED)."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("=== SYNTHESIS PHASE ===")

        sub_results = state.get("sub_results", [])
        contradictions = state.get("contradictions", [])
        gaps = state.get("coverage_gaps", [])
        query = state["query"]

        # Format sub-results
        results_text = "\n\n".join([
            f"Finding {i+1}: {r['answer']}"
            for i, r in enumerate(sub_results)
        ])

        # Build conflict awareness section
        conflict_text = ""
        if contradictions:
            high_severity = [c for c in contradictions if c.get("severity") == "HIGH"]
            if high_severity:
                conflict_text = "\n\nCRITICAL: The following contradictions were detected:\n"
                for contr in high_severity:
                    conflict_text += f"- {contr.get('issue', 'Unknown conflict')}\n"

        gaps_text = ""
        if gaps:
            gaps_text = f"\n\nNOTE: The following aspects may not be fully covered:\n"
            gaps_text += "\n".join([f"- {gap}" for gap in gaps])

        prompt = f"""You are a research synthesis agent. Combine these sub-task findings into a comprehensive answer.

ORIGINAL QUERY: {query}

FINDINGS:
{results_text}
{conflict_text}
{gaps_text}

Your task:
1. Synthesize the findings into a coherent answer
2. If contradictions exist, acknowledge them and explain which source is more reliable
3. If gaps exist, clearly state what information is missing
4. Provide an overall confidence assessment

COMPREHENSIVE SYNTHESIS:"""

        try:
            summary = await llm_service.generate(prompt=prompt, temperature=0.2, max_tokens=1500)

            # Calculate overall confidence from sub-results
            if sub_results:
                avg_confidence = sum(r.get("confidence", 0.5) for r in sub_results) / len(sub_results)
                # Reduce confidence if there are high-severity contradictions
                high_severity_count = sum(1 for c in contradictions if c.get("severity") == "HIGH")
                if high_severity_count > 0:
                    avg_confidence *= 0.7  # Reduce by 30% for conflicts
            else:
                avg_confidence = 0.0

            trace.append(f"Synthesis complete")
            trace.append(f"Overall confidence: {avg_confidence:.2f}")

            # Collect all evidence
            all_evidence = []
            for r in sub_results:
                all_evidence.extend(r.get("sources", []))

            return {
                **state,
                "hypothesis": summary.strip(),
                "confidence_score": avg_confidence,
                "evidence": all_evidence[:15],  # Top 15 sources
                "reasoning_trace": trace,
                "status": "completed",
            }
        except Exception as e:
            logger.error(f"Synthesizer failed: {e}", exc_info=True)
            trace.append(f"Synthesis failed: {e}")
            return {
                **state,
                "hypothesis": "Synthesis failed - see sub-task results.",
                "confidence_score": 0.0,
                "evidence": [],
                "reasoning_trace": trace,
                "status": "error",
            }

    async def resolver_node(state: CortexState) -> CortexState:
        """Attempt to reconcile contradictions (New in Phase A2)."""
        trace = list(state.get("reasoning_trace", []))
        contradictions = state.get("contradictions", [])
        
        # Only run if there are high-severity contradictions
        high_severity = [c for c in contradictions if c.get("severity") == "HIGH"]
        
        if not high_severity:
            trace.append("Resolver: No high-severity conflicts to resolve")
            return {**state, "resolutions": [], "reasoning_trace": trace}
            
        trace.append(f"Resolver: Attempting to resolve {len(high_severity)} conflicts...")
        
        # Prepare context for resolution
        sub_results = state.get("sub_results", [])
        evidence_text = "\n\n".join([
            f"Source: {s.get('source')} (p.{s.get('page')})\n{s.get('excerpt')}"
            for r in sub_results for s in r.get("sources", [])
        ])
        
        conflicts_text = "\n".join([
            f"- Conflict between {c.get('between')}: {c.get('issue')}"
            for c in high_severity
        ])
        
        # Phase A3: Use prompt template if enabled
        if settings.USE_PROMPT_TEMPLATES:
            template = prompt_templates.CORTEX_RESOLVER
            prompt = template.format(conflicts=conflicts_text, evidence=evidence_text[:2000])
            temperature = template.temperature
            max_tokens = template.max_tokens
            validator = prompt_templates.get_validator_for_node("resolver")
        else:
             # Fallback simple prompt
            prompt = f"""Resolve these contradictions based on the evidence:
            
CONFLICTS:
{conflicts_text}

EVIDENCE:
{evidence_text[:2000]}

Return JSON: {{ "resolutions": [ {{ "conflict_id": 0, "resolution": "...", "confidence": "HIGH" }} ] }}"""
            temperature = 0.1
            max_tokens = 1024
            validator = None
            
        try:
            response = await generate_with_validation(
                llm_service=llm_service,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                validator=validator,
                node_name="Resolver",
                max_retries=settings.MAX_VALIDATION_RETRIES if hasattr(settings, 'MAX_VALIDATION_RETRIES') else 2,
            )
            
            result = parse_json_response(response)
            resolutions = result.get("resolutions", [])
            
            trace.append(f"Resolver: Generated {len(resolutions)} resolutions")
            
            return {
                **state,
                "resolutions": resolutions,
                "reasoning_trace": trace
            }
            
        except Exception as e:
            logger.error(f"Resolver failed: {e}")
            trace.append(f"Resolver failed: {e}")
            return {**state, "resolutions": [], "reasoning_trace": trace}

    # ============================================================
    # Build the LangGraph
    # ============================================================

    graph = StateGraph(CortexState)

    # Add nodes
    graph.add_node("decomposer", decomposer_node)
    graph.add_node("executor", executor_node)
    graph.add_node("cross_checker", cross_checker_node)
    graph.add_node("resolver", resolver_node)
    graph.add_node("synthesizer", synthesizer_node)

    # Linear flow with conditional path for resolution
    graph.set_entry_point("decomposer")
    graph.add_edge("decomposer", "executor")
    graph.add_edge("executor", "cross_checker")
    
    # Conditional edge: Go to resolver if high-severity conflicts exist
    def should_resolve(state: CortexState) -> str:
        contradictions = state.get("contradictions", [])
        high_severity = [c for c in contradictions if c.get("severity") == "HIGH"]
        return "resolve" if high_severity else "synthesize"

    graph.add_conditional_edges(
        "cross_checker",
        should_resolve,
        {
            "resolve": "resolver",
            "synthesize": "synthesizer"
        }
    )
    
    graph.add_edge("resolver", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph


# ============================================================
# BRAIN 2: CORTEX (Broad/Map-Reduce, sequential execution)
# ============================================================

def _build_cortex_graph(
    llm_service: LLMService,
    qdrant_client: QdrantClient,
    collection_name: str,
) -> StateGraph:
    """Build the Cortex StateGraph.

    Map-Reduce pattern:
      mapper  - Break query into 5 sub-tasks
      worker  - Execute each sub-task sequentially (VRAM constraint)
      reducer - Summarize all results
    """

    async def mapper_node(state: SwarmState) -> SwarmState:
        """Break the broad query into 5 focused sub-tasks."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("Cortex Mapper: Breaking query into sub-tasks...")

        prompt = f"""Break this research query into exactly 5 focused sub-tasks that can be
independently searched. Each sub-task should cover a different angle or aspect.

Query: {state["query"]}

Return ONLY a JSON array of 5 strings, each a focused sub-question:
["sub-task 1", "sub-task 2", "sub-task 3", "sub-task 4", "sub-task 5"]"""

        try:
            response = await llm_service.generate(prompt=prompt, temperature=0.2, max_tokens=512)

            # Parse JSON array
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                sub_tasks = json.loads(response[start:end])
                if isinstance(sub_tasks, list) and len(sub_tasks) >= 1:
                    sub_tasks = sub_tasks[:5]
                else:
                    sub_tasks = [state["query"]]
            else:
                sub_tasks = [state["query"]]
        except Exception as e:
            trace.append(f"Cortex Mapper: Task decomposition failed: {e}")
            sub_tasks = [state["query"]]

        trace.append(f"Cortex Mapper: Created {len(sub_tasks)} sub-tasks")
        return {**state, "sub_tasks": sub_tasks, "sub_results": [], "reasoning_trace": trace}

    async def worker_node(state: SwarmState) -> SwarmState:
        """Execute each sub-task SEQUENTIALLY (GPU VRAM constraint).

        For each sub-task:
        1. Embed the sub-question
        2. Search Qdrant
        3. Generate a mini-answer
        """
        trace = list(state.get("reasoning_trace", []))
        sub_tasks = state.get("sub_tasks", [])
        sub_results = []

        for i, task in enumerate(sub_tasks):
            trace.append(f"Cortex Worker: Processing sub-task {i+1}/{len(sub_tasks)}: {task[:60]}...")

            try:
                # Search
                query_embedding = await llm_service.embed(task)
                results = qdrant_client.query_points(
                    collection_name=collection_name,
                    query=query_embedding,
                    limit=4,
                ).points

                chunk_texts = "\n".join(
                    [f"- {r.payload.get('text', '')[:300]}" for r in results[:3] if r.payload]
                )

                if not chunk_texts.strip():
                    sub_results.append({
                        "task": task,
                        "answer": "No relevant documents found for this sub-task.",
                        "sources": [],
                    })
                    continue

                # Mini-answer
                prompt = f"""Based on the evidence below, briefly answer this research sub-question.
Be specific and cite the evidence.

Sub-question: {task}

Evidence:
{chunk_texts}

Brief answer:"""

                answer = await llm_service.generate(prompt=prompt, temperature=0.2, max_tokens=512)

                sources = [
                    {
                        "source": (r.payload or {}).get("metadata", {}).get("filename", "Unknown"),
                        "page": (r.payload or {}).get("metadata", {}).get("page", 1),
                        "excerpt": (r.payload or {}).get("text", "")[:150],
                        "relevance": r.score,
                    }
                    for r in results[:3]
                    if r.payload
                ]

                sub_results.append({
                    "task": task,
                    "answer": answer.strip(),
                    "sources": sources,
                })

            except Exception as e:
                trace.append(f"Cortex Worker: Sub-task {i+1} failed: {e}")
                sub_results.append({
                    "task": task,
                    "answer": f"Error processing: {str(e)}",
                    "sources": [],
                })

        trace.append(f"Cortex Worker: Completed {len(sub_results)} sub-tasks")
        return {**state, "sub_results": sub_results, "reasoning_trace": trace}

    async def reducer_node(state: SwarmState) -> SwarmState:
        """Summarize all sub-task results into a cohesive answer."""
        trace = list(state.get("reasoning_trace", []))
        trace.append("Cortex Reducer: Synthesizing results...")

        sub_results = state.get("sub_results", [])

        results_text = "\n\n".join(
            [f"Sub-task: {r['task']}\nFindings: {r['answer']}" for r in sub_results]
        )

        prompt = f"""You are a research synthesis agent. Combine these sub-task findings
into a comprehensive, coherent answer to the original query.
Highlight patterns, contradictions, and gaps.

ORIGINAL QUERY: {state["query"]}

SUB-TASK FINDINGS:
{results_text}

COMPREHENSIVE SYNTHESIS:"""

        try:
            summary = await llm_service.generate(prompt=prompt, temperature=0.2, max_tokens=1500)
            trace.append("Cortex Reducer: Synthesis complete")

            # Collect all evidence
            all_evidence = []
            for r in sub_results:
                all_evidence.extend(r.get("sources", []))

            return {
                **state,
                "hypothesis": summary.strip(),
                "evidence": all_evidence[:10],
                "reasoning_trace": trace,
                "status": "completed",
            }
        except Exception as e:
            trace.append(f"Cortex Reducer: Synthesis failed: {e}")
            return {
                **state,
                "hypothesis": "Synthesis failed - see individual sub-task results.",
                "evidence": [],
                "reasoning_trace": trace,
                "status": "error",
            }

    # Build the graph
    graph = StateGraph(SwarmState)
    graph.add_node("mapper", mapper_node)
    graph.add_node("worker", worker_node)
    graph.add_node("reducer", reducer_node)

    graph.set_entry_point("mapper")
    graph.add_edge("mapper", "worker")
    graph.add_edge("worker", "reducer")
    graph.add_edge("reducer", END)

    return graph


# ============================================================
# PUBLIC API
# ============================================================

async def run_swarm_query(
    query: str,
    project_id: str,
    graph_service: GraphService,
    llm_service: LLMService,
    qdrant_client: QdrantClient,
    collection_name: str,
) -> Dict[str, Any]:
    """Run the Two-Brain Swarm on a query (supports Navigator 2.0 reflection).

    1. Router classifies the intent
    2. Dispatches to Navigator/Navigator 2.0 (deep) or Cortex (broad)
    3. Returns structured result with confidence scores and iteration counts

    Args:
        query: User's research question
        project_id: Project scope
        graph_service: GraphService instance
        llm_service: LLMService instance
        qdrant_client: Embedded QdrantClient
        collection_name: Qdrant collection name

    Returns:
        Dict with brain_used, hypothesis, evidence, reasoning_trace, status,
        confidence_score, iterations (Navigator 2.0 fields)
    """
    from app.core.config import settings

    # Step 1: Route
    intent = await route_intent(query, llm_service)
    logger.info(f"Swarm router classified query as: {intent}")

    # Step 2: Dispatch to appropriate brain
    if intent == "DEEP_DISCOVERY":
        brain_name = "navigator"

        # Use Navigator 2.0 if reflection is enabled
        if settings.ENABLE_NAVIGATOR_REFLECTION:
            logger.info("Using Navigator 2.0 with reflection loops")
            initial_state: NavigatorState = {
                "query": query,
                "project_id": project_id,
                "brain": brain_name,
                "reasoning_plan": "",
                "identified_gaps": [],
                "search_terms": [],
                "graph_summary": "",
                "key_paths": [],
                "entity_clusters": [],
                "chunks": [],
                "retrieval_round": 1,
                "retrieval_history": [],
                "hypothesis": "",
                "reasoning_trace": [f"Router: Classified as {intent}", "Navigator 2.0 with reflection enabled"],
                "evidence_map": "",
                "verification_result": "",
                "identified_contradictions": [],
                "confidence_score": 0.5,
                "iteration_count": 0,
                "final_answer": "",
                "evidence": [],
                "status": "running",
            }
            sg = _build_navigator_2_graph(graph_service, llm_service, qdrant_client, collection_name)
        else:
            # Legacy Navigator 1.0
            logger.info("Using Navigator 1.0 (legacy mode)")
            initial_state: SwarmState = {
                "query": query,
                "project_id": project_id,
                "brain": brain_name,
                "subgraph_summary": "",
                "chunks": [],
                "hypothesis": "",
                "sub_tasks": [],
                "sub_results": [],
                "cortex_summary": "",
                "evidence": [],
                "reasoning_trace": [f"Router: Classified as {intent}"],
                "status": "running",
            }
            sg = _build_navigator_graph(graph_service, llm_service, qdrant_client, collection_name)
    else:
        # Cortex for broad research
        brain_name = "cortex"

        # Use Cortex 2.0 if cross-checking is enabled
        if settings.ENABLE_CORTEX_CROSSCHECK:
            logger.info("Using Cortex 2.0 with cross-checking")
            initial_state: CortexState = {
                "query": query,
                "project_id": project_id,
                "brain": brain_name,
                "aspects": [],
                "sub_tasks": [],
                "task_coverage_check": "",
                "sub_results": [],
                "contradictions": [],
                "coverage_gaps": [],
                "verification_result": "",
                "resolutions": [],
                "hypothesis": "",
                "reasoning_trace": [f"Router: Classified as {intent}", "Cortex 2.0 with cross-checking enabled"],
                "evidence": [],
                "confidence_score": 0.5,
                "status": "running",
            }
            sg = _build_cortex_2_graph(llm_service, qdrant_client, collection_name)
        else:
            # Legacy Cortex 1.0
            logger.info("Using Cortex 1.0 (legacy mode)")
            initial_state: SwarmState = {
                "query": query,
                "project_id": project_id,
                "brain": brain_name,
                "subgraph_summary": "",
                "chunks": [],
                "hypothesis": "",
                "sub_tasks": [],
                "sub_results": [],
                "cortex_summary": "",
                "evidence": [],
                "reasoning_trace": [f"Router: Classified as {intent}"],
                "status": "running",
            }
            sg = _build_cortex_graph(llm_service, qdrant_client, collection_name)

    compiled = sg.compile()

    # Step 3: Execute
    final_state = await compiled.ainvoke(initial_state)

    # Step 4: Build response (Navigator 2.0 includes additional fields)
    return {
        "brain_used": brain_name,
        "hypothesis": final_state.get("final_answer") or final_state.get("hypothesis", ""),
        "evidence": final_state.get("evidence", []),
        "reasoning_trace": final_state.get("reasoning_trace", []),
        "status": final_state.get("status", "unknown"),
        # Navigator 2.0 new fields (default to None for legacy brains)
        "confidence_score": final_state.get("confidence_score"),
        "iterations": final_state.get("iteration_count"),
        "contradictions": final_state.get("identified_contradictions", []),
    }
