"""반입 파이프라인 테스트 — 파싱/매핑/검증/저장/rollback."""

from pathlib import Path

import pytest
from backend.ingest.service import IngestError, IngestService, MemoryIngestWriter
from backend.ingest.tabular import TabularParseError, parse_csv, parse_tabular
from backend.loaders.repository import InMemoryRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
SAMPLE = ROOT / "samples" / "sample_milestones.csv"
SAMPLE_ISSUES = ROOT / "samples" / "sample_issues.csv"
SAMPLE_TESTS = ROOT / "samples" / "sample_tests.csv"
SAMPLE_EVENTS = ROOT / "samples" / "sample_events.csv"
SAMPLE_EVIDENCE = ROOT / "samples" / "sample_evidence_catalog.csv"
SAMPLE_DECISIONS = ROOT / "samples" / "sample_decisions.csv"


@pytest.fixture()
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


@pytest.fixture()
def service(repo: InMemoryRepository) -> IngestService:
    return IngestService(MemoryIngestWriter(repo))


def test_parse_csv_korean_headers() -> None:
    rows = parse_csv(SAMPLE.read_bytes())
    assert len(rows) == 3
    assert rows[0]["마일스톤 ID"] == "import_u_pvt_review"


def test_parse_unsupported_extension() -> None:
    with pytest.raises(TabularParseError):
        parse_tabular("data.txt", b"x")


def test_ingest_sample_milestones(repo: InMemoryRepository, service: IngestService) -> None:
    before = len(repo.list("project_milestones"))
    report = service.ingest("sample_milestones.csv", SAMPLE.read_bytes(), "project_milestones")
    assert report.batch.accepted_count == 3
    assert report.batch.rejected_count == 0
    assert len(repo.list("project_milestones")) == before + 3

    imported = repo.get("project_milestones", "import_u_pvt_review")
    assert imported is not None
    assert imported.source.origin.value == "imported"
    assert imported.source.ref and imported.source.ref.startswith("import:")
    assert imported.week == 40
    assert imported.relevant_roles == ["pm", "hw_development"]


def test_ingest_rejects_bad_rows_korean_report(service: IngestService) -> None:
    csv_content = (
        "마일스톤 ID,프로젝트 ID,제목,설명,유형,개발 단계,결정 구간,주차,분기,관련 역할\n"
        ",project_u,제목없음ID없음,d,t,s,w,10,Q1,pm\n"
        "import_bad_week,project_u,주차가 문자,d,t,s,w,십이,Q1,pm\n"
        "import_ok,project_u,정상 행,d,t,s,w,12,Q1,pm\n"
    ).encode()
    report = service.ingest("bad.csv", csv_content, "project_milestones")
    assert report.batch.accepted_count == 1
    assert report.batch.rejected_count == 2
    reasons = {r.row_number: r.reason for r in report.rejected_rows}
    assert "필수 열 누락" in reasons[1]
    assert "형 변환 실패" in reasons[2] or "검증 실패" in reasons[2]


def test_ingest_unknown_mapping(service: IngestService) -> None:
    with pytest.raises(IngestError):
        service.ingest("x.csv", b"a,b\n1,2\n", "없는_매핑")


def test_rollback_removes_batch(repo: InMemoryRepository, service: IngestService) -> None:
    before = len(repo.list("project_milestones"))
    report = service.ingest("sample_milestones.csv", SAMPLE.read_bytes(), "project_milestones")
    assert len(repo.list("project_milestones")) == before + 3

    removed = service.rollback(report.batch.id)
    assert removed == 3
    assert len(repo.list("project_milestones")) == before
    batches = service.list_batches()
    assert batches[0].status == "rolled_back"


def test_synthetic_data_untouched_by_rollback(
    repo: InMemoryRepository, service: IngestService
) -> None:
    report = service.ingest("sample_milestones.csv", SAMPLE.read_bytes(), "project_milestones")
    service.rollback(report.batch.id)
    assert repo.get("project_milestones", "project_u_package_out_done") is not None


