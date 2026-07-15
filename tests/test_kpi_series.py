"""P3 KPI 시계열 — 계약·정렬 비교·추세 서술·반입 왕복 (16_digital_twin_followups.md §4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.ingest.service import IngestService, MemoryIngestWriter
from backend.loaders.repository import InMemoryRepository
from backend.ontology.event import KPIObservation
from backend.ontology.project import ProjectMilestone
from backend.ontology.scenario import KPIDefinition
from backend.services.kpi_series import KPINotFoundError, KPISeriesService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

_SRC = {"origin": "synthetic", "ref": "test:kpi"}


def _definition(kpi_id: str, direction: str, unit: str = "mW") -> KPIDefinition:
    return KPIDefinition.model_validate(
        {"id": kpi_id, "source": _SRC, "group": "power", "unit": unit, "direction": direction}
    )


def _obs(
    obs_id: str, project_id: str, kpi_id: str, week: int, value: float
) -> KPIObservation:
    return KPIObservation.model_validate(
        {
            "id": obs_id,
            "source": _SRC,
            "project_id": project_id,
            "kpi_id": kpi_id,
            "week": week,
            "value": value,
        }
    )


def _milestone(ms_id: str, project_id: str, milestone_type: str, week: int) -> ProjectMilestone:
    return ProjectMilestone.model_validate(
        {
            "id": ms_id,
            "source": _SRC,
            "project_id": project_id,
            "title": ms_id,
            "description": "테스트 마일스톤",
            "milestone_type": milestone_type,
            "lifecycle_stage": "evt",
            "decision_window": "none",
            "week": week,
        }
    )


def test_fixture_series_cross_project_comparison() -> None:
    """fixture 우주 — 같은 KPI(dou_power)를 U(실측)·V(예측)가 나란히 갖는다."""
    repo = InMemoryRepository.from_fixtures(FIXTURES)
    service = KPISeriesService(repo)

    catalog = {entry.kpi_id: entry for entry in service.catalog()}
    assert "dou_power" in catalog and "ddr_bw" in catalog
    assert catalog["dou_power"].project_ids == ["project_u", "project_v"]

    result = service.series("dou_power", scenario_id="uhd60_recording_eis_on")
    by_project = {s.project_id: s for s in result.series}
    assert set(by_project) == {"project_u", "project_v"}
    # 수용 기준 4 — lower_is_better에서 값 감소 = 개선 (사실 서술에 값·기준 명시).
    assert result.direction == "lower_is_better"
    assert by_project["project_u"].trend == "improved"
    assert "1450.0mW → W22 1290.0mW" in by_project["project_u"].trend_note_ko
    assert "개선" in by_project["project_u"].trend_note_ko
    # 모든 점은 관측 ref를 동반한다.
    assert by_project["project_u"].source_refs == [
        p.observation_id for p in by_project["project_u"].points
    ]


def test_milestone_alignment_and_missing_milestone_note() -> None:
    """수용 기준 2 — 마일스톤 상대 주차 정렬 + 마일스톤 없는 프로젝트는 사유 명시."""
    repo = InMemoryRepository(
        {
            "kpi_definitions": [_definition("kpi_x", "lower_is_better")],
            "project_milestones": [_milestone("ms_u_rel", "proj_u", "release", 30)],
            "kpi_observations": [
                _obs("o_u1", "proj_u", "kpi_x", 26, 100.0),
                _obs("o_u2", "proj_u", "kpi_x", 34, 90.0),
                _obs("o_v1", "proj_v", "kpi_x", 6, 120.0),
            ],
        }
    )
    result = KPISeriesService(repo).series("kpi_x", align_milestone_type="release")
    by_project = {s.project_id: s for s in result.series}
    u = by_project["proj_u"]
    assert u.align_milestone_week == 30
    assert [p.aligned_week for p in u.points] == [-4, 4]
    v = by_project["proj_v"]
    assert v.align_note_ko is not None and "release" in v.align_note_ko
    assert all(p.aligned_week is None for p in v.points)


def test_trend_directions() -> None:
    repo = InMemoryRepository(
        {
            "kpi_definitions": [
                _definition("kpi_up", "higher_is_better", unit="percent"),
            ],
            "kpi_observations": [
                _obs("o1", "proj_u", "kpi_up", 10, 5.0),
                _obs("o2", "proj_u", "kpi_up", 12, 8.0),
                _obs("o3", "proj_v", "kpi_up", 10, 9.0),
                _obs("o4", "proj_v", "kpi_up", 12, 7.0),
                _obs("o5", "proj_w", "kpi_up", 10, 4.0),
            ],
        }
    )
    result = KPISeriesService(repo).series("kpi_up")
    trends = {s.project_id: s.trend for s in result.series}
    assert trends == {
        "proj_u": "improved",
        "proj_v": "worsened",
        "proj_w": "single_point",
    }


def test_unknown_kpi_raises() -> None:
    repo = InMemoryRepository({})
    with pytest.raises(KPINotFoundError):
        KPISeriesService(repo).series("없는_kpi")


def test_ingest_roundtrip_and_rollback() -> None:
    """수용 기준 3 — KPI 관측 CSV 반입 → series 반영 → rollback 시 제거."""
    repo = InMemoryRepository(
        {"kpi_definitions": [_definition("kpi_csv", "lower_is_better")]}
    )
    ingest = IngestService(MemoryIngestWriter(repo))
    rows = [
        {
            "관측 ID": f"obs_csv_{week}",
            "프로젝트 ID": "proj_u",
            "KPI ID": "kpi_csv",
            "주차": str(week),
            "값": str(value),
            "측정 단계": "emulator",
        }
        for week, value in ((10, "812.5"), (14, "798.0"))
    ]
    report = ingest.ingest_rows("kpi.csv", rows, "kpi_observations")
    assert report.batch.accepted_count == 2

    service = KPISeriesService(repo)
    series = service.series("kpi_csv").series[0]
    assert [p.value for p in series.points] == [812.5, 798.0]
    assert series.trend == "improved"

    ingest.rollback(report.batch.id)
    assert service.series("kpi_csv").series == []
