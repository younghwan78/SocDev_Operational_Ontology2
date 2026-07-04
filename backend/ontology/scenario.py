"""scenario 모듈: KPI 정의, 시나리오 그룹/시나리오/변형, IP 요구, 시나리오 요청."""

from __future__ import annotations

from pydantic import Field

from backend.ontology.common import Confidence, OntologyModel, OntologyObject


class KPIDefinition(OntologyObject):
    """KPI 정의 — 방향(높을수록/낮을수록 좋음)과 단위를 갖는 지표."""

    group: str
    unit: str
    direction: str


class ScenarioGroup(OntologyObject):
    """시나리오 그룹 — 같은 목적/KPI 축을 공유하는 시나리오 묶음."""

    name: str
    purpose: str
    primary_kpis: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    feature_toggles: dict[str, list[bool]] | None = None
    variants: dict[str, list[str]] | None = None


class Scenario(OntologyObject):
    """개발 시나리오 — IP/시스템 블록/KPI와 연결되는 기술 단위."""

    name: str
    description: str
    domain: str
    scenario_class: str
    scenario_group_id: str
    primary_kpis: list[str] = Field(default_factory=list)
    project_relevance: list[str] = Field(default_factory=list)
    uses_ip_blocks: list[str] = Field(default_factory=list)
    depends_on_system_blocks: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    generation_path: list[str] = Field(default_factory=list)
    source_basis: list[str] = Field(default_factory=list)
    base_from_previous_project: bool = False
    derived_from_scenario_id: str | None = None
    customer_request_relevance: str
    development_relevance: str
    dou_relevance: str
    iq_relevance: str
    sustain_power_relevance: str
    hw_pipeline_change_sensitivity: str
    sw_control_complexity: str
    catalog_status: str | None = None
    legacy_aliases: list[str] = Field(default_factory=list)


class VariantStream(OntologyModel):
    """다중 스트림 변형의 개별 스트림 사양."""

    resolution: str
    fps: int


class Variant(OntologyObject):
    """시나리오 변형 — 해상도/fps/토글 등 구체 동작 조건."""

    scenario_id: str
    mode: str
    resolution: str | None = None
    fps: int | None = None
    toggles: dict[str, bool] = Field(default_factory=dict)
    streams: list[VariantStream] = Field(default_factory=list)
    operation: str | None = None
    operations: list[str] = Field(default_factory=list)
    ai_solution: str | None = None
    capture_mode: str | None = None
    dpu_clock_policy: str | None = None
    panel_mode: str | None = None


class ScenarioIPRequirement(OntologyObject):
    """시나리오가 IP에 요구하는 capability/모드."""

    scenario_id: str
    ip_id: str
    required_capability: str
    required_mode: str
    requirement_level: str
    rationale: str
    source_ref: str
    variant_id: str | None = None


class ProjectSpan(OntologyModel):
    """시나리오 요청이 각 프로젝트에 걸치는 주차 구간과 영향 방향."""

    project_id: str
    start_week: int
    end_week: int
    lifecycle_stage: str
    impact_direction: str
    posture: str
    evidence_status: str
    confidence: Confidence
    note: str | None = None


class Propagation(OntologyModel):
    """프로젝트 간 전파 — 인과 증명이 아닌 검토 연관(not_causal_proof)."""

    propagation_id: str
    from_project_id: str
    to_project_id: str
    at_week: int
    propagation_type: str
    trigger_role: str
    relation_summary: str
    not_causal_proof: bool = True


class ScenarioRequest(OntologyObject):
    """시나리오 요청 — 주간 검토 활동을 구동하는 요구 단위."""

    title: str
    request_type: str
    status: str
    priority: str
    confidence: Confidence
    origin_project_id: str
    scenario_id: str | None = None
    scenario_ids: list[str] = Field(default_factory=list)
    scenario_group_ids: list[str] = Field(default_factory=list)
    request_scope: str | None = None
    requested_by_role: str
    requested_week: int
    review_cadence: str
    domains: list[str] = Field(default_factory=list)
    role_relevance: list[str] = Field(default_factory=list)
    trigger_roles: list[str] = Field(default_factory=list)
    management_interest: str
    system_engineering_tracking_focus: str
    expected_weekly_activity_load: str
    evidence_basis: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    milestone_refs: list[str] = Field(default_factory=list)
    linked_focus_ids: list[str] = Field(default_factory=list)
    linked_review_pack_ids: list[str] = Field(default_factory=list)
    linked_review_report_scenario_id: str | None = None
    project_spans: list[ProjectSpan] = Field(default_factory=list)
    propagation: list[Propagation] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
