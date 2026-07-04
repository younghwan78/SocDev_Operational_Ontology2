"""시나리오 분석 서비스 — 실무 리더의 1차 질문에 결정론으로 답한다.

"이 시나리오에 무슨 일이 있었고, 근거는 무엇이며, 무엇이 비어 있는가?"
LLM 없이 fixture/DB 데이터만으로 계산한다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import DevelopmentEvent, Issue
from backend.ontology.evidence import (
    EvidenceCatalogEntry,
    MeasurementEvidence,
    MeasurementRequirement,
)
from backend.ontology.project import ProjectMilestone
from backend.ontology.role import RoleActivity
from backend.ontology.scenario import (
    KPIDefinition,
    Scenario,
    ScenarioGroup,
    ScenarioRequest,
    Variant,
)


class EvidenceGapItem(BaseModel):
    """근거 공백 항목 — 어떤 근거가 왜 부족한지."""

    model_config = ConfigDict(extra="forbid")

    kind: str  # missing_evidence | unavailable_catalog | required_evidence_open | confidence_blocked
    kind_ko: str
    ref_id: str
    description: str
    source_refs: list[str] = []


class TimelineItem(BaseModel):
    """주차 기반 타임라인 항목."""

    model_config = ConfigDict(extra="forbid")

    week: int
    item_type: str  # event | milestone | activity | request
    item_type_ko: str
    ref_id: str
    title: str
    project_id: str | None = None
    severity: str | None = None
    status: str | None = None
    roles: list[str] = []


class ScenarioAnalysis(BaseModel):
    """시나리오 종합 분석 — 파생 뷰(저장하지 않음)."""

    model_config = ConfigDict(extra="forbid")

    scenario: Scenario
    scenario_group: ScenarioGroup | None
    variants: list[Variant]
    kpis: list[KPIDefinition]
    requests: list[ScenarioRequest]
    events: list[DevelopmentEvent]
    activities: list[RoleActivity]
    issues: list[Issue]
    evidence_catalog: list[EvidenceCatalogEntry]
    measurement_evidence: list[MeasurementEvidence]
    measurement_requirements: list[MeasurementRequirement]
    evidence_gaps: list[EvidenceGapItem]
    timeline: list[TimelineItem]


class ScenarioNotFoundError(Exception):
    pass


class ScenarioAnalysisService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def _scenario(self, scenario_id: str) -> Scenario:
        obj = self._repo.get("scenarios", scenario_id)
        if obj is None:
            raise ScenarioNotFoundError(f"시나리오 없음: {scenario_id}")
        assert isinstance(obj, Scenario)
        return obj

    def _related_requests(self, scenario_id: str) -> list[ScenarioRequest]:
        result = []
        for request in self._repo.list("scenario_requests"):
            assert isinstance(request, ScenarioRequest)
            if scenario_id == request.scenario_id or scenario_id in request.scenario_ids:
                result.append(request)
        return result

    def _related_events(
        self, scenario_id: str, request_ids: set[str]
    ) -> list[DevelopmentEvent]:
        result = []
        for event in self._repo.list("development_events"):
            assert isinstance(event, DevelopmentEvent)
            if scenario_id in event.linked_scenario_ids or (
                request_ids and set(event.linked_request_ids) & request_ids
            ):
                result.append(event)
        return result

    def _related_activities(
        self, scenario_id: str, event_ids: set[str]
    ) -> list[RoleActivity]:
        result = []
        for activity in self._repo.list("role_activities"):
            assert isinstance(activity, RoleActivity)
            if scenario_id in activity.linked_scenario_ids or activity.linked_event_id in event_ids:
                result.append(activity)
        return result

    def _evidence_gaps(
        self,
        requests: list[ScenarioRequest],
        events: list[DevelopmentEvent],
        catalog: list[EvidenceCatalogEntry],
    ) -> list[EvidenceGapItem]:
        gaps: list[EvidenceGapItem] = []
        for request in requests:
            for missing in request.missing_evidence:
                gaps.append(
                    EvidenceGapItem(
                        kind="missing_evidence",
                        kind_ko="누락 근거",
                        ref_id=request.id,
                        description=f"요청 '{request.title}'에 필요한 근거가 없음: {missing}",
                        source_refs=request.source_refs,
                    )
                )
        for entry in catalog:
            if entry.availability != "available":
                gaps.append(
                    EvidenceGapItem(
                        kind="unavailable_catalog",
                        kind_ko="미가용 근거",
                        ref_id=entry.id,
                        description=(
                            f"근거 '{entry.title}' 가용성 {entry.availability} — {entry.known_limitation}"
                        ),
                        source_refs=[entry.source_ref],
                    )
                )
        for event in events:
            for need in event.required_evidence:
                if need.availability != "available":
                    description = f"이벤트 '{event.title}'의 요구 근거 미충족: {need.reason}"
                    if need.blocks_confidence_above:
                        description += f" (확신도 상한 {need.blocks_confidence_above})"
                    gaps.append(
                        EvidenceGapItem(
                            kind=(
                                "confidence_blocked"
                                if need.blocks_confidence_above
                                else "required_evidence_open"
                            ),
                            kind_ko=(
                                "확신도 차단" if need.blocks_confidence_above else "요구 근거 미충족"
                            ),
                            ref_id=need.evidence_need_id,
                            description=description,
                            source_refs=need.source_refs,
                        )
                    )
        return gaps

    def _timeline(
        self,
        events: list[DevelopmentEvent],
        activities: list[RoleActivity],
        requests: list[ScenarioRequest],
    ) -> list[TimelineItem]:
        items: list[TimelineItem] = []
        milestone_ids: set[str] = set()
        for event in events:
            if event.week is not None:
                items.append(
                    TimelineItem(
                        week=event.week,
                        item_type="event",
                        item_type_ko="개발 이벤트",
                        ref_id=event.id,
                        title=event.title,
                        project_id=event.project_id,
                        severity=event.severity,
                        status=event.status,
                        roles=event.roles_involved,
                    )
                )
            milestone_ids.update(event.linked_milestone_ids)
        for activity in activities:
            items.append(
                TimelineItem(
                    week=activity.week,
                    item_type="activity",
                    item_type_ko="역할 활동",
                    ref_id=activity.id,
                    title=activity.title,
                    project_id=activity.project_id,
                    roles=[activity.role_id],
                )
            )
        for request in requests:
            items.append(
                TimelineItem(
                    week=request.requested_week,
                    item_type="request",
                    item_type_ko="시나리오 요청",
                    ref_id=request.id,
                    title=request.title,
                    project_id=request.origin_project_id,
                    status=request.status,
                    roles=request.role_relevance,
                )
            )
        for milestone_id in milestone_ids:
            milestone = self._repo.get("project_milestones", milestone_id)
            if isinstance(milestone, ProjectMilestone) and milestone.week is not None:
                items.append(
                    TimelineItem(
                        week=milestone.week,
                        item_type="milestone",
                        item_type_ko="마일스톤",
                        ref_id=milestone.id,
                        title=milestone.title,
                        project_id=milestone.project_id,
                        roles=milestone.relevant_roles,
                    )
                )
        return sorted(items, key=lambda item: (item.week, item.item_type, item.ref_id))

    def analyze(self, scenario_id: str) -> ScenarioAnalysis:
        scenario = self._scenario(scenario_id)
        group = self._repo.get("scenario_groups", scenario.scenario_group_id)
        variants = [
            v
            for v in self._repo.list("variants")
            if isinstance(v, Variant) and v.scenario_id == scenario_id
        ]
        kpis = [
            k
            for k in self._repo.list("kpi_definitions")
            if isinstance(k, KPIDefinition) and k.id in set(scenario.primary_kpis)
        ]
        requests = self._related_requests(scenario_id)
        request_ids = {r.id for r in requests}
        events = self._related_events(scenario_id, request_ids)
        event_ids = {e.id for e in events}
        activities = self._related_activities(scenario_id, event_ids)
        issues = [
            i
            for i in self._repo.list("issues")
            if isinstance(i, Issue) and scenario_id in i.affected_scope.scenarios
        ]
        catalog = [
            e
            for e in self._repo.list("evidence_catalog")
            if isinstance(e, EvidenceCatalogEntry) and e.scenario_id == scenario_id
        ]
        measurement_evidence = [
            m
            for m in self._repo.list("measurement_evidence")
            if isinstance(m, MeasurementEvidence) and m.scenario_id == scenario_id
        ]
        measurement_requirements = [
            m
            for m in self._repo.list("measurement_requirements")
            if isinstance(m, MeasurementRequirement) and m.scenario_id == scenario_id
        ]

        assert group is None or isinstance(group, ScenarioGroup)
        return ScenarioAnalysis(
            scenario=scenario,
            scenario_group=group,
            variants=variants,
            kpis=kpis,
            requests=requests,
            events=events,
            activities=activities,
            issues=issues,
            evidence_catalog=catalog,
            measurement_evidence=measurement_evidence,
            measurement_requirements=measurement_requirements,
            evidence_gaps=self._evidence_gaps(requests, events, catalog),
            timeline=self._timeline(events, activities, requests),
        )
