"""PostgreSQL 연결 관리 — DSN은 인자 또는 SOC_ONTOLOGY_DSN 환경변수."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

DSN_ENV = "SOC_ONTOLOGY_DSN"


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
