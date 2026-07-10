"""실행 초안 서비스 — 시나리오 기준 리뷰 팩/체크리스트 초안 (저장하지 않음).

원점 비전 4층 루프(§1 "create review item/summarize")의 다리. 기존 결정론 파생 뷰
(위험 근거·미해결/미검증 이슈·근거 공백)를 한 장의 "실행 초안"으로 조립한다.

**초안일 뿐이다** — 저장·owner 자동할당·자동 실행 없음. 사람이 검토·커밋하며,
재진입은 ingest 계층으로만(CLAUDE.md §6.3). 모든 항목은 근거(BasisItem)를 동반한다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import Issue
from backend.ontology.evidence import EvidenceCatalogEntry
from backend.ontology.glossary import value_label
from backend.ontology.scenario import Scenario
from backend.services.common import BasisItem
from backend.services.evidence_ladder import (
    TIER_LABELS,
    EvidenceLadderService,
    EvidencePosture,
    classify_evidence,
    scenario_posture,
)
from backend.services.risk import RiskService
from backend.services.scenario_analysis import ScenarioNotFoundError


def _vl(domain: str, value: str) -> str:
    """서술용 값 라벨 — 없으면 원문 유지 (코드는 hover/패널에서만)."""
    return value_label(domain, value) or value


_CLOSED_ISSUE_STATUSES = {"closed", "resolved", "done"}

_PROVENANCE = (
    "이 문서는 결정론 파생 초안입니다. 최종 결정·담당자 배정이 아니며, "
    "사람이 검토·수정·커밋합니다. 각 항목은 근거를 동반합니다."
)


class DraftItem(BaseModel):
    """초안 항목 — 근거 없는 항목은 존재하지 않는다."""

    model_config = ConfigDict(extra="forbid")

    statement: str
    basis: list[BasisItem]
    strength_ko: str | None = None  # 근거 항목의 신뢰 등급(실측·정합 등), 해당 시에만.


class DraftSection(BaseModel):
    """초안 섹션 — 위험 근거 / 확인 필요 이슈 / 근거 수집."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    kind_ko: str
    title: str
    items: list[DraftItem]


class ActionDraft(BaseModel):
    """실행 초안 파생 뷰 — 저장되지 않는 조립 결과."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    scenario_name: str
    generated_context: str
    evidence_posture: EvidencePosture | None
    sections: list[DraftSection]
    provenance_note: str


class ActionDraftService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo
        self._risk = RiskService(repo)
        self._ladder = EvidenceLadderService(repo)

    def _scenario(self, scenario_id: str) -> Scenario:
        obj = self._repo.get("scenarios", scenario_id)
        if not isinstance(obj, Scenario):
            raise ScenarioNotFoundError(f"시나리오 없음: {scenario_id}")
        return obj

    def _risk_section(self, scenario_id: str) -> DraftSection | None:
        heatmap = self._risk.heatmap()
        row = next((r for r in heatmap.rows if r.scenario_id == scenario_id), None)
        if row is None:
            return None
        items = [
            DraftItem(statement=b.description, basis=[b])
            for b in row.overall_basis
            if b.rule != "no_signal"
        ]
        if not items:
            return None
        return DraftSection(
            kind="risk",
            kind_ko="위험 근거 검토",
            title=f"종합 위험 {row.overall_grade_ko} — 판정 근거 확인",
            items=items,
        )

    def _issue_section(self, scenario_id: str) -> DraftSection | None:
        items: list[DraftItem] = []
        for issue in self._repo.list("issues"):
            if not isinstance(issue, Issue):
                continue
            if scenario_id not in issue.affected_scope.scenarios:
                continue
            is_open = issue.status not in _CLOSED_ISSUE_STATUSES
            unverified_close = not is_open and not issue.verifying_test_ids
            if not (is_open or unverified_close):
                continue
            if is_open:
                rule, rule_ko = "open_issue", "미해결 이슈"
                statement = (
                    f"미해결 이슈 확인: '{issue.title}' "
                    f"(유형 {_vl('issue_type', issue.issue_type)}, "
                    f"상태 {_vl('issue_status', issue.status)}) — 증상: {issue.symptom}"
                )
            else:
                rule, rule_ko = "unverified_close", "검증 없는 종결"
                statement = (
                    f"검증 근거 확인: '{issue.title}'이 "
                    f"종결(상태 {_vl('issue_status', issue.status)})됐으나 "
                    "검증 테스트 연결이 없음 — 재발 여부 확인 필요"
                )
            items.append(
                DraftItem(
                    statement=statement,
                    basis=[
                        BasisItem(
                            rule=rule,
                            rule_ko=rule_ko,
                            ref_id=issue.id,
                            ref_collection="issues",
                            description=statement,
                            source_refs=issue.evidence_refs,
                        )
                    ],
                )
            )
        if not items:
            return None
        items.sort(key=lambda i: i.basis[0].ref_id)
        return DraftSection(
            kind="issue",
            kind_ko="확인 필요 이슈",
            title="미해결·미검증 이슈 점검",
            items=items,
        )

    def _evidence_gap_section(self, scenario_id: str) -> DraftSection | None:
        items: list[DraftItem] = []
        for entry in self._repo.list("evidence_catalog"):
            if not isinstance(entry, EvidenceCatalogEntry):
                continue
            if entry.scenario_id != scenario_id or entry.availability == "available":
                continue
            tier, _ = classify_evidence(entry)
            statement = (
                f"근거 확보: '{entry.title}' "
                f"(가용성 {_vl('availability', entry.availability)}, "
                f"유형 {_vl('evidence_type', entry.evidence_type)})"
            )
            items.append(
                DraftItem(
                    statement=statement,
                    strength_ko=TIER_LABELS[tier],
                    basis=[
                        BasisItem(
                            rule="required_evidence_open",
                            rule_ko="요구 근거 미충족",
                            ref_id=entry.id,
                            ref_collection="evidence_catalog",
                            description=statement,
                            source_refs=[entry.source_ref],
                        )
                    ],
                )
            )
        if not items:
            return None
        items.sort(key=lambda i: i.basis[0].ref_id)
        return DraftSection(
            kind="evidence_gap",
            kind_ko="근거 수집",
            title="미해결 근거 공백 보완",
            items=items,
        )

    def _evidence_posture(self, scenario_id: str) -> EvidencePosture | None:
        return scenario_posture(self._ladder, scenario_id)

    def draft(self, scenario_id: str) -> ActionDraft:
        scenario = self._scenario(scenario_id)
        sections = [
            section
            for section in (
                self._risk_section(scenario_id),
                self._issue_section(scenario_id),
                self._evidence_gap_section(scenario_id),
            )
            if section is not None
        ]
        counts = " · ".join(f"{s.kind_ko} {len(s.items)}" for s in sections) or "항목 없음"
        return ActionDraft(
            scenario_id=scenario_id,
            scenario_name=scenario.name,
            generated_context=f"시나리오 '{scenario.name}' 기준 결정론 조립 — {counts}",
            evidence_posture=self._evidence_posture(scenario_id),
            sections=sections,
            provenance_note=_PROVENANCE,
        )
