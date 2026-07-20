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


def test_meta_labels(client: TestClient) -> None:
    body = client.get("/api/v1/meta/labels").json()
    assert body["project_u"] == "Project U"
    assert body["ip_isp"] == "ISP"
    assert body["pm"] == "PM Agent"
    assert "uhd60_recording_eis_on" in body


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


def test_risk_heatmap(client: TestClient) -> None:
    body = client.get("/api/v1/risk/heatmap").json()
    assert body["columns"]
    assert body["rows"]
    assert 3 <= len(body["focus"]) <= 5
    for row in body["rows"]:
        assert row["overall_grade_ko"] in ("높음", "중간", "낮음")
        assert row["overall_basis"], "근거 없는 등급은 API로 나가지 않는다"
    filtered = client.get("/api/v1/risk/heatmap", params={"project_id": "project_u"}).json()
    assert 0 < len(filtered["rows"]) <= len(body["rows"])
    assert filtered["columns"] == body["columns"], "열은 프로젝트 필터와 무관하게 고정"


def test_ask_presets_and_query(client: TestClient) -> None:
    presets = client.get("/api/v1/ask/presets").json()
    assert len(presets) == 5

    body = client.post(
        "/api/v1/ask", json={"question": "UHD60 recording에서 현재 가장 위험한 IP는 무엇인가?"}
    ).json()
    assert body["provider"] == "deterministic", "테스트 환경은 LLM 미가용 — 검색 요약으로 동작"
    assert body["cards"] and body["citations"]
    assert body["cards"][0]["ref_id"] == "uhd60_recording_eis_on"
    assert client.post("/api/v1/ask", json={"question": ""}).status_code == 422


def test_issues_and_rca(client: TestClient) -> None:
    issues = client.get("/api/v1/issues").json()
    assert len(issues) >= 36
    assert issues[0]["closed_without_verification"] is True, "경고 이슈가 선두"
    no_tests = client.get("/api/v1/issues", params={"verification": "no_tests"}).json()
    assert no_tests and all(i["verification"] == "no_tests" for i in no_tests)

    chain = client.get("/api/v1/issues/issue_isp_csid_bw_overrun_u/rca").json()
    assert [n["step"] for n in chain["nodes"]] == [
        "symptom", "impact", "root_cause", "action",
        "verification", "residual_risk", "lesson",
    ]
    assert chain["verification_ko"] == "검증됨"
    assert client.get("/api/v1/issues/nope/rca").status_code == 404


def test_change_impact(client: TestClient) -> None:
    body = client.get(
        "/api/v1/change-impact",
        params={"ip_id": "ip_isp", "knob_id": "knob_isp_pixel_mode"},
    ).json()
    assert body["subject"]["ip_id"] == "ip_isp"
    assert body["impacted_scenarios"] and body["impacted_kpis"]
    assert body["chained_ips"] and body["checklist"]
    assert body["export_text"].startswith("[변경 영향 분석]")
    assert client.get("/api/v1/change-impact", params={"ip_id": "없음"}).status_code == 404
    assert (
        client.get(
            "/api/v1/change-impact",
            params={"ip_id": "ip_isp", "knob_id": "knob_dpu_bts_fps"},
        ).status_code
        == 400
    )

    options = client.get("/api/v1/change-impact/options").json()
    assert len(options["ips"]) == 11


def test_weekly_review(client: TestClient) -> None:
    index = client.get("/api/v1/review/weekly").json()
    assert index["weeks"]
    week = index["weeks"][0]
    snapshot = client.get(f"/api/v1/review/weekly/{week}").json()
    assert snapshot["week"] == week


def test_evidence_list_and_filters(client: TestClient) -> None:
    all_entries = client.get("/api/v1/evidence").json()
    assert len(all_entries) == 54
    partial = client.get("/api/v1/evidence", params={"availability": "partial"}).json()
    assert partial and all(e["availability"] == "partial" for e in partial)
    by_project = client.get("/api/v1/evidence", params={"project_id": "project_u"}).json()
    assert by_project and all(e["project_id"] == "project_u" for e in by_project)


def test_portfolio_attention_scenario_links(client: TestClient) -> None:
    body = client.get("/api/v1/portfolio/overview").json()
    linked = [item for item in body["attention"] if item.get("scenario_ids")]
    assert linked, "시나리오 링크를 가진 주의 항목이 있어야 한다"


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
        is_operation = (
            path.endswith("/advisory")
            or path.endswith("/ask")
            or path.endswith("/what-if")  # P4 — ephemeral 가정 실험, 저장 없음
            or path.endswith("/what-if/sets")  # X2 — 운영 기록(append-only), 온톨로지 아님
            or "/ingest/" in path
        )
        allowed = {"get", "post"} if is_operation else {"get"}
        assert set(operations.keys()) <= allowed, f"{path}에 허용 외 메서드 존재"
        assert not {"put", "patch", "delete"} & set(operations.keys()), path


