"""설계 25 — 리허설 변환·리플레이 가드 검증.

57 world.yaml이 있는 머신에서만 변환 테스트가 돈다 (converter roundtrip과
같은 gate 방식). DSN 가드는 어디서나 검증된다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORLD_57 = Path(r"E:\57_Claude_SoC_DigitalTwin\OperationalOntology\data\world.yaml")

sys.path.insert(0, str(ROOT))


@pytest.mark.skipif(not WORLD_57.exists(), reason="57 참조 world.yaml 없음")
def test_build_is_deterministic_and_contract_clean(tmp_path: Path) -> None:
    from datetime import date

    from backend.connectors.jira import FakeJiraClient, JiraConnector, JiraFieldMap
    from tools.build_rehearsal_from_57 import build

    plan_a = build(WORLD_57, tmp_path / "a", date(2025, 8, 4))
    plan_b = build(WORLD_57, tmp_path / "b", date(2025, 8, 4))
    assert plan_a["waves"] == plan_b["waves"]  # 결정론
    assert plan_a["issue_count"] >= 60
    assert plan_a["page_count"] >= 50

    field_map = JiraFieldMap.load(tmp_path / "a" / "jira_field_map.rehearsal.yaml")
    statuses: set[str] = set()
    required = {"이슈 ID", "프로젝트 ID", "제목", "유형", "상태", "증상", "확신도"}
    first_seen: dict[str, int] = {}
    v_transition_weeks: set[int] = set()
    for wave in plan_a["waves"]:
        if "jira" not in wave:
            continue
        connector = JiraConnector(
            FakeJiraClient(tmp_path / "a" / wave["jira"]), field_map
        )
        rows, refs = connector.rows()
        assert len(rows) == len(refs)
        week = int(wave["week"])
        for row in rows:
            # 필수 열이 전부 채워진다 — field map으로 전량 해석 가능.
            assert all(row.get(col, "").strip() for col in required), row
            statuses.add(row["상태"])
            key = row["이슈 ID"]
            if key not in first_seen:
                first_seen[key] = week  # 생성 — 전이가 아니다
            elif row["프로젝트 ID"] == "project_v":
                v_transition_weeks.add(week)
    # 의도된 미등재 상태가 심겨 있다 (경고 UX 검증 재료).
    assert "In Review" in statuses
    # 기록 규율 왜곡: project_v의 W30~37 상태 전이(생성 제외)는 W38로 몰려 있다.
    assert not (v_transition_weeks & set(range(30, 38)))
    assert 38 in v_transition_weeks


@pytest.mark.skipif(not WORLD_57.exists(), reason="57 참조 world.yaml 없음")
def test_confluence_pages_feed_semantic_chunks(tmp_path: Path) -> None:
    from datetime import date

    from backend.connectors.confluence import ConfluenceConnector, FakeConfluenceClient
    from backend.ingest.service import IngestService, MemoryIngestWriter
    from backend.loaders.repository import InMemoryRepository
    from tools.build_rehearsal_from_57 import build

    plan = build(WORLD_57, tmp_path, date(2025, 8, 4))
    repo = InMemoryRepository({})
    service = IngestService(MemoryIngestWriter(repo))
    total = 0
    official = 0
    for wave in plan["waves"]:
        if "confluence" not in wave:
            continue
        report = ConfluenceConnector(
            FakeConfluenceClient(tmp_path / wave["confluence"])
        ).sync(service, source_name=f"test:W{wave['week']}")
        assert report.batch.rejected_count == 0
        total += report.batch.accepted_count
        pages = json.loads(
            (tmp_path / wave["confluence"]).read_text(encoding="utf-8")
        )["pages"]
        official += sum(1 for p in pages if "[설계문서]" in p["title"])
    assert total >= 50  # 세부 서사·리포트·결정 노트·회의록이 검색 후보로 반입됨
    assert official >= 4  # 공식 architecture 문서 계층 존재 (W 프로젝트)


def test_replay_refuses_non_rehearsal_dsn(tmp_path: Path) -> None:
    """DSN 가드 — 운영/데모 DB에 주입 시계를 쓸 수 없다."""
    from backend.cli.main import app
    from typer.testing import CliRunner

    result = CliRunner().invoke(
        app,
        [
            "rehearsal-replay",
            "--dir",
            str(tmp_path),
            "--dsn",
            "postgresql://soc:x@127.0.0.1:5432/soc_ontology",
        ],
    )
    assert result.exit_code == 1
    assert "rehearsal" in result.output
