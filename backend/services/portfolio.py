"""포트폴리오 현황 서비스 — U/V/W 주의 lane 파생 뷰 (저장하지 않음).

56 Stage 44 Portfolio Review Board의 개념을 승계하되 결정론 파생 뷰로만 계산한다.
수치 점수·결정 자동화·담당자 할당 없음.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import DevelopmentEvent
from backend.ontology.project import Project, ProjectScenarioFocus
from backend.ontology.scenario import Scenario, ScenarioGroup, ScenarioRequest


class AttentionItem(BaseModel):
    """주의 항목 — lane별 소스 연결 항목. 점수 없음, 결정 아님."""

    model_config = ConfigDict(extra="forbid")

    lane: str
    lane_ko: str
    ref_id: str
    ref_collection: str
    title: str
    description: str
    project_ids: list[str] = []
    suggested_review_roles: list[str] = []
    source_refs: list[str] = []


class ProjectSummary(BaseModel):
    """프로젝트 요약."""

    model_config = ConfigDict(extra="forbid")

    project: Project
    milestone_count: int
    open_request_count: int
    event_count: int
    focuses: list[ProjectScenarioFocus]


class ScenarioCell(BaseModel):
    """시나리오 × 프로젝트 매트릭스 셀."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    scenario_name: str
    scenario_group_id: str
    project_ids: list[str]
    request_count: int
    event_count: int
    gap_count: int


class PortfolioOverview(BaseModel):
    """포트폴리오 현황 파생 뷰."""

    model_config = ConfigDict(extra="forbid")

    projects: list[ProjectSummary]
    attention: list[AttentionItem]
    matrix: list[ScenarioCell]


LANE_LABELS: dict[str, str] = {
    "evidence_blocked": "근거 부족",
    "definition_needed": "정의 필요",
    "confidence_blocked": "확신도 차단",
    "propagation_review": "전파 검토",
    "de_risk_candidate": "리스크 해소 후보",
    "management_attention": "경영 주의",
}