# ---- 신규 매핑 (반입 표면 확대) ----


def test_convert_row_nested_bool_single_item() -> None:
    from backend.ingest.mappings import MAPPINGS, convert_row

    mapping = MAPPINGS["issues"]
    record = convert_row(
        mapping,
        {
            "이슈 ID": "x",
            "프로젝트 ID": "project_u",
            "제목": "t",
            "유형": "underrun",
            "상태": "open",
            "증상": "s",
            "확신도": "medium",
            "영향 시나리오": "a;b",
            "영향 IP": "ip_dpu",
            "원인 유형": "architecture_miss",
            "원인 설명": "d",
            "원인 확신도": "low",
        },
    )
    assert record["affected_scope"] == {"scenarios": ["a", "b"], "ip_blocks": ["ip_dpu"]}
    assert record["root_causes"] == [
        {"cause_type": "architecture_miss", "description": "d", "confidence": "low"}
    ]

    catalog = MAPPINGS["evidence_catalog"]
    row = {"근거 ID": "e", "실측 여부": "예", "예측 여부": "false"}
    converted = convert_row(catalog, row)
    assert converted["is_measurement"] is True
    assert converted["is_prediction"] is False

    import pytest as _pytest

    with _pytest.raises(ValueError):
        convert_row(catalog, {"근거 ID": "e", "실측 여부": "몰라"})


def test_ingest_issues_roundtrip(repo: InMemoryRepository, service: IngestService) -> None:
    before = len(repo.list("issues"))
    report = service.ingest("sample_issues.csv", SAMPLE_ISSUES.read_bytes(), "issues")
    assert report.batch.accepted_count == 3
    assert report.batch.rejected_count == 0

    imported = repo.get("issues", "import_issue_dpu_ui_underrun_v")
    assert imported is not None
    assert imported.source.origin.value == "imported"
    assert imported.affected_scope.scenarios == [
        "video_mode_panel_underrun_prevention",
        "uhd60_recording_eis_on",
    ]
    assert imported.affected_scope.system_blocks == ["sys_noc", "sys_mif"]
    assert imported.severity == "high"
    assert imported.root_causes[0].cause_type.value == "architecture_miss"
    assert imported.root_causes[0].confidence.value == "medium"

    no_cause = repo.get("issues", "import_issue_isp_lowlight_close_unverified_w")
    assert no_cause is not None and no_cause.root_causes == []

    assert service.rollback(report.batch.id) == 3
    assert len(repo.list("issues")) == before


def test_ingest_tests_roundtrip(repo: InMemoryRepository, service: IngestService) -> None:
    before = len(repo.list("tests"))
    report = service.ingest("sample_tests.csv", SAMPLE_TESTS.read_bytes(), "tests")
    assert report.batch.accepted_count == 2
    assert report.batch.rejected_count == 0

    imported = repo.get("tests", "import_test_mfc_export_thermal_w")
    assert imported is not None
    assert imported.verifies_issue_ids == ["import_issue_mfc_export_thermal_w"]
    assert imported.executed_week == 31

    assert service.rollback(report.batch.id) == 2
    assert len(repo.list("tests")) == before


def test_ingest_events_roundtrip(repo: InMemoryRepository, service: IngestService) -> None:
    before = len(repo.list("development_events"))
    report = service.ingest("sample_events.csv", SAMPLE_EVENTS.read_bytes(), "development_events")
    assert report.batch.accepted_count == 3
    assert report.batch.rejected_count == 0

    imported = repo.get("development_events", "import_event_dpu_qos_risk_v")
    assert imported is not None
    assert imported.severity == "high"
    assert imported.schedule_signal == "at_risk"
    assert imported.affected_domains == ["display", "memory"]
    assert imported.related_ip_ids == ["ip_dpu"], "명시 IP 링크 열이 반입된다"
    assert imported.roles_involved == ["soc_architecture", "hw_development"]

    assert service.rollback(report.batch.id) == 3
    assert len(repo.list("development_events")) == before


