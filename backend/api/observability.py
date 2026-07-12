"""구조화 요청 로깅 (D1-2, Stage 14) — 사내 로그 수집기에 바로 물리는 JSON 라인.

한 요청 = 한 줄(JSON). 토큰/본문은 절대 기록하지 않는다 — 경로/상태/소요만.
LLM·반입 감사는 별도 기록(AgentRun/ask_log/ingest_batches)이 담당한다.
uvicorn 기본 access log와 중복되면 `--no-access-log`로 끈다 (runbook 참조).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import UTC, datetime

LOG_LEVEL_ENV = "SOC_LOG_LEVEL"  # 기본 INFO

access_logger = logging.getLogger("soc.access")
error_logger = logging.getLogger("soc.error")
_configured = False


def setup_logging() -> None:
    """stdout JSON 라인 핸들러 — 멱등 (재호출 안전)."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    level = os.environ.get(LOG_LEVEL_ENV, "INFO").upper()
    for logger in (access_logger, error_logger):
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    _configured = True


def log_request(
    method: str, path: str, status: int, duration_ms: int, *, authenticated: bool
) -> None:
    access_logger.info(
        json.dumps(
            {
                "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "kind": "access",
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": duration_ms,
                "auth": authenticated,
            },
            ensure_ascii=False,
        )
    )


def log_error(method: str, path: str, error: BaseException, duration_ms: int) -> None:
    error_logger.error(
        json.dumps(
            {
                "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
                "kind": "error",
                "method": method,
                "path": path,
                "error_type": type(error).__name__,
                "error": str(error)[:300],
                "duration_ms": duration_ms,
            },
            ensure_ascii=False,
        ),
        exc_info=error,
    )


class RequestTimer:
    """미들웨어용 소요 측정 — monotonic 기반."""

    def __init__(self) -> None:
        self._started = time.monotonic()

    def duration_ms(self) -> int:
        return int((time.monotonic() - self._started) * 1000)
