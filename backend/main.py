"""
main.py — Yap Engine V2
FastAPI backend wired to LangGraph agentic RAG pipeline.
Drop-in replacement for V1's main.py — same endpoint signatures, 
so the V1 frontend works without any changes.
"""

import os
import uuid
import time
import requests
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pypdf import PdfReader
from groq import Groq
from pinecone import Pinecone

from graph import build_graph

load_dotenv()

# ─── Init ─────────────────────────────────────────────────────────────────────

app = FastAPI(title="Yap Engine V2 — Agentic RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
INDEX_NAME = "chat-index"

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)
groq_client = Groq(api_key=GROQ_API_KEY)

# In-memory store of stored chunk texts per namespace (session_id → list of texts)
# Used for summarization without a second Pinecone fetch
session_chunks: dict[str, list[str]] = {}

# ─── Metrics Store ────────────────────────────────────────────────────────────
# Tracks per-session query stats for the /metrics endpoint

SERVER_START_TIME = time.time()

# session_id → list of query stat dicts
session_metrics: dict[str, list[dict]] = {}

def record_metric(session_id: str, stat: dict):
    if session_id not in session_metrics:
        session_metrics[session_id] = []
    session_metrics[session_id].append(stat)


# ─── Helper Functions (injected into LangGraph) ───────────────────────────────

def embed_text(text: str) -> list[float]:
    """Calls Hugging Face Inference API to get a 384-dim embedding."""
    url = "https://api-inference.huggingface.co/pipeline/feature-extraction/BAAI/bge-small-en-v1.5"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    response = requests.post(url, headers=headers, json={"inputs": text, "options": {"wait_for_model": True}})
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"HF embedding failed: {response.text}")
    result = response.json()
    # Flatten if nested (sentence-level vs token-level output)
    if isinstance(result[0], list):
        result = np.mean(result, axis=0).tolist()
    return result


def pinecone_query(embedding: list[float], session_id: str, top_k: int = 5) -> list[dict]:
    """Queries Pinecone and returns chunks with their stored embeddings."""
    results = index.query(
        vector=embedding,
        top_k=top_k,
        namespace=session_id,
        include_metadata=True,
        include_values=True,   # ← V2 addition: fetch vectors for scoring
    )
    return [
        {
            "text": match["metadata"].get("text", ""),
            "embedding": match.get("values", []),
            "score": match["score"],
        }
        for match in results.get("matches", [])
    ]


def llm_generate(query: str, context: str) -> str:
    """Calls Groq Llama 3.3 to generate an answer given retrieved context."""
    prompt = f"""You are a helpful assistant that answers questions based strictly on the provided document context.
If the answer is not found in the context, say "I couldn't find that in the document."

Context:
{context}

Question: {query}
Answer:"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


def llm_summarize(session_id: str) -> str:
    """Generates a bullet-point summary from stored session chunks."""
    chunks = session_chunks.get(session_id, [])
    if not chunks:
        return "No document found for this session. Please upload a PDF first."
    context = "\n\n".join(chunks[:20])  # limit to first 20 chunks
    prompt = f"""Summarize the following document in bullet points (max 8 bullets). Be concise.

Document:
{context}

Summary:"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


# ─── Build LangGraph ──────────────────────────────────────────────────────────

