"""반입 서비스 — 파싱 → 매핑 → 검증 → 저장(배치 단위) → rollback.

온톨로지 데이터는 이 경로로만 진입한다. 개별 객체 수정 API는 없다.
삭제는 반입 배치 단위 rollback만 허용한다.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import psycopg
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.db.connection import ConnectionSource, as_source
from backend.ingest.mappings import (
    MAPPINGS,
    IngestMapping,
    convert_row,
    field_values,
    missing_required,
)
from backend.ingest.tabular import TabularParseError, parse_tabular
from backend.loaders.repository import InMemoryRepository
from backend.ontology import COLLECTIONS, OntologyObject
from backend.ontology.common import SourceMeta, SourceOrigin
from backend.ontology.glossary import value_label

BATCH_REF_PREFIX = "import"


class RejectedRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_number: int  # 헤더 제외 1부터
    reason: str


class IngestBatch(BaseModel):
    """반입 배치 기록.

    upsert 의미론 (14_ingest_reality_gaps.md §2 J2): 같은 id 재반입 시
    accepted=신규 / updated=내용 변경 교체 / unchanged=변동 없음(쓰지 않음, 계보 유지).
    rollback은 "그 배치가 현재 소유한 객체 제거" — 갱신된 객체의 계보는 최신 배치로
    이전되므로 이전 배치 rollback은 그 객체를 건드리지 않는다.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    filename: str
    mapping_name: str
    target_collection: str
    accepted_count: int
    rejected_count: int
    updated_count: int = 0
    unchanged_count: int = 0
    status: str  # completed | rolled_back
    created_at: str


