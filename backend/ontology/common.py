"""온톨로지 공통 기반: enum, 출처 메타데이터, 베이스 모델, 근거 문장 패턴."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SourceOrigin(StrEnum):
    """데이터 출처 구분 — 모든 저장 객체의 필수 속성."""

    SYNTHETIC = "synthetic"
    IMPORTED = "imported"
    INTEGRATED = "integrated"


class Confidence(StrEnum):
    """확신도 — evidence-grounded 출력의 공통 척도."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @classmethod
    def _missing_(cls, value: object) -> Confidence | None:
        """56 fixture의 축약 표기(H/M/L)와 대소문자 변형을 정규화한다."""
        if isinstance(value, str):
            normalized = {"h": "high", "m": "medium", "l": "low"}.get(
                value.lower(), value.lower()
            )
            for member in cls:
                if member.value == normalized:
                    return member
        return None


class SourceMeta(BaseModel):
    """객체 출처 메타데이터. 실데이터 반입 시 origin/ref로 계보를 추적한다."""

    model_config = ConfigDict(extra="forbid")

    origin: SourceOrigin = SourceOrigin.SYNTHETIC
    ref: str | None = None
    ingested_at: datetime | None = None


class OntologyModel(BaseModel):
    """모든 온톨로지 모델의 베이스. 계약 외 필드는 거부한다(드리프트 차단)."""

    model_config = ConfigDict(extra="forbid")


class OntologyObject(OntologyModel):
    """저장 객체 베이스: 고유 ID + 출처 메타데이터."""

    id: str
    source: SourceMeta = Field(default_factory=SourceMeta)


class GroundedStatement(OntologyModel):
    """근거 문장 — 서술/도출 과정/뒷받침 근거/확신도를 항상 함께 갖는다."""

    description: str
    description_derivation: str
    supporting_basis: list[str]
    confidence: Confidence
