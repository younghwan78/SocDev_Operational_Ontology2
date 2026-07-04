"""In-memory repository — 테스트/개발 전용. 운영 저장소는 Stage 2 PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.loaders.yaml_loader import load_fixtures
from backend.ontology import OntologyObject
from backend.ontology.scenario import ScenarioRequest


class InMemoryRepository:
    """컬렉션 키 기반 조회 저장소."""

    def __init__(self, collections: dict[str, list[OntologyObject]]) -> None:
        self._collections = collections
        self._by_id: dict[str, dict[str, OntologyObject]] = {
            key: {obj.id: obj for obj in items} for key, items in collections.items()
        }

    @classmethod
    def from_fixtures(cls, fixtures_dir: Path) -> InMemoryRepository:
        return cls(load_fixtures(fixtures_dir))

    def collections(self) -> dict[str, list[OntologyObject]]:
        return self._collections

    def list(self, collection: str) -> list[OntologyObject]:
        return self._collections.get(collection, [])

    def get(self, collection: str, object_id: str) -> OntologyObject | None:
        return self._by_id.get(collection, {}).get(object_id)

    def ids(self, *collection_keys: str) -> set[str]:
        result: set[str] = set()
        for key in collection_keys:
            result.update(self._by_id.get(key, {}).keys())
        return result

    def propagation_ids(self) -> set[str]:
        """ScenarioRequest 내장 전파 레코드의 ID 집합."""
        result: set[str] = set()
        for request in self.list("scenario_requests"):
            assert isinstance(request, ScenarioRequest)
            result.update(p.propagation_id for p in request.propagation)
        return result


@dataclass
class Finding:
    """무결성 검사 결과 항목."""

    level: str  # "error" | "warning"
    message: str


def check_integrity(repo: InMemoryRepository) -> list[Finding]:
    """참조 무결성 검사.

    error: 반드시 해석되어야 하는 hard 참조.
    warning: 56 원본 데이터에서 의도적으로 느슨한 soft 참조
             (예: 시나리오의 variant 목록은 카탈로그가 일부만 존재).
    """
    findings: list[Finding] = []
    projects = repo.ids("projects")
    scenarios = repo.ids("scenarios")
    scenario_groups = repo.ids("scenario_groups")
    ip_blocks = repo.ids("ip_blocks")
    roles = repo.ids("roles")
    events = repo.ids("development_events")
    milestones = repo.ids("project_milestones")
    requests = repo.ids("scenario_requests")
    focuses = repo.ids("project_scenario_focuses")
    review_packs = repo.ids("review_packs")
    decisions = repo.ids("decisions")
    variants = repo.ids("variants")
    chunks = repo.ids("semantic_chunks")
    evidence_union = repo.ids("evidence", "evidence_catalog", "measurement_evidence")
    propagations = repo.propagation_ids()
    kpis = repo.ids("kpi_definitions")

    def require(
        collection: str, field: str, values: list[str], valid: set[str], level: str = "error"
    ) -> None:
        for value in values:
            if value not in valid:
                findings.append(
                    Finding(level, f"{collection}.{field}: 해석 불가 참조 '{value}'")
                )

    def field_values(obj: OntologyObject, field: str) -> list[str]:
        value = getattr(obj, field, None)
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    # project 참조 (hard)
    project_ref_fields: list[tuple[str, str]] = [
        ("project_milestones", "project_id"),
        ("customer_requests", "project_id"),
        ("project_scenario_focuses", "project_id"),
        ("development_events", "project_id"),
        ("issues", "project_id"),
        ("evidence_catalog", "project_id"),
        ("measurement_evidence", "project_id"),
        ("measurement_requirements", "project_id"),
        ("role_activities", "project_id"),
        ("decisions", "project_id"),
        ("simulation_runs", "project_id"),
        ("scenario_requests", "origin_project_id"),
        ("project_links", "from_project"),
        ("project_links", "to_project"),
        ("evidence", "project_id"),
        ("semantic_chunks", "project_id"),
    ]
    for collection, field in project_ref_fields:
        for obj in repo.list(collection):
            require(collection, field, field_values(obj, field), projects)

    # scenario / group / variant / ip 참조
    for obj in repo.list("scenarios"):
        require("scenarios", "scenario_group_id", field_values(obj, "scenario_group_id"), scenario_groups)
        require("scenarios", "uses_ip_blocks", field_values(obj, "uses_ip_blocks"), ip_blocks)
        require("scenarios", "depends_on_system_blocks", field_values(obj, "depends_on_system_blocks"), ip_blocks)
        require("scenarios", "variants", field_values(obj, "variants"), variants, level="warning")
        require("scenarios", "primary_kpis", field_values(obj, "primary_kpis"), kpis, level="warning")
    for obj in repo.list("scenario_groups"):
        require("scenario_groups", "scenarios", field_values(obj, "scenarios"), scenarios, level="warning")
    for obj in repo.list("variants"):
        require("variants", "scenario_id", field_values(obj, "scenario_id"), scenarios)
    for obj in repo.list("scenario_ip_requirements"):
        require("scenario_ip_requirements", "scenario_id", field_values(obj, "scenario_id"), scenarios)
        require("scenario_ip_requirements", "ip_id", field_values(obj, "ip_id"), ip_blocks)

    # ip 스펙 계층
    for collection in ("ip_base_specs", "ip_capabilities", "ip_knobs", "ip_dependency_rules"):
        for obj in repo.list(collection):
            require(collection, "ip_id", field_values(obj, "ip_id"), ip_blocks)
    for obj in repo.list("ip_dependency_rules"):
        require("ip_dependency_rules", "depends_on_ip_id", field_values(obj, "depends_on_ip_id"), ip_blocks)

    # 이벤트/활동의 연결 참조
    linked_targets: list[tuple[str, set[str], str]] = [
        ("linked_scenario_ids", scenarios | scenario_groups, "warning"),
        ("linked_evidence_ids", evidence_union, "error"),
        ("linked_milestone_ids", milestones, "error"),
        ("linked_request_ids", requests, "error"),
        ("linked_propagation_ids", propagations, "error"),
    ]
    for collection in ("development_events", "role_activities"):
        for obj in repo.list(collection):
            for field, valid, level in linked_targets:
                require(collection, field, field_values(obj, field), valid, level=level)
    for obj in repo.list("role_activities"):
        require("role_activities", "role_id", field_values(obj, "role_id"), roles)
        require("role_activities", "linked_event_id", field_values(obj, "linked_event_id"), events)

    # 결정/측정/시맨틱/요청 참조
    for obj in repo.list("decisions"):
        require("decisions", "event_id", field_values(obj, "event_id"), events)
    for obj in repo.list("action_items"):
        require("action_items", "source_decision_id", field_values(obj, "source_decision_id"), decisions)
    for obj in repo.list("measurement_evidence"):
        require("measurement_evidence", "event_id", field_values(obj, "event_id"), events)
        require("measurement_evidence", "scenario_id", field_values(obj, "scenario_id"), scenarios)
    for obj in repo.list("measurement_requirements"):
        require("measurement_requirements", "event_id", field_values(obj, "event_id"), events)
        require("measurement_requirements", "scenario_id", field_values(obj, "scenario_id"), scenarios)
    for obj in repo.list("semantic_vectors"):
        require("semantic_vectors", "chunk_id", field_values(obj, "chunk_id"), chunks)
    for obj in repo.list("scenario_requests"):
        require("scenario_requests", "scenario_id", field_values(obj, "scenario_id"), scenarios)
        require("scenario_requests", "scenario_ids", field_values(obj, "scenario_ids"), scenarios)
        require("scenario_requests", "linked_focus_ids", field_values(obj, "linked_focus_ids"), focuses)
        require("scenario_requests", "linked_review_pack_ids", field_values(obj, "linked_review_pack_ids"), review_packs)
        require("scenario_requests", "milestone_refs", field_values(obj, "milestone_refs"), milestones)
        require("scenario_requests", "evidence_basis", field_values(obj, "evidence_basis"), evidence_union, level="warning")
    for obj in repo.list("simulation_runs"):
        require("simulation_runs", "event_id", field_values(obj, "event_id"), events)

    return findings