def test_ingest_decisions_roundtrip(repo: InMemoryRepository, service: IngestService) -> None:
    """결정 재진입 (B3b) — 채운 행만 Decision, 결정 없는 행은 한국어 사유로 거부."""
    before = len(repo.list("decisions"))
    report = service.ingest("sample_decisions.csv", SAMPLE_DECISIONS.read_bytes(), "decisions")
    assert report.batch.accepted_count == 2
    assert report.batch.rejected_count == 1
    assert "결정" in report.rejected_rows[0].reason, "결정 빈 행은 필수 열 누락으로 보고"

    decision = repo.get("decisions", "decision_w_review_r1")
    assert decision is not None
    assert decision.event_id == "import_event_w_review_meeting"
    assert decision.decision_type == "review_decision"
    assert decision.selected_option.startswith("전력 모델을")
    basis = decision.supporting_basis[0]
    assert basis.ref_id == "import_evidence_mfc_export_thermal_w"
    assert basis.basis_type == "evidence_catalog"
    assert basis.confidence.value == "high"
    assert decision.unresolved_risks == ["고온 환경(35°C+) 마진 재확인 필요"]

    no_summary = repo.get("decisions", "decision_w_review_r2")
    assert no_summary is not None
    assert no_summary.tradeoff_summary == "", "빈 트레이드오프 요약은 기본값"

    # traceability가 재시작 없이 반입 결정을 본다 (시작 시 스냅샷 한계 제거 검증).
    from backend.resolve.traceability import TraceabilityService

    trace = TraceabilityService(repo).trace("decision_w_review_r1")
    assert trace.collection == "decisions"
    linked = {link.other_id for link in trace.links}
    assert "import_event_w_review_meeting" in linked, "회의 이벤트와 연결"

    assert service.rollback(report.batch.id) == 2
    assert len(repo.list("decisions")) == before
    assert TraceabilityService(repo).trace("decision_w_review_r1").collection is None


def test_decision_csv_template_matches_mapping_contract() -> None:
    """설계 11 §2.1 — 프론트 toDecisionCsv 헤더와 decisions 매핑 계약의 정합 고정.

    프론트 쪽은 ReviewPage 테스트가 같은 리터럴을 검증한다. 어느 한쪽이
    단독 변경되면 해당 쪽 테스트가 실패해 드리프트를 드러낸다.
    """
    from backend.ingest.mappings import MAPPINGS

    template_header = [
        "결정 ID",
        "프로젝트 ID",
        "회의 이벤트 ID",
        "시나리오 ID",
        "시나리오",
        "항목종류",
        "진술",
        "근거",
        "근거 유형",
        "신뢰등급",
        "확신도",
        "결정",
        "결정 유형",
        "트레이드오프 요약",
        "미해결 리스크",
        "담당",
        "상태",
    ]
    mapping = MAPPINGS["decisions"]
    mapped = set(mapping.column_map)
    assert mapped <= set(template_header), "매핑 열은 전부 템플릿에 존재해야 한다"
    assert mapping.required_columns <= set(template_header)
    # 읽기용(미반입) 열은 계약에 명시된 것만.
    assert set(template_header) - mapped == {"시나리오 ID", "시나리오", "항목종류", "신뢰등급", "담당", "상태"}


def test_ingest_evidence_catalog_roundtrip(
    repo: InMemoryRepository, service: IngestService
) -> None:
    before = len(repo.list("evidence_catalog"))
    report = service.ingest(
        "sample_evidence_catalog.csv", SAMPLE_EVIDENCE.read_bytes(), "evidence_catalog"
    )
    assert report.batch.accepted_count == 2
    assert report.batch.rejected_count == 0

    measured = repo.get("evidence_catalog", "import_evidence_mfc_export_thermal_w")
    assert measured is not None
    assert measured.is_measurement is True and measured.is_prediction is False
    predicted = repo.get("evidence_catalog", "import_evidence_dpu_ui_traffic_v")
    assert predicted is not None
    assert predicted.is_measurement is False and predicted.is_prediction is True

    assert service.rollback(report.batch.id) == 2
    assert len(repo.list("evidence_catalog")) == before


