"""evidence 모듈: 근거, 근거 카탈로그, 측정 근거/요구, 시맨틱 청크/벡터."""

from __future__ import annotations

from pydantic import Field

from backend.ontology.common import Confidence, OntologyModel, OntologyObject


class Evidence(OntologyObject):
    """근거 문서/진술 — 판단의 뒷받침 단위."""

    statement: str
    evidence_type: str
    source_type: str
    confidence: Confidence
    confidence_level: str
    project_id: str | None = None


class EvidenceCatalogEntry(OntologyObject):
    """근거 카탈로그 — 시나리오별 근거의 가용성/한계/기여도 목록."""

    project_id: str
    scenario_id: str
    title: str
    evidence_type: str
    availability: str
    confidence_contribution: str
    is_measurement: bool
    is_prediction: bool
    known_limitation: str
    measurement_stage: str
    scenario_match: str
    source_system: str
    source_ref: str
    week: int
    related_milestone_ids: list[str] = Field(default_factory=list)
    related_request_ids: list[str] = Field(default_factory=list)


class MeasurementEvidence(OntologyObject):
    """측정 근거 — 실측/예측 값과 한계를 갖는 근거."""

    project_id: str
    title: str
    evidence_type: str
    measurement_type: str
    event_id: str
    evidence_id: str
    scenario_id: str
    variant_id: str | None = None
    observed_value: float | str | None = None
    unit: str | None = None
    value_status: str
    qualitative_result: str
    confidence: Confidence
    source_kind: str
    source_ref: str
    limitations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    related_ip_ids: list[str] = Field(default_factory=list)
    related_knob_ids: list[str] = Field(default_factory=list)
    related_kpi_ids: list[str] = Field(default_factory=list)
    related_measurement_requirement_ids: list[str] = Field(default_factory=list)
    related_resource_profile_ids: list[str] = Field(default_factory=list)
    related_risk_basis_ids: list[str] = Field(default_factory=list)


class MeasurementRequirement(OntologyObject):
    """측정 요구 — 어떤 측정이 무엇을 위해 필요한지."""

    project_id: str
    title: str
    description: str
    measurement_type: str
    event_id: str
    scenario_id: str
    variant_id: str | None = None
    required_for: list[str] = Field(default_factory=list)
    related_evidence_gap_ids: list[str] = Field(default_factory=list)
    related_ip_ids: list[str] = Field(default_factory=list)
    related_knob_ids: list[str] = Field(default_factory=list)
    related_kpi_ids: list[str] = Field(default_factory=list)
    related_resource_profile_ids: list[str] = Field(default_factory=list)
    related_risk_basis_ids: list[str] = Field(default_factory=list)
    source_ref: str


class ChunkMetadata(OntologyModel):
    """시맨틱 청크 메타데이터."""

    decision_stage: str | None = None
    evidence_level: str | None = None
    retrieval_use: list[str] = Field(default_factory=list)
    source_confidence: str | None = None


class SemanticChunk(OntologyObject):
    """시맨틱 청크 — 검색 후보 텍스트. 증거가 아니라 supporting_basis 후보."""

    chunk_text: str
    source_id: str
    source_type: str
    project_id: str | None = None
    embedding_status: str
    evidence_confidence: str
    ip_ids: list[str] = Field(default_factory=list)
    kpi_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    scenario_group_ids: list[str] = Field(default_factory=list)
    system_block_ids: list[str] = Field(default_factory=list)
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)


class VectorMetadata(OntologyModel):
    """시맨틱 벡터 메타데이터 — 검색 결과의 지위 제한."""

    confidence_upgrade_allowed: bool = False
    not_evidence_proof: bool = True
    retrieval_role: str | None = None


class SemanticVector(OntologyObject):
    """시맨틱 벡터 — pgvector 적재 대상 (Stage 1에서는 fixture 보존만)."""

    chunk_id: str
    embedding: list[float]
    vector_model: str
    vector_dimension: int
    source_ref: str
    metadata: VectorMetadata = Field(default_factory=VectorMetadata)
