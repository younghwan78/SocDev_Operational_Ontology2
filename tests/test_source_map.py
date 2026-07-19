"""출처 지도 서비스 테스트 — origin 집계의 결정론 고정.

수용 기준: 동일 fixture → 동일 출력, 전 컬렉션 합계 일관, 수치 점수 부재.
"""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.services.source_map import SourceCoverage, SourceCoverageService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


@pytest.fixture(scope="module")
def coverage(repo: InMemoryRepository) -> SourceCoverage:
    return SourceCoverageService(repo).coverage()


def test_deterministic_same_fixture(repo: InMemoryRepository, coverage: SourceCoverage) -> None:
    again = SourceCoverageService(repo).coverage()
    assert coverage.model_dump() == again.model_dump()


def test_per_collection_counts_sum_to_total(coverage: SourceCoverage) -> None:
    for c in coverage.collections:
        assert c.synthetic + c.imported + c.integrated == c.total
        assert c.total > 0  # 빈 컬렉션은 제외됨
        assert 0 <= c.without_ref <= c.total


def test_totals_match_collection_sum(coverage: SourceCoverage) -> None:
    t = coverage.totals
    assert t.synthetic == sum(c.synthetic for c in coverage.collections)
    assert t.imported == sum(c.imported for c in coverage.collections)
    assert t.integrated == sum(c.integrated for c in coverage.collections)
    assert t.total == t.synthetic + t.imported + t.integrated


def test_collections_are_korean_labeled(coverage: SourceCoverage) -> None:
    """collection_ko는 glossary object_label에서 파생 — 원문 키 노출 금지."""
    for c in coverage.collections:
        assert c.collection_ko
        assert c.collection_ko != c.collection  # 최소한 라벨이 키와 다름(한국어화됨)


def test_fixture_is_mostly_synthetic(coverage: SourceCoverage) -> None:
    """현 fixture는 반입 전이므로 실데이터가 전체보다 작아야 한다."""
    t = coverage.totals
    assert t.total > 0
    assert t.imported + t.integrated < t.total
    assert t.real_data_note.startswith("실데이터")


def test_sorted_real_data_first(coverage: SourceCoverage) -> None:
    keys = [(-(c.imported + c.integrated), -c.total, c.collection) for c in coverage.collections]
    assert keys == sorted(keys)


# --- W2 (설계 22 §3): 링크 커버리지 ---


def test_link_coverage_counts_are_consistent(coverage: SourceCoverage) -> None:
    assert coverage.links, "fixture에 링크 대상 컬렉션 1개 이상"
    assert coverage.link_note_ko
    for link in coverage.links:
        assert 0 <= link.linked <= link.total
        assert link.total > 0  # 빈 컬렉션은 제외
        # linked는 "필드 중 하나 이상" — 필드별 건수 최댓값 이상, 합계 이하.
        field_counts = [f.linked for f in link.fields]
        assert link.linked >= max(field_counts, default=0)
        assert link.linked <= sum(field_counts)
        for field in link.fields:
            assert field.field_ko  # 표시 라벨 누락 금지


def test_link_coverage_action_items_control_group(coverage: SourceCoverage) -> None:
    """source_decision_id는 필수 필드 — 대조군은 항상 100%여야 한다."""
    control = next(
        (link for link in coverage.links if link.collection == "action_items"), None
    )
    assert control is not None
    assert control.linked == control.total


def test_link_coverage_sorted_worst_first(coverage: SourceCoverage) -> None:
    ratios = [link.linked / link.total for link in coverage.links]
    assert ratios == sorted(ratios)


def test_link_coverage_detects_unlinked_issue() -> None:
    """링크 필드가 전부 비면 linked에 세지 않는다 — 판정 룰 자체 검증."""
    from backend.ontology.event import Issue

    repo = InMemoryRepository({})
    repo.add_objects(
        "issues",
        [
            Issue.model_validate(
                {
                    "id": "iss_linked",
                    "project_id": "proj_u",
                    "title": "연결 있음",
                    "issue_type": "hw_bug",
                    "status": "open",
                    "symptom": "s",
                    "confidence": "medium",
                    "affected_scope": {"scenarios": ["sc_1"]},
                }
            ),
            Issue.model_validate(
                {
                    "id": "iss_orphan",
                    "project_id": "proj_u",
                    "title": "연결 없음",
                    "issue_type": "hw_bug",
                    "status": "open",
                    "symptom": "s",
                    "confidence": "medium",
                }
            ),
        ],
    )
    links = SourceCoverageService(repo).coverage().links
    issue_link = next(link for link in links if link.collection == "issues")
    assert issue_link.total == 2
    assert issue_link.linked == 1
    scenario_field = next(
        f for f in issue_link.fields if f.field == "affected_scope.scenarios"
    )
    assert scenario_field.linked == 1
