"""근거 신뢰 사다리 — evidence_catalog의 정성 신뢰 등급 파생 뷰 (저장하지 않음).

"이 근거를 얼마나 믿을 수 있나"를 기존 필드(measurement_stage/scenario_match/availability/
is_measurement/is_prediction)만으로 강→약 5단 정성 등급 + 판정 근거로 종합한다.
수치 점수·가중치·rank는 산출하지 않는다 (CLAUDE.md §6.3). 설계: internal_docs/design/09_evidence_ladder.md.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.evidence import EvidenceCatalogEntry
from backend.services.common import BasisItem

# 강→약 고정 순서. 목록 순서로만 서열을 표현한다 (수치 등급 없음).
TIER_ORDER: list[str] = [
    "measured_direct",
    "measured_analogous",
    "emulated",
    "predicted",
    "absent",
]

TIER_LABELS: dict[str, str] = {
    "measured_direct": "실측·정합",
    "measured_analogous": "실측·유사",
    "emulated": "에뮬레이션",
    "predicted": "예측·설계",
    "absent": "부재·미가용",
}

RULE_LABELS: dict[str, str] = {
    "availability": "가용성",
    "scenario_match": "시나리오 정합도",
    "measurement_stage": "측정 단계",
    "evidence_kind": "근거 종류",
    "confidence_contribution": "확신도 기여",
}

_TIER_RANK = {tier: i for i, tier in enumerate(TIER_ORDER)}

# 등급 판정에 쓰이는 필드값 집합.
_ABSENT_AVAILABILITY = {"missing", "planned"}
_MEASURED_STRONG_STAGES = {"current_silicon", "field"}
_MEASURED_ANY_STAGES = {
    "current_silicon",
    "field",
    "previous_project",
    "customer_project",
}
_MEASURED_TIERS = {"measured_direct", "measured_analogous"}


class EvidenceStrengthItem(BaseModel):
    """근거 항목 하나의 신뢰 등급 + 판정 근거."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    title: str
    project_id: str
    scenario_id: str
    tier: str
    tier_ko: str
    origin: str
    basis: list[BasisItem]


class TierBucket(BaseModel):
    """신뢰 등급별 분포 — 근거 건강도."""

    model_config = ConfigDict(extra="forbid")

    tier: str
    tier_ko: str
    count: int


class LadderTotals(BaseModel):
    """실측/예측/부재 3분 요약 — 정수 건수(점수 아님)."""

    model_config = ConfigDict(extra="forbid")

    total: int
    measured: int
    predicted: int
    absent: int


class EvidenceLadder(BaseModel):
    """근거 신뢰 사다리 파생 뷰."""

    model_config = ConfigDict(extra="forbid")

    distribution: list[TierBucket]
    entries: list[EvidenceStrengthItem]
    totals: LadderTotals


def _basis(entry: EvidenceCatalogEntry, rule: str, description: str) -> BasisItem:
    return BasisItem(
        rule=rule,
        rule_ko=RULE_LABELS[rule],
        ref_id=entry.id,
        ref_collection="evidence_catalog",
        description=description,
        source_refs=[entry.source_ref] if entry.source_ref else [],
    )


