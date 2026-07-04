"""decision 모듈: 결정, 결정 옵션, 액션 아이템, 리뷰 팩."""

from __future__ import annotations

from pydantic import Field

from backend.ontology.common import Confidence, OntologyModel, OntologyObject


class DecisionOption(OntologyModel):
    """결정 옵션 — 이득/리스크/비용 영향."""

    id: str
    label: str
    benefits: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    cost_impact: dict[str, str] = Field(default_factory=dict)


class DecisionBasis(OntologyModel):
    """결정의 뒷받침 근거 항목."""

    basis_type: str
    ref_id: str
    statement: str
    confidence: Confidence


class Decision(OntologyObject):
    """결정 — 옵션/선택/트레이드오프/미해결 리스크를 기록."""

    project_id: str
    event_id: str
    decision_type: str
    options: list[DecisionOption] = Field(default_factory=list)
    selected_option: str
    tradeoff_summary: str
    supporting_basis: list[DecisionBasis] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)


class ActionItem(OntologyObject):
    """액션 아이템 — 결정에서 파생된 후속 작업."""

    source_decision_id: str
    title: str
    description: str
    owner_role: str
    due_phase: str
    status: str
    required_evidence: list[str] = Field(default_factory=list)


class DocRef(OntologyModel):
    """문서 참조."""

    document: str
    section: str | None = None


class ReviewPack(OntologyObject):
    """리뷰 팩 — 함께 검토할 프로젝트/시나리오 묶음 정의."""

    title: str
    purpose: str
    project_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    source_ref: DocRef
