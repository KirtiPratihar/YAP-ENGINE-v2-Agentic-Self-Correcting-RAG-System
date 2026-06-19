# ✨ Yap Engine V2 — Agentic Self-Correcting RAG

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **V1** was a production-ready RAG pipeline.  
> **V2** is an *agentic* RAG system with a self-correcting evaluation loop, intent routing, and latency tracking — built to showcase ML engineering principles.

---

## 🆕 What's New in V2

| Feature | V1 | V2 |
|---|---|---|
| Architecture | Linear pipeline | LangGraph cyclic graph |
| Intent Routing | None (LLM for everything) | scikit-learn TF-IDF classifier (no token cost) |
| Retrieval Evaluation | None | Precision@K scoring on chunk embeddings |
| Self-Correction | None | Query rewrite loop (up to 2 retries) |
| Latency Tracking | None | Per-node ms logging + total latency |
| Answer Metadata | Just text | Intent, eval scores, rewrite count, latency log |

---

## 🧠 Architecture

```
User Query
    │
    ▼
[route_query]  ── scikit-learn TF-IDF classifier
    │
    ├── greeting ──────────────────────────────► END
    ├── summarize ──► [summarize_node] ────────► END
    │
    └── vector_search
            │
            ▼
      [retrieve_chunks]  ── Pinecone + HuggingFace embeddings
            │
            ▼
      [evaluate_chunks]  ── Precision@K scoring (sklearn cosine_similarity)
            │
       passed? ──NO (loop ≤ 2)──► [rewrite_query] ──► [retrieve_chunks]
            │
           YES
            │
            ▼
      [generate_answer]  ── Groq Llama 3.3 70B
            │
            ▼
           END
```

---

## 🛠️ Tech Stack

- **LangGraph** — cyclic graph state machine for agentic control flow
- **scikit-learn** — TF-IDF + Logistic Regression for intent classification
- **Pinecone** — vector database with per-session namespace isolation
- **Hugging Face** — `BAAI/bge-small-en-v1.5` embeddings (384 dims)
- **Groq** — Llama 3.3 70B LLM inference
- **FastAPI** — backend API (V1 endpoint-compatible)
- **Next.js** — frontend (reused from V1)

---

## ⚙️ Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:
```
PINECONE_API_KEY=your_pinecone_key
GROQ_API_KEY=your_groq_key
HF_TOKEN=your_huggingface_token
```

Run:
```bash
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The V1 frontend works with V2 out of the box — no changes needed.

---

## 📊 V2 Response Format

Every `/query` response now includes `v2_metadata`:

```json
{
  "answer": "The document states...",
  "v2_metadata": {
    "intent": "vector_search",
    "intent_confidence": 0.91,
    "eval_result": {
      "precision_at_k": 0.8,
      "mean_score": 0.82,
      "passed": true,
      "scores": [0.91, 0.85, 0.82, 0.78, 0.74],
      "threshold": 0.75,
      "k": 5
    },
    "rewrite_count": 0,
    "rewritten_query": "Key findings?",
    "latency_log": [
      {"node": "route_query", "duration_ms": 3.2},
      {"node": "retrieve_chunks", "duration_ms": 210.5},
      {"node": "evaluate_chunks", "duration_ms": 1.1},
      {"node": "generate_answer", "duration_ms": 890.4}
    ],
    "total_latency_ms": 1108.3
  }
}
```

---

## 🎯 Why This Project Stands Out

- **Precision@K** — treats retrieval like a traditional ML ranking problem, not a black box
- **Self-correction loop** — the graph retries with a rewritten query when retrieval quality fails the threshold
- **Intent classifier** — uses scikit-learn (zero LLM cost) to route queries; proves understanding of traditional ML beyond just calling APIs
- **LangGraph state machine** — applies graph/DSA theory (cyclic directed graphs, conditional edges) to AI engineering
- **Latency trade-off logging** — demonstrates production ML thinking: accuracy vs speed

---

Built by [Kirti Pratihar](https://github.com/KirtiPratihar)