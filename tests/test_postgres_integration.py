"""PostgreSQL 통합 테스트 — POSTGRES_TEST_DSN 설정 시에만 실행된다.

실행 예:
    POSTGRES_TEST_DSN=postgresql://user:pw@localhost:5432/soc_test \
        uv run pytest -m postgres -p no:cacheprovider
"""

import os
from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository, check_integrity

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
DSN = os.environ.get("POSTGRES_TEST_DSN")

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not DSN, reason="POSTGRES_TEST_DSN 미설정"),
]


@pytest.fixture(scope="module")
def pg_conn():
    import psycopg
    from backend.db.migrate import run_migrations

    conn = psycopg.connect(DSN)
    try:
        run_migrations(conn)
        conn.commit()
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture(scope="module")
def seeded(pg_conn):
    from backend.ingest.yaml_seed import seed_fixtures

    counts = seed_fixtures(pg_conn, FIXTURES)
    pg_conn.commit()
    return counts


def test_seed_counts_match_fixtures(seeded) -> None:
    memory = InMemoryRepository.from_fixtures(FIXTURES)
    for collection, count in seeded.items():
        assert count == len(memory.list(collection))


def test_repository_parity_with_memory(pg_conn, seeded) -> None:
    """PostgreSQL repository는 in-memory와 동일한 객체를 돌려줘야 한다."""
    from backend.db.repository import PostgresRepository

    memory = InMemoryRepository.from_fixtures(FIXTURES)
    pg = PostgresRepository(pg_conn)
    for collection in seeded:
        memory_objects = memory.list(collection)
        pg_objects = pg.list(collection)
        assert [o.id for o in pg_objects] == [o.id for o in memory_objects], collection
        assert pg_objects == memory_objects, f"{collection}: 모델 불일치"


def test_seed_is_idempotent(pg_conn, seeded) -> None:
    from backend.db.repository import PostgresRepository
    from backend.ingest.yaml_seed import seed_fixtures

    before = PostgresRepository(pg_conn).counts()
    seed_fixtures(pg_conn, FIXTURES)
    pg_conn.commit()
    after = PostgresRepository(pg_conn).counts()
    assert before == after


def test_integrity_on_postgres_repository(pg_conn, seeded) -> None:
    """무결성 검사가 PostgreSQL repository 위에서도 오류 0건이어야 한다."""
    from backend.db.repository import PostgresRepository

    findings = check_integrity(PostgresRepository(pg_conn))
    errors = [f for f in findings if f.level == "error"]
    assert errors == [], "\n".join(f.message for f in errors)


def test_relations_projection_populated(pg_conn, seeded) -> None:
    count = pg_conn.execute("SELECT count(*) FROM relations").fetchone()[0]
    assert count == seeded["relations"]


def test_semantic_chunks_projection_populated(pg_conn, seeded) -> None:
    count = pg_conn.execute("SELECT count(*) FROM semantic_chunks").fetchone()[0]
    assert count == seeded["semantic_chunks"]


def test_postgres_run_store_roundtrip(pg_conn) -> None:
    """agent_runs 감사 기록의 PostgreSQL 저장/조회 왕복."""
    from datetime import UTC, datetime

    from backend.agents.run_store import PostgresRunStore
    from backend.ontology.relation import AgentRun

    store = PostgresRunStore(pg_conn)
    run = AgentRun(
        id="run_test_pg_0001",
        scenario_id="uhd60_recording_eis_on",
        status="completed",
        input_hash="abc123",
        requested_roles=["pm"],
        advisories=[],
        validation_notes=["테스트 기록"],
        duration_ms=12,
        created_at=datetime.now(UTC).isoformat(),
    )
    store.save(run)
    store.save(run)  # 멱등
    stored = store.list_for_scenario("uhd60_recording_eis_on")
    assert any(r.id == "run_test_pg_0001" for r in stored)
    match = next(r for r in stored if r.id == "run_test_pg_0001")
    assert match.validation_notes == ["테스트 기록"]


def test_postgres_ingest_and_rollback(pg_conn, seeded) -> None:
    """PostgreSQL 반입 → 조회 → rollback 왕복. synthetic 데이터는 보존."""
    from pathlib import Path

    from backend.db.repository import PostgresRepository
    from backend.ingest.service import IngestService, PostgresIngestWriter

    sample = Path(__file__).resolve().parents[1] / "samples" / "sample_milestones.csv"
    service = IngestService(PostgresIngestWriter(pg_conn))
    repo = PostgresRepository(pg_conn)
    before = len(repo.list("project_milestones"))

    report = service.ingest("sample_milestones.csv", sample.read_bytes(), "project_milestones")
    assert report.batch.accepted_count == 3
    assert len(repo.list("project_milestones")) == before + 3
    imported = repo.get("project_milestones", "import_u_pvt_review")
    assert imported is not None and imported.source.origin.value == "imported"

    removed = service.rollback(report.batch.id)
    assert removed == 3
    assert len(repo.list("project_milestones")) == before
    assert repo.get("project_milestones", "project_u_package_out_done") is not None
    assert service.list_batches()[0].status == "rolled_back"


def test_api_parity_memory_vs_postgres(pg_conn, seeded) -> None:
    """API 응답은 저장소 백엔드(메모리/PostgreSQL)와 무관하게 동일해야 한다."""
    from backend.api.app import create_app
    from backend.db.repository import PostgresRepository
    from fastapi.testclient import TestClient

    memory_client = TestClient(create_app())
    pg_client = TestClient(create_app(repo=PostgresRepository(pg_conn)))

    for path in (
        "/api/v1/scenarios/uhd60_recording_eis_on/analysis",
        "/api/v1/portfolio/overview",
        "/api/v1/review/weekly",
        "/api/v1/traceability/uhd60_recording_eis_on",
    ):
        memory_body = memory_client.get(path).json()
        pg_body = pg_client.get(path).json()
        assert memory_body == pg_body, f"{path}: 백엔드 간 응답 불일치"
