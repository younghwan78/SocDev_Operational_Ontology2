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