def test_ingest_mappings_endpoint(client) -> None:
    """반입 센터 계약 — 매핑 메타(열 순서 = 템플릿 헤더) 노출 (읽기 전용)."""
    mappings = client.get("/api/v1/ingest/mappings").json()
    names = {m["name"] for m in mappings}
    assert {"issues", "tests", "development_events", "evidence_catalog", "decisions"} <= names
    issues = next(m for m in mappings if m["name"] == "issues")
    assert issues["columns"][0] == "이슈 ID"
    assert "이슈 ID" in issues["required_columns"]
    assert issues["label_ko"] == "개발 이슈"


def test_decisions_endpoint_filters(client) -> None:
    decisions = client.get("/api/v1/decisions").json()
    assert isinstance(decisions, list) and decisions, "fixture 결정 1건 이상"
    filtered = client.get("/api/v1/decisions", params={"project_id": "없는_프로젝트"}).json()
    assert filtered == []


def test_decision_watermarks_endpoint(client) -> None:
    """W1 (설계 22) — 결정마다 워터마크 1건, 캡처 이전은 리플레이 진입점 없음."""
    decisions = client.get("/api/v1/decisions").json()
    marks = client.get("/api/v1/decisions/watermarks").json()
    assert {m["decision_id"] for m in marks} == {d["id"] for d in decisions}
    for mark in marks:
        assert mark["source"] in {"version_log", "ingested_at", "precapture"}
        if mark["source"] == "precapture":
            assert mark["recorded_at"] is None
            assert mark["note_ko"]
    filtered = client.get(
        "/api/v1/decisions/watermarks", params={"project_id": "없는_프로젝트"}
    ).json()
    assert filtered == []


def test_action_items_endpoint() -> None:
    """B3 — 결정별 액션 아이템 조회 (읽기 전용)."""
    from backend.api.app import create_app
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    all_items = client.get("/api/v1/action-items").json()
    assert len(all_items) >= 1
    filtered = client.get(
        "/api/v1/action-items", params={"decision_id": "dec_w_area_exploration_initial"}
    ).json()
    assert all(
        item["source_decision_id"] == "dec_w_area_exploration_initial" for item in filtered
    )
    assert filtered, "fixture 결정의 액션이 조회돼야 한다"


def test_list_pagination() -> None:
    """B5 — limit/offset 페이지네이션 (미지정 시 전량, 하위 호환)."""
    from backend.api.app import create_app
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    full = client.get("/api/v1/issues").json()
    assert len(full) > 3
    page = client.get("/api/v1/issues", params={"limit": 2, "offset": 1}).json()
    assert len(page) == 2
    assert page[0]["issue_id"] == full[1]["issue_id"]
    assert client.get("/api/v1/issues", params={"limit": 0}).status_code == 422


def test_api_token_auth(monkeypatch) -> None:
    """D1-1 — SOC_API_TOKEN 설정 시 /health 제외 전 API가 Bearer 토큰을 요구한다."""
    from backend.api.app import API_TOKEN_ENV, create_app
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    monkeypatch.setenv(API_TOKEN_ENV, "secret-token")
    # 무토큰/오토큰 → 401
    assert client.get("/api/v1/projects").status_code == 401
    assert (
        client.get(
            "/api/v1/projects", headers={"Authorization": "Bearer wrong"}
        ).status_code
        == 401
    )
    # /health는 모니터링용으로 무인증
    assert client.get("/api/v1/health").status_code == 200
    # 올바른 토큰 → 200
    assert (
        client.get(
            "/api/v1/projects", headers={"Authorization": "Bearer secret-token"}
        ).status_code
        == 200
    )
    # env 해제 → 개발 모드(무인증) 복귀
    monkeypatch.delenv(API_TOKEN_ENV)
    assert client.get("/api/v1/projects").status_code == 200


