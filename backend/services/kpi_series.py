"""KPI 시계열 서비스 — 과제 간 시점 정렬 비교 (16_digital_twin_followups.md §4).

domain time(week) 축의 결정론 파생 뷰다 — 저장하지 않는다.
추세는 KPIDefinition.direction과 첫/마지막 관측값의 대조에서 나온 **사실 서술**이며
수치 점수가 아니다. 모든 서술에 관측 ref를 동반한다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import KPIObservation
from backend.ontology.project import ProjectMilestone
from backend.ontology.scenario import KPIDefinition

DIRECTION_LABELS: dict[str, str] = {
    "lower_is_better": "낮을수록 좋음",
    "lower_is_better_with_margin": "낮을수록 좋음(마진 확보)",
    "higher_is_better": "높을수록 좋음",
}

TREND_LABELS: dict[str, str] = {
    "improved": "개선",
    "worsened": "악화",
    "flat": "변화 없음",
    "single_point": "판단 불가 (관측 1건)",
    "unknown_direction": "방향 미상 (KPI 정의 없음)",
}


class KPINotFoundError(Exception):
    pass


class KPISeriesPoint(BaseModel):
    """시계열의 점 — 원 관측 참조 동반."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str
    week: int
    # align_milestone_type 지정 시 마일스톤 주차를 0으로 하는 상대 주차.
    aligned_week: int | None = None
    value: float
    unit: str | None = None
    scenario_id: str | None = None
    measurement_stage: str | None = None
    source_ref: str | None = None
    evidence_id: str | None = None


