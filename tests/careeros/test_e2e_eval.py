import importlib
import json
from pathlib import Path


EXPECTED_STAGES = {
    "harvest": "passed",
    "privacy": "passed",
    "validation": "passed",
    "encryptedStore": "passed",
    "safeWrite": "passed",
    "readBack": "passed",
    "outputs": "passed",
    "backgroundConsent": "passed",
}


def test_eval_proves_required_pipeline(tmp_path: Path) -> None:
    runner = importlib.import_module("evals.careeros.run")

    report = runner.run_eval(tmp_path)

    assert report["status"] == "passed"
    assert report["stages"] == EXPECTED_STAGES
    assert report["counts"] == {
        "sourceObservations": 3,
        "mergedRecords": 1,
        "persistedRecords": 1,
        "rejectedRecords": 1,
        "validationIssues": 1,
        "gatewayRequests": 3,
        "gatewayWrites": 1,
        "gatewayReadBacks": 1,
        "timelineCards": 1,
        "promotionWorkCards": 1,
    }
    assert report["ruleIds"] == {
        "harvest": [
            "harvest.overlap.merged",
            "harvest.persistence.succeeded",
        ],
        "privacy": ["privacy.blocked"],
        "validation": ["impact.evidence.missing"],
        "encryptedStore": [
            "store.sqlcipher.active",
            "store.plaintext.rejected",
            "store.reopen.succeeded",
        ],
        "safeWrite": ["sync.raw.required", "sync.synced"],
        "readBack": ["sync.read_back.exact"],
        "outputs": ["outputs.period.resolved"],
        "backgroundConsent": ["consent.background.required"],
    }

    serialized = json.dumps(report, sort_keys=True)
    assert "SYNTHETIC_SECRET_CANARY" not in serialized
    assert not {
        "body",
        "excerpt",
        "sourceBody",
        "sourceBodies",
    }.intersection(_all_keys(report))

    report_path = tmp_path / ".eval-results" / "careeros" / "report.json"
    assert json.loads(report_path.read_text(encoding="utf-8")) == report


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {
            *(str(key) for key in value),
            *(
                nested
                for item in value.values()
                for nested in _all_keys(item)
            ),
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _all_keys(item)}
    return set()