def test_access_log_json_lines(caplog) -> None:
    """D1-2 — 요청당 JSON 한 줄(경로/상태/소요), 토큰 값은 기록되지 않는다."""
    import json as jsonlib
    import logging

    from backend.api.app import create_app
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    with caplog.at_level(logging.INFO, logger="soc.access"):
        client.get("/api/v1/projects", headers={"Authorization": "Bearer whatever"})
    lines = [r.getMessage() for r in caplog.records if r.name == "soc.access"]
    assert lines, "access 로그 한 줄 이상"
    entry = jsonlib.loads(lines[-1])
    assert entry["kind"] == "access"
    assert entry["method"] == "GET"
    assert entry["path"] == "/api/v1/projects"
    assert entry["status"] == 200
    assert entry["auth"] is True
    assert isinstance(entry["duration_ms"], int)
    assert "whatever" not in lines[-1], "토큰 값 비기록"


def test_history_unknown_collection_404(client: TestClient) -> None:
    assert client.get("/api/v1/history/없는_컬렉션/x").status_code == 404


def test_history_empty_for_precapture_object(client: TestClient) -> None:
    """캡처 이전(synthetic) 객체는 빈 이력 200 — 오류가 아니다."""
    body = client.get("/api/v1/history/issues/이력없는_id").json()
    assert body["versions"] == []
    assert body["status_transitions"] == []


def test_history_roundtrip_via_ingest(client: TestClient) -> None:
    """반입 → 갱신 → 이력 조회 (시간 모델 T2)."""
    header = "이슈 ID,프로젝트 ID,제목,유형,상태,증상,확신도"

    def upload(status: str):
        csv = (
            f"{header}\napi_hist_issue,project_u,이력 이슈,underrun,{status},증상,medium\n"
        ).encode()
        return client.post(
            "/api/v1/ingest/file?mapping=issues",
            files={"file": ("issues.csv", csv, "text/csv")},
        )

    assert upload("open").status_code == 200
    assert upload("resolved").status_code == 200
    body = client.get("/api/v1/history/issues/api_hist_issue").json()
    assert [v["change_kind"] for v in body["versions"]] == ["created", "updated"]
    assert body["versions"][1]["changed_fields"] == ["status"]
    assert [(t["from_status"], t["to_status"]) for t in body["status_transitions"]] == [
        (None, "open"),
        ("open", "resolved"),
    ]

def test_as_of_heatmap_bad_timestamp_400(client: TestClient) -> None:
    assert client.get("/api/v1/as-of/risk/heatmap?ts=어제쯤").status_code == 400


def test_as_of_heatmap_roundtrip(client: TestClient) -> None:
    """P2 — as-of 지도는 현재 지도와 같은 계약, meta에 가정/근사가 명시된다."""
    # 미래 시점 재생 = 로그 전체 적용 = 현재 상태 — 지도가 정확히 일치해야 한다.
    response = client.get("/api/v1/as-of/risk/heatmap?ts=2100-01-01T00:00:00Z")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["as_of"].startswith("2100-01-01")
    assert body["meta"]["precapture_assumed_objects"] > 0  # fixture 우주 전체가 가정
    assert "가정" in body["meta"]["note_ko"]
    current = client.get("/api/v1/risk/heatmap").json()
    assert body["heatmap"] == current

