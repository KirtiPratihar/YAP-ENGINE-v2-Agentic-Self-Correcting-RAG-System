"""
router.py — Yap Engine V2
Lightweight intent classifier using scikit-learn (no LLM call needed).
Routes queries to: vector_search | summarize | calculation | greeting
This avoids burning expensive Groq tokens on simple routing decisions.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import numpy as np

# --- Training data for the intent classifier ---
TRAINING_DATA = [
    # vector_search
    ("What does the document say about X?", "vector_search"),
    ("Find information about the introduction", "vector_search"),
    ("What are the key findings?", "vector_search"),
    ("Explain the methodology section", "vector_search"),
    ("What does the author argue?", "vector_search"),
    ("Look up the references", "vector_search"),
    ("Search for conclusions", "vector_search"),
    ("Tell me about chapter 3", "vector_search"),
    ("Who is mentioned in the document?", "vector_search"),
    ("What happened in 2023 according to this?", "vector_search"),

    # summarize
    ("Summarize the document", "summarize"),
    ("Give me a summary", "summarize"),
    ("What is this document about?", "summarize"),
    ("Provide an overview", "summarize"),
    ("TL;DR", "summarize"),
    ("Key points please", "summarize"),
    ("What are the main ideas?", "summarize"),
    ("Brief summary", "summarize"),

    # calculation
    ("Calculate the total", "calculation"),
    ("What is 20% of 500?", "calculation"),
    ("Add up all the numbers", "calculation"),
    ("What is the average?", "calculation"),
    ("Compute the difference", "calculation"),
    ("How many pages?", "calculation"),

    # greeting
    ("Hello", "greeting"),
    ("Hi there", "greeting"),
    ("How are you?", "greeting"),
    ("What can you do?", "greeting"),
    ("Help", "greeting"),
]

texts, labels = zip(*TRAINING_DATA)

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(texts)

classifier = LogisticRegression(max_iter=200)
classifier.fit(X, labels)


def classify_intent(query: str) -> dict:
    """
    Classifies the user's query into one of: vector_search, summarize, calculation, greeting.

    Returns:
        dict with intent (str) and confidence (float)
    """
    x = vectorizer.transform([query])
    intent = classifier.predict(x)[0]
    proba = classifier.predict_proba(x)[0]
    confidence = float(np.max(proba))

    return {
        "intent": intent,
        "confidence": round(confidence, 4),
    }