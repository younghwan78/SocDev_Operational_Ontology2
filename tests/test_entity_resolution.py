"""엔티티 해석 테스트 — 별칭 해석의 결정론 + 미해석 큐 수집.

수용 기준: IPBlock alias/domain → canonical ip_id 고정, 미해석 토큰 큐 수집, 쓰기 없음.
"""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.ontology.ip import IPBlock
from backend.resolve.entity_resolution import (
    EntityResolutionReport,
    EntityResolutionService,
    IPAliasIndex,
    normalize_tokens,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


@pytest.fixture(scope="module")
def report(repo: InMemoryRepository) -> EntityResolutionReport:
    return EntityResolutionService(repo).report()


def test_normalize_splits_underscore() -> None:
    assert normalize_tokens("System_MMU") == {"system_mmu", "system", "mmu"}
    assert normalize_tokens("") == set()


def test_resolve_by_name_and_alias(repo: InMemoryRepository) -> None:
    index = IPAliasIndex(repo)
    blocks = [b for b in repo.list("ip_blocks") if isinstance(b, IPBlock)]
    assert blocks, "fixture에 IP 블록이 있어야 한다"
    for ip in blocks:
        assert index.resolve(ip.id) == ip.id
        assert index.resolve(ip.name) == ip.id
        for alias in ip.aliases:
            assert index.resolve(alias) == ip.id


def test_resolve_unknown_returns_none(repo: InMemoryRepository) -> None:
    assert IPAliasIndex(repo).resolve("완전히_없는_토큰_zzz") is None


def test_deterministic(repo: InMemoryRepository, report: EntityResolutionReport) -> None:
    again = EntityResolutionService(repo).report()
    assert report.model_dump() == again.model_dump()


def test_alias_entries_cover_all_ip_blocks(
    repo: InMemoryRepository, report: EntityResolutionReport
) -> None:
    ip_ids = {b.id for b in repo.list("ip_blocks") if isinstance(b, IPBlock)}
    assert {a.ip_id for a in report.aliases} == ip_ids


def test_unmatched_queue_is_sorted_and_resolvable_excluded(
    repo: InMemoryRepository, report: EntityResolutionReport
) -> None:
    index = IPAliasIndex(repo)
    # 미해석 큐의 토큰은 실제로 해석 불가여야 한다.
    for item in report.unmatched:
        assert index.resolve(item.token) is None
        assert item.occurrences >= 1
        assert item.sample_refs
    # 정렬: 빈도 내림차순, 토큰 오름차순.
    keys = [(-u.occurrences, u.token) for u in report.unmatched]
    assert keys == sorted(keys)
