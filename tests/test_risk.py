"""위험 지도 서비스 테스트 — 정성 등급 판정의 결정론 고정.

수용 기준: 동일 fixture → 동일 등급, 모든 등급에 근거 목록, 수치 점수 부재.
"""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.services.risk import (
    GRADE_LABELS,
    RULE_LABELS,
    RiskCell,
    RiskHeatmap,
    RiskService,
    ScenarioRiskRow,
    WeeklyFocusItem,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


@pytest.fixture(scope="module")
def heatmap(repo) -> RiskHeatmap:
    return RiskService(repo).heatmap()


def _row(heatmap: RiskHeatmap, scenario_id: str) -> ScenarioRiskRow:
    return next(r for r in heatmap.rows if r.scenario_id == scenario_id)


def test_deterministic_same_fixture_same_grades(repo, heatmap) -> None:
    again = RiskService(repo).heatmap()
    assert heatmap.model_dump() == again.model_dump()


def test_rows_cover_all_scenarios(repo, heatmap) -> None:
    assert {r.scenario_id for r in heatmap.rows} == set(repo.ids("scenarios"))


def test_columns_are_scenario_referenced_blocks_only(repo, heatmap) -> None:
    column_ids = {c.ip_id for c in heatmap.columns}
    referenced: set[str] = set()
    for scenario in repo.list("scenarios"):
        referenced.update(scenario.uses_ip_blocks)  # type: ignore[attr-defined]
        referenced.update(scenario.depends_on_system_blocks)  # type: ignore[attr-defined]
    assert column_ids == referenced, "열은 시나리오가 참조하는 블록에서만 파생된다"
    assert "ip_cpu" not in column_ids, "시나리오가 쓰지 않는 CPU는 열에 없다"


def test_every_grade_has_basis(heatmap) -> None:
    for row in heatmap.rows:
        assert row.overall_grade in GRADE_LABELS
        assert row.overall_grade_ko == GRADE_LABELS[row.overall_grade]
        assert row.overall_basis, f"근거 없는 종합 등급: {row.scenario_id}"
        for cell in row.cells:
            assert cell.grade in GRADE_LABELS
            assert cell.grade_ko == GRADE_LABELS[cell.grade]
            assert cell.basis, f"근거 없는 셀 등급: {row.scenario_id}×{cell.ip_id}"
            for item in cell.basis:
                assert item.rule in RULE_LABELS
                assert item.rule_ko == RULE_LABELS[item.rule]
                assert item.ref_id
                assert item.description


def test_cells_limited_to_relevant_ips(heatmap) -> None:
    row = _row(heatmap, "voice_call_audio_ai_latency")
    cell_ips = {c.ip_id for c in row.cells}
    assert "ip_abox_vts" in cell_ips
    assert "ip_isp" not in cell_ips, "무관한 IP에는 셀을 만들지 않는다"


def test_open_issue_drives_high_grade(heatmap) -> None:
    row = _row(heatmap, "uhd60_recording_eis_on")
    isp = next(c for c in row.cells if c.ip_id == "ip_isp")
    assert isp.grade == "high"
    issue_refs = {b.ref_id for b in isp.basis if b.rule == "open_issue"}
    assert "issue_u_uhd60_eis_power_gap" in issue_refs
    assert row.overall_grade == "high"
    assert any(b.rule != "no_signal" for b in row.overall_basis)


def test_quiet_scenario_stays_low_with_no_signal_basis(heatmap) -> None:
    row = _row(heatmap, "high_speed_fhd240_recording")
    assert row.overall_grade == "low"
    for cell in row.cells:
        assert cell.grade == "low"
        assert cell.basis[0].rule == "no_signal"


def test_confidence_cap_weighting() -> None:
    """확신도 차단 가중 — 상한 low만 높음, medium 상한은 중간."""
    from backend.services.risk import _confidence_cap

    assert _confidence_cap("L") == "low"
    assert _confidence_cap("M") == "medium"
    assert _confidence_cap("medium") == "medium"


def test_no_numeric_score_fields() -> None:
    """수치 리스크 점수 금지 — 등급/근거 외 점수형 필드가 계약에 없어야 한다."""
    for model in (RiskCell, ScenarioRiskRow, RiskHeatmap, WeeklyFocusItem):
        for name in model.model_fields:
            assert "score" not in name
            assert "weight" not in name
            assert "rank" not in name


def test_rows_sorted_worst_first(heatmap) -> None:
    ranks = [{"high": 0, "medium": 1, "low": 2}[r.overall_grade] for r in heatmap.rows]
    assert ranks == sorted(ranks), "위험한 시나리오가 먼저 보여야 한다"


def test_project_filter(repo) -> None:
    service = RiskService(repo)
    rows_u = {r.scenario_id for r in service.heatmap("project_u").rows}
    rows_w = {r.scenario_id for r in service.heatmap("project_w").rows}
    assert "voice_call_audio_ai_latency" not in rows_u, "W 전용 시나리오는 U 탭에 없다"
    assert "voice_call_audio_ai_latency" in rows_w
    full = {r.scenario_id for r in service.heatmap().rows}
    assert rows_u <= full


def test_focus_top_items(heatmap) -> None:
    assert 3 <= len(heatmap.focus) <= 5
    kinds = {item.kind for item in heatmap.focus}
    assert kinds <= {"priority_request", "confidence_blocked", "schedule_risk"}
    # P1 요청 근거 부족이 최우선 — 존재하는 한 앞에 온다.
    first_kinds = [item.kind for item in heatmap.focus]
    if "priority_request" in first_kinds:
        assert first_kinds[0] == "priority_request"
    for item in heatmap.focus:
        assert item.title
        assert item.description


def test_focus_respects_project_filter(repo) -> None:
    service = RiskService(repo)
    for item in service.heatmap("project_v").focus:
        assert item.project_ids == ["project_v"]


def test_event_explicit_related_ip_ids_override_heuristic(repo) -> None:
    """명시 IP 링크가 있으면 affected_domains 토큰 확장 없이 정확 귀속된다 (L8)."""
    from backend.ontology.event import DevelopmentEvent
    from backend.resolve.entity_resolution import IPAliasIndex
    from backend.services.risk import event_related_ips

    index = IPAliasIndex(repo)
    base = {
        "id": "evt_x",
        "project_id": "project_v",
        "title": "t",
        "description": "d",
        "event_type": "risk_raised",
        "event_category": "risk",
        "affected_domains": ["memory"],
    }
    heuristic = DevelopmentEvent.model_validate(base)
    assert len(event_related_ips(heuristic, index)) >= 2, "'memory'는 다중 IP로 확장"

    explicit = DevelopmentEvent.model_validate({**base, "related_ip_ids": ["ip_dpu"]})
    assert event_related_ips(explicit, index) == {"ip_dpu"}


def test_open_issue_low_severity_grades_medium() -> None:
    """이슈 자체 심각도가 낮음으로 명시되면 미해결이라도 중간 — 근거에 심각도 표기.

    모듈 공유 repo를 오염시키지 않도록 독립 repo를 사용한다.
    """
    from backend.ontology.event import Issue

    # 다른 신호가 없는 조용한 시나리오를 사용해 이슈 심각도의 효과만 격리한다.
    scenario_id = "high_speed_fhd240_recording"
    baseline = InMemoryRepository.from_fixtures(FIXTURES)
    quiet_row = next(
        r for r in RiskService(baseline).heatmap().rows if r.scenario_id == scenario_id
    )
    ip_id = quiet_row.cells[0].ip_id
    assert quiet_row.cells[0].grade == "low", "전제: 기준선이 조용한 셀"

    base = {
        "id": "issue_sev_test",
        "project_id": "project_u",
        "title": "저심각도 미해결 이슈",
        "issue_type": "underrun",
        "status": "open",
        "symptom": "간헐 재현",
        "confidence": "medium",
        "affected_scope": {"scenarios": [scenario_id], "ip_blocks": [ip_id]},
    }

    def _cell(severity: str | None) -> RiskCell:
        local = InMemoryRepository.from_fixtures(FIXTURES)
        payload = base if severity is None else {**base, "severity": severity}
        local.add_objects("issues", [Issue.model_validate(payload)])
        row = next(
            r for r in RiskService(local).heatmap().rows if r.scenario_id == scenario_id
        )
        return next(c for c in row.cells if c.ip_id == ip_id)

    low = _cell("low")
    low_basis = next(b for b in low.basis if b.ref_id == "issue_sev_test")
    assert low.grade == "medium", "심각도 low 미해결 이슈는 중간"
    assert "심각도 low" in low_basis.description

    high = _cell("high")
    assert high.grade == "high", "심각도 high는 기존대로 높음"

    unspecified = _cell(None)
    assert unspecified.grade == "high", "심각도 미명시는 기존 동작 보존 (높음)"
