"""참조 무결성 테스트 — 배포 fixture는 오류 0건이어야 한다."""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository, check_integrity
from backend.ontology.event import DevelopmentEvent
from backend.ontology.project import Project

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


def test_shipped_fixtures_have_zero_errors(repo: InMemoryRepository) -> None:
    errors = [f for f in check_integrity(repo) if f.level == "error"]
    assert errors == [], "\n".join(f.message for f in errors)


def test_broken_reference_detected() -> None:
    """존재하지 않는 project_id 참조는 오류로 검출되어야 한다."""
    project = Project(id="project_x", name="X", type="t", phase="p")
    event = DevelopmentEvent(
        id="evt_broken",
        project_id="project_missing",
        title="t",
        description="d",
        event_type="et",
        event_category="ec",
    )
    repo = InMemoryRepository({"projects": [project], "development_events": [event]})
    errors = [f for f in check_integrity(repo) if f.level == "error"]
    assert any("project_missing" in f.message for f in errors)
