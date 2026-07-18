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
    derivation: str = ""
    citations: list[str] = Field(default_factory=list)
    # B4 캐시 키의 절반 — 카드 지문(id+상태 해시). 데이터가 바뀌면 지문이 바뀌어
    # 캐시가 자동 무효화된다 (TTL 불필요, 결정론).
    cards_hash: str | None = None
    cached: bool = False  # 이 기록 자체가 캐시 응답이었는지 (FAQ 횟수에는 포함)
    duration_ms: int = 0
    created_at: str
    # R4 (설계 21): 질의 행위자 — X-SOC-Actor 헤더 유래, 미설정 시 None.
    actor: str | None = None


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


def cards_fingerprint(cards: list) -> str:
    """카드 지문 — id·상태가 같으면 같은 근거 국면. 캐시 유효성의 결정론 판정."""
    import hashlib

    payload = json.dumps(
        sorted((card.ref_id, card.status_ko or "") for card in cards),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_entry(
    result: AskResult, cards_hash: str | None = None, actor: str | None = None
) -> AskLogEntry:
    return AskLogEntry(
        id=f"ask_{uuid.uuid4().hex[:10]}",
        question=result.question,
        normalized=normalize_question(result.question),
        provider=result.provider,
        model_name=result.model_name,
        confidence=result.confidence,
        answer=result.answer,
        derivation=result.derivation,
        citations=result.citations,
        cards_hash=cards_hash if cards_hash is not None else cards_fingerprint(result.cards),
        cached=result.cached,
        duration_ms=result.duration_ms,
        created_at=datetime.now(UTC).isoformat(),
        actor=actor,
    )


ASK_CACHE_ENV = "SOC_ASK_CACHE"  # "false"면 캐시 비활성


def ask_with_cache(
    runner, store: AskLogStoreProtocol, question: str, actor: str | None = None
) -> AskResult:
    """B4 — 질의 로그 캐시를 앞단에 둔 Ask 실행.

    같은 정규화 질문 + 같은 카드 지문의 LLM 답변이 로그에 있으면 재호출 없이
    재사용한다(cached=True 명시 — 감사 원칙 유지). 결정론 답변은 재계산이 싸므로
    캐시하지 않는다. 캐시 히트도 로그에 남아 FAQ 횟수에 포함된다.
    """
    import os

    enabled = os.environ.get(ASK_CACHE_ENV, "true").lower() != "false"
    normalized = normalize_question(question)
    if enabled:
        preview = runner.preview(question)
        fingerprint = cards_fingerprint(preview.cards)
        hit = store.find_cached(normalized, fingerprint)
        if hit is not None:
            result = AskResult(
                question=question,
                provider=hit.provider,
                model_name=hit.model_name,
                answer=hit.answer,
                confidence=hit.confidence,
                derivation=hit.derivation,
                citations=hit.citations,
                cards=preview.cards,
                unmatched_terms=preview.unmatched_terms,
                cached=True,
                validation_notes=[f"캐시 응답 — 원 질의 {hit.created_at}"],
                duration_ms=0,
            )
            store.save(build_entry(result, cards_hash=fingerprint, actor=actor))
            return result

    result = runner.ask(question)
    store.save(build_entry(result, actor=actor))
    return result


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

    def find_cached(self, normalized: str, cards_hash: str) -> AskLogEntry | None: ...


class InMemoryAskLog:
    def __init__(self) -> None:
        self._entries: list[AskLogEntry] = []

    def save(self, entry: AskLogEntry) -> None:
        self._entries.append(entry)

    def recent(self, limit: int = 20) -> list[AskLogEntry]:
        return sorted(self._entries, key=lambda e: e.created_at, reverse=True)[:limit]

    def faq(self, limit: int = 8) -> list[FAQEntry]:
        return _aggregate_faq(self._entries, limit)

    def find_cached(self, normalized: str, cards_hash: str) -> AskLogEntry | None:
        for entry in sorted(self._entries, key=lambda e: e.created_at, reverse=True):
            if (
                entry.normalized == normalized
                and entry.cards_hash == cards_hash
                and entry.provider != "deterministic"
            ):
                return entry
        return None


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

    def find_cached(self, normalized: str, cards_hash: str) -> AskLogEntry | None:
        with self._db.connection() as conn:
            rows = conn.execute(
                """
                SELECT payload FROM ask_log
                WHERE normalized = %s AND provider != 'deterministic'
                ORDER BY created_at DESC LIMIT 20
                """,
                (normalized,),
            ).fetchall()
        for row in rows:
            entry = AskLogEntry.model_validate(
                row[0] if isinstance(row[0], dict) else json.loads(row[0])
            )
            if entry.cards_hash == cards_hash:
                return entry
        return None
