"""온톨로지 v1.0 계약 — Pydantic 모델이 단일 소스다.

COLLECTIONS: fixture 컬렉션 키 → (모듈명, 저장 객체 모델) 레지스트리.
fixtures/<module>.yaml 파일 안에 해당 모듈의 컬렉션들이 들어간다.
"""

from __future__ import annotations

from backend.ontology.common import (
    Confidence,
    GroundedStatement,
    OntologyModel,
    OntologyObject,
    SourceMeta,
    SourceOrigin,
)
from backend.ontology.decision import ActionItem, Decision, ReviewPack
from backend.ontology.event import DevelopmentEvent, Issue, KPIObservation, Test
from backend.ontology.evidence import (
    Evidence,
    EvidenceCatalogEntry,
    MeasurementEvidence,
    MeasurementRequirement,
    SemanticChunk,
    SemanticVector,
)
from backend.ontology.ip import IPBaseSpec, IPBlock, IPCapability, IPDependencyRule, IPKnob
from backend.ontology.project import (
    CustomerRequest,
    Project,
    ProjectLink,
    ProjectMilestone,
    ProjectScenarioFocus,
)
from backend.ontology.relation import AgentRun, Relation, SimulationRun
from backend.ontology.role import RoleActivity, RoleAdvisory, RoleAgent, RoleOutput
from backend.ontology.scenario import (
    KPIDefinition,
    Scenario,
    ScenarioGroup,
    ScenarioIPRequirement,
    ScenarioRequest,
    Variant,
)

# 컬렉션 키 → (fixture 모듈명, 모델). 모듈명이 fixtures/<모듈명>.yaml 파일명이 된다.
COLLECTIONS: dict[str, tuple[str, type[OntologyObject]]] = {
    "projects": ("project", Project),
    "project_milestones": ("project", ProjectMilestone),
    "customer_requests": ("project", CustomerRequest),
    "project_links": ("project", ProjectLink),
    "project_scenario_focuses": ("project", ProjectScenarioFocus),
    "kpi_definitions": ("scenario", KPIDefinition),
    "scenario_groups": ("scenario", ScenarioGroup),
    "scenarios": ("scenario", Scenario),
    "variants": ("scenario", Variant),
    "scenario_ip_requirements": ("scenario", ScenarioIPRequirement),
    "scenario_requests": ("scenario", ScenarioRequest),
    "ip_blocks": ("ip", IPBlock),
    "ip_base_specs": ("ip", IPBaseSpec),
    "ip_capabilities": ("ip", IPCapability),
    "ip_knobs": ("ip", IPKnob),
    "ip_dependency_rules": ("ip", IPDependencyRule),
    "development_events": ("event", DevelopmentEvent),
    "issues": ("event", Issue),
    "tests": ("event", Test),
    "kpi_observations": ("event", KPIObservation),
    "evidence": ("evidence", Evidence),
    "evidence_catalog": ("evidence", EvidenceCatalogEntry),
    "measurement_evidence": ("evidence", MeasurementEvidence),
    "measurement_requirements": ("evidence", MeasurementRequirement),
    "semantic_chunks": ("evidence", SemanticChunk),
    "semantic_vectors": ("evidence", SemanticVector),
    "roles": ("role", RoleAgent),
    "role_activities": ("role", RoleActivity),
    "decisions": ("decision", Decision),
    "action_items": ("decision", ActionItem),
    "review_packs": ("decision", ReviewPack),
    "relations": ("relation", Relation),
    "simulation_runs": ("relation", SimulationRun),
}

# 런타임 전용 계약 (fixture 없음) — 스키마 export 대상에는 포함한다.
RUNTIME_CONTRACTS: dict[str, type[OntologyModel]] = {
    "role_output": RoleOutput,
    "grounded_statement": GroundedStatement,
    "role_advisory": RoleAdvisory,
    "agent_run": AgentRun,
}

__all__ = [
    "COLLECTIONS",
    "RUNTIME_CONTRACTS",
    "Confidence",
    "GroundedStatement",
    "OntologyModel",
    "OntologyObject",
    "SourceMeta",
    "SourceOrigin",
]
