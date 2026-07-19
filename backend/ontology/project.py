"""project 모듈: 프로젝트, 마일스톤, 고객 요구, 프로젝트 연결, 시나리오 포커스."""

from __future__ import annotations

from pydantic import Field

from backend.ontology.common import OntologyModel, OntologyObject


class Project(OntologyObject):
    """SoC 개발 프로젝트 (U: 양산 N / V: N+1 / W: N+2 스펙 탐색)."""

    name: str
    type: str
    phase: str
    key_themes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    silicon_status: str | None = None
    customer_stage: str | None = None
    hw_status: str | None = None
    sw_status: str | None = None
    spec_status: str | None = None
    target_product_generation: str | None = None


class GateCriterion(OntologyModel):
    """마일스톤 exit 기준 — 결정론 판정 가능한 조건 (설계 23 §2).

    판정(충족/미충족/판정 불가)은 서비스 계층의 파생 뷰다 — 여기 저장하지
    않는다. 점수·가중치·자동 차단 없음: 게이트는 판정을 보여줄 뿐이다.
    """

    criterion_id: str
    kind: str  # gate_criterion_kind 도메인: max_open_issues | required_evidence | verified_closure
    description: str
    # kind별 파라미터 — 해당 kind에서만 의미를 갖는다.
    max_open_issues: int | None = None  # max_open_issues: 허용 상한 (기본 0)
    min_severity: str | None = None  # max_open_issues: 이 심각도 이상만 계수
    evidence_types: list[str] = Field(default_factory=list)  # required_evidence
    scenario_ids: list[str] = Field(default_factory=list)  # 범위 제한 — 비면 프로젝트 전체


class ProjectMilestone(OntologyObject):
    """프로젝트 마일스톤 — 주차/분기 기반 개발 일정 앵커."""

    project_id: str
    title: str
    description: str
    milestone_type: str
    lifecycle_stage: str
    decision_window: str
    week: int | None = None
    quarter: str | None = None
    relevant_roles: list[str] = Field(default_factory=list)
    source_basis: list[str] = Field(default_factory=list)
    historical_relation: str | None = None
    timeline_scope: str | None = None
    # 설계 23: exit 기준 (additive) — 56 유래 데이터는 이 필드 없이 통과한다.
    exit_criteria: list[GateCriterion] = Field(default_factory=list)


class CustomerRequest(OntologyObject):
    """고객 요구 — 시나리오/KPI 개선 요구의 출발점."""

    project_id: str
    title: str
    request_type: str
    evidence_level: int
    related_scenario_groups: list[str] = Field(default_factory=list)
    target_improvement: str | None = None
    target_kpis: list[str] = Field(default_factory=list)


class ProjectLink(OntologyObject):
    """프로젝트 간 연결 — 이슈/교훈/요구의 전파 경로."""

    from_project: str
    to_project: str
    link_type: str
    title: str
    related_scenario_groups: list[str] = Field(default_factory=list)


class WeekWindow(OntologyModel):
    """주차 구간."""

    start_week: int
    end_week: int


class StageWindow(OntologyModel):
    """개발 단계별 주차 구간과 측정 정책."""

    stage: str
    start_week: int
    end_week: int
    focus_types: list[str] = Field(default_factory=list)
    measurement_policy: str | None = None


class ProjectScenarioFocus(OntologyObject):
    """프로젝트가 특정 시나리오 그룹에 두는 연간 포커스."""

    project_id: str
    title: str
    priority: str
    objectives: list[str] = Field(default_factory=list)
    relevant_roles: list[str] = Field(default_factory=list)
    scenario_group_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    annual_horizon: WeekWindow
    development_stage_windows: list[StageWindow] = Field(default_factory=list)
