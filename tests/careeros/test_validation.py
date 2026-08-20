from careeros.dedup import deduplicate
from careeros.models import EvidenceRef, ValidationIssue
from careeros.validation import validate_records


def synthetic_kudos(*, name: str = "Alex", month: str | None = "2026-03") -> dict[str, object]:
    return {
        "record_type": "kudos",
        "id": "kudos-synthetic-001",
        "name": name,
        "month": month,
    }


def synthetic_delivery(
    *,
    record_id: str = "rec-synthetic-001",
    title: str = "[Impact] Synthetic delivery",
    tags: tuple[str, ...] = ("impact",),
    jira_key: str | None = None,
    pr_status: str | None = None,
    narrative_status: str | None = None,
    result: str = "Synthetic result with evidence",
    evidence: tuple[EvidenceRef, ...] | None = None,
    confidence: str = "complete",
    epic_parent: str | None = None,
) -> dict[str, object]:
    if evidence is None:
        evidence = (
            EvidenceRef(
                locator="https://github.test/org/repo/pull/1",
                excerpt="Synthetic PR excerpt",
                observed_at="2026-01-15T00:00:00Z",
            ),
        )
    record: dict[str, object] = {
        "record_type": "delivery",
        "id": record_id,
        "title": title,
        "tags": tags,
        "confidence": confidence,
        "result": result,
        "evidence": evidence,
    }
    if jira_key is not None:
        record["jira_key"] = jira_key
    if pr_status is not None:
        record["pr_status"] = pr_status
    if narrative_status is not None:
        record["narrative_status"] = narrative_status
    if epic_parent is not None:
        record["epic_parent"] = epic_parent
    return record


def test_kudos_requires_name_and_month() -> None:
    issues = validate_records([synthetic_kudos(name="", month=None)], {})
    assert {issue.rule_id for issue in issues} == {
        "kudos.name.required",
        "kudos.month.required",
    }


def test_title_tags_mismatch() -> None:
    record = synthetic_delivery(title="[Impact] Mismatched title", tags=("community",))
    issues = validate_records([record], {})
    assert any(issue.rule_id == "title.tags.mismatch" for issue in issues)


def test_jira_uniqueness() -> None:
    records = [
        synthetic_delivery(record_id="rec-a", jira_key="SYN-100"),
        synthetic_delivery(record_id="rec-b", jira_key="SYN-100"),
    ]
    issues = validate_records(records, {})
    assert any(issue.rule_id == "jira.duplicate" for issue in issues)


def test_github_pr_narrative_mismatch() -> None:
    record = synthetic_delivery(pr_status="merged", narrative_status="open")
    issues = validate_records([record], {})
    assert any(issue.rule_id == "github.pr.narrative_mismatch" for issue in issues)


def test_impact_without_evidence_links() -> None:
    record = synthetic_delivery(
        title="[Impact] Claim without proof",
        tags=("impact",),
        result="Improved latency by 40%",
        evidence=(),
    )
    issues = validate_records([record], {})
    assert {issue.rule_id for issue in issues} >= {
        "impact.evidence.missing",
        "taxonomy.confidence.exceeds_cap",
    }


def test_epic_tree_duplicates() -> None:
    records = [
        synthetic_delivery(record_id="rec-parent", epic_parent="SYN-EPIC-1"),
        synthetic_delivery(record_id="rec-child", epic_parent="SYN-EPIC-1"),
    ]
    issues = validate_records(records, {})
    assert any(issue.rule_id == "epic.duplicate" for issue in issues)


def test_taxonomy_prefix_required() -> None:
    record = synthetic_delivery(title="Missing prefix", tags=("impact",))
    issues = validate_records([record], {})
    assert any(issue.rule_id == "taxonomy.prefix.required" for issue in issues)


def test_taxonomy_confidence_exceeds_cap() -> None:
    record = synthetic_delivery(confidence="complete", evidence=())
    issues = validate_records([record], {})
    assert any(issue.rule_id == "taxonomy.confidence.exceeds_cap" for issue in issues)


def test_deduplicate_preserves_provenance() -> None:
    observations = [
        {
            "id": "obs-1",
            "source_id": "github:pull/1",
            "jira_key": "SYN-42",
            "pr_locator": "https://github.test/org/repo/pull/1",
            "provenance": ("github",),
        },
        {
            "id": "obs-2",
            "source_id": "thread:msg-9",
            "jira_key": "SYN-42",
            "pr_locator": "https://github.test/org/repo/pull/1",
            "provenance": ("thread",),
        },
    ]
    merged = deduplicate(observations)
    assert len(merged) == 1
    assert set(merged[0]["provenance"]) == {"github", "thread"}
    assert {merged[0]["source_id"], *merged[0].get("merged_source_ids", ())} >= {
        "github:pull/1",
        "thread:msg-9",
    }


def test_validation_issue_has_rule_id_not_bool() -> None:
    issues = validate_records([synthetic_kudos(name="", month=None)], {})
    assert issues
    assert all(isinstance(issue, ValidationIssue) for issue in issues)
    assert all(isinstance(issue.rule_id, str) and issue.rule_id for issue in issues)
