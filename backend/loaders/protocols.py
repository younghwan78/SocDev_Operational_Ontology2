"""Repository 인터페이스 — in-memory(테스트/개발)와 PostgreSQL(운영)이 공유한다."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.ontology import OntologyObject


@runtime_checkable
class RepositoryProtocol(Protocol):
    """온톨로지 조회 저장소 계약."""

    def list(self, collection: str) -> list[OntologyObject]:
        """컬렉션의 전체 객체를 적재 순서대로 반환한다."""
        ...

    def get(self, collection: str, object_id: str) -> OntologyObject | None:
        """ID로 객체를 조회한다."""
        ...

    def ids(self, *collection_keys: str) -> set[str]:
        """컬렉션들의 ID 합집합."""
        ...

    def propagation_ids(self) -> set[str]:
        """ScenarioRequest 내장 전파 레코드의 ID 집합."""
        ...
