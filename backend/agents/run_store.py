"""AgentRun 감사 기록 저장소 — 메모리(개발/테스트) / PostgreSQL(운영)."""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

import psycopg

from backend.db.connection import ConnectionSource, as_source
from backend.ontology.relation import AgentRun


@runtime_checkable
class RunStoreProtocol(Protocol):
    def save(self, run: AgentRun) -> None: ...

    def list_for_scenario(self, scenario_id: str) -> list[AgentRun]:
        """최신순으로 반환한다."""
        ...


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: list[AgentRun] = []

    def save(self, run: AgentRun) -> None:
        self._runs.append(run)

    def list_for_scenario(self, scenario_id: str) -> list[AgentRun]:
        matched = [run for run in self._runs if run.scenario_id == scenario_id]
        return sorted(matched, key=lambda run: run.created_at, reverse=True)


class PostgresRunStore:
    def __init__(self, db: psycopg.Connection | ConnectionSource) -> None:
        self._db = as_source(db)

    def save(self, run: AgentRun) -> None:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs (id, scenario_id, status, input_hash, created_at, payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    run.id,
                    run.scenario_id,
                    run.status,
                    run.input_hash,
                    run.created_at,
                    json.dumps(
                        run.model_dump(mode="json", exclude_none=True), ensure_ascii=False
                    ),
                ),
            )

    def list_for_scenario(self, scenario_id: str) -> list[AgentRun]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT payload FROM agent_runs WHERE scenario_id = %s ORDER BY created_at DESC",
                (scenario_id,),
            ).fetchall()
        result = []
        for row in rows:
            payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            result.append(AgentRun.model_validate(payload))
        return result
