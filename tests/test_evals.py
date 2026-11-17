"""Regression guard: the evaluation metrics must stay above sane thresholds.

Thresholds sit deliberately below observed values so this catches regressions
without being flaky. Run the full report with `make eval`.
"""

from __future__ import annotations

from evals.run_eval import evaluate


def test_eval_metrics_above_thresholds() -> None:
    m = evaluate(k=3)
    assert m["dataset_size"] >= 15
    assert m["intent_accuracy"] >= 0.80
    assert m["retrieval_precision_at_1"] >= 0.80
    assert m["retrieval_recall_at_k"] >= 0.95
    assert m["retrieval_mrr"] >= 0.85
    assert m["sql_success_rate"] >= 0.95
    assert m["grounding_pass_rate"] >= 0.85
