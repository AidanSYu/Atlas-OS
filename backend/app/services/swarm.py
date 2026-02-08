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
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

import networkx as nx
from langgraph.graph import StateGraph, END

from app.services.graph import GraphService
from app.services.llm import LLMService
from qdrant_client import QdrantClient

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

        G = graph_service.get_networkx_subgraph(project_id=state["project_id"])
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
            results = qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=8,
            )

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
                results = qdrant_client.search(
                    collection_name=collection_name,
                    query_vector=query_embedding,
                    limit=4,
                )

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
    """Run the Two-Brain Swarm on a query.

    1. Router classifies the intent
    2. Dispatches to Navigator (deep) or Cortex (broad)
    3. Returns structured result

    Args:
        query: User's research question
        project_id: Project scope
        graph_service: GraphService instance
        llm_service: LLMService instance
        qdrant_client: Embedded QdrantClient
        collection_name: Qdrant collection name

    Returns:
        Dict with brain_used, hypothesis, evidence, reasoning_trace, status
    """
    # Step 1: Route
    intent = await route_intent(query, llm_service)
    logger.info(f"Swarm router classified query as: {intent}")

    initial_state: SwarmState = {
        "query": query,
        "project_id": project_id,
        "brain": "",
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

    # Step 2: Dispatch
    if intent == "DEEP_DISCOVERY":
        initial_state["brain"] = "navigator"
        sg = _build_navigator_graph(graph_service, llm_service, qdrant_client, collection_name)
    else:
        initial_state["brain"] = "cortex"
        sg = _build_cortex_graph(llm_service, qdrant_client, collection_name)

    compiled = sg.compile()

    # Step 3: Execute
    final_state = await compiled.ainvoke(initial_state)

    return {
        "brain_used": final_state.get("brain", "unknown"),
        "hypothesis": final_state.get("hypothesis", ""),
        "evidence": final_state.get("evidence", []),
        "reasoning_trace": final_state.get("reasoning_trace", []),
        "status": final_state.get("status", "unknown"),
    }
