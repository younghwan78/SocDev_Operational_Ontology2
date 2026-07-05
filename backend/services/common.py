"""서비스 계층 공용 계약 — 파생 뷰가 공유하는 근거 항목 모델."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BasisItem(BaseModel):
    """판정/영향 근거 — 어떤 룰이 어떤 원본 객체 때문에 발화했는가."""

    model_config = ConfigDict(extra="forbid")

    rule: str
    rule_ko: str
    ref_id: str
    ref_collection: str
    description: str
    source_refs: list[str] = Field(default_factory=list)
