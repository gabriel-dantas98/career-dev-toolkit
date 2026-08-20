from __future__ import annotations

from collections.abc import Mapping, Sequence


def _normalize_pr_locator(locator: str) -> str:
    return locator.strip().rstrip("/").lower()


def _source_key(source_id: str) -> str:
    return f"source:{source_id.strip()}"


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


def _observation_keys(observation: Mapping[str, object]) -> list[str]:
    keys = _secondary_keys(observation)
    source_id = observation.get("source_id")
    if isinstance(source_id, str) and source_id.strip():
        keys.insert(0, _source_key(source_id))
    return keys


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, index: int) -> int:
        while self._parent[index] != index:
            self._parent[index] = self._parent[self._parent[index]]
            index = self._parent[index]
        return index

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self._parent[root_right] = root_left


def _merge_provenance(buckets: Sequence[Sequence[str] | None]) -> tuple[str, ...]:
    merged: list[str] = []
    for bucket in buckets:
        if bucket is None:
            continue
        for item in bucket:
            if item not in merged:
                merged.append(item)
    return tuple(merged)


def _canonical_index(observations: Sequence[Mapping[str, object]], members: Sequence[int]) -> int:
    def sort_key(index: int) -> tuple[int, str, int]:
        source_id = observations[index].get("source_id")
        if isinstance(source_id, str) and source_id.strip():
            return (0, source_id.strip(), index)
        return (1, "", index)

    return min(members, key=sort_key)


def deduplicate(observations: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    if not observations:
        return []

    union_find = _UnionFind(len(observations))
    key_owner: dict[str, int] = {}

    for index, observation in enumerate(observations):
        for key in _observation_keys(observation):
            if key in key_owner:
                union_find.union(index, key_owner[key])
            else:
                key_owner[key] = index

    grouped: dict[int, list[int]] = {}
    for index in range(len(observations)):
        root = union_find.find(index)
        grouped.setdefault(root, []).append(index)

    merged: list[dict[str, object]] = []
    for members in grouped.values():
        canonical = _canonical_index(observations, members)
        result = dict(observations[canonical])
        provenance_buckets: list[Sequence[str] | None] = []
        merged_source_ids: list[str] = []

        for index in members:
            observation = observations[index]
            provenance = observation.get("provenance")
            if isinstance(provenance, Sequence) and not isinstance(provenance, str):
                provenance_buckets.append(provenance)
            source_id = observation.get("source_id")
            if isinstance(source_id, str) and source_id.strip() and source_id not in merged_source_ids:
                merged_source_ids.append(source_id)

        result["provenance"] = _merge_provenance(provenance_buckets)
        result["merged_source_ids"] = tuple(merged_source_ids)
        merged.append(result)

    return merged
