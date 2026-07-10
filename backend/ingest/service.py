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

from backend.ingest.mappings import MAPPINGS, IngestMapping, convert_row, missing_required
from backend.ingest.tabular import TabularParseError, parse_tabular
from backend.loaders.repository import InMemoryRepository
from backend.ontology import COLLECTIONS, OntologyObject
from backend.ontology.common import SourceMeta, SourceOrigin

BATCH_REF_PREFIX = "import"


class RejectedRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_number: int  # 헤더 제외 1부터
    reason: str


class IngestBatch(BaseModel):
    """반입 배치 기록."""

    model_config = ConfigDict(extra="forbid")

    id: str
    filename: str
    mapping_name: str
    target_collection: str
    accepted_count: int
    rejected_count: int
    status: str  # completed | rolled_back
    created_at: str


class IngestReport(BaseModel):
    """반입 결과 보고서 — 실패 행 사유는 한국어로."""

    model_config = ConfigDict(extra="forbid")

    batch: IngestBatch
    rejected_rows: list[RejectedRow] = Field(default_factory=list)


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


class PostgresIngestWriter:
    """운영용 — ontology_objects + ingest_batches 테이블."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def add_objects(self, collection: str, objects: list[OntologyObject], batch_id: str) -> None:
        from backend.ingest.yaml_seed import UPSERT_OBJECT, build_row

        with self._conn.cursor() as cur:
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
        self._conn.commit()

    def remove_batch(self, batch_id: str) -> int:
        prefix = f"{BATCH_REF_PREFIX}:{batch_id}:%"
        result = self._conn.execute(
            "DELETE FROM ontology_objects WHERE source_ref LIKE %s", (prefix,)
        )
        self._conn.commit()
        return result.rowcount or 0

    def record_batch(self, batch: IngestBatch) -> None:
        self._conn.execute(
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
        self._conn.commit()

    def update_batch_status(self, batch_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE ingest_batches SET status = %s WHERE id = %s", (status, batch_id)
        )
        self._conn.commit()

    def list_batches(self) -> list[IngestBatch]:
        rows = self._conn.execute(
            """
            SELECT id, filename, mapping_name, target_collection,
                   accepted_count, rejected_count, status, created_at
            FROM ingest_batches ORDER BY created_at DESC
            """
        ).fetchall()
        return [
            IngestBatch(
                id=row[0],
                filename=row[1],
                mapping_name=row[2],
                target_collection=row[3],
                accepted_count=row[4],
                rejected_count=row[5],
                status=row[6],
                created_at=row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
            )
            for row in rows
        ]


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

        accepted: list[OntologyObject] = []
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
                accepted.append(model.model_validate(record))
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

        if accepted:
            self._writer.add_objects(mapping.target_collection, accepted, batch_id)

        batch = IngestBatch(
            id=batch_id,
            filename=source_name,
            mapping_name=mapping.name,
            target_collection=mapping.target_collection,
            accepted_count=len(accepted),
            rejected_count=len(rejected),
            status="completed",
            created_at=now.isoformat(),
        )
        self._writer.record_batch(batch)
        return IngestReport(batch=batch, rejected_rows=rejected)

    def rollback(self, batch_id: str) -> int:
        removed = self._writer.remove_batch(batch_id)
        self._writer.update_batch_status(batch_id, "rolled_back")
        return removed

    def list_batches(self) -> list[IngestBatch]:
        return self._writer.list_batches()