def test_what_if_roundtrip(client: TestClient) -> None:
    """P4 — 가정 실험: 종결 이슈의 재발 가정이 등급 변화로 재계산된다."""
    response = client.post(
        "/api/v1/what-if",
        json={
            "assumptions": [
                {
                    "kind": "issue_status",
                    "target_id": "issue_isp_csid_bw_overrun_u",
                    "value": "open",
                }
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assumption = body["assumptions"][0]
    assert assumption["basis_type"] == "assumption"
    assert assumption["confidence"] == "medium"
    assert assumption["from_value"] == "closed"
    assert "저장되지 않는다" in body["note_ko"]
    # 재발 가정이므로 어떤 시나리오든 등급이 오르거나(변화 행) 전부 유지된다 — 구조 검증.
    assert isinstance(body["changed_rows"], list)
    assert isinstance(body["unchanged_scenario_count"], int)


def test_what_if_unknown_target_404_and_bad_value_400(client: TestClient) -> None:
    base = {"kind": "issue_status", "value": "open"}
    missing = client.post(
        "/api/v1/what-if", json={"assumptions": [{**base, "target_id": "없는_이슈"}]}
    )
    assert missing.status_code == 404
    bad = client.post(
        "/api/v1/what-if",
        json={
            "assumptions": [
                {
                    "kind": "issue_status",
                    "target_id": "issue_isp_csid_bw_overrun_u",
                    "value": "이상한값",
                }
            ]
        },
    )
    assert bad.status_code == 400


def test_what_if_candidates_endpoint(client: TestClient) -> None:
    """W1 (설계 18) — 가정 후보 제안: 결정론 도출, 후보는 그대로 실행 가능하다."""
    response = client.get("/api/v1/what-if/candidates")
    assert response.status_code == 200
    body = response.json()
    candidates = body["candidates"]
    assert candidates, "fixture 우주에는 후보 신호가 존재한다"
    rules = {c["rule"] for c in candidates}
    assert rules <= {
        "unverified_close",
        "open_high_resolve",
        "due_week_shift",
        "event_at_risk",
    }
    assert "제안" in body["note_ko"]
    # project 필터 — 필터 결과는 전체의 부분집합.
    filtered = client.get("/api/v1/what-if/candidates?project_id=project_u").json()
    assert {c["id"] for c in filtered["candidates"]} <= {c["id"] for c in candidates}
    assert all(c["project_id"] == "project_u" for c in filtered["candidates"])
    # 후보 좌표를 그대로 POST /what-if에 넣으면 400 없이 계산된다.
    first = candidates[0]
    roundtrip = client.post(
        "/api/v1/what-if",
        json={
            "assumptions": [
                {
                    "kind": first["kind"],
                    "target_id": first["target_id"],
                    "value": first["value"],
                    "week_delta": first["week_delta"],
                }
            ]
        },
    )
    assert roundtrip.status_code == 200


def test_what_if_sets_roundtrip(client: TestClient) -> None:
    """X2 (설계 19) — 가정 세트 저장→목록→단건 왕복. 온톨로지는 불변."""
    payload = {
        "name": "8K30 재발 시나리오",
        "note": "주간 리뷰 전 공유용",
        "project_id": "project_u",
        "assumptions": [
            {
                "kind": "issue_status",
                "target_id": "issue_isp_csid_bw_overrun_u",
                "value": "open",
            }
        ],
    }
    saved = client.post("/api/v1/what-if/sets", json=payload)
    assert saved.status_code == 200
    body = saved.json()
    assert body["id"].startswith("wset_")
    assert body["name"] == payload["name"]

    listed = client.get("/api/v1/what-if/sets?project_id=project_u").json()
    assert [s["id"] for s in listed][0] == body["id"]  # 최신순
    single = client.get(f"/api/v1/what-if/sets/{body['id']}")
    assert single.status_code == 200
    assert single.json()["assumptions"] == body["assumptions"]
    # 온톨로지 불변 — 저장은 운영 기록일 뿐, 이슈 상태는 그대로.
    issues = client.get("/api/v1/issues").json()
    target = next(i for i in issues if i["issue_id"] == "issue_isp_csid_bw_overrun_u")
    assert target["status"] == "closed"


def test_what_if_sets_reject_broken_assumptions(client: TestClient) -> None:
    """X2 — 깨진 가정 세트는 저장이 거부된다 (오류 계약은 POST /what-if와 동일)."""
    missing = client.post(
        "/api/v1/what-if/sets",
        json={
            "name": "깨진 세트",
            "assumptions": [
                {"kind": "issue_status", "target_id": "없는_이슈", "value": "open"}
            ],
        },
    )
    assert missing.status_code == 404
    bad_value = client.post(
        "/api/v1/what-if/sets",
        json={
            "name": "깨진 세트",
            "assumptions": [
                {
                    "kind": "issue_status",
                    "target_id": "issue_isp_csid_bw_overrun_u",
                    "value": "이상한값",
                }
            ],
        },
    )
    assert bad_value.status_code == 400
    unknown = client.get("/api/v1/what-if/sets/wset_없음")
    assert unknown.status_code == 404


def test_as_of_risk_diff_endpoint(client: TestClient) -> None:
    """Y2 (설계 20) — 같은 ts끼리는 변화 없음, 두 메타 동반, 잘못된 ts는 400."""
    same = client.get(
        "/api/v1/as-of/risk/diff?ts_a=2100-01-01T00:00:00Z&ts_b=2100-01-01T00:00:00Z"
    )
    assert same.status_code == 200
    body = same.json()
    assert body["changed_rows"] == []
    assert body["unchanged_scenario_count"] >= 1
    assert body["meta_a"]["as_of"] == body["meta_b"]["as_of"]
    bad = client.get("/api/v1/as-of/risk/diff?ts_a=이상한값&ts_b=2100-01-01T00:00:00Z")
    assert bad.status_code == 400


def test_history_carries_transition_findings(client: TestClient) -> None:
    """Y1 (설계 20) — history 응답에 프로세스 판정 필드가 병기된다 (빈 이력 포함)."""
    response = client.get("/api/v1/history/issues/issue_isp_csid_bw_overrun_u")
    assert response.status_code == 200
    body = response.json()
    assert "transition_findings" in body
    assert body["transition_findings"] == []  # 메모리 클라이언트 — 버전 이력 없음


def test_as_of_portfolio_and_change_impact(client: TestClient) -> None:
    """Q3 — as-of 확대 표면: 미래 ts 재생은 현재 뷰와 동일, 오류 계약 동일."""
    portfolio = client.get("/api/v1/as-of/portfolio/overview?ts=2100-01-01T00:00:00Z")
    assert portfolio.status_code == 200
    assert portfolio.json()["overview"] == client.get("/api/v1/portfolio/overview").json()
    assert client.get("/api/v1/as-of/portfolio/overview?ts=어제").status_code == 400

    impact = client.get(
        "/api/v1/as-of/change-impact",
        params={"ts": "2100-01-01T00:00:00Z", "ip_id": "ip_isp", "knob_id": "knob_isp_pixel_mode"},
    )
    assert impact.status_code == 200
    current = client.get(
        "/api/v1/change-impact",
        params={"ip_id": "ip_isp", "knob_id": "knob_isp_pixel_mode"},
    ).json()
    assert impact.json()["result"] == current
    assert (
        client.get(
            "/api/v1/as-of/change-impact",
            params={"ts": "2100-01-01T00:00:00Z", "ip_id": "없음"},
        ).status_code
        == 404
    )


# ---- R2/R4 (설계 21): 반입 열 스펙 + 행위자 기록 API 표면 ----


def test_ingest_mapping_column_specs(client: TestClient) -> None:
    """R2: 열 스펙 — 허용값(코드+라벨)·형식·참조 컬렉션이 화면 계약으로 노출된다."""
    mappings = client.get("/api/v1/ingest/mappings").json()
    issues = next(m for m in mappings if m["name"] == "issues")
    specs = {s["column"]: s for s in issues["column_specs"]}

    status = specs["상태"]
    assert status["required"] is True
    assert status["kind"] == "text"
    assert any(v.startswith("open (") for v in status["allowed_values"])

    scenarios = specs["영향 시나리오"]
    assert scenarios["kind"] == "list"
    assert scenarios["separator"] == ";"
    assert scenarios["ref_collection"] == "scenarios"

    week = specs["해결 주차"]
    assert week["kind"] == "int" and week["required"] is False


def test_ask_records_actor_header(client: TestClient) -> None:
    """R4: Ask 질의 로그에 행위자가 남는다 (percent-encoded 헤더 디코딩)."""
    response = client.post(
        "/api/v1/ask",
        json={"question": "UHD60 위험 IP"},
        headers={"X-SOC-Actor": "%EC%9E%A5%EA%B8%B8%EB%8F%99"},  # "장길동"
    )
    assert response.status_code == 200
    history = client.get("/api/v1/ask/history").json()
    assert history[0]["actor"] == "장길동"


def test_what_if_set_records_actor(client: TestClient) -> None:
    """R4: 가정 세트 created_by — 헤더 미설정 시 None."""
    issue = client.get("/api/v1/issues").json()[0]["issue_id"]
    saved = client.post(
        "/api/v1/what-if/sets",
        json={
            "name": "actor 테스트 세트",
            "assumptions": [
                {"kind": "issue_status", "target_id": issue, "value": "resolved"}
            ],
        },
        headers={"X-SOC-Actor": "%EC%9E%A5%EA%B8%B8%EB%8F%99"},
    )
    assert saved.status_code == 200
    assert saved.json()["created_by"] == "장길동"


def test_gate_console_endpoint(client: TestClient) -> None:
    """G1 (설계 26): 게이트 콘솔 — 과제별 판정 배너 데이터 + 신뢰도 줄."""
    body = client.get("/api/v1/gate-console").json()
    assert len(body["projects"]) == 3
    assert body["rule_note_ko"]
    gated = [p for p in body["projects"] if p["selected_milestone_id"]]
    assert gated, "fixture에 exit_criteria 게이트가 있어야 한다 (설계 23)"
    picked = gated[0]
    selected = next(
        r
        for r in picked["reviews"]
        if r["review"]["milestone_id"] == picked["selected_milestone_id"]
    )
    assert selected["verdict_line_ko"]
    # GO/NO-GO 어휘 금지 — 판정은 조언 (설계 23·26).
    assert "GO" not in selected["verdict_line_ko"].upper()
    trust = picked["trust"]
    assert trust["issue_total"] >= trust["issue_linked"] >= 0
    assert trust["note_ko"]
