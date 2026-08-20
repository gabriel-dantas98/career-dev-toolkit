from careeros.dedup import deduplicate
from careeros.models import DeliveryRecord, EvidenceRef, RecordMetadata, ValidationIssue
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


def test_impact_satisfied_by_external_evidence_mapping() -> None:
    record = synthetic_delivery(
        title="[Impact] Claim with mapped proof",
        tags=("impact",),
        result="Improved latency by 40%",
        evidence=(),
    )
    evidence_map = {
        "rec-synthetic-001": (
            EvidenceRef(
                locator="https://github.test/org/repo/pull/9",
                excerpt="Synthetic mapped excerpt",
                observed_at="2026-01-15T00:00:00Z",
            ),
        ),
    }
    issues = validate_records([record], evidence_map)
    assert "impact.evidence.missing" not in {issue.rule_id for issue in issues}


def test_impact_evidence_inconsistent_with_mapping() -> None:
    record = synthetic_delivery(
        evidence=(
            EvidenceRef(
                locator="https://github.test/org/repo/pull/a",
                excerpt="Synthetic PR excerpt",
                observed_at="2026-01-15T00:00:00Z",
            ),
        ),
    )
    evidence_map = {
        "rec-synthetic-001": (
            EvidenceRef(
                locator="https://github.test/org/repo/pull/b",
                excerpt="Synthetic mapped excerpt",
                observed_at="2026-01-15T00:00:00Z",
            ),
        ),
    }
    issues = validate_records([record], evidence_map)
    assert any(issue.rule_id == "impact.evidence.inconsistent" for issue in issues)


def test_validate_typed_delivery_record_preserves_metadata() -> None:
    record = DeliveryRecord(
        id="rec-typed-001",
        schema_version=1,
        source_connector="thread",
        source_locator="thread:typed-001",
        title="[Impact] Typed delivery",
        period="Q1 2026",
        tags=("impact",),
        context=None,
        confidence="complete",
        situation="Synthetic situation",
        task="Synthetic task",
        action="Synthetic action",
        result="Synthetic result",
        evidence=(
            EvidenceRef(
                locator="https://github.test/org/repo/pull/1",
                excerpt="Synthetic PR excerpt",
                observed_at="2026-01-15T00:00:00Z",
            ),
        ),
        evidence_gaps=(),
        content_fingerprint="fp-typed-001",
        observed_at="2026-01-15T00:00:00Z",
        metadata=RecordMetadata(
            jira_key="SYN-200",
            pr_status="merged",
            narrative_status="open",
        ),
    )
    issues = validate_records([record], {})
    assert any(issue.rule_id == "github.pr.narrative_mismatch" for issue in issues)


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
    assert set(merged[0]["merged_source_ids"]) == {"github:pull/1", "thread:msg-9"}


def test_deduplicate_transitive_chain() -> None:
    observations = [
        {
            "id": "obs-a",
            "source_id": "github:pull/1",
            "jira_key": "SYN-CHAIN",
            "provenance": ("github",),
        },
        {
            "id": "obs-b",
            "jira_key": "SYN-CHAIN",
            "pr_locator": "https://github.test/org/repo/pull/9",
            "provenance": ("jira",),
        },
        {
            "id": "obs-c",
            "source_id": "thread:msg-3",
            "pr_locator": "https://github.test/org/repo/pull/9",
            "provenance": ("thread",),
        },
    ]
    merged = deduplicate(observations)
    assert len(merged) == 1
    assert set(merged[0]["provenance"]) == {"github", "jira", "thread"}


def test_deduplicate_order_independent() -> None:
    pr_locator = "https://github.test/org/repo/pull/77"
    obs_a = {"id": "obs-1", "jira_key": "SYN-ORDER", "provenance": ("a",)}
    obs_b = {
        "id": "obs-2",
        "jira_key": "SYN-ORDER",
        "pr_locator": pr_locator,
        "provenance": ("b",),
    }
    obs_c = {"id": "obs-3", "pr_locator": pr_locator, "provenance": ("c",)}

    forward_result = deduplicate([obs_a, obs_b, obs_c])
    reverse_result = deduplicate([obs_c, obs_b, obs_a])
    assert len(forward_result) == 1
    assert len(reverse_result) == 1
    assert set(forward_result[0]["provenance"]) == {"a", "b", "c"}
    assert set(reverse_result[0]["provenance"]) == {"a", "b", "c"}


def test_deduplicate_source_id_priority() -> None:
    observations = [
        {
            "id": "obs-secondary",
            "jira_key": "SYN-PRIORITY",
            "provenance": ("jira",),
        },
        {
            "id": "obs-primary",
            "source_id": "github:pull/99",
            "jira_key": "SYN-PRIORITY",
            "provenance": ("github",),
        },
    ]
    merged = deduplicate(observations)
    assert len(merged) == 1
    assert merged[0]["source_id"] == "github:pull/99"


def test_deduplicate_evidence_only_key() -> None:
    observations = [
        {
            "id": "obs-1",
            "source_id": "thread:msg-1",
            "evidence_locator": "https://docs.test/evidence/shared",
            "provenance": ("thread",),
        },
        {
            "id": "obs-2",
            "source_id": "github:issue/5",
            "evidence_locator": "https://docs.test/evidence/shared",
            "provenance": ("github",),
        },
    ]
    merged = deduplicate(observations)
    assert len(merged) == 1
    assert set(merged[0]["merged_source_ids"]) == {"thread:msg-1", "github:issue/5"}


def test_deduplicate_normalized_pr_url() -> None:
    observations = [
        {
            "id": "obs-1",
            "source_id": "github:pull/1",
            "pr_locator": "https://github.test/org/repo/pull/1/",
            "provenance": ("github",),
        },
        {
            "id": "obs-2",
            "source_id": "thread:msg-2",
            "pr_locator": "https://github.test/org/repo/pull/1",
            "provenance": ("thread",),
        },
    ]
    merged = deduplicate(observations)
    assert len(merged) == 1
    assert set(merged[0]["provenance"]) == {"github", "thread"}


def test_validation_issue_has_rule_id_not_bool() -> None:
    issues = validate_records([synthetic_kudos(name="", month=None)], {})
    assert issues
    assert all(isinstance(issue, ValidationIssue) for issue in issues)
    assert all(isinstance(issue.rule_id, str) and issue.rule_id for issue in issues)
