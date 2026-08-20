from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from careeros.outputs import TimelineContract, timeline_mapping


@dataclass(frozen=True)
class HeroMetric:
    label: str
    value: str
    kind: str
    evidence_links: tuple[str, ...]


@dataclass(frozen=True)
class PolicyFinding:
    rule_id: str
    metric_label: str
    message: str


@dataclass(frozen=True)
class TimelineParityResult:
    matches: bool
    differences: tuple[str, ...]


def validate_hero_metrics(
    metrics: Sequence[HeroMetric],
) -> tuple[PolicyFinding, ...]:
    findings: list[PolicyFinding] = []
    for metric in metrics:
        if not any(link.strip() for link in metric.evidence_links):
            findings.append(
                PolicyFinding(
                    rule_id="hero_metric.evidence.required",
                    metric_label=metric.label,
                    message="Hero metrics require at least one supporting evidence link.",
                )
            )
        if metric.kind.strip().lower() == "vanity":
            findings.append(
                PolicyFinding(
                    rule_id="hero_metric.vanity.disallowed",
                    metric_label=metric.label,
                    message="Vanity metrics are not eligible for the hero surface.",
                )
            )
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.metric_label,
                finding.rule_id,
                finding.message,
            ),
        )
    )


def timeline_parity(
    generated: TimelineContract | Mapping[str, Any],
    apps_script_preview: Mapping[str, Any],
) -> TimelineParityResult:
    expected = _json_shape(timeline_mapping(generated))
    actual = _json_shape(dict(apps_script_preview))
    differences: list[str] = []
    _compare_values(expected, actual, "", differences)
    unique_differences = tuple(sorted(set(differences)))
    return TimelineParityResult(
        matches=not unique_differences,
        differences=unique_differences,
    )


def _json_shape(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_shape(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_json_shape(item) for item in value]
    return value


def _compare_values(
    expected: Any,
    actual: Any,
    path: str,
    differences: list[str],
) -> None:
    if type(expected) is not type(actual):
        differences.append(path or "$")
        return
    if isinstance(expected, dict):
        keys = set(expected) | set(actual)
        for key in sorted(keys):
            child_path = f"{path}.{key}" if path else key
            if key not in expected or key not in actual:
                differences.append(child_path)
                continue
            _compare_values(expected[key], actual[key], child_path, differences)
        return
    if isinstance(expected, list):
        if len(expected) != len(actual):
            differences.append(f"{path}.length" if path else "$.length")
        for index, (expected_item, actual_item) in enumerate(
            zip(expected, actual, strict=False)
        ):
            child_path = f"{path}[{index}]" if path else f"$[{index}]"
            _compare_values(expected_item, actual_item, child_path, differences)
        return
    if expected != actual:
        differences.append(path or "$")
