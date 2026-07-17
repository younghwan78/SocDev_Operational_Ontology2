"""Q1 프로세스 전이 모델 — 단계 정의·건너뜀/역행/미등재 판정 (설계 17 §2)."""

from __future__ import annotations

from backend.ingest.history import StatusTransition
from backend.ingest.service import IngestService, MemoryIngestWriter
from backend.loaders.repository import InMemoryRepository
from backend.services.process_model import issue_transition_findings
from backend.services.rca import RCAService


def _t(version: int, from_status: str | None, to_status: str) -> StatusTransition:
    return StatusTransition(
        object_id="iss_x",
        from_status=from_status,
        to_status=to_status,
        version=version,
        recorded_at=f"2026-07-{version:02d}T00:00:00+00:00",
    )


def test_skip_and_backward_detected_with_stage_notes() -> None:
    """수용 기준 1 — open→closed 직행=건너뜀, resolved→under_analysis=역행."""
    findings = issue_transition_findings(
        [
            _t(1, None, "open"),
            _t(2, "open", "closed"),
            _t(3, "closed", "resolved"),  # 역행 (종결→해결)
            _t(4, "resolved", "under_analysis"),  # 역행 (해결→분석)
        ]
    )
    kinds = [(f.version, f.kind) for f in findings]
    assert kinds == [(2, "skipped"), (3, "backward"), (4, "backward")]
    skipped = findings[0]
    assert "'접수'→'종결'" in skipped.note_ko
    assert "분석" in skipped.note_ko and "해결" in skipped.note_ko
    # 종결셋에서의 후퇴는 재개 참조를 병기한다.
    assert "재개" in findings[1].note_ko
    assert "재개" not in findings[2].note_ko


def test_normal_progression_produces_no_findings() -> None:
    """수용 기준 2 — 정상 진행은 판정 없음 (동일 단계 내 이동 포함)."""
    findings = issue_transition_findings(
        [
            _t(1, None, "open"),
            _t(2, "open", "synthetic_open"),  # 동일 단계 내 이동
            _t(3, "synthetic_open", "under_analysis"),
            _t(4, "under_analysis", "workaround_applied"),
            _t(5, "workaround_applied", "resolved"),
            _t(6, "resolved", "closed"),
        ]
    )
    assert findings == []


def test_unknown_status_surfaces_even_at_start() -> None:
    """수용 기준 3 — 미등재 상태는 시작 상태여도 드러난다 (침묵 금지)."""
    findings = issue_transition_findings(
        [
            _t(1, None, "이상한상태"),
            _t(2, "이상한상태", "open"),  # 출발이 모델 밖 — 도착 시점에 이미 판정됨
        ]
    )
    assert [(f.version, f.kind) for f in findings] == [(1, "unknown_status")]
    assert "'이상한상태'" in findings[0].note_ko


def test_rca_chain_carries_findings_from_version_log() -> None:
    """수용 기준 4 겸 통합 — 반입 이력에서 판정이 RCA 응답으로 나간다."""
    repo = InMemoryRepository({})
    service = IngestService(MemoryIngestWriter(repo))

    def row(status: str, symptom: str) -> dict[str, str]:
        return {
            "이슈 ID": "iss_p",
            "프로젝트 ID": "proj_u",
            "제목": "직행 종결 이슈",
            "유형": "defect",
            "상태": status,
            "증상": symptom,
            "확신도": "medium",
        }

    service.ingest_rows("w1.csv", [row("open", "s1")], "issues")
    service.ingest_rows("w2.csv", [row("closed", "s2")], "issues")

    chain = RCAService(repo, versions=service).chain("iss_p")
    assert [f.kind for f in chain.transition_findings] == ["skipped"]
    assert chain.transition_findings[0].version == 2

    # 버전 이력 없는 이슈는 findings 없음 — 하위 호환.
    no_versions = RCAService(repo).chain("iss_p")
    assert no_versions.transition_findings == []


# ------------------------------------------------- Y1 타 컬렉션 모델 (설계 20 §2)


def test_action_items_model_skip_and_reopen() -> None:
    """수용 기준 1 — 미착수→종결 직행=건너뜀, 종결→진행 후퇴=역행(재개)."""
    from backend.services.process_model import transition_findings

    findings = transition_findings(
        "action_items",
        [
            _t(1, None, "open"),
            _t(2, "open", "done"),  # 진행 기록 없이 완료
            _t(3, "done", "in_progress"),  # 재작업
            _t(4, "in_progress", "blocked"),  # 동일 단계 내 이동 — 정상
            _t(5, "blocked", "cancelled"),  # 1단계 전진 — 정상
        ],
    )
    assert [(f.version, f.kind) for f in findings] == [(2, "skipped"), (3, "backward")]
    assert "진행 단계 기록 없음" in findings[0].note_ko
    assert "재개" in findings[1].note_ko


def test_development_events_model_skip() -> None:
    """수용 기준 1 — 이벤트 접수→처리 직행은 검토 기록 없음으로 드러난다."""
    from backend.services.process_model import transition_findings

    findings = transition_findings(
        "development_events",
        [_t(1, None, "open"), _t(2, "open", "mitigated")],
    )
    assert [(f.kind, f.version) for f in findings] == [("skipped", 2)]
    assert "검토 단계 기록 없음" in findings[0].note_ko


def test_unregistered_collection_yields_no_findings() -> None:
    """수용 기준 2 — 모델 미등재 컬렉션은 판정 대상이 아니다 (빈 목록)."""
    from backend.services.process_model import transition_findings

    assert transition_findings("scenarios", [_t(1, "a", "b")]) == []


def test_annotate_history_carries_findings() -> None:
    """Y1 표면 — history 응답에 판정이 병기되고 기존 필드는 그대로다."""
    from backend.services.process_model import annotate_history

    repo = InMemoryRepository({})
    service = IngestService(MemoryIngestWriter(repo))

    def row(status: str, symptom: str) -> dict[str, str]:
        return {
            "이슈 ID": "iss_h",
            "프로젝트 ID": "proj_u",
            "제목": "이력 판정",
            "유형": "defect",
            "상태": status,
            "증상": symptom,
            "확신도": "medium",
        }

    service.ingest_rows("w1.csv", [row("open", "s1")], "issues")
    service.ingest_rows("w2.csv", [row("done", "s2")], "issues")
    annotated = annotate_history(service.history("issues", "iss_h"))
    assert [v.version for v in annotated.versions] == [1, 2]
    assert [f.kind for f in annotated.transition_findings] == ["skipped"]
