"""PostgreSQL 연결 관리 — DSN은 인자 또는 SOC_ONTOLOGY_DSN 환경변수.

B2 (14_ingest_reality_gaps 후속 — backend 운영 갭): API는 단일 공유 커넥션이
아니라 **커넥션 풀**을 쓴다. 호출 단위 대여/commit/반납이라 idle-in-transaction이
남지 않고, DB 재시작 시 자동 재접속되며, 동시 요청이 직렬화되지 않는다.
CLI/테스트의 단일 커넥션 경로는 SingleConnection 어댑터로 동일 계약을 만족한다.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol, runtime_checkable

import psycopg

DSN_ENV = "SOC_ONTOLOGY_DSN"
POOL_MAX_ENV = "SOC_ONTOLOGY_POOL_MAX"  # 기본 8


class MissingDSNError(Exception):
    """DSN 미지정 — PostgreSQL 기능은 DSN이 있을 때만 활성화된다."""


def resolve_dsn(dsn: str | None = None) -> str:
    resolved = dsn or os.environ.get(DSN_ENV)
    if not resolved:
        raise MissingDSNError(
            f"PostgreSQL DSN이 없습니다. --dsn 옵션 또는 {DSN_ENV} 환경변수를 설정하세요."
        )
    return resolved


@contextmanager
def get_connection(dsn: str | None = None) -> Iterator[psycopg.Connection]:
    """트랜잭션 커넥션 — 정상 종료 시 commit, 예외 시 rollback."""
    conn = psycopg.connect(resolve_dsn(dsn))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@runtime_checkable
class ConnectionSource(Protocol):
    """저장소/스토어가 커넥션을 빌려 쓰는 계약 — 호출 단위 commit/rollback."""

    def connection(self) -> AbstractContextManager[psycopg.Connection]: ...


class SingleConnection:
    """단일 커넥션 어댑터 (CLI·테스트) — 메서드 단위로 commit해 트랜잭션을 닫는다."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise


class PooledConnections:
    """운영 경로 — psycopg_pool 기반. 자동 재접속·동시 요청 병렬 처리."""

    def __init__(self, dsn: str | None = None, max_size: int | None = None) -> None:
        from psycopg_pool import ConnectionPool

        resolved_max = max_size or int(os.environ.get(POOL_MAX_ENV, "8"))
        self._pool = ConnectionPool(
            resolve_dsn(dsn), min_size=1, max_size=resolved_max, open=True
        )

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        # psycopg_pool이 대여/commit(정상)/rollback(예외)/반납을 관리한다.
        with self._pool.connection() as conn:
            yield conn


def as_source(db: psycopg.Connection | ConnectionSource) -> ConnectionSource:
    """기존 단일 커넥션 호출부(하위 호환)와 풀 경로를 하나의 계약으로 정규화."""
    if isinstance(db, psycopg.Connection):
        return SingleConnection(db)
    return db