class QuarantineEntry(BaseModel):
    """보류 행 (J1 2단계) — 거부 행을 원본 열 값 그대로 저장해 큐레이션 대기열로.

    온톨로지 객체가 아니라 ingest 스테이징이다. 같은 매핑에서 같은 id의 행이
    나중에 수용되면 resolved로 해소되고, 원 배치 rollback 시 함께 제거된다.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    batch_id: str
    mapping_name: str
    row_number: int
    object_id: str | None = None  # 행의 id 열 값 — 재반입 해소 매칭 키
    row_data: dict[str, str]
    reason: str
    status: str = "pending"  # pending | resolved
    created_at: str


class QualityReport(BaseModel):
    """J1 반입 품질 리포트 — 결정론 대조, 경고이지 거부가 아니다."""

    model_config = ConfigDict(extra="forbid")

    # 온톨로지 연결률: 시나리오/IP 등 linkage_fields에 1건 이상 연결된 행 비율.
    linkage_total: int = 0
    linkage_connected: int = 0
    # VALUE_LABELS 미등재 값 — "도메인: '값' ×건수"
    unlabeled_values: list[str] = Field(default_factory=list)
    # 저장소에 실재하지 않는 참조 — "컬렉션: '참조 id' ×건수"
    missing_ref_warnings: list[str] = Field(default_factory=list)


class IngestReport(BaseModel):
    """반입 결과 보고서 — 실패 행 사유는 한국어로."""

    model_config = ConfigDict(extra="forbid")

    batch: IngestBatch
    rejected_rows: list[RejectedRow] = Field(default_factory=list)
    quality: QualityReport | None = None


class IngestError(Exception):
    pass


@runtime_checkable
class IngestWriterProtocol(Protocol):
    """저장 백엔드별 쓰기 계약."""

    def add_objects(self, collection: str, objects: list[OntologyObject], batch_id: str) -> None: ...

    def remove_batch(self, batch_id: str) -> int: ...

    def record_batch(self, batch: IngestBatch) -> None: ...

    def update_batch_status(self, batch_id: str, status: str) -> None: ...

    def list_batches(self) -> list[IngestBatch]: ...

    # upsert/품질 리포트용 읽기 계약 (J1·J2)
    def known_ids(self, collection: str) -> set[str]: ...

    def existing_payloads(self, collection: str, ids: list[str]) -> dict[str, dict]: ...

    def remove_by_ids(self, collection: str, ids: list[str]) -> None: ...

    # 보류 풀 (J1 2단계) — ingest 스테이징, 온톨로지 컬렉션 아님
    def add_quarantine(self, entries: list[QuarantineEntry]) -> None: ...

    def list_quarantine(self, mapping_name: str | None = None) -> list[QuarantineEntry]: ...

    def resolve_quarantine(self, mapping_name: str, object_ids: set[str]) -> int: ...

    def remove_quarantine_by_batch(self, batch_id: str) -> int: ...


def batch_ref(batch_id: str, filename: str, row_number: int) -> str:
    return f"{BATCH_REF_PREFIX}:{batch_id}:{filename}#row{row_number}"


def external_ref(batch_id: str, external_key: str) -> str:
    """커넥터 행의 계보 — rollback 접두(import:<batch>:)를 유지하며 외부 키를 담는다."""
    return f"{BATCH_REF_PREFIX}:{batch_id}:{external_key}"


class MemoryIngestWriter:
    """개발/테스트용 — InMemoryRepository에 직접 추가/제거."""

    def __init__(self, repo: InMemoryRepository) -> None:
        self._repo = repo
        self._batches: list[IngestBatch] = []
        self._quarantine: list[QuarantineEntry] = []

    def add_objects(self, collection: str, objects: list[OntologyObject], batch_id: str) -> None:
        self._repo.add_objects(collection, objects)

    def remove_batch(self, batch_id: str) -> int:
        prefix = f"{BATCH_REF_PREFIX}:{batch_id}:"
        return self._repo.remove_by_ref_prefix(prefix)

    def record_batch(self, batch: IngestBatch) -> None:
        self._batches.append(batch)

    def update_batch_status(self, batch_id: str, status: str) -> None:
        for index, batch in enumerate(self._batches):
            if batch.id == batch_id:
                self._batches[index] = batch.model_copy(update={"status": status})

    def list_batches(self) -> list[IngestBatch]:
        return sorted(self._batches, key=lambda b: b.created_at, reverse=True)

    def known_ids(self, collection: str) -> set[str]:
        return self._repo.ids(collection)

    def add_quarantine(self, entries: list[QuarantineEntry]) -> None:
        self._quarantine.extend(entries)

    def list_quarantine(self, mapping_name: str | None = None) -> list[QuarantineEntry]:
        entries = [e for e in self._quarantine if e.status == "pending"]
        if mapping_name:
            entries = [e for e in entries if e.mapping_name == mapping_name]
        return sorted(entries, key=lambda e: (e.mapping_name, e.created_at, e.row_number))

    def resolve_quarantine(self, mapping_name: str, object_ids: set[str]) -> int:
        resolved = 0
        for index, entry in enumerate(self._quarantine):
            if (
                entry.status == "pending"
                and entry.mapping_name == mapping_name
                and entry.object_id
                and entry.object_id in object_ids
            ):
                self._quarantine[index] = entry.model_copy(update={"status": "resolved"})
                resolved += 1
        return resolved

    def remove_quarantine_by_batch(self, batch_id: str) -> int:
        before = len(self._quarantine)
        self._quarantine = [e for e in self._quarantine if e.batch_id != batch_id]
        return before - len(self._quarantine)

    def existing_payloads(self, collection: str, ids: list[str]) -> dict[str, dict]:
        # Postgres 저장 형식(build_row)과 동일하게 exclude_none — upsert 비교 정규화.
        payloads: dict[str, dict] = {}
        for object_id in ids:
            obj = self._repo.get(collection, object_id)
            if obj is not None:
                payloads[object_id] = obj.model_dump(mode="json", exclude_none=True)
        return payloads

    def remove_by_ids(self, collection: str, ids: list[str]) -> None:
        self._repo.remove_by_ids(collection, ids)


class PostgresIngestWriter:
    """운영용 — ontology_objects + ingest_batches 테이블. 커넥션은 호출 단위 대여(B2)."""

    def __init__(self, db: psycopg.Connection | ConnectionSource) -> None:
        self._db = as_source(db)

    def add_objects(self, collection: str, objects: list[OntologyObject], batch_id: str) -> None:
        from backend.ingest.yaml_seed import UPSERT_OBJECT, build_row

        with self._db.connection() as conn, conn.cursor() as cur:
            for position, obj in enumerate(objects):
                row = build_row(collection, 100_000 + position, obj)
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

    def remove_batch(self, batch_id: str) -> int:
        prefix = f"{BATCH_REF_PREFIX}:{batch_id}:%"
        with self._db.connection() as conn:
            result = conn.execute(
                "DELETE FROM ontology_objects WHERE source_ref LIKE %s", (prefix,)
            )
            return result.rowcount or 0

    def record_batch(self, batch: IngestBatch) -> None:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO ingest_batches
                    (id, filename, mapping_name, target_collection,
                     accepted_count, rejected_count, status, created_at, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    batch.id,
                    batch.filename,
                    batch.mapping_name,
                    batch.target_collection,
                    batch.accepted_count,
                    batch.rejected_count,
                    batch.status,
                    batch.created_at,
                    json.dumps(batch.model_dump(mode="json"), ensure_ascii=False),
                ),
            )

    def update_batch_status(self, batch_id: str, status: str) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "UPDATE ingest_batches SET status = %s WHERE id = %s", (status, batch_id)
            )

    def list_batches(self) -> list[IngestBatch]:
        # updated/unchanged 카운트는 테이블 열이 아니라 payload(jsonb)에 있다 — 스키마 불변.
        with self._db.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, filename, mapping_name, target_collection,
                       accepted_count, rejected_count, status, created_at, payload
                FROM ingest_batches ORDER BY created_at DESC
                """
            ).fetchall()
        batches: list[IngestBatch] = []
        for row in rows:
            payload = row[8] if isinstance(row[8], dict) else {}
            batches.append(
                IngestBatch(
                    id=row[0],
                    filename=row[1],
                    mapping_name=row[2],
                    target_collection=row[3],
                    accepted_count=row[4],
                    rejected_count=row[5],
                    updated_count=int(payload.get("updated_count", 0) or 0),
                    unchanged_count=int(payload.get("unchanged_count", 0) or 0),
                    status=row[6],
                    created_at=(
                        row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7])
                    ),
                )
            )
        return batches

    def known_ids(self, collection: str) -> set[str]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT id FROM ontology_objects WHERE collection = %s", (collection,)
            ).fetchall()
        return {row[0] for row in rows}

    def existing_payloads(self, collection: str, ids: list[str]) -> dict[str, dict]:
        if not ids:
            return {}
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT id, payload FROM ontology_objects WHERE collection = %s AND id = ANY(%s)",
                (collection, ids),
            ).fetchall()
        return {row[0]: row[1] for row in rows if isinstance(row[1], dict)}

    def remove_by_ids(self, collection: str, ids: list[str]) -> None:
        if not ids:
            return
        with self._db.connection() as conn:
            conn.execute(
                "DELETE FROM ontology_objects WHERE collection = %s AND id = ANY(%s)",
                (collection, ids),
            )

    def add_quarantine(self, entries: list[QuarantineEntry]) -> None:
        with self._db.connection() as conn, conn.cursor() as cur:
            for entry in entries:
                cur.execute(
                    """
                    INSERT INTO ingest_quarantine
                        (id, batch_id, mapping_name, row_number, object_id,
                         row_data, reason, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        entry.id,
                        entry.batch_id,
                        entry.mapping_name,
                        entry.row_number,
                        entry.object_id,
                        json.dumps(entry.row_data, ensure_ascii=False),
                        entry.reason,
                        entry.status,
                        entry.created_at,
                    ),
                )

    def list_quarantine(self, mapping_name: str | None = None) -> list[QuarantineEntry]:
        sql = (
            "SELECT id, batch_id, mapping_name, row_number, object_id, row_data,"
            " reason, status, created_at FROM ingest_quarantine WHERE status = 'pending'"
        )
        params: tuple = ()
        if mapping_name:
            sql += " AND mapping_name = %s"
            params = (mapping_name,)
        sql += " ORDER BY mapping_name, created_at, row_number"
        with self._db.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            QuarantineEntry(
                id=row[0],
                batch_id=row[1],
                mapping_name=row[2],
                row_number=row[3],
                object_id=row[4],
                row_data=row[5] if isinstance(row[5], dict) else {},
                reason=row[6],
                status=row[7],
                created_at=(
                    row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8])
                ),
            )
            for row in rows
        ]

    def resolve_quarantine(self, mapping_name: str, object_ids: set[str]) -> int:
        if not object_ids:
            return 0
        with self._db.connection() as conn:
            result = conn.execute(
                """
                UPDATE ingest_quarantine SET status = 'resolved'
                WHERE status = 'pending' AND mapping_name = %s AND object_id = ANY(%s)
                """,
                (mapping_name, sorted(object_ids)),
            )
            return result.rowcount or 0

    def remove_quarantine_by_batch(self, batch_id: str) -> int:
        with self._db.connection() as conn:
            result = conn.execute(
                "DELETE FROM ingest_quarantine WHERE batch_id = %s", (batch_id,)
            )
            return result.rowcount or 0


class IngestService:
    def __init__(self, writer: IngestWriterProtocol) -> None:
        self._writer = writer

    def mappings(self) -> list[IngestMapping]:
        return list(MAPPINGS.values())

    def ingest(self, filename: str, content: bytes, mapping_name: str) -> IngestReport:
        try:
            rows = parse_tabular(filename, content)
        except TabularParseError as exc:
            raise IngestError(str(exc)) from exc
        return self.ingest_rows(filename, rows, mapping_name)

    def ingest_rows(
        self,
        source_name: str,
        rows: list[dict[str, str]],
        mapping_name: str,
        *,
        origin: SourceOrigin = SourceOrigin.IMPORTED,
        row_refs: list[str] | None = None,
    ) -> IngestReport:
        """정규화된 행을 배치로 반입한다 — CSV/XLSX와 커넥터(integrated)의 공용 경로.

        `row_refs[i]`가 있으면 계보에 외부 키를 담는다 (예: `jira:PROJ-123` →
        `import:<batch>:jira:PROJ-123`). rollback 접두 계약은 동일하게 유지된다.
        """
        mapping = MAPPINGS.get(mapping_name)
        if mapping is None:
            raise IngestError(
                f"알 수 없는 매핑: {mapping_name} (사용 가능: {', '.join(sorted(MAPPINGS))})"
            )
        if row_refs is not None and len(row_refs) != len(rows):
            raise IngestError("row_refs 길이가 행 수와 다릅니다")

        model = COLLECTIONS[mapping.target_collection][1]
        batch_id = f"batch_{uuid.uuid4().hex[:10]}"
        now = datetime.now(UTC)

        validated: list[tuple[int, OntologyObject]] = []
        rejected: list[RejectedRow] = []
        for index, row in enumerate(rows, start=1):
            missing = missing_required(mapping, row)
            if missing:
                rejected.append(
                    RejectedRow(row_number=index, reason=f"필수 열 누락: {', '.join(missing)}")
                )
                continue
            try:
                record = convert_row(mapping, row)
            except (ValueError, TypeError) as exc:
                rejected.append(RejectedRow(row_number=index, reason=f"형 변환 실패: {exc}"))
                continue
            if row_refs is not None:
                ref = external_ref(batch_id, row_refs[index - 1])
            else:
                ref = batch_ref(batch_id, source_name, index)
            record["source"] = SourceMeta(
                origin=origin,
                ref=ref,
                ingested_at=now,
            ).model_dump(mode="json")
            try:
                validated.append((index, model.model_validate(record)))
            except ValidationError as exc:
                first = exc.errors()[0]
                location = ".".join(str(part) for part in first["loc"])
                rejected.append(
                    RejectedRow(
                        row_number=index,
                        reason=f"필드 '{location}' 검증 실패: {first['msg']}",
                    )
                )
            except (ValueError, TypeError) as exc:
                rejected.append(RejectedRow(row_number=index, reason=f"형 변환 실패: {exc}"))

        # 배치 내 중복 id — 마지막 행이 이긴다 (앞선 행은 거부로 보고).
        seen_last: dict[str, int] = {obj.id: idx for idx, obj in validated}
        deduped: list[OntologyObject] = []
        for idx, obj in validated:
            if seen_last[obj.id] != idx:
                rejected.append(
                    RejectedRow(row_number=idx, reason=f"배치 내 중복 ID '{obj.id}' — 마지막 행 적용")
                )
                continue
            deduped.append(obj)

        # J2 upsert 3분류: 신규 / 갱신(내용 변경 교체) / 변동 없음(쓰지 않음, 계보 유지).
        existing_ids = self._writer.known_ids(mapping.target_collection)
        overlap = [obj.id for obj in deduped if obj.id in existing_ids]
        previous = (
            self._writer.existing_payloads(mapping.target_collection, overlap)
            if overlap
            else {}
        )
        new_objects: list[OntologyObject] = []
        updated_objects: list[OntologyObject] = []
        unchanged_count = 0
        for obj in deduped:
            old_payload = previous.get(obj.id)
            if old_payload is None:
                new_objects.append(obj)
                continue
            # 저장 형식(exclude_none)과 같은 정규화로 비교 — source 메타는 배치마다 다르므로 제외.
            old_body = {k: v for k, v in old_payload.items() if k != "source"}
            new_body = {
                k: v
                for k, v in obj.model_dump(mode="json", exclude_none=True).items()
                if k != "source"
            }
            if old_body == new_body:
                unchanged_count += 1
            else:
                updated_objects.append(obj)

        if updated_objects:
            self._writer.remove_by_ids(
                mapping.target_collection, [obj.id for obj in updated_objects]
            )
        to_write = new_objects + updated_objects
        if to_write:
            self._writer.add_objects(mapping.target_collection, to_write, batch_id)

        # J1 2단계 보류 풀: 거부 행을 원본 그대로 저장(큐레이션 대기열) —
        # 수용된 id와 같은 보류 행은 해소된다 (수정 후 재반입 루프의 자동 마감).
        id_column = next(
            (col for col, path in mapping.column_map.items() if path == "id"), None
        )
        rejected_numbers = {r.row_number: r.reason for r in rejected}
        quarantine_entries = [
            QuarantineEntry(
                id=f"q_{batch_id}_{index}",
                batch_id=batch_id,
                mapping_name=mapping.name,
                row_number=index,
                object_id=(row.get(id_column) or "").strip() or None if id_column else None,
                row_data={k: str(v) for k, v in row.items()},
                reason=rejected_numbers[index],
                created_at=now.isoformat(),
            )
            for index, row in enumerate(rows, start=1)
            if index in rejected_numbers
        ]
        if quarantine_entries:
            self._writer.add_quarantine(quarantine_entries)
        if deduped:
            self._writer.resolve_quarantine(
                mapping.name, {obj.id for obj in deduped}
            )

        batch = IngestBatch(
            id=batch_id,
            filename=source_name,
            mapping_name=mapping.name,
            target_collection=mapping.target_collection,
            accepted_count=len(new_objects),
            rejected_count=len(rejected),
            updated_count=len(updated_objects),
            unchanged_count=unchanged_count,
            status="completed",
            created_at=now.isoformat(),
        )
        self._writer.record_batch(batch)
        return IngestReport(
            batch=batch,
            rejected_rows=rejected,
            quality=self._quality(mapping, deduped),
        )

    def _quality(
        self, mapping: IngestMapping, objects: list[OntologyObject]
    ) -> QualityReport | None:
        """J1 품질 리포트 — 라벨 미등재 값·참조 무결성·온톨로지 연결률 (경고, 거부 아님)."""
        if not objects:
            return None
        if not (mapping.label_domains or mapping.ref_checks or mapping.linkage_fields):
            return None
        dumps = [obj.model_dump(mode="json") for obj in objects]

        unlabeled: dict[tuple[str, str], int] = {}
        for path, domain in mapping.label_domains.items():
            for dump in dumps:
                for value in field_values(dump, path):
                    if value_label(domain, value) is None:
                        key = (domain, value)
                        unlabeled[key] = unlabeled.get(key, 0) + 1

        missing_refs: dict[tuple[str, str], int] = {}
        known_cache: dict[str, set[str]] = {}
        for path, collection in mapping.ref_checks.items():
            if collection not in known_cache:
                known_cache[collection] = self._writer.known_ids(collection)
            known = known_cache[collection]
            # 같은 배치에서 함께 들어온 대상은 실재로 간주 (예: 이슈+검증 테스트 동시 반입).
            if collection == mapping.target_collection:
                known = known | {obj.id for obj in objects}
            for dump in dumps:
                for value in field_values(dump, path):
                    if value not in known:
                        key = (collection, value)
                        missing_refs[key] = missing_refs.get(key, 0) + 1

        linkage_total = 0
        linkage_connected = 0
        if mapping.linkage_fields:
            linkage_total = len(dumps)
            for dump in dumps:
                if any(field_values(dump, path) for path in mapping.linkage_fields):
                    linkage_connected += 1

        return QualityReport(
            linkage_total=linkage_total,
            linkage_connected=linkage_connected,
            unlabeled_values=[
                f"{domain}: '{value}' ×{count}"
                for (domain, value), count in sorted(unlabeled.items())
            ],
            missing_ref_warnings=[
                f"{collection}: '{value}' ×{count}"
                for (collection, value), count in sorted(missing_refs.items())
            ],
        )

    def rollback(self, batch_id: str) -> int:
        removed = self._writer.remove_batch(batch_id)
        self._writer.remove_quarantine_by_batch(batch_id)  # 보류 행도 배치와 함께 제거
        self._writer.update_batch_status(batch_id, "rolled_back")
        return removed

    def list_batches(self) -> list[IngestBatch]:
        return self._writer.list_batches()

    def list_quarantine(self, mapping_name: str | None = None) -> list[QuarantineEntry]:
        return self._writer.list_quarantine(mapping_name)


class SyncSourceStatus(BaseModel):
    """커넥터 소스별 동기화 상태 — sync-status CLI 표시용 (D1-4)."""

    model_config = ConfigDict(extra="forbid")

    source: str  # jira-sync | confluence-sync | ...
    mapping_name: str
    last_completed_at: str | None = None
    last_counts: str | None = None  # "신규 n / 갱신 n / 변동 없음 n / 거부 n"
    pending_quarantine: int = 0


def summarize_sync_status(
    batches: list[IngestBatch], quarantine: list[QuarantineEntry]
) -> list[SyncSourceStatus]:
    """배치 이력 → 소스별 마지막 완료 동기화 요약 (결정론, 별도 상태 저장 없음)."""
    pending_by_mapping: dict[str, int] = {}
    for entry in quarantine:
        pending_by_mapping[entry.mapping_name] = (
            pending_by_mapping.get(entry.mapping_name, 0) + 1
        )
    latest: dict[tuple[str, str], IngestBatch] = {}
    for batch in batches:  # list_batches는 최신순
        key = (batch.filename, batch.mapping_name)
        if batch.status == "completed" and key not in latest:
            latest[key] = batch
    statuses = []
    for (source, mapping_name), batch in sorted(latest.items()):
        statuses.append(
            SyncSourceStatus(
                source=source,
                mapping_name=mapping_name,
                last_completed_at=batch.created_at,
                last_counts=(
                    f"신규 {batch.accepted_count} / 갱신 {batch.updated_count} / "
                    f"변동 없음 {batch.unchanged_count} / 거부 {batch.rejected_count}"
                ),
                pending_quarantine=pending_by_mapping.get(mapping_name, 0),
            )
        )
    return statuses
