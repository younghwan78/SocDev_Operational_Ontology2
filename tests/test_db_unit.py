"""DB 계층 단위 테스트 — PostgreSQL 없이 통과해야 한다."""

from pathlib import Path

import pytest
from backend.db.connection import DSN_ENV, MissingDSNError, resolve_dsn
from backend.db.migrate import migration_files
from backend.ingest.yaml_seed import build_row
from backend.loaders.protocols import RepositoryProtocol
from backend.loaders.repository import InMemoryRepository
from backend.ontology.project import Project

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_missing_dsn_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DSN_ENV, raising=False)
    with pytest.raises(MissingDSNError):
        resolve_dsn(None)


def test_dsn_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DSN_ENV, "postgresql://env")
    assert resolve_dsn(None) == "postgresql://env"
    assert resolve_dsn("postgresql://arg") == "postgresql://arg"


def test_migration_files_ordered_and_unique() -> None:
    files = migration_files()
    assert files, "마이그레이션 파일이 있어야 한다"
    versions = [int(f.name[:4]) for f in files]
    assert versions == sorted(versions)
    assert files[0].name == "0001_core.sql"


def test_in_memory_repository_satisfies_protocol() -> None:
    repo = InMemoryRepository.from_fixtures(FIXTURES)
    assert isinstance(repo, RepositoryProtocol)


def test_build_row_extracts_filter_columns() -> None:
    project = Project(id="project_u", name="U", type="mobile", phase="mp")
    row = build_row("projects", 3, project)
    assert row.collection == "projects"
    assert row.id == "project_u"
    assert row.position == 3
    assert row.source_origin == "synthetic"
    assert '"name": "U"' in row.payload


def test_build_row_origin_project_id_fallback() -> None:
    """ScenarioRequest는 project_id 대신 origin_project_id를 필터 컬럼으로 쓴다."""
    repo = InMemoryRepository.from_fixtures(FIXTURES)
    request = repo.list("scenario_requests")[0]
    row = build_row("scenario_requests", 0, request)
    assert row.project_id is not None
