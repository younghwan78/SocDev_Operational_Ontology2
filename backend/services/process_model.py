"""프로세스 전이 모델 — 단계 정의와 전이 적합성 판정 (설계 17 §2, 설계 20 §2).

컬렉션별 상태 값 도메인을 진행 단계로 사상하고, 전이 이력 위에서
단계 건너뜀/역행/미등재 상태를 결정론으로 판정한다. 전부 사실 서술 + 전이 ref —
점수도, 차단도 없다. 판정 재료는 시간 모델 T2의 status 전이(transaction time)다.

Y1(설계 20)에서 이슈 전용 모델을 레지스트리로 일반화했다 — 판정 룰은 하나,
단계 사상만 컬렉션별 계약이다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.ingest.history import ObjectHistory, ObjectVersion, StatusTransition

# 단계 정의 (계약) — issue_status 값 도메인 전체를 rank로 사상한다.
ISSUE_STAGES: list[tuple[str, set[str]]] = [
    ("접수", {"open", "synthetic_open"}),
    ("분석", {"under_analysis"}),
    ("우회", {"workaround_applied"}),
    ("해결", {"resolved"}),
    ("종결", {"closed", "done"}),
]

# Y1 — 타 컬렉션 단계 사상. blocked는 진행 단계 내 상황(단계가 아님),
# cancelled는 종결의 한 형태 — 취소 직행도 "종결 직행"으로 드러난다.
ACTION_STAGES: list[tuple[str, set[str]]] = [
    ("미착수", {"open"}),
    ("진행", {"in_progress", "blocked"}),
    ("종결", {"done", "cancelled"}),
]

EVENT_STAGES: list[tuple[str, set[str]]] = [
    ("접수", {"recorded", "open"}),
    ("검토", {"in_review"}),
    ("처리", {"mitigated", "deferred", "available"}),
]

# 컬렉션 → (단계표, 최종 단계발 역행에 붙는 재개 문구).
# 이슈만 P1 프로세스 신호(재개 배지)가 있어 참조 문구를 유지한다.
PROCESS_MODELS: dict[str, tuple[list[tuple[str, set[str]]], str]] = {
    "issues": (ISSUE_STAGES, " (재개 — 프로세스 신호 참조)"),
    "action_items": (ACTION_STAGES, " (재개)"),
    "development_events": (EVENT_STAGES, " (재개)"),
}

KIND_LABELS: dict[str, str] = {
    "skipped": "단계 건너뜀",
    "backward": "역행",
    "unknown_status": "미등재 상태",
}


class TransitionFinding(BaseModel):
    """전이 하나에 대한 프로세스 적합성 판정 — normal은 만들지 않는다 (잡음 방지)."""

    model_config = ConfigDict(extra="forbid")

    version: int
    from_status: str | None
    to_status: str
    kind: str  # skipped | backward | unknown_status
    kind_ko: str
    note_ko: str
    recorded_at: str


class ObjectHistoryFindings(BaseModel):
    """이력 조회 응답 + 프로세스 판정 (Y1) — 저장 계약 무변경, 읽기 시점 계산.

    모델 미등재 컬렉션은 findings가 항상 빈 목록이다 (판정 대상이 아니다).
    """

    model_config = ConfigDict(extra="forbid")

    collection: str
    object_id: str
    versions: list[ObjectVersion] = Field(default_factory=list)
    status_transitions: list[StatusTransition] = Field(default_factory=list)
    transition_findings: list[TransitionFinding] = Field(default_factory=list)


def _finding(
    transition: StatusTransition, kind: str, note_ko: str
) -> TransitionFinding:
    return TransitionFinding(
        version=transition.version,
        from_status=transition.from_status,
        to_status=transition.to_status,
        kind=kind,
        kind_ko=KIND_LABELS[kind],
        note_ko=note_ko,
        recorded_at=transition.recorded_at,
    )


def transition_findings(
    collection: str, transitions: list[StatusTransition]
) -> list[TransitionFinding]:
    """전이 시퀀스의 프로세스 판정 — 동일 입력 동일 출력.

    - created 첫 전이(from=None)는 어느 단계로 시작해도 정상 (도입 시점 차이).
      단 시작 상태가 모델 밖이면 미등재로 드러낸다 (침묵 금지).
    - 동일 단계 내 이동·1단계 전진은 정상 — 판정을 만들지 않는다.
    - 모델 미등재 컬렉션은 빈 목록 (판정 대상이 아니다).
    """
    model = PROCESS_MODELS.get(collection)
    if model is None:
        return []
    stages, reopen_suffix = model
    stage_rank = {
        status: rank for rank, (_, statuses) in enumerate(stages) for status in statuses
    }
    stage_ko = {status: label for label, statuses in stages for status in statuses}
    closed_rank = len(stages) - 1

    findings: list[TransitionFinding] = []
    for transition in transitions:
        to_rank = stage_rank.get(transition.to_status)
        if to_rank is None:
            findings.append(
                _finding(
                    transition,
                    "unknown_status",
                    f"프로세스 모델 밖의 상태 '{transition.to_status}' — 단계 사상 필요",
                )
            )
            continue
        if transition.from_status is None:
            continue
        from_rank = stage_rank.get(transition.from_status)
        if from_rank is None:
            # 출발 상태가 모델 밖 — 그 상태로의 도착 시점에 이미 판정됐다.
            continue
        if to_rank > from_rank + 1:
            skipped = " / ".join(
                label for rank, (label, _) in enumerate(stages)
                if from_rank < rank < to_rank
            )
            findings.append(
                _finding(
                    transition,
                    "skipped",
                    f"'{stage_ko[transition.from_status]}'→"
                    f"'{stage_ko[transition.to_status]}' — "
                    f"{skipped} 단계 기록 없음",
                )
            )
        elif to_rank < from_rank:
            suffix = reopen_suffix if from_rank == closed_rank else ""
            findings.append(
                _finding(
                    transition,
                    "backward",
                    f"'{stage_ko[transition.from_status]}'→"
                    f"'{stage_ko[transition.to_status]}' — 역행{suffix}",
                )
            )
    return findings


def issue_transition_findings(
    transitions: list[StatusTransition],
) -> list[TransitionFinding]:
    """이슈 전이 판정 — 하위 호환 wrapper (RCA 표면 무변경)."""
    return transition_findings("issues", transitions)


def annotate_history(history: ObjectHistory) -> ObjectHistoryFindings:
    """이력 응답에 프로세스 판정을 병기한다 (Y1 표면 — 읽기 시점 계산)."""
    return ObjectHistoryFindings(
        collection=history.collection,
        object_id=history.object_id,
        versions=history.versions,
        status_transitions=history.status_transitions,
        transition_findings=transition_findings(
            history.collection, history.status_transitions
        ),
    )
