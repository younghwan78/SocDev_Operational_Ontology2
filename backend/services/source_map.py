"""출처 지도 서비스 — 전 컬렉션의 origin 집계 파생 뷰 (저장하지 않음).

원점 비전의 Data Fragmentation Map(§8.4·§9) 대응. 모든 저장 객체가 이미 가진
`SourceMeta.origin`(synthetic/imported/integrated)과 `ref` 유무를 집계해
"이 지식 중 무엇이 가상이고 무엇이 실데이터인가"를 한 화면에 보인다.

수치 리스크 점수가 아니라 단순 건수/비율 집계다 (CLAUDE.md §6.3 무관).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology import COLLECTIONS, OntologyObject, SourceOrigin
from backend.ontology.glossary import object_label


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
    """출처 지도 파생 뷰 — 컬렉션별 집계 + 전체 요약."""

    model_config = ConfigDict(extra="forbid")

    collections: list[CollectionCoverage]
    totals: OriginTotals


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
        )
