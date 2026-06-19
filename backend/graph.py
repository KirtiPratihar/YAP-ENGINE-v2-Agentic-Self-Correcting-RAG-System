"""
graph.py — Yap Engine V2
LangGraph-powered agentic RAG with a self-correcting evaluation loop.

Graph structure:
    START
      │
      ▼
  [route_query]  ──── greeting ──────────────────────────────► END
      │
      ├── summarize ──► [summarize_node] ────────────────────► END
      │
      └── vector_search / calculation
              │
              ▼
        [retrieve_chunks]
              │
              ▼
        [evaluate_chunks]
              │
         passed? ──NO (loop < 2)──► [rewrite_query] ──► [retrieve_chunks]
              │
             YES
              │
              ▼
        [generate_answer]
              │
              ▼
             END
"""

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from evaluator import score_chunks, compute_precision_at_k, rewrite_query
from router import classify_intent
import time


# ─── State Schema ────────────────────────────────────────────────────────────

class RagState(TypedDict):
    # Inputs
    query: str
    session_id: str

    # Routing
    intent: str
    intent_confidence: float

    # Retrieval
    chunks: list[str]
    chunk_embeddings: list[list[float]]
    query_embedding: list[float]

    # Evaluation
    eval_result: dict
    rewrite_count: int
    rewritten_query: str

    # Output
    answer: str
    latency_log: list[dict]   # [{node, duration_ms}] for trade-off graph


# ─── Node Functions ───────────────────────────────────────────────────────────

def route_query_node(state: RagState) -> RagState:
    t0 = time.time()
    result = classify_intent(state["query"])
    state["intent"] = result["intent"]
    state["intent_confidence"] = result["confidence"]
    state["rewrite_count"] = 0
    state["rewritten_query"] = state["query"]
    state["latency_log"] = state.get("latency_log", [])
    state["latency_log"].append({
        "node": "route_query",
        "duration_ms": round((time.time() - t0) * 1000, 2)
    })
    return state


def retrieve_chunks_node(state: RagState, pinecone_query_fn, embed_fn) -> RagState:
    """
    Calls Pinecone to retrieve top-K chunks for the current query.
    pinecone_query_fn and embed_fn are injected at build time (see build_graph).
    """
    t0 = time.time()
    active_query = state.get("rewritten_query") or state["query"]
    query_embedding = embed_fn(active_query)
    state["query_embedding"] = query_embedding

    results = pinecone_query_fn(
        embedding=query_embedding,
        session_id=state["session_id"],
        top_k=5,
    )
    state["chunks"] = [r["text"] for r in results]
    state["chunk_embeddings"] = [r["embedding"] for r in results]

    state["latency_log"].append({
        "node": "retrieve_chunks",
        "duration_ms": round((time.time() - t0) * 1000, 2)
    })
    return state


def evaluate_chunks_node(state: RagState) -> RagState:
    t0 = time.time()
    scores = score_chunks(state["query_embedding"], state["chunk_embeddings"])
    eval_result = compute_precision_at_k(scores, threshold=0.75, k=5)
    state["eval_result"] = eval_result
    state["latency_log"].append({
        "node": "evaluate_chunks",
        "duration_ms": round((time.time() - t0) * 1000, 2)
    })
    return state


def rewrite_query_node(state: RagState) -> RagState:
    t0 = time.time()
    state["rewritten_query"] = rewrite_query(state["query"])
    state["rewrite_count"] = state.get("rewrite_count", 0) + 1
    state["latency_log"].append({
        "node": "rewrite_query",
        "duration_ms": round((time.time() - t0) * 1000, 2)
    })
    return state


def generate_answer_node(state: RagState, llm_fn) -> RagState:
    """
    llm_fn: callable(query, chunks) -> str  (injected at build time)
    """
    t0 = time.time()
    context = "\n\n---\n\n".join(state["chunks"])
    answer = llm_fn(query=state["query"], context=context)
    state["answer"] = answer
    state["latency_log"].append({
        "node": "generate_answer",
        "duration_ms": round((time.time() - t0) * 1000, 2)
    })
    return state


def summarize_node(state: RagState, summarize_fn) -> RagState:
    t0 = time.time()
    state["answer"] = summarize_fn(session_id=state["session_id"])
    state["latency_log"].append({
        "node": "summarize",
        "duration_ms": round((time.time() - t0) * 1000, 2)
    })
    return state


def greeting_node(state: RagState) -> RagState:
    state["answer"] = (
        "Hello! I'm Yap Engine V2. Upload a PDF and ask me anything about it. "
        "I can search, summarize, and self-correct my answers for accuracy."
    )
    return state


# ─── Conditional Edge Logic ───────────────────────────────────────────────────

def route_after_intent(state: RagState) -> str:
    intent = state.get("intent", "vector_search")
    if intent == "greeting":
        return "greeting"
    if intent == "summarize":
        return "summarize"
    return "retrieve"   # vector_search or calculation both go through retrieval


def route_after_evaluation(state: RagState) -> str:
    eval_result = state.get("eval_result", {})
    rewrite_count = state.get("rewrite_count", 0)
    if eval_result.get("passed", True) or rewrite_count >= 2:
        return "generate"
    return "rewrite"


# ─── Graph Builder ────────────────────────────────────────────────────────────

def build_graph(pinecone_query_fn, embed_fn, llm_fn, summarize_fn):
    """
    Builds and compiles the LangGraph state machine.
    Dependency injection keeps this testable — pass mock fns in unit tests.
    """
    from functools import partial

    graph = StateGraph(RagState)

    # Register nodes (partial-apply injected dependencies)
    graph.add_node("route_query", route_query_node)
    graph.add_node("retrieve_chunks", partial(retrieve_chunks_node, pinecone_query_fn=pinecone_query_fn, embed_fn=embed_fn))
    graph.add_node("evaluate_chunks", evaluate_chunks_node)
    graph.add_node("rewrite_query", rewrite_query_node)
    graph.add_node("generate_answer", partial(generate_answer_node, llm_fn=llm_fn))
    graph.add_node("summarize", partial(summarize_node, summarize_fn=summarize_fn))
    graph.add_node("greeting", greeting_node)

    # Entry point
    graph.set_entry_point("route_query")

    # Edges
    graph.add_conditional_edges("route_query", route_after_intent, {
        "greeting": "greeting",
        "summarize": "summarize",
        "retrieve": "retrieve_chunks",
    })
    graph.add_edge("greeting", END)
    graph.add_edge("summarize", END)
    graph.add_edge("retrieve_chunks", "evaluate_chunks")
    graph.add_conditional_edges("evaluate_chunks", route_after_evaluation, {
        "generate": "generate_answer",
        "rewrite": "rewrite_query",
    })
    graph.add_edge("rewrite_query", "retrieve_chunks")   # ← self-correction loop
    graph.add_edge("generate_answer", END)

    return graph.compile()