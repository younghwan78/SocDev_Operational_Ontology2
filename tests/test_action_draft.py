"""실행 초안 서비스 테스트 — 결정론 조립 + 근거 동반 + 무저장.

수용 기준: 동일 fixture → 동일 출력, 모든 항목 최소 1개 근거, 저장 부작용 없음.
"""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.services.action_draft import ActionDraft, ActionDraftService
from backend.services.risk import RiskService
from backend.services.scenario_analysis import ScenarioNotFoundError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


def _scenario_with_signals(repo: InMemoryRepository) -> str:
    """근거 있는(no_signal 아님) 시나리오 하나를 결정론으로 고른다."""
    heatmap = RiskService(repo).heatmap()
    for row in heatmap.rows:
        if any(b.rule != "no_signal" for b in row.overall_basis):
            return row.scenario_id
    raise AssertionError("근거 있는 시나리오가 fixture에 있어야 한다")


@pytest.fixture(scope="module")
def draft(repo: InMemoryRepository) -> ActionDraft:
    return ActionDraftService(repo).draft(_scenario_with_signals(repo))


def test_deterministic(repo: InMemoryRepository, draft: ActionDraft) -> None:
    again = ActionDraftService(repo).draft(draft.scenario_id)
    assert draft.model_dump() == again.model_dump()


def test_every_item_has_basis(draft: ActionDraft) -> None:
    assert draft.sections, "근거 있는 시나리오는 최소 한 섹션을 가져야 한다"
    for section in draft.sections:
        for item in section.items:
            assert item.basis, "근거 없는 초안 항목은 존재할 수 없다"
            assert item.statement


def test_provenance_note_present(draft: ActionDraft) -> None:
    assert "초안" in draft.provenance_note
    assert "커밋" in draft.provenance_note


def test_no_store_side_effect(repo: InMemoryRepository, draft: ActionDraft) -> None:
    """초안 생성은 저장하지 않는다 — 생성 전후 컬렉션 크기 불변."""
    before = {
        key: len(repo.list(key))
        for key in ("issues", "evidence_catalog", "scenarios", "decisions", "action_items")
    }
    ActionDraftService(repo).draft(draft.scenario_id)
    after = {key: len(repo.list(key)) for key in before}
    assert before == after


def test_unknown_scenario_raises(repo: InMemoryRepository) -> None:
    with pytest.raises(ScenarioNotFoundError):
        ActionDraftService(repo).draft("존재하지_않는_시나리오")


def test_evidence_posture_when_scenario_has_evidence(repo: InMemoryRepository) -> None:
    """근거가 있는 시나리오는 태세 요약(실측/예측/부재 + 정성 판정)을 갖는다."""
    from backend.ontology.evidence import EvidenceCatalogEntry
    from backend.services.evidence_ladder import EvidenceLadderService

    scn = next(
        e.scenario_id
        for e in repo.list("evidence_catalog")
        if isinstance(e, EvidenceCatalogEntry)
    )
    draft = ActionDraftService(repo).draft(scn)
    posture = draft.evidence_posture
    assert posture is not None
    total = EvidenceLadderService(repo).ladder(scenario_id=scn).totals.total
    assert posture.measured + posture.predicted + posture.absent == total
    assert posture.note_ko


def test_evidence_gap_items_carry_strength(repo: InMemoryRepository) -> None:
    """근거 수집 항목은 신뢰 등급(strength_ko)을 동반한다."""
    from backend.ontology.evidence import EvidenceCatalogEntry
    from backend.services.evidence_ladder import TIER_LABELS

    # 미가용 근거가 있는 시나리오를 결정론으로 고른다.
    scn = next(
        e.scenario_id
        for e in repo.list("evidence_catalog")
        if isinstance(e, EvidenceCatalogEntry) and e.availability != "available"
    )
    draft = ActionDraftService(repo).draft(scn)
    gap = next((s for s in draft.sections if s.kind == "evidence_gap"), None)
    assert gap is not None
    for item in gap.items:
        assert item.strength_ko in TIER_LABELS.values()
