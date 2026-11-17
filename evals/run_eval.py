"""Run the NexusOps evaluation harness and report retrieval + agent metrics.

Fully offline and deterministic: no API key, no network. Metrics:
  - intent accuracy          (router vs. gold label)
  - retrieval Precision@1    (top hit is a gold-relevant doc)
  - retrieval Recall@k       (all gold docs found in top-k)
  - retrieval MRR            (reciprocal rank of the first gold doc)
  - SQL success rate         (needs_sql queries that return >= 1 row)
  - grounding pass rate      (guardrail PASSED)
  - mean / p95 latency (ms)

Usage:
    python -m evals.run_eval [--k 3] [--update-readme]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nexus.agents.supervisor import supervisor_agent  # noqa: E402
from nexus.rag.hybrid_search import hybrid_retriever  # noqa: E402

GOLD_PATH = Path(__file__).with_name("gold.json")
RESULTS_PATH = Path(__file__).with_name("results.json")
README_PATH = Path(__file__).resolve().parent.parent / "README.md"
BENCH_START = "<!-- benchmarks:start -->"
BENCH_END = "<!-- benchmarks:end -->"


def load_gold() -> list[dict[str, Any]]:
    with open(GOLD_PATH, encoding="utf-8") as f:
        return json.load(f)


def evaluate(k: int = 3) -> dict[str, Any]:
    gold = load_gold()

    intent_hits = 0
    precision_at_1: list[float] = []
    recall_at_k: list[float] = []
    reciprocal_ranks: list[float] = []
    sql_hits = 0
    sql_total = 0
    grounded_hits = 0
    latencies: list[float] = []

    for case in gold:
        query = case["query"]
        relevant = set(case["relevant_docs"])

        # Retrieval metrics (only for queries that cite policy docs).
        if relevant:
            ranked = [c.document_id for c in hybrid_retriever.retrieve(query, top_k=k)]
            precision_at_1.append(1.0 if ranked[:1] and ranked[0] in relevant else 0.0)
            recall_at_k.append(len(relevant & set(ranked)) / len(relevant))
            rr = 0.0
            for rank, doc_id in enumerate(ranked, start=1):
                if doc_id in relevant:
                    rr = 1.0 / rank
                    break
            reciprocal_ranks.append(rr)

        # Full-pipeline metrics.
        state = supervisor_agent.process(query)
        if state.intent == case["intent"]:
            intent_hits += 1
        if case["needs_sql"]:
            sql_total += 1
            if state.sql_results:
                sql_hits += 1
        if state.guardrail_status == "PASSED":
            grounded_hits += 1
        latencies.append(state.total_latency_ms)

    total = len(gold)
    return {
        "dataset_size": total,
        "k": k,
        "intent_accuracy": round(intent_hits / total, 3),
        "retrieval_precision_at_1": round(float(np.mean(precision_at_1)), 3),
        "retrieval_recall_at_k": round(float(np.mean(recall_at_k)), 3),
        "retrieval_mrr": round(float(np.mean(reciprocal_ranks)), 3),
        "sql_success_rate": round(sql_hits / sql_total, 3) if sql_total else 1.0,
        "grounding_pass_rate": round(grounded_hits / total, 3),
        "mean_latency_ms": round(float(np.mean(latencies)), 2),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
    }


def render_table(m: dict[str, Any]) -> str:
    rows = [
        ("Dataset size", f"{m['dataset_size']} queries"),
        ("Intent routing accuracy", f"{m['intent_accuracy']:.0%}"),
        ("Retrieval Precision@1", f"{m['retrieval_precision_at_1']:.0%}"),
        (f"Retrieval Recall@{m['k']}", f"{m['retrieval_recall_at_k']:.0%}"),
        ("Retrieval MRR", f"{m['retrieval_mrr']:.3f}"),
        ("SQL success rate", f"{m['sql_success_rate']:.0%}"),
        ("Grounding pass rate", f"{m['grounding_pass_rate']:.0%}"),
        ("Mean latency", f"{m['mean_latency_ms']} ms"),
        ("p95 latency", f"{m['p95_latency_ms']} ms"),
    ]
    lines = ["| Metric | Value |", "|---|---|"]
    lines += [f"| {name} | {value} |" for name, value in rows]
    return "\n".join(lines)


def update_readme(table: str) -> bool:
    if not README_PATH.exists():
        return False
    text = README_PATH.read_text(encoding="utf-8")
    if BENCH_START not in text or BENCH_END not in text:
        return False
    head, rest = text.split(BENCH_START, 1)
    _, tail = rest.split(BENCH_END, 1)
    new = f"{head}{BENCH_START}\n\n{table}\n\n_Reproduce: `make eval`. Fully offline, no API key._\n\n{BENCH_END}{tail}"
    README_PATH.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="NexusOps evaluation harness")
    parser.add_argument("--k", type=int, default=3, help="retrieval cutoff (default 3)")
    parser.add_argument(
        "--update-readme", action="store_true", help="write the README benchmarks block"
    )
    args = parser.parse_args()

    metrics = evaluate(k=args.k)
    table = render_table(metrics)

    print("\nNexusOps evaluation (offline, deterministic)\n")
    print(table)
    RESULTS_PATH.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {RESULTS_PATH}")

    if args.update_readme and update_readme(table):
        print(f"Updated benchmarks block in {README_PATH}")


if __name__ == "__main__":
    main()
