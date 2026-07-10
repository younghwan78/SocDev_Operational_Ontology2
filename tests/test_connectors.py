"""JIRA/Confluence 커넥터 테스트 — 정규화/설정 매핑/ingest 경유/rollback.

네트워크 없음: Fake 클라이언트 + fixture payload만 사용한다.
설계: internal_docs/design/12_jira_connector.md
"""

from pathlib import Path

import pytest
from backend.connectors.confluence import ConfluenceConnector, FakeConfluenceClient
from backend.connectors.jira import (
    FakeJiraClient,
    JiraConnector,
    JiraFieldMap,
    extract_path,
)
from backend.ingest.service import IngestService, MemoryIngestWriter
from backend.loaders.repository import InMemoryRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
JIRA_PAYLOAD = ROOT / "samples" / "sample_jira_issues.json"
CONFLUENCE_PAYLOAD = ROOT / "samples" / "sample_confluence_pages.json"


@pytest.fixture()
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


@pytest.fixture()
def service(repo: InMemoryRepository) -> IngestService:
    return IngestService(MemoryIngestWriter(repo))


def test_extract_path_dict_list_missing() -> None:
    payload = {"fields": {"labels": ["project_v"], "status": {"name": "Open"}}}
    assert extract_path(payload, "fields.labels.0") == "project_v"
    assert extract_path(payload, "fields.status.name") == "Open"
    assert extract_path(payload, "fields.없는.경로") == ""


def test_field_map_loads_default_yaml() -> None:
    field_map = JiraFieldMap.load()
    assert field_map.issue_mapping == "issues"
    assert field_map.columns["이슈 ID"] == "key"
    assert field_map.value_maps["상태"]["Closed"] == "closed"
    assert field_map.constants["확신도"] == "medium"


def test_jira_rows_normalization() -> None:
    connector = JiraConnector(FakeJiraClient(JIRA_PAYLOAD), JiraFieldMap.load())
    rows, refs = connector.rows()
    assert len(rows) == 3
    assert refs == ["jira:MMIP-101", "jira:MMIP-102", "jira:MMIP-103"]

    first = rows[0]
    assert first["이슈 ID"] == "MMIP-101"
    assert first["프로젝트 ID"] == "project_v"
    assert first["상태"] == "open", "value_map이 'In Progress'를 open으로 정규화"
    assert first["유형"] == "defect"
    assert first["심각도"] == "high"
    assert first["확신도"] == "medium", "constants 고정값"
    assert rows[1]["상태"] == "closed"
    assert rows[2]["심각도"] == "critical", "Highest → critical"


def test_jira_sync_ingests_as_integrated(
    repo: InMemoryRepository, service: IngestService
) -> None:
    from backend.services.risk import RiskService

    connector = JiraConnector(FakeJiraClient(JIRA_PAYLOAD), JiraFieldMap.load())
    report = connector.sync(service)
    assert report.batch.accepted_count == 3
    assert report.batch.rejected_count == 0

    issue = repo.get("issues", "MMIP-101")
    assert issue is not None
    assert issue.source.origin.value == "integrated", "커넥터 반입은 integrated"
    assert issue.source.ref == f"import:{report.batch.id}:jira:MMIP-101", (
        "rollback 접두 + 외부 키 합성 계보"
    )
    assert issue.affected_scope.scenarios == ["uhd60_recording_eis_on"]
    assert issue.affected_scope.ip_blocks == ["ip_isp"]

    # 파생 뷰 반영: open 이슈가 위험 지도 셀 근거로 등장.
    heatmap = RiskService(repo).heatmap(project_id="project_v")
    row = next(r for r in heatmap.rows if r.scenario_id == "uhd60_recording_eis_on")
    cell = next(c for c in row.cells if c.ip_id == "ip_isp")
    assert any(b.ref_id == "MMIP-101" for b in cell.basis)

    removed = service.rollback(report.batch.id)
    assert removed == 3
    assert repo.get("issues", "MMIP-101") is None


def test_confluence_pages_become_search_candidates(
    repo: InMemoryRepository, service: IngestService
) -> None:
    connector = ConfluenceConnector(FakeConfluenceClient(CONFLUENCE_PAYLOAD))
    report = connector.sync(service)
    assert report.batch.accepted_count == 2
    assert report.batch.rejected_count == 0

    chunk = repo.get("semantic_chunks", "chunk_confluence_9001")
    assert chunk is not None
    assert chunk.source.origin.value == "integrated"
    assert chunk.source_type == "confluence_page"
    assert chunk.embedding_status == "pending"
    assert chunk.evidence_confidence == "low", "검색 후보 지위 — 증거 아님"
    assert "M2M 재인출" in chunk.chunk_text

    assert service.rollback(report.batch.id) == 2


def test_ingest_rows_row_refs_length_mismatch(service: IngestService) -> None:
    from backend.ingest.service import IngestError

    with pytest.raises(IngestError):
        service.ingest_rows("x", [{"a": "1"}], "issues", row_refs=["r1", "r2"])


def test_field_map_custom_yaml(tmp_path: Path, service: IngestService) -> None:
    """사내 스키마 교체 시나리오 — YAML만 바꿔 다른 필드 배치를 수용."""
    custom = tmp_path / "map.yaml"
    custom.write_text(
        """
issue_mapping: issues
columns:
  이슈 ID: key
  제목: fields.title
  유형: fields.kind
  상태: fields.state
  증상: fields.detail
  프로젝트 ID: fields.project
constants:
  확신도: low
""",
        encoding="utf-8",
    )
    payload = tmp_path / "payload.json"
    payload.write_text(
        """
{"issues": [{"key": "X-1", "fields": {"title": "t", "kind": "defect",
 "state": "open", "detail": "d", "project": "project_u"}}]}
""",
        encoding="utf-8",
    )
    connector = JiraConnector(FakeJiraClient(payload), JiraFieldMap.load(custom))
    report = connector.sync(service)
    assert report.batch.accepted_count == 1
