"""출처 지도 서비스 — 전 컬렉션의 origin 집계 파생 뷰 (저장하지 않음).

원점 비전의 Data Fragmentation Map(§8.4·§9) 대응. 모든 저장 객체가 이미 가진
`SourceMeta.origin`(synthetic/imported/integrated)과 `ref` 유무를 집계해
"이 지식 중 무엇이 가상이고 무엇이 실데이터인가"를 한 화면에 보인다.

수치 리스크 점수가 아니라 단순 건수/비율 집계다 (CLAUDE.md §6.3 무관).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.ingest.mappings import field_values
from backend.loaders.protocols import RepositoryProtocol
from backend.ontology import COLLECTIONS, OntologyObject, SourceOrigin
from backend.ontology.glossary import object_label

# W2 (설계 22 §3): 컬렉션별 명시 링크 필드 — "linked" = 1개 이상 비어있지 않음.
# 도메인 태그(affected_domains 등)는 링크가 아니다 — 명시 ID 참조만 센다 (L8 원칙).
# ingest linkage_fields(J1 배치 연결률)와 같은 철학의 전역 상설판이며,
# OCEL export(W3)의 O2O 관계도 이 상수를 재사용한다.
LINK_FIELDS: dict[str, list[str]] = {
    "issues": [
        "affected_scope.scenarios",
        "affected_scope.ip_blocks",
        "affected_scope.system_blocks",
        "verifying_test_ids",
        "evidence_refs",
    ],
    "development_events": [
        "related_ip_ids",
        "linked_scenario_ids",
        "linked_evidence_ids",
        "linked_milestone_ids",
    ],
    "tests": ["linked_scenario_ids", "verifies_issue_ids", "linked_evidence_ids"],
    "kpi_observations": ["scenario_id", "evidence_id"],
    "measurement_evidence": ["related_ip_ids", "related_kpi_ids", "related_knob_ids"],
    # 필수 필드라 항상 100% — 지표 자체의 대조군 (링크 규칙이 깨지면 여기부터 틀어진다).
    "action_items": ["source_decision_id"],
}

# 표시 라벨 — 중첩 경로("affected_scope.scenarios")는 glossary 필드 라벨로
# 표현되지 않아 서비스 로컬 사전으로 둔다 (UI 문자열 하드코딩 영어 금지).
LINK_FIELD_LABELS: dict[str, str] = {
    "affected_scope.scenarios": "영향 시나리오",
    "affected_scope.ip_blocks": "영향 IP",
    "affected_scope.system_blocks": "영향 시스템 블록",
    "verifying_test_ids": "검증 테스트",
    "evidence_refs": "근거 참조",
    "related_ip_ids": "관련 IP",
    "linked_scenario_ids": "연결 시나리오",
    "linked_evidence_ids": "연결 근거",
    "linked_milestone_ids": "연결 마일스톤",
    "verifies_issue_ids": "검증 대상 이슈",
    "scenario_id": "시나리오",
    "evidence_id": "근거",
    "related_kpi_ids": "관련 KPI",
    "related_knob_ids": "관련 노브",
    "source_decision_id": "원 결정",
}

LINK_NOTE_KO = (
    "연결률은 위험 지도·변경 영향이 볼 수 있는 범위의 한계다 — "
    "링크 없는 객체는 파생 뷰에 나타나지 않는다."
)


class LinkFieldCoverage(BaseModel):
    """링크 필드 하나의 채움 건수."""

    model_config = ConfigDict(extra="forbid")

    field: str
    field_ko: str
    linked: int


class LinkCoverage(BaseModel):
    """컬렉션 하나의 온톨로지 연결률 — 트윈 충실도 메타 지표 (점수 아님)."""

    model_config = ConfigDict(extra="forbid")

    collection: str
    collection_ko: str
    total: int
    linked: int
    fields: list[LinkFieldCoverage]


class CollectionCoverage(BaseModel):
    """컬렉션별 출처 집계 — 가상/반입/연동 건수 + 계보(ref) 누락 건수."""

    model_config = ConfigDict(extra="forbid")

    collection: str
    collection_ko: str
    total: int
    synthetic: int
    imported: int
    integrated: int
    without_ref: int


class OriginTotals(BaseModel):
    """전체 출처 요약 — 실데이터(반입+연동) 진척을 건수/문구로 표기."""

    model_config = ConfigDict(extra="forbid")

    total: int
    synthetic: int
    imported: int
    integrated: int
    real_data_note: str


class SourceCoverage(BaseModel):
    """출처 지도 파생 뷰 — 컬렉션별 집계 + 전체 요약 (+ W2 링크 커버리지)."""

    model_config = ConfigDict(extra="forbid")

    collections: list[CollectionCoverage]
    totals: OriginTotals
    links: list[LinkCoverage] = Field(default_factory=list)
    link_note_ko: str = LINK_NOTE_KO


class SourceCoverageService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def coverage(self) -> SourceCoverage:
        collections: list[CollectionCoverage] = []
        t_syn = t_imp = t_int = 0
        for key, (_module, model) in COLLECTIONS.items():
            objects = [o for o in self._repo.list(key) if isinstance(o, OntologyObject)]
            if not objects:
                continue
            syn = imp = intg = without_ref = 0
            for obj in objects:
                origin = obj.source.origin
                if origin == SourceOrigin.IMPORTED:
                    imp += 1
                elif origin == SourceOrigin.INTEGRATED:
                    intg += 1
                else:
                    syn += 1
                if not obj.source.ref:
                    without_ref += 1
            collections.append(
                CollectionCoverage(
                    collection=key,
                    collection_ko=object_label(model.__name__) or key,
                    total=len(objects),
                    synthetic=syn,
                    imported=imp,
                    integrated=intg,
                    without_ref=without_ref,
                )
            )
            t_syn += syn
            t_imp += imp
            t_int += intg
        # 실데이터가 많은 컬렉션 먼저, 그다음 total 내림차순, 키 순.
        collections.sort(
            key=lambda c: (-(c.imported + c.integrated), -c.total, c.collection)
        )
        grand = t_syn + t_imp + t_int
        real = t_imp + t_int
        return SourceCoverage(
            collections=collections,
            totals=OriginTotals(
                total=grand,
                synthetic=t_syn,
                imported=t_imp,
                integrated=t_int,
                real_data_note=f"실데이터(반입+연동) {real}/{grand}건",
            ),
            links=self._link_coverage(),
        )

    def _link_coverage(self) -> list[LinkCoverage]:
        """W2: 컬렉션별 연결률 — 커버리지 낮은 순 (개선 대상이 먼저 보인다)."""
        results: list[LinkCoverage] = []
        for collection, paths in LINK_FIELDS.items():
            _, model = COLLECTIONS[collection]
            objects = [
                o for o in self._repo.list(collection) if isinstance(o, OntologyObject)
            ]
            if not objects:
                continue
            per_field = dict.fromkeys(paths, 0)
            linked = 0
            for obj in objects:
                dump = obj.model_dump(mode="json")
                hit = False
                for path in paths:
                    if field_values(dump, path):
                        per_field[path] += 1
                        hit = True
                if hit:
                    linked += 1
            results.append(
                LinkCoverage(
                    collection=collection,
                    collection_ko=object_label(model.__name__) or collection,
                    total=len(objects),
                    linked=linked,
                    fields=[
                        LinkFieldCoverage(
                            field=path,
                            field_ko=LINK_FIELD_LABELS.get(path, path),
                            linked=count,
                        )
                        for path, count in per_field.items()
                    ],
                )
            )
        results.sort(key=lambda c: (c.linked / c.total, c.collection))
        return results
