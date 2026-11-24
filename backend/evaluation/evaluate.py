"""
Evaluation module: Baseline vs RAG comparison.

Compares Gemini answers without retrieved context (baseline) against
answers grounded with RAG-retrieved passages.

Usage:
    python -m evaluation.evaluate

Requires GEMINI_API_KEY in .env or environment.
This module uses its own isolated data (not the production database).
"""

import json
import time
import sys
import os
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.services.llm import LLMService, LLMServiceError


def load_dataset() -> list[dict]:
    """Load the evaluation dataset."""
    dataset_path = Path(__file__).parent / "dataset.json"
    with open(dataset_path, "r") as f:
        return json.load(f)


def term_coverage(answer: str, expected_terms: list[str]) -> float:
    """
    Calculate the fraction of expected terms found in the answer.

    This is a lightweight correctness proxy, not a true correctness measure.
    A high score suggests the answer covers expected concepts; a low score
    may indicate missed content or different phrasing.
    """
    if not expected_terms:
        return 0.0
    answer_lower = answer.lower()
    found = sum(1 for term in expected_terms if term.lower() in answer_lower)
    return found / len(expected_terms)


def run_evaluation():
    """Run baseline vs RAG evaluation and print results."""
    settings = get_settings()

    if not settings.GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not configured. Cannot run evaluation.")
        print("Set GEMINI_API_KEY in backend/.env to run this evaluation.")
        sys.exit(1)

    llm = LLMService(settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
    dataset = load_dataset()

    print(f"\n{'=' * 70}")
    print("IntelliNotes Evaluation: Baseline vs RAG")
    print(f"{'=' * 70}")
    print(f"Model: {settings.GEMINI_MODEL}")
    print(f"Dataset: {len(dataset)} questions")
    print(f"{'=' * 70}\n")

    baseline_results = []
    rag_results = []

    for item in dataset:
        question = item["question"]
        expected_terms = item["expected_terms"]
        passage = item["relevant_passage"]
        source_doc = item["source_document"]

        print(f"\nQ: {question}")
        print(f"   Source: {source_doc}")

        # ── Baseline (no context) ──
        try:
            start = time.time()
            baseline_answer = llm.generate(
                f"Answer this academic question concisely:\n{question}",
                temperature=0.3,
                max_output_tokens=512,
            )
            baseline_latency = (time.time() - start) * 1000

            baseline_coverage = term_coverage(baseline_answer, expected_terms)
            baseline_results.append({
                "question_id": item["id"],
                "coverage": baseline_coverage,
                "latency_ms": baseline_latency,
                "has_answer": True,
            })
            print(f"   Baseline: coverage={baseline_coverage:.2f}, latency={baseline_latency:.0f}ms")
        except LLMServiceError as e:
            print(f"   Baseline: FAILED - {e}")
            baseline_results.append({
                "question_id": item["id"],
                "coverage": 0.0,
                "latency_ms": 0,
                "has_answer": False,
            })

        # ── RAG (with context) ──
        try:
            rag_prompt = (
                f"Answer the following question using ONLY the provided source passage.\n\n"
                f"Source ({source_doc}):\n{passage}\n\n"
                f"Question: {question}"
            )
            start = time.time()
            rag_answer = llm.generate(
                rag_prompt,
                system_instruction=(
                    "You are an academic study assistant. Answer using only the provided source. "
                    "If the source is insufficient, say so."
                ),
                temperature=0.3,
                max_output_tokens=512,
            )
            rag_latency = (time.time() - start) * 1000

            rag_coverage = term_coverage(rag_answer, expected_terms)
            # Check citation match (does the answer reference the source)
            citation_match = source_doc.lower() in rag_answer.lower() or "source" in rag_answer.lower()

            rag_results.append({
                "question_id": item["id"],
                "coverage": rag_coverage,
                "latency_ms": rag_latency,
                "citation_match": citation_match,
                "has_answer": True,
            })
            print(f"   RAG:      coverage={rag_coverage:.2f}, latency={rag_latency:.0f}ms, citation={citation_match}")
        except LLMServiceError as e:
            print(f"   RAG: FAILED - {e}")
            rag_results.append({
                "question_id": item["id"],
                "coverage": 0.0,
                "latency_ms": 0,
                "citation_match": False,
                "has_answer": False,
            })

    # ── Summary ──
    print(f"\n{'=' * 70}")
    print("RESULTS SUMMARY")
    print(f"{'=' * 70}")

    baseline_valid = [r for r in baseline_results if r["has_answer"]]
    rag_valid = [r for r in rag_results if r["has_answer"]]

    if baseline_valid:
        avg_baseline_coverage = sum(r["coverage"] for r in baseline_valid) / len(baseline_valid)
        avg_baseline_latency = sum(r["latency_ms"] for r in baseline_valid) / len(baseline_valid)
        print(f"\nBaseline (no context):")
        print(f"  Avg term coverage:   {avg_baseline_coverage:.3f}")
        print(f"  Avg latency:         {avg_baseline_latency:.0f}ms")
        print(f"  Successful answers:  {len(baseline_valid)}/{len(dataset)}")
    else:
        print("\nBaseline: No successful answers")

    if rag_valid:
        avg_rag_coverage = sum(r["coverage"] for r in rag_valid) / len(rag_valid)
        avg_rag_latency = sum(r["latency_ms"] for r in rag_valid) / len(rag_valid)
        citation_rate = sum(1 for r in rag_valid if r["citation_match"]) / len(rag_valid)
        unsupported_rate = sum(1 for r in rag_valid if r["coverage"] < 0.2) / len(rag_valid)

        print(f"\nRAG (with context):")
        print(f"  Avg term coverage:   {avg_rag_coverage:.3f}")
        print(f"  Avg latency:         {avg_rag_latency:.0f}ms")
        print(f"  Citation match rate: {citation_rate:.3f}")
        print(f"  Unsupported rate:    {unsupported_rate:.3f}")
        print(f"    (Fraction of answers with term coverage < 0.2)")
        print(f"  Successful answers:  {len(rag_valid)}/{len(dataset)}")
    else:
        print("\nRAG: No successful answers")

    print(f"\n{'=' * 70}")
    print("NOTE: Term coverage is a proxy metric, not a true correctness measure.")
    print("Human evaluation is needed for genuine accuracy assessment.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    run_evaluation()
