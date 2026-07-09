"""근거 신뢰 사다리 테스트 — 정성 등급 분류의 결정론 + 근거 동반 + 수치 점수 부재.

수용 기준(설계 09 §5): 동일 fixture→동일 사다리, 항목마다 정확히 한 tier+근거,
분포 합=항목 수=필터된 evidence_catalog 수, 한국어 라벨, score/weight/rank 필드 부재.
"""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.ontology.evidence import EvidenceCatalogEntry
from backend.services.evidence_ladder import (
    TIER_LABELS,
    TIER_ORDER,
    EvidenceLadder,
    EvidenceLadderService,
    EvidenceStrengthItem,
    LadderTotals,
    TierBucket,
    classify_evidence,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


@pytest.fixture(scope="module")
def ladder(repo: InMemoryRepository) -> EvidenceLadder:
    return EvidenceLadderService(repo).ladder()


def _entry(**overrides: object) -> EvidenceCatalogEntry:
    base: dict[str, object] = dict(
        id="ev_test",
        project_id="project_u",
        scenario_id="scn_test",
        title="테스트 근거",
        evidence_type="measurement",
        availability="available",
        confidence_contribution="medium",
        is_measurement=False,
        is_prediction=False,
        known_limitation="",
        measurement_stage="architecture",
        scenario_match="partial",
        source_system="sim",
        source_ref="ref://test",
        week=1,
    )
    base.update(overrides)
    return EvidenceCatalogEntry(**base)


def test_deterministic_same_fixture_same_ladder(repo, ladder) -> None:
    again = EvidenceLadderService(repo).ladder()
    assert ladder.model_dump() == again.model_dump()


def test_every_entry_classified_with_basis(ladder) -> None:
    for item in ladder.entries:
        assert item.tier in TIER_LABELS
        assert item.tier_ko == TIER_LABELS[item.tier]
        assert item.basis, f"근거 없는 등급: {item.evidence_id}"
        for b in item.basis:
            assert b.ref_id == item.evidence_id
            assert b.ref_collection == "evidence_catalog"
            assert b.description


def test_distribution_counts_sum_to_entries(repo, ladder) -> None:
    total_catalog = sum(
        1 for e in repo.list("evidence_catalog") if isinstance(e, EvidenceCatalogEntry)
    )
    assert ladder.totals.total == total_catalog
    assert len(ladder.entries) == total_catalog
    assert sum(b.count for b in ladder.distribution) == total_catalog
    # 실측 + 예측(에뮬 포함) + 부재 = 전체.
    assert (
        ladder.totals.measured + ladder.totals.predicted + ladder.totals.absent
        == total_catalog
    )


def test_distribution_is_strong_to_weak_order(ladder) -> None:
    assert [b.tier for b in ladder.distribution] == TIER_ORDER


def test_entries_sorted_strongest_first(ladder) -> None:
    rank = {tier: i for i, tier in enumerate(TIER_ORDER)}
    ranks = [rank[i.tier] for i in ladder.entries]
    assert ranks == sorted(ranks), "강한 근거가 먼저 보여야 한다"


def test_no_numeric_score_fields() -> None:
    for model in (EvidenceStrengthItem, TierBucket, LadderTotals, EvidenceLadder):
        for name in model.model_fields:
            assert "score" not in name
            assert "weight" not in name
            assert "rank" not in name


def test_project_and_scenario_filter(repo) -> None:
    service = EvidenceLadderService(repo)
    full = service.ladder()
    filtered = service.ladder(project_id="project_u")
    assert filtered.totals.total <= full.totals.total
    assert all(i.project_id == "project_u" for i in filtered.entries)
    if filtered.entries:
        scn = filtered.entries[0].scenario_id
        by_scn = service.ladder(scenario_id=scn)
        assert all(i.scenario_id == scn for i in by_scn.entries)


# ---- classify_evidence 규칙 경계 (단위) ----


def test_absent_takes_precedence_over_measurement() -> None:
    # 미가용은 실측 신호보다 우선 — 없는 근거를 강하게 믿지 않는다.
    tier, basis = classify_evidence(
        _entry(
            availability="missing",
            is_measurement=True,
            measurement_stage="current_silicon",
            scenario_match="strong",
        )
    )
    assert tier == "absent"
    assert basis[0].rule == "availability"


def test_scenario_match_none_is_absent() -> None:
    tier, _ = classify_evidence(_entry(scenario_match="none", is_measurement=True))
    assert tier == "absent"


def test_measured_direct_requires_silicon_strong_match() -> None:
    tier, _ = classify_evidence(
        _entry(
            availability="available",
            is_measurement=True,
            measurement_stage="current_silicon",
            scenario_match="strong",
        )
    )
    assert tier == "measured_direct"


def test_measured_analogous_when_borrowed() -> None:
    tier, _ = classify_evidence(
        _entry(
            is_measurement=True,
            measurement_stage="previous_project",
            scenario_match="partial",
        )
    )
    assert tier == "measured_analogous"


def test_emulator_stage_is_emulated() -> None:
    tier, _ = classify_evidence(
        _entry(measurement_stage="emulator", scenario_match="partial")
    )
    assert tier == "emulated"


def test_prediction_fallback() -> None:
    tier, basis = classify_evidence(
        _entry(
            is_prediction=True,
            measurement_stage="architecture",
            scenario_match="partial",
        )
    )
    assert tier == "predicted"
    assert basis[0].rule == "evidence_kind"


def test_no_store_side_effect(repo) -> None:
    before = len(repo.list("evidence_catalog"))
    EvidenceLadderService(repo).ladder()
    assert len(repo.list("evidence_catalog")) == before
