"""P1 프로세스 신호 — 전이 이력 기반 재개·정체 판정 (16_digital_twin_followups.md §2)."""

from __future__ import annotations

from backend.ingest.history import ObjectVersion
from backend.ingest.service import IngestService, MemoryIngestWriter
from backend.loaders.repository import InMemoryRepository
from backend.ontology.event import Issue
from backend.services.rca import RCAService


def _issue_row(issue_id: str, status: str, symptom: str = "화면 깨짐") -> dict[str, str]:
    return {
        "이슈 ID": issue_id,
        "프로젝트 ID": "proj_u",
        "제목": "ISP 출력 이상",
        "유형": "hw_bug",
        "상태": status,
        "증상": symptom,
        "확신도": "medium",
    }


def _make_service() -> tuple[InMemoryRepository, IngestService]:
    repo = InMemoryRepository({})
    return repo, IngestService(MemoryIngestWriter(repo))


def _issue_object(issue_id: str, status: str) -> Issue:
    return Issue.model_validate(
        {
            "id": issue_id,
            "project_id": "proj_u",
            "title": "ISP 출력 이상",
            "issue_type": "hw_bug",
            "status": status,
            "symptom": "화면 깨짐",
            "confidence": "medium",
            "source": {"origin": "imported", "ref": f"test:{issue_id}"},
        }
    )


def _version(
    issue_id: str, version: int, status: str, recorded_at: str, kind: str = "created"
) -> ObjectVersion:
    return ObjectVersion(
        collection="issues",
        object_id=issue_id,
        version=version,
        change_kind=kind,
        recorded_at=recorded_at,
        source_origin="imported",
        payload={"id": issue_id, "status": status},
    )


def test_reopened_issue_flagged_with_transition_basis() -> None:
    """수용 기준 1 — open→closed→open 반입 시 재개 신호 + 전이 근거 문구."""
    repo, service = _make_service()
    service.ingest_rows("w1.csv", [_issue_row("iss_re", "open")], "issues")
    service.ingest_rows("w2.csv", [_issue_row("iss_re", "closed")], "issues")
    service.ingest_rows("w3.csv", [_issue_row("iss_re", "open", symptom="재발")], "issues")

    rca = RCAService(repo, versions=service)
    summary = {s.issue_id: s for s in rca.list_issues()}["iss_re"]
    assert summary.reopened is True
    assert summary.freshness_ko is not None and "재개" in summary.freshness_ko
    assert summary.last_activity_at is not None

    chain = rca.chain("iss_re")
    assert chain.reopened is True
    assert chain.reopen_note_ko is not None and "v3" in chain.reopen_note_ko


def test_closed_then_stays_closed_is_not_reopened() -> None:
    repo, service = _make_service()
    service.ingest_rows("w1.csv", [_issue_row("iss_ok", "open")], "issues")
    service.ingest_rows("w2.csv", [_issue_row("iss_ok", "closed")], "issues")

    summary = {
        s.issue_id: s for s in RCAService(repo, versions=service).list_issues()
    }["iss_ok"]
    assert summary.reopened is False


def test_transition_stale_uses_log_reference_instant() -> None:
    """수용 기준 3 — 기준 시점(로그 최신 recorded_at) 대비 28일 이상 무활동 = 정체."""
    repo, service = _make_service()
    repo.add_objects("issues", [_issue_object("iss_old", "open")])
    repo.add_objects("issues", [_issue_object("iss_new", "open")])
    repo.add_objects("issues", [_issue_object("iss_closed_old", "closed")])
    service.collection_versions("issues")  # 빈 로그에서도 죽지 않는다
    writer_versions = [
        _version("iss_old", 1, "open", "2026-06-01T00:00:00+00:00"),
        _version("iss_new", 1, "open", "2026-07-10T00:00:00+00:00"),
        _version("iss_closed_old", 1, "closed", "2026-05-01T00:00:00+00:00"),
    ]
    # 감사 인프라 직접 적재 — 테스트 전용 (운영 경로는 ingest 관문뿐).
    service._writer.append_versions(writer_versions)  # noqa: SLF001

    summaries = {
        s.issue_id: s for s in RCAService(repo, versions=service).list_issues()
    }
    assert summaries["iss_old"].stale is True
    assert summaries["iss_old"].freshness_ko is not None
    assert "정체 — 마지막 기록 활동 2026-06-01" in summaries["iss_old"].freshness_ko
    assert summaries["iss_new"].stale is False
    # 종결 이슈는 오래됐어도 정체가 아니다.
    assert summaries["iss_closed_old"].stale is False


def test_fixture_only_fallback_matches_week_based_rule() -> None:
    """수용 기준 2 — 버전 소스 없으면(순수 fixture) 기존 주차 기반 판정 그대로."""
    repo, service = _make_service()
    service.ingest_rows("w1.csv", [_issue_row("iss_x", "open")], "issues")

    with_versions = {
        s.issue_id: s for s in RCAService(repo, versions=service).list_issues()
    }["iss_x"]
    without_versions = {s.issue_id: s for s in RCAService(repo).list_issues()}["iss_x"]
    assert without_versions.reopened is False
    assert without_versions.last_activity_at is None
    # 같은 날 반입이므로 전이 기반 정체도 없다 — 판정 자체는 동일.
    assert with_versions.stale == without_versions.stale


def test_deterministic_same_input_same_output() -> None:
    repo, service = _make_service()
    service.ingest_rows("w1.csv", [_issue_row("iss_d", "open")], "issues")
    service.ingest_rows("w2.csv", [_issue_row("iss_d", "resolved")], "issues")
    service.ingest_rows("w3.csv", [_issue_row("iss_d", "open", symptom="재발")], "issues")
    rca = RCAService(repo, versions=service)
    first = [s.model_dump() for s in rca.list_issues()]
    second = [s.model_dump() for s in rca.list_issues()]
    assert first == second
