from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence


def _normalize_pr_locator(locator: str) -> str:
    return locator.strip().rstrip("/").lower()


def _secondary_keys(observation: Mapping[str, object]) -> list[str]:
    keys: list[str] = []
    jira_key = observation.get("jira_key")
    if isinstance(jira_key, str) and jira_key.strip():
        keys.append(f"jira:{jira_key.strip().upper()}")

    pr_locator = observation.get("pr_locator")
    if isinstance(pr_locator, str) and pr_locator.strip():
        keys.append(f"pr:{_normalize_pr_locator(pr_locator)}")

    evidence_locator = observation.get("evidence_locator")
    if isinstance(evidence_locator, str) and evidence_locator.strip():
        keys.append(f"evidence:{evidence_locator.strip().lower()}")

    return keys


def _merge_provenance(
    left: Sequence[str] | None,
    right: Sequence[str] | None,
) -> tuple[str, ...]:
    merged: list[str] = []
    for bucket in (left, right):
        if bucket is None:
            continue
        for item in bucket:
            if item not in merged:
                merged.append(item)
    return tuple(merged)


def _merge_source_ids(
    left: Sequence[str] | None,
    right: str | None,
) -> tuple[str, ...]:
    merged = list(left or ())
    if isinstance(right, str) and right and right not in merged:
        merged.append(right)
    return tuple(merged)


def deduplicate(observations: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, MutableMapping[str, object]] = {}
    source_index: dict[str, str] = {}
    secondary_index: dict[str, str] = {}

    for observation in observations:
        source_id = observation.get("source_id")
        group_key: str | None = None

        if isinstance(source_id, str) and source_id.strip() and source_id in source_index:
            group_key = source_index[source_id]
        else:
            for secondary_key in _secondary_keys(observation):
                if secondary_key in secondary_index:
                    group_key = secondary_index[secondary_key]
                    break

        if group_key is None:
            observation_id = str(observation.get("id", len(grouped)))
            group_key = f"group:{observation_id}"

        if group_key not in grouped:
            grouped[group_key] = dict(observation)
            provenance = observation.get("provenance")
            if isinstance(provenance, Sequence) and not isinstance(provenance, str):
                grouped[group_key]["provenance"] = tuple(provenance)
            else:
                grouped[group_key]["provenance"] = ()
            grouped[group_key]["merged_source_ids"] = _merge_source_ids(
                (),
                source_id if isinstance(source_id, str) else None,
            )
        else:
            current = grouped[group_key]
            current["provenance"] = _merge_provenance(
                current.get("provenance"),
                observation.get("provenance"),
            )
            current["merged_source_ids"] = _merge_source_ids(
                current.get("merged_source_ids"),
                source_id if isinstance(source_id, str) else None,
            )

        if isinstance(source_id, str) and source_id.strip():
            source_index[source_id] = group_key
            current_ids = grouped[group_key].get("merged_source_ids", ())
            if isinstance(current_ids, Sequence) and source_id not in current_ids:
                grouped[group_key]["merged_source_ids"] = _merge_source_ids(current_ids, source_id)

        for secondary_key in _secondary_keys(observation):
            secondary_index[secondary_key] = group_key

    return [dict(item) for item in grouped.values()]
