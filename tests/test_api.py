"""Read-only API 테스트 — httpx TestClient."""

import pytest
from backend.api.app import create_app
from fastapi.testclient import TestClient

SCENARIO = "uhd60_recording_eis_on"


@pytest.fixture(scope="module")
def client(request: pytest.FixtureRequest) -> TestClient:
    # 테스트에서 LLM provider 체인 비활성화 — advisory는 결정론 경로만 사용
    import os

    original = os.environ.get("SOC_ADVISORY_PROVIDERS")
    os.environ["SOC_ADVISORY_PROVIDERS"] = ""
    request.addfinalizer(
        lambda: os.environ.update({"SOC_ADVISORY_PROVIDERS": original})
        if original is not None
        else os.environ.pop("SOC_ADVISORY_PROVIDERS", None)
    )
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


def test_advisory_post_and_get(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/scenarios/{SCENARIO}/advisory", json={"roles": ["pm", "management"]}
    )
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert len(run["advisories"]) == 2
    assert {a["role_id"] for a in run["advisories"]} == {"pm", "management"}
    assert all(a["provider"] == "deterministic" for a in run["advisories"])
    assert all(a["not_final_decision"] for a in run["advisories"])

    listed = client.get(f"/api/v1/scenarios/{SCENARIO}/advisory").json()
    assert listed and listed[0]["id"] == run["id"]

    assert client.post("/api/v1/scenarios/nope/advisory", json={}).status_code == 404


def test_no_write_endpoints(client: TestClient) -> None:
    """read-only 계약 — advisory 실행(연산)을 제외하면 GET만 존재해야 한다.

    advisory POST는 데이터 수정이 아니라 조언 생성 연산이며, 온톨로지 데이터의
    수정/삭제 엔드포인트는 어떤 경로에도 없어야 한다.
    """
    openapi = client.get("/openapi.json").json()
    for path, operations in openapi["paths"].items():
        allowed = {"get", "post"} if path.endswith("/advisory") else {"get"}
        assert set(operations.keys()) <= allowed, f"{path}에 허용 외 메서드 존재"
        assert not {"put", "patch", "delete"} & set(operations.keys()), path
