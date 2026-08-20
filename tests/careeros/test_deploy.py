import pytest

from careeros.deploy import DeploymentBlocked, DeployService, parse_web_app_url
from careeros.outputs import BRAG_DOCUMENT_GID


REAL_URL = "https://script.google.com/macros/s/AKfycbSynthetic_123/exec"


class FakeClasp:
    def __init__(self, *, healthy: bool, deploy_output: str = REAL_URL) -> None:
        self.healthy = healthy
        self.deploy_output = deploy_output
        self.calls: list[str] = []

    def health(self) -> bool:
        self.calls.append("health")
        return self.healthy

    def deploy(self) -> str:
        self.calls.append("deploy")
        return self.deploy_output


class RecordingRegistry:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def register(self, web_app_url: str) -> None:
        self.urls.append(web_app_url)


def test_deploy_refuses_before_external_mutation_when_clasp_health_fails() -> None:
    clasp = FakeClasp(healthy=False)
    registry = RecordingRegistry()

    with pytest.raises(DeploymentBlocked, match="health"):
        DeployService(clasp=clasp, registry=registry).deploy()

    assert clasp.calls == ["health"]
    assert registry.urls == []


def test_deploy_registers_exact_real_exec_url_and_homepage_uses_it() -> None:
    clasp = FakeClasp(
        healthy=True,
        deploy_output=f"Deployment complete\nWeb app: {REAL_URL}\n",
    )
    registry = RecordingRegistry()

    result = DeployService(clasp=clasp, registry=registry).deploy()

    assert clasp.calls == ["health", "deploy"]
    assert result.web_app_url == REAL_URL
    assert registry.urls == [REAL_URL]
    assert result.homepage["webAppUrl"] == REAL_URL
    assert result.homepage["source"] == {
        "kind": "brag-document",
        "gid": BRAG_DOCUMENT_GID,
    }


@pytest.mark.parametrize(
    "output",
    [
        "Deployed AKfycbSynthetic_123",
        "https://example.test/macros/s/AKfycbSynthetic_123/exec",
        "https://script.google.com/macros/s/AKfycbSynthetic_123/dev",
        "prefixhttps://script.google.com/macros/s/AKfycbSynthetic_123/execsuffix",
        "https://script.google.com/macros/s/AKfycbSynthetic_123/exec?user=synthetic",
    ],
)
def test_parse_web_app_url_rejects_non_real_or_derived_urls(output: str) -> None:
    with pytest.raises(DeploymentBlocked, match="/exec"):
        parse_web_app_url(output)


def test_parse_web_app_url_accepts_workspace_domain_exec_url() -> None:
    url = (
        "https://script.google.com/a/macros/example.test/s/"
        "AKfycbSynthetic_123/exec"
    )

    assert parse_web_app_url(f"web app {url}") == url
