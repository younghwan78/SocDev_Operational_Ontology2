"""객체 버전 이력 — append-only 캡처 계약 (15_temporal_model.md).

온톨로지 컬렉션이 아니라 감사 인프라다 (agent_runs/ask_log와 같은 지위) —
ingest로 진입하지 않고, fixture에 없고, JSON Schema 대상이 아니다.
쓰기 관문(ingest_rows/rollback/db-seed)의 부수 기록이며 자체 진입 경로가 없다.

시간 의미론: recorded_at은 transaction time(twin이 알게 된 시각),
source_updated_at은 원천 시스템이 주장하는 시각(있을 때만) — 두 축을 합치지 않는다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

CHANGE_CREATED = "created"
CHANGE_UPDATED = "updated"
CHANGE_RETRACTED = "retracted"


class ObjectVersion(BaseModel):
    """객체 한 버전 — 변경 후 전체 payload 스냅샷. retracted는 payload 없음."""

    model_config = ConfigDict(extra="forbid")

    collection: str
    object_id: str
    version: int  # (collection, object_id)별 1부터 증가
    change_kind: str  # created | updated | retracted
    recorded_at: str
    batch_id: str | None = None  # ingest 배치 / "seed:<ts>" — 계보
    source_origin: str
    source_updated_at: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
    payload: dict[str, Any] | None = None


class StatusTransition(BaseModel):
    """status 필드 전이 — 버전 시퀀스에서 읽기 시점에 결정론 계산 (저장 안 함)."""

    model_config = ConfigDict(extra="forbid")

    object_id: str
    from_status: str | None  # created 버전은 None
    to_status: str
    version: int
    recorded_at: str
    source_updated_at: str | None = None


class ObjectHistory(BaseModel):
    """이력 조회 응답 — 버전 목록(오름차순) + status 전이 추출."""

    model_config = ConfigDict(extra="forbid")

    collection: str
    object_id: str
    versions: list[ObjectVersion] = Field(default_factory=list)
    status_transitions: list[StatusTransition] = Field(default_factory=list)


def changed_top_level_fields(old_body: dict[str, Any], new_body: dict[str, Any]) -> list[str]:
    """직전/신규 payload(source 메타 제외본)에서 달라진 top-level 필드 — 정렬 반환."""
    fields = set(old_body) | set(new_body)
    return sorted(f for f in fields if old_body.get(f) != new_body.get(f))


def extract_status_transitions(versions: list[ObjectVersion]) -> list[StatusTransition]:
    """버전 시퀀스에서 status 전이만 뽑는다 — 동일 입력 동일 출력.

    retracted 버전(payload 없음)은 상태 주장이 아니므로 전이를 만들지 않고,
    이후 재생성(created)의 from_status에도 승계되지 않는다.
    """
    transitions: list[StatusTransition] = []
    previous_status: str | None = None
    for version in sorted(versions, key=lambda v: v.version):
        if version.payload is None:
            previous_status = None
            continue
        status = version.payload.get("status")
        if not isinstance(status, str):
            continue
        if status != previous_status:
            transitions.append(
                StatusTransition(
                    object_id=version.object_id,
                    from_status=previous_status,
                    to_status=status,
                    version=version.version,
                    recorded_at=version.recorded_at,
                    source_updated_at=version.source_updated_at,
                )
            )
        previous_status = status
    return transitions
