"""event 모듈: 개발 이벤트(구 event + development_event 통합 계약), 이슈, 검증 테스트."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from backend.ontology.common import Confidence, OntologyModel, OntologyObject


class ConfidenceSignal(OntologyModel):
    """이벤트가 주는 확신도 신호 — 방향과 근거."""

    direction: str
    reason: str
    basis: str | None = None


class CandidateOption(OntologyModel):
    """검토 후보 옵션 — 결정이 아닌 검토 대상."""

    option_id: str
    title: str
    description: str | None = None
    option_type: str | None = None
    current_posture: str | None = None
    feasibility: str | None = None
    known_risks: list[str] = Field(default_factory=list)
    qualitative_impact: dict[str, str] = Field(default_factory=dict)
    related_ip_ids: list[str] = Field(default_factory=list)
    related_scenario_ids: list[str] = Field(default_factory=list)
    required_evidence_need_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    target_project_id: str | None = None


class DecisionQuestion(OntologyModel):
    """이벤트가 제기하는 결정 질문 — 최종 결정이 아님."""

    question_id: str
    question: str
    scopes: list[str] = Field(default_factory=list)
    required_by_week: int | None = None
    not_final_decision: bool = True
    source_refs: list[str] = Field(default_factory=list)


class EventRelations(OntologyModel):
    """이벤트 간 관계 — 인과 증명이 아닌 유래/전파/검증 연결."""

    predecessor_event_ids: list[str] = Field(default_factory=list)
    derived_from_event_ids: list[str] = Field(default_factory=list)
    propagation_event_ids: list[str] = Field(default_factory=list)
    supersedes_event_ids: list[str] = Field(default_factory=list)
    validation_event_ids: list[str] = Field(default_factory=list)
    not_causal_proof: bool = True


class ExpectedReviewOutput(OntologyModel):
    """이벤트 검토의 기대 산출물."""

    output_type: str
    description: str
    not_final_decision: bool = True


class RequiredEvidenceNeed(OntologyModel):
    """검토에 필요한 근거 요구 — 가용성과 확신도 상한을 명시."""

    evidence_need_id: str
    evidence_type: str
    reason: str
    availability: str
    blocks_confidence_above: str | None = None
    linked_evidence_ids: list[str] = Field(default_factory=list)
    related_option_ids: list[str] = Field(default_factory=list)
    required_by_week: int | None = None
    review_impact: str | None = None
    source_refs: list[str] = Field(default_factory=list)


class DevelopmentEvent(OntologyObject):
    """개발 이벤트 — 마일스톤/이슈/검토/전파 등 개발 과정의 사건 단위.

    56의 event(구 MVP)와 development_event(Stage36) 계약을 통합했다.
    구 event는 week/quarter가 없으므로 해당 필드는 optional이다.
    """

    project_id: str
    title: str
    description: str
    event_type: str
    event_category: str
    lifecycle_stage: str | None = None
    week: int | None = None
    quarter: str | None = None
    severity: str = "info"
    status: str = "recorded"
    schedule_signal: str | None = None
    roles_involved: list[str] = Field(default_factory=list)
    affected_domains: list[str] = Field(default_factory=list)
    # 명시 IP 링크 (L8 해소) — 있으면 affected_domains 토큰 휴리스틱보다 우선한다.
    # 56 유래 데이터는 이 필드 없이 통과한다 (반입/커넥터 경로가 채우는 필드).
    related_ip_ids: list[str] = Field(default_factory=list)
    linked_scenario_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    linked_milestone_ids: list[str] = Field(default_factory=list)
    linked_request_ids: list[str] = Field(default_factory=list)
    linked_propagation_ids: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    resource_signal: list[str] = Field(default_factory=list)
    confidence_signal: ConfidenceSignal | None = None
    source_basis: list[str] = Field(default_factory=list)
    requested_by: str | None = None
    candidate_options: list[CandidateOption] = Field(default_factory=list)
    decision_question: DecisionQuestion | None = None
    event_relations: EventRelations | None = None
    expected_review_output: ExpectedReviewOutput | None = None
    required_evidence: list[RequiredEvidenceNeed] = Field(default_factory=list)
    review_posture: str | None = None
    not_final_decision: bool = True
    read_only: bool = True


class AffectedScope(OntologyModel):
    """이슈 영향 범위."""

    scenarios: list[str] = Field(default_factory=list)
    ip_blocks: list[str] = Field(default_factory=list)
    system_blocks: list[str] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)


class RootCauseType(StrEnum):
    """근본 원인 유형 — 원점 문서 분류 승계 (Stage 10)."""

    ARCHITECTURE_MISS = "architecture_miss"
    SPEC_AMBIGUITY = "spec_ambiguity"
    VERIFICATION_GAP = "verification_gap"
    POWER_MODEL_ERROR = "power_model_error"
    SW_WORKAROUND_DEPENDENCY = "sw_workaround_dependency"
    CUSTOMER_SCENARIO_MISMATCH = "customer_scenario_mismatch"


class RootCause(OntologyModel):
    """구조화된 근본 원인 — 유형/서술/확신도/근거."""

    cause_type: RootCauseType
    description: str
    confidence: Confidence
    evidence_refs: list[str] = Field(default_factory=list)


class Test(OntologyObject):
    """검증 테스트 — 이슈 해결과 시나리오 동작을 검증하는 실행 단위."""

    title: str
    test_type: str  # regression | scenario | cts_vts | power
    result: str  # passed | failed | blocked | planned
    project_id: str
    summary: str
    linked_scenario_ids: list[str] = Field(default_factory=list)
    verifies_issue_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    executed_week: int | None = None


class Issue(OntologyObject):
    """개발 이슈 — 증상/근본원인/조치/검증/잔존 리스크/교훈 (RCA 체인)."""

    project_id: str
    title: str
    issue_type: str
    status: str
    # 이슈 자체 심각도 (optional) — 위험 룰이 이벤트 심각도 대신 사용할 수 있다.
    # 56 유래 데이터는 이 필드 없이 통과한다.
    severity: str | None = None
    symptom: str
    confidence: Confidence
    evidence_refs: list[str] = Field(default_factory=list)
    root_cause_candidates: list[str] = Field(default_factory=list)
    affected_scope: AffectedScope = Field(default_factory=AffectedScope)
    # Stage 10 RCA 확장 — 56 유래 이슈는 아래 필드 없이 통과한다.
    root_causes: list[RootCause] = Field(default_factory=list)
    fix_type: str | None = None  # hw_fix | sw_fix | tuning | spec_change | process_change | none
    fix_description: str | None = None
    workaround: str | None = None
    verifying_test_ids: list[str] = Field(default_factory=list)
    residual_risk: str | None = None
    reusable_lesson: str | None = None
    resolved_week: int | None = None
    # J3 신선도·일정 (optional — 56 유래 데이터는 없이 통과, 14_ingest_reality_gaps.md §2):
    # 사내 JIRA의 updated/duedate에서 유도(반입은 ISO 주차, synthetic은 우주 주차).
    # 정체/지연 판정은 서비스 계층의 결정론 룰 — 여기 저장하지 않는다.
    updated_week: int | None = None
    due_week: int | None = None
