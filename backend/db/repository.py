"""PostgreSQL repository — RepositoryProtocol의 운영 구현."""

from __future__ import annotations

import json

import psycopg

from backend.ontology import COLLECTIONS, OntologyObject
from backend.ontology.scenario import ScenarioRequest


class PostgresRepository:
    """ontology_objects 테이블 기반 조회 저장소.

    payload(JSONB)가 모델의 완전한 직렬화본이므로 재구성은 항상 payload에서 한다.
    필터 컬럼(project_id 등)은 SQL 질의 최적화 전용이다.
    """

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def _model_for(self, collection: str) -> type[OntologyObject]:
        if collection not in COLLECTIONS:
            raise KeyError(f"알 수 없는 컬렉션: {collection}")
        return COLLECTIONS[collection][1]

    def list(self, collection: str) -> list[OntologyObject]:
        model = self._model_for(collection)
        rows = self._conn.execute(
            "SELECT payload FROM ontology_objects WHERE collection = %s ORDER BY position",
            (collection,),
        ).fetchall()
        return [model.model_validate(_as_dict(row[0])) for row in rows]

    def get(self, collection: str, object_id: str) -> OntologyObject | None:
        model = self._model_for(collection)
        row = self._conn.execute(
            "SELECT payload FROM ontology_objects WHERE collection = %s AND id = %s",
            (collection, object_id),
        ).fetchone()
        if row is None:
            return None
        return model.model_validate(_as_dict(row[0]))

    def ids(self, *collection_keys: str) -> set[str]:
        if not collection_keys:
            return set()
        rows = self._conn.execute(
            "SELECT id FROM ontology_objects WHERE collection = ANY(%s)",
            (list(collection_keys),),
        ).fetchall()
        return {row[0] for row in rows}

    def propagation_ids(self) -> set[str]:
        result: set[str] = set()
        for request in self.list("scenario_requests"):
            assert isinstance(request, ScenarioRequest)
            result.update(p.propagation_id for p in request.propagation)
        return result

    def counts(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT collection, count(*) FROM ontology_objects GROUP BY collection"
        ).fetchall()
        return {row[0]: row[1] for row in rows}


def _as_dict(payload: object) -> dict:
    """psycopg는 jsonb를 dict로 돌려주지만 드라이버 설정에 따라 str일 수 있다."""
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        return json.loads(payload)
    raise TypeError(f"payload 타입 예상 밖: {type(payload)}")
