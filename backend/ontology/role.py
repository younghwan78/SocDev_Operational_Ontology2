"""role 모듈: role agent 정의, 주간 활동, 런타임 출력 계약."""

from __future__ import annotations

from pydantic import Field

from backend.ontology.common import (
    Confidence,
    GroundedStatement,
    OntologyModel,
    OntologyObject,
)


class UIIdentity(OntologyModel):
    """역할의 UI 표현 정체성."""

    visual_concept: str | None = None
    icon_keywords: list[str] = Field(default_factory=list)


class RoleAgent(OntologyObject):
    """Role agent 정의 — 7개 고정 역할 (CLAUDE.md §2.2)."""

    name: str
    role_type: str
    includes_verification: bool = False
    goals: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    primary_concerns: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    feedback_targets: list[str] = Field(default_factory=list)
    ui_identity: UIIdentity = Field(default_factory=UIIdentity)


class ActivityInputContext(OntologyModel):
    """활동 입력 컨텍스트 — 어떤 fixture 근거로 검토했는지."""

    event_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    milestone_ids: list[str] = Field(default_factory=list)
    propagation_ids: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    candidate_option_ids: list[str] = Field(default_factory=list)
    required_evidence_need_ids: list[str] = Field(default_factory=list)
    decision_question_ref: bool = False


class EvidenceAssessment(OntologyModel):
    """근거 평가 — 개별 근거의 한계와 역할 해석."""

    evidence_id: str | None = None
    assessment: str
    limitation: str | None = None
    missing_information_ref: str | None = None
    role_interpretation: str | None = None


class OptionAssessment(OntologyModel):
    """옵션 평가 — 역할 관점의 후보 옵션 검토."""

    option_id: str
    role_posture: str
    rationale: str
    blockers: list[str] = Field(default_factory=list)
    expected_impact: dict[str, str] = Field(default_factory=dict)


class ConfidencePosture(OntologyModel):
    """확신도 자세 — 수준/방향/차단 요인."""

    level: Confidence
    direction: str
    rationale: str
    blocked_by: list[str] = Field(default_factory=list)


class ActivityRecommendation(OntologyModel):
    """활동 권고 — 최종 결정이 아닌 검토 권고."""

    recommendation_type: str
    summary: str
    target_roles: list[str] = Field(default_factory=list)
    not_final_decision: bool = True


class SafetyFlags(OntologyModel):
    """활동의 안전 플래그 — 자동 결정/실행이 아님을 명시."""

    fixture_derived: bool = True
    not_agent_execution: bool = True
    not_final_decision: bool = True
    read_only: bool = True


class ActivityTraceability(OntologyModel):
    """활동 traceability — 출처와 도출 과정."""

    source_refs: list[str] = Field(default_factory=list)
    description_derivation: str
    not_causal_proof: bool = True


class RoleActivity(OntologyObject):
    """역할 주간 활동 — 이벤트 검토의 역할별 기록."""

    role_id: str
    project_id: str
    week: int
    title: str
    summary: str
    activity_type: str
    expected_output: str
    linked_event_id: str
    linked_scenario_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    linked_milestone_ids: list[str] = Field(default_factory=list)
    linked_request_ids: list[str] = Field(default_factory=list)
    linked_propagation_ids: list[str] = Field(default_factory=list)
    input_context: ActivityInputContext
    observations: list[GroundedStatement] = Field(default_factory=list)
    concerns: list[GroundedStatement] = Field(default_factory=list)
    evidence_assessment: list[EvidenceAssessment] = Field(default_factory=list)
    option_assessments: list[OptionAssessment] = Field(default_factory=list)
    confidence_posture: ConfidencePosture
    recommendation: ActivityRecommendation
    follow_up_actions: list[str] = Field(default_factory=list)
    handoff_to_roles: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    safety: SafetyFlags = Field(default_factory=SafetyFlags)
    traceability: ActivityTraceability


class FeedbackItem(OntologyModel):
    """HW/SW 개발 → System Engineering/SoC Architecture 피드백 (런타임 계약)."""

    target_role: str
    description: str
    description_derivation: str
    supporting_basis: list[str] = Field(default_factory=list)
    confidence: Confidence


class RoleOutput(OntologyModel):
    """Role agent 런타임 출력 계약 — Stage 5 advisory의 스키마 (fixture 없음)."""

    run_id: str
    event_id: str
    role_id: str
    summary: str
    concerns: list[GroundedStatement] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    risk_assessment: str | None = None
    cost_impact: dict[str, str] = Field(default_factory=dict)
    recommendation: str
    confidence: Confidence
    missing_information: list[str] = Field(default_factory=list)
    feedback_items: list[FeedbackItem] = Field(default_factory=list)
    derivation_summary: str | None = None