def test_ingested_data_flows_into_derived_views(
    repo: InMemoryRepository, service: IngestService
) -> None:
    """반입 데이터가 위험 지도/RCA/근거 사다리에 즉시 반영되고 rollback 시 사라진다."""
    from backend.services.evidence_ladder import EvidenceLadderService
    from backend.services.rca import RCAService
    from backend.services.risk import RiskService

    rca = RCAService(repo)
    risk = RiskService(repo)
    ladder = EvidenceLadderService(repo)

    baseline_issue_ids = {s.issue_id for s in rca.list_issues()}
    baseline_ladder_total = ladder.ladder().totals.total

    issues_batch = service.ingest("sample_issues.csv", SAMPLE_ISSUES.read_bytes(), "issues")
    tests_batch = service.ingest("sample_tests.csv", SAMPLE_TESTS.read_bytes(), "tests")
    evidence_batch = service.ingest(
        "sample_evidence_catalog.csv", SAMPLE_EVIDENCE.read_bytes(), "evidence_catalog"
    )

    # RCA: 반입 이슈 등장 + 검증 배지 — 검증 테스트 없는 close는 빨간 경고.
    summaries = {s.issue_id: s for s in rca.list_issues()}
    assert "import_issue_dpu_ui_underrun_v" in summaries
    assert summaries["import_issue_isp_lowlight_close_unverified_w"].closed_without_verification
    assert summaries["import_issue_mfc_export_thermal_w"].verification == "verified"

    # 위험 지도: open 이슈가 걸린 시나리오×IP 셀이 미해결 이슈 근거로 표시.
    heatmap = risk.heatmap(project_id="project_v")
    row = next(
        r for r in heatmap.rows if r.scenario_id == "video_mode_panel_underrun_prevention"
    )
    cell = next(c for c in row.cells if c.ip_id == "ip_dpu")
    assert cell.grade == "high"
    assert any(
        b.rule == "open_issue" and b.ref_id == "import_issue_dpu_ui_underrun_v"
        for b in cell.basis
    )

    # 근거 사다리: 반입 근거 2건이 분류되어 합계 증가 (실측·정합 1 + 예측 1).
    after = ladder.ladder()
    assert after.totals.total == baseline_ladder_total + 2
    tiers = {e.evidence_id: e.tier for e in after.entries if e.evidence_id.startswith("import_")}
    assert tiers["import_evidence_mfc_export_thermal_w"] == "measured_direct"
    assert tiers["import_evidence_dpu_ui_traffic_v"] == "predicted"

    # rollback 후 전 파생 뷰가 기준선으로 복귀.
    for batch in (issues_batch, tests_batch, evidence_batch):
        service.rollback(batch.batch.id)
    assert {s.issue_id for s in rca.list_issues()} == baseline_issue_ids
    assert ladder.ladder().totals.total == baseline_ladder_total


def test_ingest_api_roundtrip() -> None:
    from backend.api.app import create_app
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/ingest/file",
        params={"mapping": "project_milestones"},
        files={"file": ("sample_milestones.csv", SAMPLE.read_bytes(), "text/csv")},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["batch"]["accepted_count"] == 3

    batches = client.get("/api/v1/ingest/batches").json()
    assert batches[0]["id"] == report["batch"]["id"]

    rollback = client.post(f"/api/v1/ingest/batches/{report['batch']['id']}/rollback")
    assert rollback.json()["removed"] == 3

    bad = client.post(
        "/api/v1/ingest/file",
        params={"mapping": "없는매핑"},
        files={"file": ("x.csv", b"a\n1\n", "text/csv")},
    )
    assert bad.status_code == 400
