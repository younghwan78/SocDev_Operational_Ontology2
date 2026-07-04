"""반입 파이프라인 테스트 — 파싱/매핑/검증/저장/rollback."""

from pathlib import Path

import pytest
from backend.ingest.service import IngestError, IngestService, MemoryIngestWriter
from backend.ingest.tabular import TabularParseError, parse_csv, parse_tabular
from backend.loaders.repository import InMemoryRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
SAMPLE = ROOT / "samples" / "sample_milestones.csv"


@pytest.fixture()
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


@pytest.fixture()
def service(repo: InMemoryRepository) -> IngestService:
    return IngestService(MemoryIngestWriter(repo))


def test_parse_csv_korean_headers() -> None:
    rows = parse_csv(SAMPLE.read_bytes())
    assert len(rows) == 3
    assert rows[0]["마일스톤 ID"] == "import_u_pvt_review"


def test_parse_unsupported_extension() -> None:
    with pytest.raises(TabularParseError):
        parse_tabular("data.txt", b"x")


def test_ingest_sample_milestones(repo: InMemoryRepository, service: IngestService) -> None:
    before = len(repo.list("project_milestones"))
    report = service.ingest("sample_milestones.csv", SAMPLE.read_bytes(), "project_milestones")
    assert report.batch.accepted_count == 3
    assert report.batch.rejected_count == 0
    assert len(repo.list("project_milestones")) == before + 3

    imported = repo.get("project_milestones", "import_u_pvt_review")
    assert imported is not None
    assert imported.source.origin.value == "imported"
    assert imported.source.ref and imported.source.ref.startswith("import:")
    assert imported.week == 40
    assert imported.relevant_roles == ["pm", "hw_development"]


def test_ingest_rejects_bad_rows_korean_report(service: IngestService) -> None:
    csv_content = (
        "마일스톤 ID,프로젝트 ID,제목,설명,유형,개발 단계,결정 구간,주차,분기,관련 역할\n"
        ",project_u,제목없음ID없음,d,t,s,w,10,Q1,pm\n"
        "import_bad_week,project_u,주차가 문자,d,t,s,w,십이,Q1,pm\n"
        "import_ok,project_u,정상 행,d,t,s,w,12,Q1,pm\n"
    ).encode()
    report = service.ingest("bad.csv", csv_content, "project_milestones")
    assert report.batch.accepted_count == 1
    assert report.batch.rejected_count == 2
    reasons = {r.row_number: r.reason for r in report.rejected_rows}
    assert "필수 열 누락" in reasons[1]
    assert "형 변환 실패" in reasons[2] or "검증 실패" in reasons[2]


def test_ingest_unknown_mapping(service: IngestService) -> None:
    with pytest.raises(IngestError):
        service.ingest("x.csv", b"a,b\n1,2\n", "없는_매핑")


def test_rollback_removes_batch(repo: InMemoryRepository, service: IngestService) -> None:
    before = len(repo.list("project_milestones"))
    report = service.ingest("sample_milestones.csv", SAMPLE.read_bytes(), "project_milestones")
    assert len(repo.list("project_milestones")) == before + 3

    removed = service.rollback(report.batch.id)
    assert removed == 3
    assert len(repo.list("project_milestones")) == before
    batches = service.list_batches()
    assert batches[0].status == "rolled_back"


def test_synthetic_data_untouched_by_rollback(
    repo: InMemoryRepository, service: IngestService
) -> None:
    report = service.ingest("sample_milestones.csv", SAMPLE.read_bytes(), "project_milestones")
    service.rollback(report.batch.id)
    assert repo.get("project_milestones", "project_u_package_out_done") is not None


def test_ingest_api_roundtrip() -> None:
    from backend.api.app import create_app
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/ingest/file",
        params={"mapping": "project_milestones"},
        files={"file": ("sample_milestones.csv", SAMPLE.read_bytes(), "text/csv")},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["batch"]["accepted_count"] == 3

    batches = client.get("/api/v1/ingest/batches").json()
    assert batches[0]["id"] == report["batch"]["id"]

    rollback = client.post(f"/api/v1/ingest/batches/{report['batch']['id']}/rollback")
    assert rollback.json()["removed"] == 3

    bad = client.post(
        "/api/v1/ingest/file",
        params={"mapping": "없는매핑"},
        files={"file": ("x.csv", b"a\n1\n", "text/csv")},
    )
    assert bad.status_code == 400
