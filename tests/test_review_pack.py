"""리뷰 팩 조립 테스트 — 결정론 조립 + 롤업 일치 + 무저장 + 404.

수용 기준(설계 10 §5): 동일 fixture→동일 조립, rollup 집계=시나리오 합, 없는 pack→404,
score/weight/rank 필드 부재.
"""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.ontology.decision import ReviewPack
from backend.services.review_pack import (
    ReviewPackDocument,
    ReviewPackNotFoundError,
    ReviewPackRollup,
    ReviewPackService,
    ReviewPackSummary,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


def _a_pack_id(repo: InMemoryRepository) -> str:
    pack = next(p for p in repo.list("review_packs") if isinstance(p, ReviewPack))
    return pack.id


@pytest.fixture(scope="module")
def document(repo: InMemoryRepository) -> ReviewPackDocument:
    return ReviewPackService(repo).assemble(_a_pack_id(repo))


def test_list_packs_covers_fixture(repo: InMemoryRepository) -> None:
    ids = {p.id for p in repo.list("review_packs") if isinstance(p, ReviewPack)}
    assert {s.pack_id for s in ReviewPackService(repo).list_packs()} == ids


def test_deterministic(repo: InMemoryRepository, document: ReviewPackDocument) -> None:
    again = ReviewPackService(repo).assemble(document.pack_id)
    assert document.model_dump() == again.model_dump()


def test_scenarios_assembled(repo: InMemoryRepository, document: ReviewPackDocument) -> None:
    pack = next(
        p
        for p in repo.list("review_packs")
        if isinstance(p, ReviewPack) and p.id == document.pack_id
    )
    # 존재하는 시나리오는 모두 초안으로 포함된다.
    assembled = {d.scenario_id for d in document.scenarios}
    existing = {s for s in pack.scenario_ids if repo.get("scenarios", s) is not None}
    assert assembled == existing
    assert document.rollup.scenario_count == len(document.scenarios)


def test_rollup_matches_scenario_sums(document: ReviewPackDocument) -> None:
    risk = issue = gap = measured = predicted = absent = 0
    for d in document.scenarios:
        for s in d.sections:
            if s.kind == "risk":
                risk += len(s.items)
            elif s.kind == "issue":
                issue += len(s.items)
            elif s.kind == "evidence_gap":
                gap += len(s.items)
        if d.evidence_posture is not None:
            measured += d.evidence_posture.measured
            predicted += d.evidence_posture.predicted
            absent += d.evidence_posture.absent
    r = document.rollup
    assert (r.risk_items, r.issue_items, r.evidence_gap_items) == (risk, issue, gap)
    assert (r.measured, r.predicted, r.absent) == (measured, predicted, absent)


def test_unknown_pack_raises(repo: InMemoryRepository) -> None:
    with pytest.raises(ReviewPackNotFoundError):
        ReviewPackService(repo).assemble("존재하지_않는_팩")


def test_no_numeric_score_fields() -> None:
    for model in (ReviewPackSummary, ReviewPackRollup, ReviewPackDocument):
        for name in model.model_fields:
            assert "score" not in name
            assert "weight" not in name
            assert "rank" not in name


def test_no_store_side_effect(repo: InMemoryRepository, document: ReviewPackDocument) -> None:
    before = {k: len(repo.list(k)) for k in ("review_packs", "decisions", "scenarios")}
    ReviewPackService(repo).assemble(document.pack_id)
    after = {k: len(repo.list(k)) for k in before}
    assert before == after


def test_provenance_present(document: ReviewPackDocument) -> None:
    assert "결정" in document.provenance_note
    assert "ingest" in document.provenance_note
