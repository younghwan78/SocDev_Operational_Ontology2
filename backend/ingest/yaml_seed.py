"""YAML fixture → PostgreSQL 시드 반입 (멱등)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

from backend.ingest.history import CHANGE_CREATED, CHANGE_UPDATED, changed_top_level_fields
from backend.loaders.yaml_loader import load_fixtures
from backend.ontology import OntologyObject
from backend.ontology.evidence import SemanticChunk
from backend.ontology.relation import Relation


@dataclass
class SeedRow:
    """ontology_objects 테이블 한 행."""

    collection: str
    id: str
    project_id: str | None
    scenario_id: str | None
    position: int
    payload: str
    source_origin: str
    source_ref: str | None


def build_row(collection: str, position: int, obj: OntologyObject) -> SeedRow:
    payload: dict[str, Any] = obj.model_dump(mode="json", exclude_none=True)
    return SeedRow(
        collection=collection,
        id=obj.id,
        project_id=getattr(obj, "project_id", None) or getattr(obj, "origin_project_id", None),
        scenario_id=getattr(obj, "scenario_id", None),
        position=position,
        payload=json.dumps(payload, ensure_ascii=False),
        source_origin=obj.source.origin.value,
        source_ref=obj.source.ref,
    )


UPSERT_OBJECT = """
INSERT INTO ontology_objects
    (collection, id, project_id, scenario_id, position, payload, source_origin, source_ref)
VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
ON CONFLICT (collection, id) DO UPDATE SET
    project_id = EXCLUDED.project_id,
    scenario_id = EXCLUDED.scenario_id,
    position = EXCLUDED.position,
    payload = EXCLUDED.payload,
    source_origin = EXCLUDED.source_origin,
    source_ref = EXCLUDED.source_ref
"""

UPSERT_RELATION = """
INSERT INTO relations
    (id, source_id, source_type, relation_type, target_id, target_type, confidence, payload)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
ON CONFLICT (id) DO UPDATE SET
    source_id = EXCLUDED.source_id,
    source_type = EXCLUDED.source_type,
    relation_type = EXCLUDED.relation_type,
    target_id = EXCLUDED.target_id,
    target_type = EXCLUDED.target_type,
    confidence = EXCLUDED.confidence,
    payload = EXCLUDED.payload
"""

UPSERT_CHUNK = """
INSERT INTO semantic_chunks (id, project_id, chunk_text, payload)
VALUES (%s, %s, %s, %s::jsonb)
ON CONFLICT (id) DO UPDATE SET
    project_id = EXCLUDED.project_id,
    chunk_text = EXCLUDED.chunk_text,
    payload = EXCLUDED.payload
"""


INSERT_VERSION = """
INSERT INTO object_versions
    (collection, object_id, version, change_kind, recorded_at,
     batch_id, source_origin, changed_fields, payload)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
"""


def seed_fixtures(conn: psycopg.Connection, fixtures_dir: Path) -> dict[str, int]:
    """fixture 전량을 반입한다. 재실행해도 결과가 동일하다(멱등).

    ontology_objects가 전 컬렉션의 source of truth이고,
    relations / semantic_chunks 테이블은 그래프·검색 질의용 투영이다.

    시간 모델 T1: payload(source 메타 제외)가 기존과 다를 때만 버전을 기록한다 —
    동일 fixture 재시드는 버전을 만들지 않는다(시드 멱등, 15_temporal_model.md §4.3).
    """
    collections = load_fixtures(fixtures_dir)
    counts: dict[str, int] = {}
    now_iso = datetime.now(UTC).isoformat()
    seed_batch = f"seed:{now_iso}"

    with conn.cursor() as cur:
        for collection, objects in collections.items():
            existing: dict[str, dict[str, Any]] = {
                row_id: payload
                for row_id, payload in cur.execute(
                    "SELECT id, payload FROM ontology_objects WHERE collection = %s",
                    (collection,),
                ).fetchall()
                if isinstance(payload, dict)
            }
            latest: dict[str, int] = {
                object_id: int(version)
                for object_id, version in cur.execute(
                    "SELECT object_id, MAX(version) FROM object_versions"
                    " WHERE collection = %s GROUP BY object_id",
                    (collection,),
                ).fetchall()
            }
            for position, obj in enumerate(objects):
                row = build_row(collection, position, obj)
                new_payload: dict[str, Any] = obj.model_dump(mode="json", exclude_none=True)
                old_payload = existing.get(obj.id)
                new_body = {k: v for k, v in new_payload.items() if k != "source"}
                old_body = (
                    {k: v for k, v in old_payload.items() if k != "source"}
                    if old_payload is not None
                    else None
                )
                if old_body != new_body:
                    cur.execute(
                        INSERT_VERSION,
                        (
                            collection,
                            obj.id,
                            latest.get(obj.id, 0) + 1,
                            CHANGE_CREATED if old_body is None else CHANGE_UPDATED,
                            now_iso,
                            seed_batch,
                            row.source_origin,
                            changed_top_level_fields(old_body or {}, new_body)
                            if old_body is not None
                            else [],
                            json.dumps(new_payload, ensure_ascii=False),
                        ),
                    )
                cur.execute(
                    UPSERT_OBJECT,
                    (
                        row.collection,
                        row.id,
                        row.project_id,
                        row.scenario_id,
                        row.position,
                        row.payload,
                        row.source_origin,
                        row.source_ref,
                    ),
                )
            counts[collection] = len(objects)

        for obj in collections.get("relations", []):
            assert isinstance(obj, Relation)
            cur.execute(
                UPSERT_RELATION,
                (
                    obj.id,
                    obj.source_id,
                    obj.source_type,
                    obj.relation_type,
                    obj.target_id,
                    obj.target_type,
                    obj.confidence.value,
                    json.dumps(obj.model_dump(mode="json", exclude_none=True), ensure_ascii=False),
                ),
            )

        for obj in collections.get("semantic_chunks", []):
            assert isinstance(obj, SemanticChunk)
            cur.execute(
                UPSERT_CHUNK,
                (
                    obj.id,
                    obj.project_id,
                    obj.chunk_text,
                    json.dumps(obj.model_dump(mode="json", exclude_none=True), ensure_ascii=False),
                ),
            )

    return counts
