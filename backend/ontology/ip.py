"""ip 모듈: IP 블록, IP 기본 스펙/capability/knob, IP 의존 규칙."""

from __future__ import annotations

from pydantic import Field

from backend.ontology.common import Confidence, OntologyObject


class IPBlock(OntologyObject):
    """IP 블록 — functional MM IP 또는 system influence block."""

    name: str
    category: str
    domain: str
    aliases: list[str] = Field(default_factory=list)
    notes: str | None = None
    rt_relevant: bool = False


class IPBaseSpec(OntologyObject):
    """IP 기본 스펙 — 커널 드라이버 유래의 구조화 스펙."""

    ip_id: str
    spec_id: str
    display_name: str
    domain: str
    driver_name: str
    driver_path: str
    internal_blocks: list[str] = Field(default_factory=list)
    supported_modes: list[str] = Field(default_factory=list)
    dvfs_or_control_domains: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    knobs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    source_ref: str


class IPCapability(OntologyObject):
    """IP capability — 지원 기능/조건/값."""

    ip_id: str
    name: str
    category: str
    support_status: str
    condition: str | None = None
    confidence: Confidence
    value: str | None = None
    values: list[str] = Field(default_factory=list)
    unit: str | None = None
    aliases: list[str] = Field(default_factory=list)
    source_ref: str


class IPKnob(OntologyObject):
    """IP knob — 전력/지연/대역폭/리스크 방향성을 갖는 제어 항목."""

    ip_id: str
    name: str
    category: str
    description: str
    control_domain: str
    power_direction: str
    latency_direction: str
    bandwidth_direction: str
    risk_direction: str
    affected_kpis: list[str] = Field(default_factory=list)
    related_scenarios: list[str] = Field(default_factory=list)
    confidence: Confidence
    source_ref: str


class IPDependencyRule(OntologyObject):
    """IP 간 의존 규칙 — 조건부 동작 의존성."""

    ip_id: str
    depends_on_ip_id: str
    relationship: str
    condition: str
    rationale: str
    confidence: Confidence
    source_ref: str
