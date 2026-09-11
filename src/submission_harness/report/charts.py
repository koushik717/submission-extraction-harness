"""Static matplotlib charts for REPORT.md."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from submission_harness.routing.policy import RoutingPolicy
from submission_harness.stability.runner import StabilityReport
from submission_harness.verify.metrics import EvaluationReport


def chart_per_field_accuracy(evaluation: EvaluationReport, path: Path) -> None:
    fields = list(evaluation.per_field.keys())
    accs = [evaluation.per_field[f].accuracy for f in fields]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(range(len(fields)), accs, color="#2c5f7c")
    ax.set_xticks(range(len(fields)))
    ax.set_xticklabels(fields, rotation=45, ha="right", fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Accuracy")
    ax.set_title("Per-field accuracy")
    ax.axhline(evaluation.headline_aggregate, color="#c44", linestyle="--", label="headline aggregate")
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def chart_accuracy_by_tier(evaluation: EvaluationReport, path: Path) -> None:
    tiers = list(evaluation.by_tier.keys())
    accs = [evaluation.by_tier[t].aggregate_accuracy for t in tiers]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(tiers, accs, color="#4a7c59")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Aggregate accuracy")
    ax.set_title("Accuracy by difficulty tier")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def chart_flip_rates(stability: StabilityReport, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, (name, cond) in zip(axes, sorted(stability.by_condition.items())):
        fields = sorted(cond.flip_rates.keys())
        rates = [cond.flip_rates[f] for f in fields]
        ax.bar(range(len(fields)), rates, color="#8b5a2b")
        ax.set_xticks(range(len(fields)))
        ax.set_xticklabels(fields, rotation=45, ha="right", fontsize=7)
        ax.set_ylim(0, 1.05)
        ax.set_title(f"Flip rate — {name}")
        ax.set_ylabel("Flip rate")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def chart_routing(policy: RoutingPolicy, path: Path) -> None:
    counts = {"auto_post": 0, "review": 0, "always_human": 0}
    for f in policy.fields:
        counts[f.class_] = counts.get(f.class_, 0) + 1
    fig, ax = plt.subplots(figsize=(5, 4))
    labels = list(counts.keys())
    ax.bar(labels, [counts[k] for k in labels], color=["#2c5f7c", "#c9a227", "#a33"])
    ax.set_ylabel("# fields")
    ax.set_title("Routing class counts")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
