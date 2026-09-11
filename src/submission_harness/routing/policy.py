"""Routing policy from per-field accuracy + flip rate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from submission_harness.stability.runner import StabilityReport
from submission_harness.verify.metrics import EvaluationReport


@dataclass
class FieldRouting:
    field: str
    accuracy: float
    flip_rate: float
    flip_rate_temp_0: float
    flip_rate_temp_default: float
    class_: str  # auto_post | review | always_human


@dataclass
class RoutingPolicy:
    fields: list[FieldRouting]
    thresholds: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {
            "thresholds": self.thresholds,
            "fields": [
                {
                    "field": f.field,
                    "accuracy": f.accuracy,
                    "flip_rate": f.flip_rate,
                    "flip_rate_temp_0": f.flip_rate_temp_0,
                    "flip_rate_temp_default": f.flip_rate_temp_default,
                    "class": f.class_,
                }
                for f in self.fields
            ],
        }


def classify_field(
    *,
    accuracy: float,
    flip_rate: float,
    thresholds: dict[str, Any],
) -> str:
    ap = thresholds["auto_post"]
    ah = thresholds["always_human"]
    if accuracy >= ap["min_accuracy"] and flip_rate <= ap["max_flip_rate"]:
        return "auto_post"
    if accuracy < ah["max_accuracy"] and flip_rate > ah["min_flip_rate"]:
        return "always_human"
    return "review"


def build_routing_policy(
    evaluation: EvaluationReport,
    stability: StabilityReport,
    *,
    thresholds_path: Path = Path("configs/routing_thresholds.yaml"),
) -> RoutingPolicy:
    with thresholds_path.open(encoding="utf-8") as fh:
        thresholds = yaml.safe_load(fh)

    temp0 = stability.by_condition.get("temp_0")
    tempd = stability.by_condition.get("temp_default")
    fields: list[FieldRouting] = []

    for name, fa in sorted(evaluation.per_field.items()):
        fr0 = temp0.flip_rates.get(name, 0.0) if temp0 else 0.0
        frd = tempd.flip_rates.get(name, 0.0) if tempd else 0.0
        if thresholds.get("flip_rate_source") == "max_of_conditions":
            fr = max(fr0, frd)
        else:
            fr = fr0
        cls = classify_field(accuracy=fa.accuracy, flip_rate=fr, thresholds=thresholds)
        fields.append(
            FieldRouting(
                field=name,
                accuracy=fa.accuracy,
                flip_rate=fr,
                flip_rate_temp_0=fr0,
                flip_rate_temp_default=frd,
                class_=cls,
            )
        )

    return RoutingPolicy(fields=fields, thresholds=thresholds)


def write_routing_policy(policy: RoutingPolicy, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy.to_json(), indent=2) + "\n", encoding="utf-8")


def format_routing_table(policy: RoutingPolicy) -> str:
    lines = [
        "| Field | Accuracy | Flip (temp_0) | Flip (temp_default) | Flip used | Class |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for f in policy.fields:
        lines.append(
            f"| {f.field} | {f.accuracy:.3f} | {f.flip_rate_temp_0:.3f} | "
            f"{f.flip_rate_temp_default:.3f} | {f.flip_rate:.3f} | {f.class_} |"
        )
    return "\n".join(lines) + "\n"
