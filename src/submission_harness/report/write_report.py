"""Assemble REPORT.md from evaluation + stability + routing."""

from __future__ import annotations

from pathlib import Path

from submission_harness.report.charts import (
    chart_accuracy_by_tier,
    chart_flip_rates,
    chart_per_field_accuracy,
    chart_routing,
)
from submission_harness.routing.policy import RoutingPolicy, format_routing_table
from submission_harness.stability.runner import StabilityReport
from submission_harness.verify.metrics import EvaluationReport


def write_report(
    *,
    evaluation: EvaluationReport,
    stability: StabilityReport,
    policy: RoutingPolicy,
    output_dir: Path,
    report_path: Path,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    charts = output_dir / "charts"
    charts.mkdir(exist_ok=True)

    chart_per_field_accuracy(evaluation, charts / "per_field_accuracy.png")
    chart_accuracy_by_tier(evaluation, charts / "accuracy_by_tier.png")
    chart_flip_rates(stability, charts / "flip_rates.png")
    chart_routing(policy, charts / "routing.png")

    # Relative paths from REPORT.md location
    rel = Path("runs/report/charts")

    lines: list[str] = []
    lines.append("# Submission Extraction Reliability Report")
    lines.append("")
    lines.append(
        "**Synthetic documents only.** No real insurance data or PII was used."
    )
    lines.append("")
    lines.append("## Headline aggregate (hides variation)")
    lines.append("")
    lines.append(
        f"- Headline aggregate accuracy: **{evaluation.headline_aggregate:.3f}** "
        f"across {evaluation.n_docs} documents"
    )
    lines.append(
        f"- Per-field accuracy range: **{evaluation.per_field_min:.3f}** … "
        f"**{evaluation.per_field_max:.3f}**"
    )
    lines.append(f"- Provider: `{stability.provider}`")
    lines.append(f"- Total spend: **${stability.spend_usd:.4f}**")
    lines.append("")
    lines.append("## Per-field accuracy")
    lines.append("")
    lines.append("| Field | Accuracy | Correct / Total |")
    lines.append("|---|---:|---:|")
    for name, fa in evaluation.per_field.items():
        lines.append(f"| {name} | {fa.accuracy:.3f} | {fa.correct}/{fa.total} |")
    lines.append("")
    lines.append(f"![Per-field accuracy]({rel}/per_field_accuracy.png)")
    lines.append("")
    lines.append("## Accuracy by difficulty tier")
    lines.append("")
    lines.append("| Tier | Aggregate accuracy | N |")
    lines.append("|---|---:|---:|")
    for tier, ta in evaluation.by_tier.items():
        lines.append(
            f"| {tier} | {ta.aggregate_accuracy:.3f} | {ta.n_docs} |"
        )
    lines.append("")
    lines.append(f"![Accuracy by tier]({rel}/accuracy_by_tier.png)")
    lines.append("")
    lines.append("## Stability (flip rates) — conditions reported separately")
    lines.append("")
    for name, cond in stability.by_condition.items():
        lines.append(f"### {name}")
        lines.append("")
        lines.append(
            f"Single-run mean accuracy: {cond.mean_single_accuracy:.3f}; "
            f"majority-vote accuracy: {cond.mean_majority_accuracy:.3f} "
            f"(N docs={cond.n_docs})"
        )
        lines.append("")
        lines.append("| Field | Flip rate |")
        lines.append("|---|---:|")
        for fname, rate in sorted(cond.flip_rates.items()):
            lines.append(f"| {fname} | {rate:.3f} |")
        lines.append("")
    lines.append(f"![Flip rates]({rel}/flip_rates.png)")
    lines.append("")
    lines.append("## Majority-vote comparison")
    lines.append("")
    lines.append("| Condition | Single-run accuracy | Majority-vote accuracy | Delta |")
    lines.append("|---|---:|---:|---:|")
    for name, cond in stability.by_condition.items():
        delta = cond.mean_majority_accuracy - cond.mean_single_accuracy
        lines.append(
            f"| {name} | {cond.mean_single_accuracy:.3f} | "
            f"{cond.mean_majority_accuracy:.3f} | {delta:+.3f} |"
        )
    lines.append("")
    lines.append("## Routing policy")
    lines.append("")
    lines.append(format_routing_table(policy))
    lines.append("")
    lines.append(f"![Routing]({rel}/routing.png)")
    lines.append("")
    lines.append("Full machine-readable policy: `runs/report/routing_policy.json`")
    lines.append("")

    report_path = Path(report_path)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
