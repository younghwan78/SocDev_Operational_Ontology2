"""Traceability — 임의 객체의 연결 관계를 양방향으로 조립한다.

명시적 관계(relations 컬렉션)와 암묵적 관계(linked_* 등 참조 필드)를 통합한다.
인과 증명이 아닌 연결 관계다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.glossary import object_label
from backend.ontology.relation import Relation
from backend.resolve.object_index import ObjectIndex

# 컬렉션별 참조 필드 → 관계 유형. traceability가 따라가는 암묵 링크 정의.
REFERENCE_FIELDS: dict[str, list[tuple[str, str]]] = {
    "development_events": [
        ("linked_scenario_ids", "관련_시나리오"),
        ("linked_evidence_ids", "관련_근거"),
        ("linked_milestone_ids", "관련_마일스톤"),
        ("linked_request_ids", "관련_요청"),
        ("linked_propagation_ids", "관련_전파"),
    ],
    "role_activities": [
        ("linked_event_id", "검토_이벤트"),
        ("linked_scenario_ids", "관련_시나리오"),
        ("linked_evidence_ids", "관련_근거"),
        ("linked_milestone_ids", "관련_마일스톤"),
        ("linked_request_ids", "관련_요청"),
        ("linked_propagation_ids", "관련_전파"),
    ],
    "scenarios": [
        ("scenario_group_id", "소속_그룹"),
        ("uses_ip_blocks", "사용_IP"),
        ("depends_on_system_blocks", "의존_시스템블록"),
        ("variants", "변형"),
        ("derived_from_scenario_id", "파생_원본"),
    ],
    "scenario_requests": [
        ("scenario_id", "대상_시나리오"),
        ("scenario_ids", "대상_시나리오"),
        ("origin_project_id", "발원_프로젝트"),
        ("evidence_basis", "근거_기반"),
        ("milestone_refs", "관련_마일스톤"),
        ("linked_focus_ids", "관련_포커스"),
    ],
    "variants": [("scenario_id", "소속_시나리오")],
    "project_milestones": [("project_id", "소속_프로젝트")],
    "customer_requests": [("project_id", "소속_프로젝트")],
    "issues": [("project_id", "소속_프로젝트"), ("evidence_refs", "근거_참조")],
    "evidence_catalog": [
        ("project_id", "소속_프로젝트"),
        ("scenario_id", "대상_시나리오"),
        ("related_milestone_ids", "관련_마일스톤"),
        ("related_request_ids", "관련_요청"),
    ],
    "measurement_evidence": [
        ("event_id", "관련_이벤트"),
        ("scenario_id", "대상_시나리오"),
        ("related_ip_ids", "관련_IP"),
    ],
    "measurement_requirements": [
        ("event_id", "관련_이벤트"),
        ("scenario_id", "대상_시나리오"),
    ],
    "decisions": [("event_id", "관련_이벤트"), ("project_id", "소속_프로젝트")],
    "action_items": [("source_decision_id", "원천_결정")],
    "ip_base_specs": [("ip_id", "대상_IP")],
    "ip_capabilities": [("ip_id", "대상_IP")],
    "ip_knobs": [("ip_id", "대상_IP")],
    "ip_dependency_rules": [("ip_id", "대상_IP"), ("depends_on_ip_id", "의존_IP")],
    "scenario_ip_requirements": [("scenario_id", "대상_시나리오"), ("ip_id", "대상_IP")],
    "semantic_chunks": [("scenario_ids", "대상_시나리오"), ("ip_ids", "관련_IP")],
    "semantic_vectors": [("chunk_id", "원본_청크")],
}


class TraceLink(BaseModel):
    """traceability 링크 하나 — 방향/유형/상대 객체."""

    model_config = ConfigDict(extra="forbid")

    direction: str  # "outgoing" | "incoming"
    link_type: str
    other_id: str
    other_collection: str | None = None
    other_label_ko: str | None = None
    other_title: str | None = None
    resolved: bool = True


class TraceabilityResult(BaseModel):
    """객체 하나의 traceability 조립 결과."""

    model_config = ConfigDict(extra="forbid")

    object_id: str
    collection: str | None = None
    label_ko: str | None = None
    links: list[TraceLink]


class TraceabilityService:
    """양방향 traceability 조립기 — 결정론, 저장하지 않음.

    호출 시점에 인덱스·링크 그래프를 조립한다 — 시작 시 스냅샷이면 반입(ingest)된
    객체가 재시작 전까지 보이지 않는다 (B3b 결정 재진입에서 확인된 한계).
    파일럿 규모(수천 객체)에서 저비용. 대규모화 시 배치 버전 키 캐시는 Stage 14 항목.
    """

    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def trace(self, object_id: str) -> TraceabilityResult:
        return _LinkGraph(self._repo).trace(object_id)


class _LinkGraph:
    """저장소 현재 상태의 링크 그래프 1회 조립체."""

    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo
        self._index = ObjectIndex(repo)
        self._outgoing: dict[str, list[TraceLink]] = {}
        self._incoming: dict[str, list[TraceLink]] = {}
        self._build()

    def _describe(self, object_id: str) -> tuple[str | None, str | None, str | None]:
        entry = self._index.resolve(object_id)
        if entry is None:
            if self._index.resolve_propagation(object_id):
                return None, "전파", None
            return None, None, None
        collection, obj = entry
        model_name = type(obj).__name__
        title = getattr(obj, "title", None) or getattr(obj, "name", None)
        return collection, object_label(model_name), title

    def _add(self, source_id: str, link_type: str, target_id: str) -> None:
        collection, label_ko, title = self._describe(target_id)
        resolved = self._index.exists(target_id)
        self._outgoing.setdefault(source_id, []).append(
            TraceLink(
                direction="outgoing",
                link_type=link_type,
                other_id=target_id,
                other_collection=collection,
                other_label_ko=label_ko,
                other_title=title,
                resolved=resolved,
            )
        )
        src_collection, src_label, src_title = self._describe(source_id)
        self._incoming.setdefault(target_id, []).append(
            TraceLink(
                direction="incoming",
                link_type=link_type,
                other_id=source_id,
                other_collection=src_collection,
                other_label_ko=src_label,
                other_title=src_title,
                resolved=True,
            )
        )

    def _build(self) -> None:
        # 암묵 링크 — 참조 필드
        for collection, fields in REFERENCE_FIELDS.items():
            for obj in self._repo.list(collection):
                for field_name, link_type in fields:
                    value = getattr(obj, field_name, None)
                    if value is None:
                        continue
                    targets = value if isinstance(value, list) else [value]
                    for target in targets:
                        self._add(obj.id, link_type, target)
        # 명시 링크 — relations 컬렉션
        for relation in self._repo.list("relations"):
            assert isinstance(relation, Relation)
            self._add(relation.source_id, relation.relation_type, relation.target_id)

    def trace(self, object_id: str) -> TraceabilityResult:
        collection, label_ko, _ = self._describe(object_id)
        links = list(self._outgoing.get(object_id, [])) + list(self._incoming.get(object_id, []))
        return TraceabilityResult(
            object_id=object_id, collection=collection, label_ko=label_ko, links=links
        )
