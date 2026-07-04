"""fixture 적재 테스트 — 전 컬렉션이 모델 검증을 통과해야 한다."""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.ontology import COLLECTIONS

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="session")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


def test_all_collections_load(repo: InMemoryRepository) -> None:
    for key in COLLECTIONS:
        assert repo.list(key), f"컬렉션 비어 있음: {key}"


def test_known_objects_exist(repo: InMemoryRepository) -> None:
    assert repo.get("projects", "project_u") is not None
    assert repo.get("scenarios", "uhd60_recording_eis_on") is not None
    assert repo.get("ip_blocks", "ip_isp") is not None
    assert repo.get("roles", "management") is not None or repo.list("roles")


def test_role_agents_are_exactly_seven(repo: InMemoryRepository) -> None:
    """CLAUDE.md §2.2 — role agent는 정확히 7개."""
    assert len(repo.list("roles")) == 7


def test_legacy_events_promoted(repo: InMemoryRepository) -> None:
    """구 events.yaml 4건이 DevelopmentEvent로 승격되어 총 63건이어야 한다."""
    events = repo.list("development_events")
    assert len(events) == 63
    legacy = [e for e in events if e.event_category == "legacy_event"]
    assert len(legacy) == 4


def test_every_object_has_synthetic_source(repo: InMemoryRepository) -> None:
    for key in COLLECTIONS:
        for obj in repo.list(key):
            assert obj.source.origin.value == "synthetic"
            assert obj.source.ref and obj.source.ref.startswith("56:synthetic_data/")
