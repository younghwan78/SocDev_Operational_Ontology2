"""결정론 서비스 테스트 — 시나리오 분석 / 포트폴리오 / 리뷰 / traceability."""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.resolve.traceability import TraceabilityService
from backend.services.portfolio import LANE_LABELS, PortfolioService
from backend.services.review import ReviewService
from backend.services.scenario_analysis import ScenarioAnalysisService, ScenarioNotFoundError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SCENARIO = "uhd60_recording_eis_on"


@pytest.fixture(scope="module")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


@pytest.fixture(scope="module")
def analysis(repo):
    return ScenarioAnalysisService(repo).analyze(SCENARIO)


def test_analysis_core_sections(analysis) -> None:
    assert analysis.scenario.id == SCENARIO
    assert analysis.scenario_group is not None
    assert analysis.requests, "UHD60 EIS 시나리오는 요청이 있어야 한다"
    assert analysis.events, "연결 이벤트가 있어야 한다"
    assert analysis.evidence_catalog, "근거 카탈로그 항목이 있어야 한다"


def test_analysis_kpis_resolved(analysis) -> None:
    kpi_ids = {k.id for k in analysis.kpis}
    assert kpi_ids <= set(analysis.scenario.primary_kpis)
    assert kpi_ids, "primary KPI가 정의 카탈로그에서 해석되어야 한다"


def test_analysis_evidence_gaps_structured(analysis) -> None:
    assert analysis.evidence_gaps, "이 시나리오에는 알려진 근거 공백이 있다"
    for gap in analysis.evidence_gaps:
        assert gap.kind_ko
        assert gap.description
        assert gap.ref_id


def test_analysis_timeline_sorted(analysis) -> None:
    weeks = [item.week for item in analysis.timeline]
    assert weeks == sorted(weeks)
    types = {item.item_type for item in analysis.timeline}
    assert "event" in types
    assert "request" in types


def test_analysis_unknown_scenario_raises(repo) -> None:
    with pytest.raises(ScenarioNotFoundError):
        ScenarioAnalysisService(repo).analyze("scenario_없음")


def test_portfolio_overview(repo) -> None:
    overview = PortfolioService(repo).overview()
    assert len(overview.projects) == 3
    lanes = {item.lane for item in overview.attention}
    assert lanes <= set(LANE_LABELS)
    assert "definition_needed" in lanes, "미정의 시나리오 15건이 lane으로 잡혀야 한다"
    assert "propagation_review" in lanes
    for item in overview.attention:
        assert item.lane_ko == LANE_LABELS[item.lane]
    assert len(overview.matrix) == len(repo.list("scenarios"))


def test_review_weekly(repo) -> None:
    service = ReviewService(repo)
    index = service.index()
    assert index.weeks
    week = index.weeks[0]
    snapshot = service.snapshot(week)
    assert snapshot.week == week
    assert len(snapshot.events) == index.event_counts.get(week, 0)


def test_traceability_bidirectional(repo) -> None:
    service = TraceabilityService(repo)
    result = service.trace(SCENARIO)
    assert result.collection == "scenarios"
    assert result.label_ko == "시나리오"
    directions = {link.direction for link in result.links}
    assert directions == {"outgoing", "incoming"}
    incoming_types = {
        link.link_type for link in result.links if link.direction == "incoming"
    }
    assert "관련_시나리오" in incoming_types or "대상_시나리오" in incoming_types


def test_traceability_unknown_object(repo) -> None:
    service = TraceabilityService(repo)
    result = service.trace("없는_객체_id")
    assert result.collection is None
    assert result.links == []


def test_portfolio_descriptions_hide_raw_codes(repo) -> None:
    """주의 항목 서술의 원문 코드·id 은닉 (B2) — id는 source_refs로 유지."""
    from backend.services.portfolio import PortfolioService

    overview = PortfolioService(repo).overview()
    blocked = [i for i in overview.attention if i.lane == "evidence_blocked"]
    assert blocked, "근거 부족 lane 존재"
    for item in blocked:
        assert "누락 근거" in item.description and "_" not in item.description
        assert item.source_refs, "누락 근거 id는 source_refs로 추적 가능해야 한다"
    for item in overview.attention:
        assert "근거 '" not in item.description, "need id 인용 금지"
