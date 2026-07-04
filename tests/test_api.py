"""Read-only API 테스트 — httpx TestClient."""

import pytest
from backend.api.app import create_app
from fastapi.testclient import TestClient

SCENARIO = "uhd60_recording_eis_on"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_meta_counts(client: TestClient) -> None:
    body = client.get("/api/v1/meta").json()
    assert body["collections"]["projects"] == 3
    assert body["collections"]["development_events"] == 63


def test_glossary_endpoint(client: TestClient) -> None:
    body = client.get("/api/v1/meta/glossary").json()
    assert body["objects"]["Scenario"] == "시나리오"
    assert body["enums"]["Confidence"]["low"] == "낮음"


def test_projects(client: TestClient) -> None:
    assert len(client.get("/api/v1/projects").json()) == 3
    assert client.get("/api/v1/projects/project_u").json()["id"] == "project_u"
    assert client.get("/api/v1/projects/project_x").status_code == 404


def test_scenarios_filter(client: TestClient) -> None:
    all_scenarios = client.get("/api/v1/scenarios").json()
    filtered = client.get("/api/v1/scenarios", params={"project_id": "project_u"}).json()
    assert 0 < len(filtered) <= len(all_scenarios)


def test_scenario_analysis(client: TestClient) -> None:
    body = client.get(f"/api/v1/scenarios/{SCENARIO}/analysis").json()
    assert body["scenario"]["id"] == SCENARIO
    assert body["evidence_gaps"]
    assert body["timeline"]
    assert client.get("/api/v1/scenarios/nope/analysis").status_code == 404


def test_scenario_timeline(client: TestClient) -> None:
    body = client.get(f"/api/v1/scenarios/{SCENARIO}/timeline").json()
    assert body
    assert all("week" in item and "item_type_ko" in item for item in body)


def test_events_filter(client: TestClient) -> None:
    week_events = client.get("/api/v1/events", params={"week": 2}).json()
    assert all(e["week"] == 2 for e in week_events)
    single = client.get("/api/v1/events/project_u_package_out_checkpoint")
    assert single.status_code == 200


def test_traceability(client: TestClient) -> None:
    body = client.get(f"/api/v1/traceability/{SCENARIO}").json()
    assert body["label_ko"] == "시나리오"
    assert body["links"]
    assert client.get("/api/v1/traceability/없는id").status_code == 404


def test_portfolio_overview(client: TestClient) -> None:
    body = client.get("/api/v1/portfolio/overview").json()
    assert len(body["projects"]) == 3
    assert body["attention"]
    assert body["matrix"]


def test_weekly_review(client: TestClient) -> None:
    index = client.get("/api/v1/review/weekly").json()
    assert index["weeks"]
    week = index["weeks"][0]
    snapshot = client.get(f"/api/v1/review/weekly/{week}").json()
    assert snapshot["week"] == week


def test_no_write_endpoints(client: TestClient) -> None:
    """read-only 계약 — GET 외 메서드는 존재하지 않아야 한다."""
    openapi = client.get("/openapi.json").json()
    for path, operations in openapi["paths"].items():
        assert set(operations.keys()) <= {"get"}, f"{path}에 GET 외 메서드 존재"