class PortfolioService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def _attention(self) -> list[AttentionItem]:
        items: list[AttentionItem] = []

        requests = [r for r in self._repo.list("scenario_requests") if isinstance(r, ScenarioRequest)]
        events = [e for e in self._repo.list("development_events") if isinstance(e, DevelopmentEvent)]

        # 근거 부족 — 요청의 누락 근거
        for request in requests:
            for missing in request.missing_evidence:
                items.append(
                    AttentionItem(
                        lane="evidence_blocked",
                        lane_ko=LANE_LABELS["evidence_blocked"],
                        ref_id=request.id,
                        ref_collection="scenario_requests",
                        title=request.title,
                        description=f"누락 근거: {missing}",
                        project_ids=[request.origin_project_id],
                        suggested_review_roles=request.role_relevance,
                        source_refs=request.source_refs,
                    )
                )

        # 정의 필요 — 그룹이 참조하지만 카탈로그에 없는 시나리오
        scenario_ids = self._repo.ids("scenarios")
        for group in self._repo.list("scenario_groups"):
            assert isinstance(group, ScenarioGroup)
            for referenced in group.scenarios:
                if referenced not in scenario_ids:
                    items.append(
                        AttentionItem(
                            lane="definition_needed",
                            lane_ko=LANE_LABELS["definition_needed"],
                            ref_id=group.id,
                            ref_collection="scenario_groups",
                            title=group.name,
                            description=f"그룹이 참조하는 시나리오 '{referenced}'가 미정의 상태",
                        )
                    )

        for event in events:
            # 확신도 차단 — 요구 근거가 확신도 상한을 거는 경우
            for need in event.required_evidence:
                if need.blocks_confidence_above and need.availability != "available":
                    items.append(
                        AttentionItem(
                            lane="confidence_blocked",
                            lane_ko=LANE_LABELS["confidence_blocked"],
                            ref_id=event.id,
                            ref_collection="development_events",
                            title=event.title,
                            description=(
                                f"근거 '{need.evidence_need_id}' 미가용 — "
                                f"확신도 상한 {need.blocks_confidence_above}: {need.reason}"
                            ),
                            project_ids=[event.project_id],
                            suggested_review_roles=event.roles_involved,
                            source_refs=need.source_refs,
                        )
                    )
            # 리스크 해소 후보 — 후보 옵션이 검토 대기 중인 이벤트
            for option in event.candidate_options:
                items.append(
                    AttentionItem(
                        lane="de_risk_candidate",
                        lane_ko=LANE_LABELS["de_risk_candidate"],
                        ref_id=event.id,
                        ref_collection="development_events",
                        title=option.title,
                        description=(
                            f"이벤트 '{event.title}'의 후보 옵션 검토 대기"
                            + (f" — 자세: {option.current_posture}" if option.current_posture else "")
                        ),
                        project_ids=[event.project_id],
                        suggested_review_roles=event.roles_involved,
                        source_refs=option.source_refs,
                    )
                )

        # 전파 검토 — 프로젝트 간 전파 레코드 (인과 증명 아님)
        for request in requests:
            for propagation in request.propagation:
                items.append(
                    AttentionItem(
                        lane="propagation_review",
                        lane_ko=LANE_LABELS["propagation_review"],
                        ref_id=propagation.propagation_id,
                        ref_collection="scenario_requests",
                        title=request.title,
                        description=(
                            f"{propagation.from_project_id} → {propagation.to_project_id} "
                            f"(W{propagation.at_week}, {propagation.propagation_type}): "
                            f"{propagation.relation_summary}"
                        ),
                        project_ids=[propagation.from_project_id, propagation.to_project_id],
                        suggested_review_roles=[propagation.trigger_role],
                        source_refs=request.source_refs,
                    )
                )

        # 경영 주의 — P1 + 경영 관심사 명시 요청
        for request in requests:
            if request.priority == "P1" and request.management_interest not in ("", "none"):
                items.append(
                    AttentionItem(
                        lane="management_attention",
                        lane_ko=LANE_LABELS["management_attention"],
                        ref_id=request.id,
                        ref_collection="scenario_requests",
                        title=request.title,
                        description=f"경영 관심사: {request.management_interest} (P1, {request.status})",
                        project_ids=[request.origin_project_id],
                        suggested_review_roles=["management", *request.trigger_roles],
                        source_refs=request.source_refs,
                    )
                )

        return items

    def _matrix(self) -> list[ScenarioCell]:
        cells: list[ScenarioCell] = []
        requests = [r for r in self._repo.list("scenario_requests") if isinstance(r, ScenarioRequest)]
        events = [e for e in self._repo.list("development_events") if isinstance(e, DevelopmentEvent)]
        for scenario in self._repo.list("scenarios"):
            assert isinstance(scenario, Scenario)
            related_requests = [
                r for r in requests if scenario.id == r.scenario_id or scenario.id in r.scenario_ids
            ]
            related_events = [e for e in events if scenario.id in e.linked_scenario_ids]
            gap_count = sum(len(r.missing_evidence) for r in related_requests) + sum(
                1
                for e in related_events
                for need in e.required_evidence
                if need.availability != "available"
            )
            cells.append(
                ScenarioCell(
                    scenario_id=scenario.id,
                    scenario_name=scenario.name,
                    scenario_group_id=scenario.scenario_group_id,
                    project_ids=scenario.project_relevance,
                    request_count=len(related_requests),
                    event_count=len(related_events),
                    gap_count=gap_count,
                )
            )
        return cells

    def overview(self) -> PortfolioOverview:
        summaries: list[ProjectSummary] = []
        for project in self._repo.list("projects"):
            assert isinstance(project, Project)
            milestones = [
                m for m in self._repo.list("project_milestones") if m.project_id == project.id  # type: ignore[attr-defined]
            ]
            open_requests = [
                r
                for r in self._repo.list("scenario_requests")
                if isinstance(r, ScenarioRequest)
                and r.origin_project_id == project.id
                and r.status not in ("closed", "done")
            ]
            events = [
                e
                for e in self._repo.list("development_events")
                if isinstance(e, DevelopmentEvent) and e.project_id == project.id
            ]
            focuses = [
                f
                for f in self._repo.list("project_scenario_focuses")
                if isinstance(f, ProjectScenarioFocus) and f.project_id == project.id
            ]
            summaries.append(
                ProjectSummary(
                    project=project,
                    milestone_count=len(milestones),
                    open_request_count=len(open_requests),
                    event_count=len(events),
                    focuses=focuses,
                )
            )
        return PortfolioOverview(
            projects=summaries, attention=self._attention(), matrix=self._matrix()
        )
