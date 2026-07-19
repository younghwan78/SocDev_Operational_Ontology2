"""W3 OCEL 2.0 export — 구조·결정론·시간 축 정직성 검증 (설계 22 §4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from backend.ingest.history import ObjectVersion
from backend.ingest.service import IngestService, MemoryIngestWriter
from backend.loaders.repository import InMemoryRepository
from backend.ontology.event import Issue
from backend.services.ocel_export import build_ocel
from backend.services.source_map import LINK_FIELDS

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _issue_payload(issue_id: str, status: str, scenarios: list[str]) -> dict:
    return Issue.model_validate(
        {
            "id": issue_id,
            "project_id": "project_u",
            "title": "ISP 전력 이슈",
            "issue_type": "power_gap",
            "status": status,
            "symptom": "전력 초과",
            "confidence": "medium",
            "affected_scope": {"scenarios": scenarios},
            "source": {"origin": "imported", "ref": f"test:{issue_id}"},
        }
    ).model_dump(mode="json", exclude_none=True)


@pytest.fixture(scope="module")
def fixture_setup() -> tuple[InMemoryRepository, IngestService]:
    repo = InMemoryRepository.from_fixtures(FIXTURES)
    service = IngestService(MemoryIngestWriter(repo))
    scenario_id = repo.list("scenarios")[0].id
    service._writer.append_versions(  # noqa: SLF001 — 테스트 전용 직접 적재
        [
            ObjectVersion(
                collection="issues",
                object_id="iss_ocel",
                version=1,
                change_kind="created",
                recorded_at="2026-07-01T09:00:00+00:00",
                batch_id="batch_1",
                source_origin="imported",
                payload=_issue_payload("iss_ocel", "open", [scenario_id]),
            ),
            ObjectVersion(
                collection="issues",
                object_id="iss_ocel",
                version=2,
                change_kind="updated",
                recorded_at="2026-07-05T09:00:00+00:00",
                batch_id="batch_2",
                source_origin="imported",
                payload=_issue_payload("iss_ocel", "resolved", [scenario_id]),
            ),
        ]
    )
    repo.add_objects(
        "issues",
        [Issue.model_validate(_issue_payload("iss_ocel", "resolved", [scenario_id]))],
    )
    return repo, service


def test_required_ocel_keys_and_counts(fixture_setup) -> None:
    repo, service = fixture_setup
    document = build_ocel(repo, service)
    assert set(document) == {"meta", "objectTypes", "eventTypes", "objects", "events"}
    # 이벤트 수 = 버전 로그 행 수 (여기서는 iss_ocel 2건).
    assert len(document["events"]) == 2
    for event in document["events"]:
        assert {"id", "type", "time", "attributes", "relationships"} <= set(event)
    for obj in document["objects"]:
        assert {"id", "type", "attributes", "relationships"} <= set(obj)


def test_events_carry_subject_and_status_refinement(fixture_setup) -> None:
    repo, service = fixture_setup
    events = build_ocel(repo, service)["events"]
    first, second = events
    # 시간순 정렬 + status 전이 세분 타입.
    assert first["time"] < second["time"]
    assert first["type"] == "issues_status_open"
    assert second["type"] == "issues_status_resolved"
    for event in (first, second):
        qualifiers = {r["qualifier"] for r in event["relationships"]}
        assert "subject" in qualifiers
        assert "affected_scope.scenarios" in qualifiers  # payload 링크 필드 유래


def test_o2o_only_from_link_fields(fixture_setup) -> None:
    repo, service = fixture_setup
    document = build_ocel(repo, service)
    allowed = {path for paths in LINK_FIELDS.values() for path in paths}
    exported_ids = {obj["id"] for obj in document["objects"]}
    for obj in document["objects"]:
        for rel in obj["relationships"]:
            assert rel["qualifier"] in allowed
            assert rel["objectId"] in exported_ids  # 존재하지 않는 대상 참조 금지


def test_no_fabricated_timestamps_from_week(fixture_setup) -> None:
    """domain time(week)은 이벤트 시각이 되지 않는다 — attribute로만 남는다."""
    repo, service = fixture_setup
    document = build_ocel(repo, service)
    version_times = {"2026-07-01T09:00:00+00:00", "2026-07-05T09:00:00+00:00"}
    assert {e["time"] for e in document["events"]} == version_times
    issue_type = next(t for t in document["objectTypes"] if t["name"] == "issues")
    assert any(a["name"] == "status" for a in issue_type["attributes"])
    assert "transaction time" in document["meta"]["note_ko"]


def test_deterministic_output(fixture_setup) -> None:
    repo, service = fixture_setup
    assert build_ocel(repo, service) == build_ocel(repo, service)
