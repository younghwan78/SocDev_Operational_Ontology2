"""이슈 프로세스 전이 모델 — 단계 정의와 전이 적합성 판정 (설계 17 §2).

이슈 상태(issue_status 값 도메인)를 진행 단계로 사상하고, 전이 이력 위에서
단계 건너뜀/역행/미등재 상태를 결정론으로 판정한다. 전부 사실 서술 + 전이 ref —
점수도, 차단도 없다. 판정 재료는 시간 모델 T2의 status 전이(transaction time)다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.ingest.history import StatusTransition

# 단계 정의 (계약) — issue_status 값 도메인 전체를 rank로 사상한다.
ISSUE_STAGES: list[tuple[str, set[str]]] = [
    ("접수", {"open", "synthetic_open"}),
    ("분석", {"under_analysis"}),
    ("우회", {"workaround_applied"}),
    ("해결", {"resolved"}),
    ("종결", {"closed", "done"}),
]

_STAGE_RANK: dict[str, int] = {
    status: rank
    for rank, (_, statuses) in enumerate(ISSUE_STAGES)
    for status in statuses
}
_STAGE_KO: dict[str, str] = {
    status: label
    for label, statuses in ISSUE_STAGES
    for status in statuses
}

KIND_LABELS: dict[str, str] = {
    "skipped": "단계 건너뜀",
    "backward": "역행",
    "unknown_status": "미등재 상태",
}

_CLOSED_RANK = len(ISSUE_STAGES) - 1


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


def issue_transition_findings(
    transitions: list[StatusTransition],
) -> list[TransitionFinding]:
    """전이 시퀀스의 프로세스 판정 — 동일 입력 동일 출력.

    - created 첫 전이(from=None)는 어느 단계로 시작해도 정상 (도입 시점 차이).
      단 시작 상태가 모델 밖이면 미등재로 드러낸다 (침묵 금지).
    - 동일 단계 내 이동·1단계 전진은 정상 — 판정을 만들지 않는다.
    """
    findings: list[TransitionFinding] = []
    for transition in transitions:
        to_rank = _STAGE_RANK.get(transition.to_status)
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
        from_rank = _STAGE_RANK.get(transition.from_status)
        if from_rank is None:
            # 출발 상태가 모델 밖 — 그 상태로의 도착 시점에 이미 판정됐다.
            continue
        if to_rank > from_rank + 1:
            skipped = " / ".join(
                label for rank, (label, _) in enumerate(ISSUE_STAGES)
                if from_rank < rank < to_rank
            )
            findings.append(
                _finding(
                    transition,
                    "skipped",
                    f"'{_STAGE_KO[transition.from_status]}'→"
                    f"'{_STAGE_KO[transition.to_status]}' — "
                    f"{skipped} 단계 기록 없음",
                )
            )
        elif to_rank < from_rank:
            reopen_suffix = (
                " (재개 — 프로세스 신호 참조)"
                if from_rank == _CLOSED_RANK
                else ""
            )
            findings.append(
                _finding(
                    transition,
                    "backward",
                    f"'{_STAGE_KO[transition.from_status]}'→"
                    f"'{_STAGE_KO[transition.to_status]}' — 역행{reopen_suffix}",
                )
            )
    return findings
