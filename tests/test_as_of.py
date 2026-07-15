"""P2 T3 as-of 재구성 — 재생 규칙표 검증 (16_digital_twin_followups.md §3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.ingest.history import ObjectVersion
from backend.ingest.service import IngestService, MemoryIngestWriter
from backend.loaders.repository import InMemoryRepository
from backend.ontology.event import Issue
from backend.services.as_of import AsOfService, InvalidTimestampError
from backend.services.risk import RiskService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _issue_payload(issue_id: str, status: str) -> dict:
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
    ).model_dump(mode="json", exclude_none=True)


def _version(
    issue_id: str,
    version: int,
    recorded_at: str,
    kind: str,
    status: str | None = None,
) -> ObjectVersion:
    return ObjectVersion(
        collection="issues",
        object_id=issue_id,
        version=version,
        change_kind=kind,
        recorded_at=recorded_at,
        source_origin="imported",
        payload=_issue_payload(issue_id, status) if status is not None else None,
    )


def _setup() -> tuple[InMemoryRepository, AsOfService]:
    repo = InMemoryRepository({})
    service = IngestService(MemoryIngestWriter(repo))
    # 규칙표 재료 — 결정론 타임스탬프를 위해 감사 로그를 직접 적재 (테스트 전용).
    service._writer.append_versions(  # noqa: SLF001
        [
            # A: created → updated → retracted(rollback) → created (번호 연속)
            _version("iss_a", 1, "2026-06-01T00:00:00+00:00", "created", "open"),
            _version("iss_a", 2, "2026-06-10T00:00:00+00:00", "updated", "closed"),
            _version("iss_a", 3, "2026-06-20T00:00:00+00:00", "retracted"),
            _version("iss_a", 4, "2026-06-25T00:00:00+00:00", "created", "open"),
            # C: 첫 버전이 updated — 캡처 이전부터 존재했던 객체
            _version("iss_c", 1, "2026-06-10T00:00:00+00:00", "updated", "open"),
            # D: ts 이전에 없던 신규 객체
            _version("iss_d", 1, "2026-06-10T00:00:00+00:00", "created", "open"),
        ]
    )
    # 현재 상태: A(v4)·C·D + 버전 없는 synthetic B
    for issue_id, status in (("iss_a", "open"), ("iss_c", "open"), ("iss_d", "open")):
        repo.add_objects("issues", [Issue.model_validate(_issue_payload(issue_id, status))])
    b = _issue_payload("iss_b", "open")
    b["source"] = {"origin": "synthetic", "ref": "fixture:test"}
    repo.add_objects("issues", [Issue.model_validate(b)])
    return repo, AsOfService(repo, service)


def _status_map(repo: InMemoryRepository) -> dict[str, str]:
    return {obj.id: obj.status for obj in repo.list("issues")}  # type: ignore[union-attr]


def test_replay_rule_table() -> None:
    """수용 기준 1 — 각 시점 재생 상태가 규칙표와 일치."""
    _, service = _setup()

    # 06-05: A=v1(open), C=근사(open), D=미생성 제외, B=가정 포함
    snapshot, meta = service.snapshot("2026-06-05T00:00:00+00:00")
    statuses = _status_map(snapshot)
    assert statuses == {"iss_a": "open", "iss_b": "open", "iss_c": "open"}
    assert meta.approximated_objects == 1  # C
    assert meta.excluded_objects == 1  # D
    assert meta.precapture_assumed_objects >= 1  # B

    # 06-15: A=v2(closed), C·D 실재
    snapshot, _ = service.snapshot("2026-06-15T00:00:00+00:00")
    assert _status_map(snapshot)["iss_a"] == "closed"
    assert set(_status_map(snapshot)) == {"iss_a", "iss_b", "iss_c", "iss_d"}

    # 06-22: A는 철회 상태 — 제외
    snapshot, meta = service.snapshot("2026-06-22T00:00:00+00:00")
    assert "iss_a" not in _status_map(snapshot)
    assert meta.excluded_objects == 1  # A (D는 이미 생성됨)

    # 06-30: A=v4(open, 재생성)
    snapshot, _ = service.snapshot("2026-06-30T00:00:00+00:00")
    assert _status_map(snapshot)["iss_a"] == "open"


def test_versionless_objects_always_included_with_assumption_count() -> None:
    """수용 기준 2 — synthetic(버전 없음)은 항상 포함 + 가정 건수 명시."""
    _, service = _setup()
    snapshot, meta = service.snapshot("2026-01-01T00:00:00+00:00")
    assert "iss_b" in _status_map(snapshot)
    assert meta.precapture_assumed_objects == 1
    assert "가정" in meta.note_ko


def test_as_of_heatmap_matches_current_when_log_empty() -> None:
    """수용 기준 3 — 빈 로그의 as-of 지도는 현재 지도와 동일 (동일 룰·동일 계약)."""
    repo = InMemoryRepository.from_fixtures(FIXTURES)
    service = AsOfService(repo, IngestService(MemoryIngestWriter(repo)))
    snapshot, meta = service.snapshot("2026-07-15T00:00:00+00:00")
    baseline = RiskService(repo).heatmap()
    replayed = RiskService(snapshot).heatmap()
    assert replayed.model_dump() == baseline.model_dump()
    assert meta.replayed_versions == 0
    assert meta.skipped_invalid == 0


def test_invalid_timestamp_rejected() -> None:
    _, service = _setup()
    with pytest.raises(InvalidTimestampError):
        service.snapshot("어제쯤")


def test_naive_and_z_suffix_timestamps_accepted() -> None:
    _, service = _setup()
    for ts in ("2026-06-15T00:00:00Z", "2026-06-15T00:00:00"):
        snapshot, _ = service.snapshot(ts)
        assert _status_map(snapshot)["iss_a"] == "closed"