class ProjectKPISeries(BaseModel):
    """프로젝트 하나의 궤적 + 추세 사실 서술."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    points: list[KPISeriesPoint]
    align_milestone_id: str | None = None
    align_milestone_week: int | None = None
    align_note_ko: str | None = None  # 비정렬 사유 (마일스톤 부재 등)
    trend: str  # improved | worsened | flat | single_point | unknown_direction
    trend_ko: str
    trend_note_ko: str  # 첫→마지막 값과 방향 기준을 명시한 사실 서술
    source_refs: list[str] = Field(default_factory=list)


class KPISeriesResult(BaseModel):
    """KPI 하나의 과제 간 비교 응답."""

    model_config = ConfigDict(extra="forbid")

    kpi_id: str
    group: str | None = None
    unit: str | None = None
    direction: str | None = None
    direction_ko: str | None = None
    align_milestone_type: str | None = None
    series: list[ProjectKPISeries]


class KPICatalogEntry(BaseModel):
    """관측이 존재하는 KPI — 선택기용."""

    model_config = ConfigDict(extra="forbid")

    kpi_id: str
    group: str | None = None
    unit: str | None = None
    direction: str | None = None
    observation_count: int
    project_ids: list[str]
    scenario_ids: list[str] = Field(default_factory=list)


class KPISeriesService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def _observations(self) -> list[KPIObservation]:
        return [
            o
            for o in self._repo.list("kpi_observations")
            if isinstance(o, KPIObservation)
        ]

    def _definition(self, kpi_id: str) -> KPIDefinition | None:
        obj = self._repo.get("kpi_definitions", kpi_id)
        return obj if isinstance(obj, KPIDefinition) else None

    def catalog(self) -> list[KPICatalogEntry]:
        grouped: dict[str, list[KPIObservation]] = {}
        for obs in self._observations():
            grouped.setdefault(obs.kpi_id, []).append(obs)
        entries: list[KPICatalogEntry] = []
        for kpi_id in sorted(grouped):
            observations = grouped[kpi_id]
            definition = self._definition(kpi_id)
            entries.append(
                KPICatalogEntry(
                    kpi_id=kpi_id,
                    group=definition.group if definition else None,
                    unit=definition.unit if definition else None,
                    direction=definition.direction if definition else None,
                    observation_count=len(observations),
                    project_ids=sorted({o.project_id for o in observations}),
                    scenario_ids=sorted(
                        {o.scenario_id for o in observations if o.scenario_id}
                    ),
                )
            )
        return entries

    def series(
        self,
        kpi_id: str,
        scenario_id: str | None = None,
        project_id: str | None = None,
        align_milestone_type: str | None = None,
    ) -> KPISeriesResult:
        definition = self._definition(kpi_id)
        observations = [o for o in self._observations() if o.kpi_id == kpi_id]
        if definition is None and not observations:
            raise KPINotFoundError(f"KPI 없음: {kpi_id} (정의·관측 모두 부재)")
        if scenario_id:
            observations = [o for o in observations if o.scenario_id == scenario_id]
        if project_id:
            observations = [o for o in observations if o.project_id == project_id]

        by_project: dict[str, list[KPIObservation]] = {}
        for obs in observations:
            by_project.setdefault(obs.project_id, []).append(obs)

        direction = definition.direction if definition else None
        series = [
            self._project_series(
                pid, sorted(items, key=lambda o: (o.week, o.id)), definition,
                align_milestone_type,
            )
            for pid, items in sorted(by_project.items())
        ]
        return KPISeriesResult(
            kpi_id=kpi_id,
            group=definition.group if definition else None,
            unit=definition.unit if definition else None,
            direction=direction,
            direction_ko=(
                DIRECTION_LABELS.get(direction, direction) if direction else None
            ),
            align_milestone_type=align_milestone_type,
            series=series,
        )

    # ---- 내부 ----

    def _alignment_milestone(
        self, project_id: str, milestone_type: str
    ) -> ProjectMilestone | None:
        """정렬 기준 마일스톤 — 같은 유형이 여럿이면 (주차, id) 최소가 기준 (결정론)."""
        candidates = [
            m
            for m in self._repo.list("project_milestones")
            if isinstance(m, ProjectMilestone)
            and m.project_id == project_id
            and m.milestone_type == milestone_type
            and m.week is not None
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda m: (m.week, m.id))

    def _project_series(
        self,
        project_id: str,
        observations: list[KPIObservation],
        definition: KPIDefinition | None,
        align_milestone_type: str | None,
    ) -> ProjectKPISeries:
        milestone: ProjectMilestone | None = None
        align_note: str | None = None
        if align_milestone_type:
            milestone = self._alignment_milestone(project_id, align_milestone_type)
            if milestone is None:
                align_note = (
                    f"비정렬 — 프로젝트에 '{align_milestone_type}' 유형 마일스톤이 없음"
                )

        default_unit = definition.unit if definition else None
        points = [
            KPISeriesPoint(
                observation_id=obs.id,
                week=obs.week,
                aligned_week=(
                    obs.week - milestone.week
                    if milestone is not None and milestone.week is not None
                    else None
                ),
                value=obs.value,
                unit=obs.unit or default_unit,
                scenario_id=obs.scenario_id,
                measurement_stage=obs.measurement_stage,
                source_ref=obs.source_ref,
                evidence_id=obs.evidence_id,
            )
            for obs in observations
        ]
        trend, trend_note = self._trend(points, definition)
        return ProjectKPISeries(
            project_id=project_id,
            points=points,
            align_milestone_id=milestone.id if milestone else None,
            align_milestone_week=milestone.week if milestone else None,
            align_note_ko=align_note,
            trend=trend,
            trend_ko=TREND_LABELS[trend],
            trend_note_ko=trend_note,
            source_refs=[p.observation_id for p in points],
        )

    @staticmethod
    def _trend(
        points: list[KPISeriesPoint], definition: KPIDefinition | None
    ) -> tuple[str, str]:
        """첫↔마지막 관측 대조 — 사실 서술 (수치 점수 아님)."""
        if len(points) < 2:
            return "single_point", "관측이 1건뿐이라 추세를 말할 수 없음"
        first, last = points[0], points[-1]
        unit = first.unit or ""
        span = (
            f"W{first.week} {first.value}{unit} → W{last.week} {last.value}{unit}"
        )
        if definition is None:
            return "unknown_direction", f"{span} — KPI 정의가 없어 방향 판단 불가"
        if last.value == first.value:
            return "flat", f"{span} — 변화 없음"
        decreasing = last.value < first.value
        lower_better = definition.direction.startswith("lower_is_better")
        improved = decreasing == lower_better
        direction_ko = DIRECTION_LABELS.get(definition.direction, definition.direction)
        verdict = "개선" if improved else "악화"
        return (
            "improved" if improved else "worsened",
            f"{span} — '{direction_ko}' 기준 {verdict}",
        )
