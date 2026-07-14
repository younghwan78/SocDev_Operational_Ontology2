"""시간 모델 T1+T2 — append-only 버전 로그와 전이 추출 (15_temporal_model.md §6)."""

from pathlib import Path

import pytest
from backend.ingest.history import (
    ObjectVersion,
    changed_top_level_fields,
    extract_status_transitions,
)
from backend.ingest.service import IngestService, MemoryIngestWriter
from backend.loaders.repository import InMemoryRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"

HEADER = "이슈 ID,프로젝트 ID,제목,유형,상태,증상,확신도"


def issue_csv(status: str, symptom: str = "언더런 발생") -> bytes:
    return f"{HEADER}\nhist_issue_1,project_u,테스트 이슈,underrun,{status},{symptom},medium\n".encode()


@pytest.fixture()
def service() -> IngestService:
    repo = InMemoryRepository.from_fixtures(FIXTURES)
    return IngestService(MemoryIngestWriter(repo))


def test_version_chain_created_updated_retracted(service: IngestService) -> None:
    """수용 기준 1: created(v1) → updated(v2) → retracted(v3) 체인."""
    service.ingest("issues.csv", issue_csv("open"), "issues")
    report2 = service.ingest("issues.csv", issue_csv("resolved"), "issues")
    service.rollback(report2.batch.id)

    history = service.history("issues", "hist_issue_1")
    kinds = [(v.version, v.change_kind) for v in history.versions]
    assert kinds == [(1, "created"), (2, "updated"), (3, "retracted")]
    assert history.versions[0].payload is not None
    assert history.versions[2].payload is None  # retracted는 스냅샷 없음
    assert history.versions[2].batch_id == report2.batch.id


def test_unchanged_reingest_creates_no_version(service: IngestService) -> None:
    """수용 기준 1: 변동 없음 재반입은 버전을 만들지 않는다."""
    service.ingest("issues.csv", issue_csv("open"), "issues")
    report = service.ingest("issues.csv", issue_csv("open"), "issues")
    assert report.batch.unchanged_count == 1
    history = service.history("issues", "hist_issue_1")
    assert len(history.versions) == 1


def test_changed_fields_match_actual_diff(service: IngestService) -> None:
    """수용 기준 3: changed_fields = 실제 달라진 top-level 필드 (source 제외)."""
    service.ingest("issues.csv", issue_csv("open"), "issues")
    service.ingest("issues.csv", issue_csv("resolved", symptom="언더런 재현"), "issues")
    history = service.history("issues", "hist_issue_1")
    assert history.versions[1].changed_fields == ["status", "symptom"]
    assert history.versions[0].changed_fields == []  # created는 diff 없음


def test_recreate_after_rollback_continues_version_numbers(service: IngestService) -> None:
    """rollback 후 재반입은 이력을 이어간다 — 로그는 지워지지 않는다."""
    report1 = service.ingest("issues.csv", issue_csv("open"), "issues")
    service.rollback(report1.batch.id)
    service.ingest("issues.csv", issue_csv("open"), "issues")
    history = service.history("issues", "hist_issue_1")
    kinds = [(v.version, v.change_kind) for v in history.versions]
    assert kinds == [(1, "created"), (2, "retracted"), (3, "created")]


def test_status_transitions_extraction(service: IngestService) -> None:
    """수용 기준 4: status 전이는 버전 시퀀스에서 결정론 계산된다."""
    service.ingest("issues.csv", issue_csv("open"), "issues")
    service.ingest("issues.csv", issue_csv("under_analysis"), "issues")
    service.ingest("issues.csv", issue_csv("resolved"), "issues")

    history = service.history("issues", "hist_issue_1")
    transitions = [(t.from_status, t.to_status) for t in history.status_transitions]
    assert transitions == [
        (None, "open"),
        ("open", "under_analysis"),
        ("under_analysis", "resolved"),
    ]
    # 동일 입력 동일 출력
    again = extract_status_transitions(history.versions)
    assert [t.model_dump() for t in again] == [
        t.model_dump() for t in history.status_transitions
    ]


def test_status_unchanged_update_yields_no_transition(service: IngestService) -> None:
    """status 외 필드만 바뀐 갱신은 전이를 만들지 않는다."""
    service.ingest("issues.csv", issue_csv("open"), "issues")
    service.ingest("issues.csv", issue_csv("open", symptom="언더런 재현"), "issues")
    history = service.history("issues", "hist_issue_1")
    assert len(history.versions) == 2
    assert len(history.status_transitions) == 1  # 생성 전이만


def test_retraction_resets_transition_baseline() -> None:
    """retracted 이후 재생성의 from_status는 승계되지 않는다 (None)."""
    versions = [
        ObjectVersion(
            collection="issues",
            object_id="x",
            version=1,
            change_kind="created",
            recorded_at="2026-07-14T00:00:00+00:00",
            source_origin="imported",
            payload={"status": "open"},
        ),
        ObjectVersion(
            collection="issues",
            object_id="x",
            version=2,
            change_kind="retracted",
            recorded_at="2026-07-14T01:00:00+00:00",
            source_origin="imported",
            payload=None,
        ),
        ObjectVersion(
            collection="issues",
            object_id="x",
            version=3,
            change_kind="created",
            recorded_at="2026-07-14T02:00:00+00:00",
            source_origin="imported",
            payload={"status": "open"},
        ),
    ]
    transitions = extract_status_transitions(versions)
    assert [(t.from_status, t.to_status, t.version) for t in transitions] == [
        (None, "open", 1),
        (None, "open", 3),
    ]


def test_changed_top_level_fields_sorted_and_symmetric() -> None:
    old = {"a": 1, "b": 2, "c": 3}
    new = {"a": 1, "b": 9, "d": 4}
    assert changed_top_level_fields(old, new) == ["b", "c", "d"]


def test_history_empty_for_unknown_or_precapture_object(service: IngestService) -> None:
    """캡처 이전(synthetic) 객체는 빈 이력 — 오류가 아니다."""
    history = service.history("issues", "존재하지_않는_id")
    assert history.versions == []
    assert history.status_transitions == []