def classify_evidence(entry: EvidenceCatalogEntry) -> tuple[str, list[BasisItem]]:
    """근거 항목을 강→약 5단 tier로 분류하고 판정 근거를 동반한다 (top-down 첫 매치)."""
    basis: list[BasisItem] = []

    # 0) 부재·미가용 — 없는 근거를 강하게 신뢰하는 오류를 최우선 차단.
    if entry.availability in _ABSENT_AVAILABILITY:
        basis.append(
            _basis(
                entry,
                "availability",
                f"가용성 '{entry.availability}' — 근거가 아직 확보되지 않음(판단 유보/수집 필요)",
            )
        )
        return "absent", basis
    if entry.scenario_match == "none":
        basis.append(
            _basis(
                entry,
                "scenario_match",
                "이 시나리오와의 정합도 'none' — 다른 맥락의 근거라 직접 신뢰 불가",
            )
        )
        return "absent", basis
    if entry.confidence_contribution == "none":
        basis.append(
            _basis(
                entry,
                "confidence_contribution",
                "확신도 기여 'none' — 판단에 실질 기여가 없는 근거",
            )
        )
        return "absent", basis

    # 1) 실측·정합 — 이 시나리오를 직접 실측한 최강 근거.
    if (
        entry.is_measurement
        and entry.measurement_stage in _MEASURED_STRONG_STAGES
        and entry.scenario_match == "strong"
    ):
        basis.append(
            _basis(
                entry,
                "measurement_stage",
                f"측정 단계 '{entry.measurement_stage}' 실측 — 이 시나리오를 직접 계측",
            )
        )
        basis.append(
            _basis(entry, "scenario_match", "시나리오 정합도 'strong' — 대상과 직접 대응")
        )
        return "measured_direct", basis

    # 2) 실측·유사 — 실측이나 타 프로젝트/부분 정합에서 인용.
    if entry.is_measurement or entry.measurement_stage in _MEASURED_ANY_STAGES:
        stage_note = (
            f"측정 단계 '{entry.measurement_stage}'"
            if entry.measurement_stage in _MEASURED_ANY_STAGES
            else "실측 근거"
        )
        basis.append(
            _basis(
                entry,
                "measurement_stage",
                f"{stage_note} — 실측이나 정합도 '{entry.scenario_match}'로 유사·인용 지위",
            )
        )
        return "measured_analogous", basis

    # 3) 에뮬레이션 — 에뮬/초기 실측 단계.
    if entry.measurement_stage == "emulator":
        basis.append(
            _basis(
                entry,
                "measurement_stage",
                "측정 단계 'emulator' — 에뮬레이션 기반 방향성 근거(실측 전)",
            )
        )
        return "emulated", basis

    # 4) 예측·설계 — 예측·설계 산출물(검증 전).
    kind = "예측" if entry.is_prediction else "설계·분석"
    basis.append(
        _basis(
            entry,
            "evidence_kind",
            f"{kind} 산출물(측정 단계 '{entry.measurement_stage}') — 검증 전 근거",
        )
    )
    return "predicted", basis


class EvidenceLadderService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def _entries(
        self, project_id: str | None, scenario_id: str | None
    ) -> list[EvidenceCatalogEntry]:
        entries = [
            e
            for e in self._repo.list("evidence_catalog")
            if isinstance(e, EvidenceCatalogEntry)
        ]
        if project_id:
            entries = [e for e in entries if e.project_id == project_id]
        if scenario_id:
            entries = [e for e in entries if e.scenario_id == scenario_id]
        return entries

    def ladder(
        self, project_id: str | None = None, scenario_id: str | None = None
    ) -> EvidenceLadder:
        raw = self._entries(project_id, scenario_id)
        items: list[EvidenceStrengthItem] = []
        counts: dict[str, int] = {tier: 0 for tier in TIER_ORDER}
        for entry in raw:
            tier, basis = classify_evidence(entry)
            counts[tier] += 1
            items.append(
                EvidenceStrengthItem(
                    evidence_id=entry.id,
                    title=entry.title,
                    project_id=entry.project_id,
                    scenario_id=entry.scenario_id,
                    tier=tier,
                    tier_ko=TIER_LABELS[tier],
                    origin=str(entry.source.origin.value),
                    basis=basis,
                )
            )
        # 강→약 tier 순, 동급이면 제목/ID로 안정 정렬.
        items.sort(key=lambda i: (_TIER_RANK[i.tier], i.title, i.evidence_id))
        distribution = [
            TierBucket(tier=tier, tier_ko=TIER_LABELS[tier], count=counts[tier])
            for tier in TIER_ORDER
        ]
        measured = sum(counts[t] for t in _MEASURED_TIERS)
        totals = LadderTotals(
            total=len(raw),
            measured=measured,
            predicted=counts["predicted"] + counts["emulated"],
            absent=counts["absent"],
        )
        return EvidenceLadder(distribution=distribution, entries=items, totals=totals)
