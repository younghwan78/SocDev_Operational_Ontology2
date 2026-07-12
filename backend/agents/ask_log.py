"""Ask SoC 질의/답변 로그 — 감사 기록 + 자주 묻는 질문(FAQ)의 원천.

AgentRun 감사 기록과 같은 지위: 온톨로지 데이터가 아니라 운영 로그이며,
POST /ask 처리 안에서만 기록된다 (신규 쓰기 API 없음). 좋은 질문/답변이
쌓이면 FAQ 목록이 되어 처음 쓰는 사람의 예제가 된다 (2026-07-12 사용자 요청).
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import psycopg
from pydantic import BaseModel, ConfigDict, Field

from backend.agents.ask_runner import AskResult
from backend.db.connection import ConnectionSource, as_source


class AskLogEntry(BaseModel):
    """질의 1건의 기록 — 답변 전문과 인용을 보존한다."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    normalized: str  # 집계 키 — 공백/대소문자 정규화
    provider: str
    model_name: str | None = None
    confidence: str
    answer: str
    citations: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    created_at: str


class FAQEntry(BaseModel):
    """자주 묻는 질문 — normalized 기준 집계, 최신 답변 미리보기 동반."""

    model_config = ConfigDict(extra="forbid")

    question: str  # 최신 원문 표기
    count: int
    last_asked: str
    last_confidence: str
    answer_preview: str


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def build_entry(result: AskResult) -> AskLogEntry:
    return AskLogEntry(
        id=f"ask_{uuid.uuid4().hex[:10]}",
        question=result.question,
        normalized=normalize_question(result.question),
        provider=result.provider,
        model_name=result.model_name,
        confidence=result.confidence,
        answer=result.answer,
        citations=result.citations,
        duration_ms=result.duration_ms,
        created_at=datetime.now(UTC).isoformat(),
    )


def _aggregate_faq(entries: list[AskLogEntry], limit: int) -> list[FAQEntry]:
    """최신순 entries → normalized 그룹 집계 (결정론: 횟수 내림차순, 최근 우선)."""
    groups: dict[str, list[AskLogEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.normalized, []).append(entry)
    faq = []
    for group in groups.values():
        latest = max(group, key=lambda e: e.created_at)
        preview = latest.answer.replace("\n", " ")
        faq.append(
            FAQEntry(
                question=latest.question,
                count=len(group),
                last_asked=latest.created_at,
                last_confidence=latest.confidence,
                answer_preview=preview[:160] + ("…" if len(preview) > 160 else ""),
            )
        )
    faq.sort(key=lambda f: (-f.count, f.last_asked), reverse=False)
    faq.sort(key=lambda f: f.last_asked, reverse=True)
    faq.sort(key=lambda f: f.count, reverse=True)
    return faq[:limit]


@runtime_checkable
class AskLogStoreProtocol(Protocol):
    def save(self, entry: AskLogEntry) -> None: ...

    def recent(self, limit: int = 20) -> list[AskLogEntry]: ...

    def faq(self, limit: int = 8) -> list[FAQEntry]: ...


class InMemoryAskLog:
    def __init__(self) -> None:
        self._entries: list[AskLogEntry] = []

    def save(self, entry: AskLogEntry) -> None:
        self._entries.append(entry)

    def recent(self, limit: int = 20) -> list[AskLogEntry]:
        return sorted(self._entries, key=lambda e: e.created_at, reverse=True)[:limit]

    def faq(self, limit: int = 8) -> list[FAQEntry]:
        return _aggregate_faq(self._entries, limit)


class PostgresAskLog:
    def __init__(self, db: psycopg.Connection | ConnectionSource) -> None:
        self._db = as_source(db)

    def save(self, entry: AskLogEntry) -> None:
        with self._db.connection() as conn:
            conn.execute(
                """
                INSERT INTO ask_log (id, normalized, provider, confidence, created_at, payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    entry.id,
                    entry.normalized,
                    entry.provider,
                    entry.confidence,
                    entry.created_at,
                    json.dumps(entry.model_dump(mode="json"), ensure_ascii=False),
                ),
            )

    def _load(self, limit: int | None = None) -> list[AskLogEntry]:
        sql = "SELECT payload FROM ask_log ORDER BY created_at DESC"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        with self._db.connection() as conn:
            rows = conn.execute(sql).fetchall()
        return [
            AskLogEntry.model_validate(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
            for row in rows
        ]

    def recent(self, limit: int = 20) -> list[AskLogEntry]:
        return self._load(limit)

    def faq(self, limit: int = 8) -> list[FAQEntry]:
        # FAQ는 전 이력 집계 — 로그 규모가 커지면 최근 N건 창으로 제한한다.
        return _aggregate_faq(self._load(1000), limit)