rag_graph = build_graph(
    pinecone_query_fn=pinecone_query,
    embed_fn=embed_text,
    llm_fn=llm_generate,
    summarize_fn=llm_summarize,
)


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Yap Engine V2 is running", "version": "2.0.0"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...), session_id: str = None):
    """
    Accepts a PDF, chunks it, embeds each chunk, and upserts into Pinecone.
    Compatible with V1 frontend (x-session-id header also accepted via /query).
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    import io
    reader = PdfReader(io.BytesIO(content))
    full_text = " ".join(page.extract_text() or "" for page in reader.pages)

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF.")

    # Chunk text (1000 chars with 100-char overlap for context continuity)
    chunk_size = 1000
    overlap = 100
    chunks = []
    start = 0
    while start < len(full_text):
        end = min(start + chunk_size, len(full_text))
        chunks.append(full_text[start:end])
        start += chunk_size - overlap

    # Store chunks in memory for summarization
    session_chunks[session_id] = chunks

    # Embed and upsert to Pinecone
    vectors = []
    for i, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        vectors.append({
            "id": f"{session_id}-chunk-{i}",
            "values": embedding,
            "metadata": {"text": chunk, "chunk_index": i},
        })
        # Upsert in batches of 50
        if len(vectors) >= 50:
            index.upsert(vectors=vectors, namespace=session_id)
            vectors = []

    if vectors:
        index.upsert(vectors=vectors, namespace=session_id)

    return {
        "status": "success",
        "message": "PDF indexed successfully",
        "chunks_created": len(chunks),
        "session_id": session_id,
        "version": "v2",
    }


class QueryRequest(BaseModel):
    question: str
    session_id: str = None


@app.post("/query")
async def query_document(request: QueryRequest):
    """
    Runs the LangGraph agentic pipeline:
    route → retrieve → evaluate → (rewrite loop) → generate
    Returns the answer plus V2 metadata (eval scores, latency log, intent).
    """
    session_id = request.session_id or "default"

    t_total = time.time()
    initial_state = {
        "query": request.question,
        "session_id": session_id,
        "intent": "",
        "intent_confidence": 0.0,
        "chunks": [],
        "chunk_embeddings": [],
        "query_embedding": [],
        "eval_result": {},
        "rewrite_count": 0,
        "rewritten_query": request.question,
        "answer": "",
        "latency_log": [],
    }

    final_state = rag_graph.invoke(initial_state)

    eval_result = final_state.get("eval_result", {})
    precision = eval_result.get("precision_at_k", 0)
    total_ms = round((time.time() - t_total) * 1000, 2)

    # Confidence label for frontend badge display
    if precision >= 0.8:
        confidence_label = "high"
    elif precision >= 0.5:
        confidence_label = "medium"
    else:
        confidence_label = "low"

    # Record to metrics store
    record_metric(session_id, {
        "timestamp": time.time(),
        "intent": final_state.get("intent"),
        "precision_at_k": precision,
        "rewrite_count": final_state.get("rewrite_count", 0),
        "total_latency_ms": total_ms,
        "latency_log": final_state.get("latency_log", []),
        "passed": eval_result.get("passed", False),
    })

    return {
        "answer": final_state["answer"],
        "confidence_label": confidence_label,   # "high" | "medium" | "low"
        # V2 bonus metadata — great to showcase in your resume/demo
        "v2_metadata": {
            "intent": final_state.get("intent"),
            "intent_confidence": final_state.get("intent_confidence"),
            "eval_result": eval_result,
            "rewrite_count": final_state.get("rewrite_count", 0),
            "rewritten_query": final_state.get("rewritten_query"),
            "latency_log": final_state.get("latency_log", []),
            "total_latency_ms": total_ms,
        },
    }


class SummarizeRequest(BaseModel):
    session_id: str = None


@app.post("/summarize")
async def summarize_document(request: SummarizeRequest):
    """Same signature as V1 — works with V1 frontend's summarize button."""
    session_id = request.session_id or "default"
    summary = llm_summarize(session_id)
    return {"summary": summary}


@app.get("/metrics/{session_id}")
async def get_session_metrics(session_id: str):
    """
    Returns a summary dashboard for a session:
    avg precision@k, avg latency per node, rewrite rate, intent distribution.
    """
    stats = session_metrics.get(session_id, [])
    if not stats:
        return {"session_id": session_id, "query_count": 0, "message": "No queries recorded yet."}

    query_count = len(stats)
    avg_precision = round(sum(s["precision_at_k"] for s in stats) / query_count, 4)
    avg_latency_ms = round(sum(s["total_latency_ms"] for s in stats) / query_count, 2)
    rewrite_rate = round(sum(1 for s in stats if s["rewrite_count"] > 0) / query_count, 4)
    pass_rate = round(sum(1 for s in stats if s["passed"]) / query_count, 4)

    # Per-node average latency across all queries
    node_totals: dict[str, list[float]] = {}
    for s in stats:
        for entry in s.get("latency_log", []):
            node = entry["node"]
            node_totals.setdefault(node, []).append(entry["duration_ms"])
    avg_latency_per_node = {
        node: round(sum(vals) / len(vals), 2)
        for node, vals in node_totals.items()
    }

    # Intent distribution
    intent_counts: dict[str, int] = {}
    for s in stats:
        intent = s.get("intent") or "unknown"
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    return {
        "session_id": session_id,
        "query_count": query_count,
        "avg_precision_at_k": avg_precision,
        "avg_total_latency_ms": avg_latency_ms,
        "rewrite_rate": rewrite_rate,
        "retrieval_pass_rate": pass_rate,
        "avg_latency_per_node_ms": avg_latency_per_node,
        "intent_distribution": intent_counts,
    }


@app.get("/health")
async def health_check():
    """
    Production-standard health endpoint.
    Returns version, uptime, and live Pinecone index stats.
    """
    uptime_seconds = round(time.time() - SERVER_START_TIME, 1)
    uptime_str = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m {int(uptime_seconds % 60)}s"

    try:
        index_stats = index.describe_index_stats()
        pinecone_status = "connected"
        total_vectors = index_stats.get("total_vector_count", 0)
        active_namespaces = len(index_stats.get("namespaces", {}))
    except Exception as e:
        pinecone_status = f"error: {str(e)}"
        total_vectors = None
        active_namespaces = None

    return {
        "status": "ok",
        "version": "2.0.0",
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "active_sessions_in_memory": len(session_chunks),
        "total_queries_recorded": sum(len(v) for v in session_metrics.values()),
        "pinecone": {
            "status": pinecone_status,
            "index": INDEX_NAME,
            "total_vectors": total_vectors,
            "active_namespaces": active_namespaces,
        },
        "models": {
            "llm": "llama-3.3-70b-versatile (Groq)",
            "embeddings": "BAAI/bge-small-en-v1.5 (HuggingFace, 384-dim)",
            "router": "TF-IDF + LogisticRegression (scikit-learn)",
        },
    }


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Deletes a Pinecone namespace, clears memory cache and metrics."""
    try:
        index.delete(delete_all=True, namespace=session_id)
        session_chunks.pop(session_id, None)
        session_metrics.pop(session_id, None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "cleared", "session_id": session_id}