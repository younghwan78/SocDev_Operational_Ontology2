"""변경 영향 서비스 테스트 — 그래프 순회의 결정론 고정.

수용 기준: ISP knob 변경 예시로 4분면 출력 완결, 체크리스트가 역할 책임 경계와 일치,
모든 영향 항목이 근거 객체 ref 동반.
"""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.services.change_impact import (
    ChangeImpactResult,
    ChangeImpactService,
    InvalidSelectionError,
    UnknownIPError,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def service() -> ChangeImpactService:
    return ChangeImpactService(InMemoryRepository.from_fixtures(FIXTURES))


@pytest.fixture(scope="module")
def isp_knob_result(service) -> ChangeImpactResult:
    """수용 기준 예시 — ISP pixel_mode knob 변경."""
    return service.analyze("ip_isp", knob_id="knob_isp_pixel_mode")


def test_isp_knob_four_quadrants_complete(isp_knob_result) -> None:
    result = isp_knob_result
    assert result.impacted_scenarios, "① 영향 시나리오"
    assert result.impacted_kpis, "② 영향 KPI"
    assert result.chained_ips, "③ 연쇄 IP"
    assert result.checklist, "④ 검토 체크리스트"
    assert result.similar_cases, "과거 유사 사례"
    assert result.export_text.startswith("[변경 영향 분석]")


def test_knob_narrows_scenarios(service, isp_knob_result) -> None:
    ip_level = service.analyze("ip_isp")
    assert len(isp_knob_result.impacted_scenarios) < len(ip_level.impacted_scenarios)
    ids = {s.scenario_id for s in isp_knob_result.impacted_scenarios}
    assert ids == {"uhd60_recording_eis_on", "eight_k30_recording_kpi"}, (
        "knob 관련 시나리오 + 요구 연결 시나리오로 한정"
    )


def test_every_impact_item_has_refs(isp_knob_result) -> None:
    for scenario in isp_knob_result.impacted_scenarios:
        assert scenario.reasons, f"근거 없는 영향 시나리오: {scenario.scenario_id}"
        for reason in scenario.reasons:
            assert reason.ref_id and reason.ref_collection
    for chained in isp_knob_result.chained_ips:
        assert chained.rule_id and chained.source_ref and chained.condition
    for item in isp_knob_result.checklist:
        assert item.basis, f"근거 없는 체크리스트 항목: {item.role_id}"
    for case in isp_knob_result.similar_cases:
        assert case.ref_id and case.why_similar


def test_checklist_respects_role_boundaries(isp_knob_result) -> None:
    by_role = {item.role_id: item for item in isp_knob_result.checklist}
    # Verification 독립 역할 금지 — 7개 역할 외 항목 없음.
    assert set(by_role) <= {
        "product_planning", "soc_architecture", "system_engineering",
        "hw_development", "sw_development", "pm", "management",
    }
    # HW/SW는 아키텍처 결정을 소유하지 않고 feedback_items로 전달한다.
    assert "feedback_items" in by_role["hw_development"].perspective
    assert "feedback_items" in by_role["sw_development"].perspective
    # Management는 구현 세부를 결정하지 않는다 (존재 시).
    if "management" in by_role:
        assert "구현 세부 결정 아님" in by_role["management"].perspective


def test_management_item_requires_trigger(service) -> None:
    """리스크 증가 knob에서만 management 항목 — 일반론 금지."""
    risky = service.analyze("ip_isp", knob_id="knob_isp_preview_stream_max")
    assert any(i.role_id == "management" for i in risky.checklist)
    mixed = service.analyze("ip_isp", knob_id="knob_isp_pixel_mode")
    assert not any(i.role_id == "management" for i in mixed.checklist)


def test_sw_item_requires_knob(service) -> None:
    ip_only = service.analyze("ip_isp")
    assert not any(i.role_id == "sw_development" for i in ip_only.checklist)


def test_knob_kpis_listed_first(isp_knob_result) -> None:
    via_flags = [k.via_knob for k in isp_knob_result.impacted_kpis]
    assert via_flags == sorted(via_flags, reverse=True)
    knob_kpis = {k.kpi_id for k in isp_knob_result.impacted_kpis if k.via_knob}
    assert knob_kpis == {"ddr_bw", "isp_power", "fps_stability"}


def test_chained_ip_directions(service) -> None:
    isp = service.analyze("ip_isp")
    assert [(c.ip_id, c.direction) for c in isp.chained_ips] == [("sys_mif", "outgoing")]
    mif = service.analyze("sys_mif")
    incoming = {c.ip_id for c in mif.chained_ips if c.direction == "incoming"}
    assert {"ip_isp", "ip_mfc", "ip_npu", "ip_gpu"} <= incoming, (
        "시스템 블록 선택 시 역방향 의존(그 블록에 기대는 IP)이 보여야 한다"
    )


def test_mode_filters_requirements(service) -> None:
    result = service.analyze("ip_isp", mode="octa_pixel")
    assert [s.scenario_id for s in result.impacted_scenarios] == ["uhd60_recording_eis_on"]
    assert all(
        reason.rule == "ip_requirement"
        for s in result.impacted_scenarios
        for reason in s.reasons
    )


def test_capability_conservative_matching(service) -> None:
    result = service.analyze("ip_mfc", capability_id="cap_mfc_8k_resolution")
    ids = {s.scenario_id for s in result.impacted_scenarios}
    assert ids == {"eight_k30_recording_kpi", "video_editor_export"}


def test_similar_cases_issue_first_with_overlap(isp_knob_result) -> None:
    first = isp_knob_result.similar_cases[0]
    assert first.kind == "issue"
    assert first.ref_id == "issue_u_uhd60_eis_power_gap"
    assert first.scenario_ids == ["uhd60_recording_eis_on"]


def test_deterministic(service, isp_knob_result) -> None:
    again = service.analyze("ip_isp", knob_id="knob_isp_pixel_mode")
    assert again.model_dump() == isp_knob_result.model_dump()


def test_no_numeric_score_fields(isp_knob_result) -> None:
    for name in type(isp_knob_result).model_fields:
        assert "score" not in name and "weight" not in name
    assert "수치 점수 없음" in isp_knob_result.export_text


def test_errors(service) -> None:
    with pytest.raises(UnknownIPError):
        service.analyze("ip_없음")
    with pytest.raises(InvalidSelectionError):
        service.analyze("ip_isp", knob_id="knob_mfc_없거나_남의것")
    with pytest.raises(InvalidSelectionError):
        service.analyze("ip_isp", capability_id="cap_mfc_hevc_encode")
    with pytest.raises(InvalidSelectionError):
        service.analyze("ip_isp", mode="encode")


def test_options_shape(service) -> None:
    options = service.options()
    assert len(options.ips) == 11
    isp = next(o for o in options.ips if o.ip_id == "ip_isp")
    assert {k["id"] for k in isp.knobs} == {
        "knob_isp_devfreq_isp", "knob_isp_pixel_mode",
        "knob_isp_preview_stream_max", "knob_isp_otf_dma_path",
    }
    assert "octa_pixel" in isp.modes
    mif = next(o for o in options.ips if o.ip_id == "sys_mif")
    assert mif.knobs == [] and mif.modes == []
