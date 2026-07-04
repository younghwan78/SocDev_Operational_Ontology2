"""relation 모듈: 온톨로지 관계, 시뮬레이션 실행 기록."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.ontology.common import Confidence, OntologyModel, OntologyObject
from backend.ontology.role import RoleAdvisory


class Relation(OntologyObject):
    """온톨로지 관계 — 객체 간 typed link. traceability의 골격."""

    source_id: str
    source_type: str
    relation_type: str
    target_id: str
    target_type: str
    confidence: Confidence
    basis: list[str] = Field(default_factory=list)
    description: str | None = None


class SimulationRun(OntologyObject):
    """시뮬레이션 실행 기록 — 56 PoC 산출물 보존용."""

    project_id: str
    event_id: str
    status: str
    expected_outputs: dict[str, Any] = Field(default_factory=dict)


class AgentRun(OntologyModel):
    """Advisory 실행 감사 기록 — 누가 언제 어떤 근거로 조언을 받았는지 (런타임 계약).

    provider/모델/입력 해시/검증 기록을 남긴다. 온톨로지 데이터가 아니라 감사 데이터다.
    """

    id: str
    scenario_id: str
    status: str  # completed | failed
    input_hash: str
    requested_roles: list[str] = Field(default_factory=list)
    advisories: list[RoleAdvisory] = Field(default_factory=list)
    validation_notes: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    created_at: str
