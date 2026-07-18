"""what-if 가정 세트 영속화 — 운영 기록 (설계 19 §3).

온톨로지 데이터가 아니라 ask_log(0005)·agent_runs(0002)와 같은 운영 기록이다.
append-only: 수정/삭제 API를 만들지 않는다 — 같은 이름을 다시 저장하면 새 기록.
세트를 불러와도 적용은 URL 파라미터 경유(ephemeral)로, 온톨로지 저장소에는
어떤 경우에도 쓰지 않는다.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import psycopg
from pydantic import BaseModel, ConfigDict, Field

from backend.db.connection import ConnectionSource, as_source
from backend.services.what_if import WhatIfAssumption


class WhatIfSet(BaseModel):
    """저장된 가정 세트 — 이름 붙은 실험 질문 묶음."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    note: str | None = None
    project_id: str | None = None
    assumptions: list[WhatIfAssumption] = Field(min_length=1, max_length=10)
    created_at: str
    # R4 (설계 21): 저장 행위자 — X-SOC-Actor 헤더 유래, 미설정 시 None.
    created_by: str | None = None


def build_set(
    name: str,
    assumptions: list[WhatIfAssumption],
    note: str | None = None,
    project_id: str | None = None,
    created_by: str | None = None,
) -> WhatIfSet:
    return WhatIfSet(
        id=f"wset_{uuid.uuid4().hex[:10]}",
        name=name,
        note=note,
        project_id=project_id,
        assumptions=assumptions,
        created_at=datetime.now(UTC).isoformat(),
        created_by=created_by,
    )


@runtime_checkable
class WhatIfSetStoreProtocol(Protocol):
    def save(self, item: WhatIfSet) -> None: ...

    def list(self, project_id: str | None = None) -> list[WhatIfSet]: ...

    def get(self, set_id: str) -> WhatIfSet | None: ...


class InMemoryWhatIfSets:
    def __init__(self) -> None:
        self._items: list[WhatIfSet] = []

    def save(self, item: WhatIfSet) -> None:
        self._items.append(item)

    def list(self, project_id: str | None = None) -> list[WhatIfSet]:
        items = [
            item
            for item in self._items
            if project_id is None or item.project_id == project_id
        ]
        return sorted(items, key=lambda item: (item.created_at, item.id), reverse=True)

    def get(self, set_id: str) -> WhatIfSet | None:
        return next((item for item in self._items if item.id == set_id), None)


class PostgresWhatIfSets:
    def __init__(self, db: psycopg.Connection | ConnectionSource) -> None:
        self._db = as_source(db)

    def save(self, item: WhatIfSet) -> None:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO whatif_sets (id, name, project_id, created_at, payload)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    item.id,
                    item.name,
                    item.project_id,
                    item.created_at,
                    json.dumps(item.model_dump(mode="json"), ensure_ascii=False),
                ),
            )

    def list(self, project_id: str | None = None) -> list[WhatIfSet]:
        sql = "SELECT payload FROM whatif_sets"
        params: tuple = ()
        if project_id is not None:
            sql += " WHERE project_id = %s"
            params = (project_id,)
        sql += " ORDER BY created_at DESC, id DESC LIMIT 200"
        with self._db.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            WhatIfSet.model_validate(
                row[0] if isinstance(row[0], dict) else json.loads(row[0])
            )
            for row in rows
        ]

    def get(self, set_id: str) -> WhatIfSet | None:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT payload FROM whatif_sets WHERE id = %s", (set_id,)
            ).fetchall()
        if not rows:
            return None
        return WhatIfSet.model_validate(
            rows[0][0] if isinstance(rows[0][0], dict) else json.loads(rows[0][0])
        )
