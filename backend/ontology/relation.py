"""relation 모듈: 온톨로지 관계, 시뮬레이션 실행 기록."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.ontology.common import Confidence, OntologyObject


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
    """시뮬레이션 실행 기록 — 56 PoC 산출물 보존용 (Stage 5에서 AgentRun으로 대체 예정)."""

    project_id: str
    event_id: str
    status: str
    expected_outputs: dict[str, Any] = Field(default_factory=dict)
