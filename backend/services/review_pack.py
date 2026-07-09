"""리뷰 팩 조립 서비스 — ReviewPack이 묶은 시나리오들의 실행 초안을 한 장으로 (저장 안 함).

원점 4층 루프의 review→decision 고리. 미사용 ReviewPack 객체를 살려, 묶인 시나리오별
실행 초안(ActionDraft)+근거 태세를 조립하고 회의용 롤업을 더한다. 결정 CSV는 프론트에서
생성(결정 컬럼 빈 round-trip 템플릿). 저장·결정 자동생성 없음. 설계: internal_docs/design/10_review_pack.md.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.decision import ReviewPack
from backend.services.action_draft import ActionDraft, ActionDraftService

_PROVENANCE = (
    "이 리뷰 팩은 결정론 파생 조립입니다. 결정·담당은 회의에서 사람이 채우며, "
    "재진입은 ingest 계층으로만 이뤄집니다. 각 항목은 근거를 동반합니다."
)


class ReviewPackNotFoundError(Exception):
    """존재하지 않는 리뷰 팩."""


class ReviewPackSummary(BaseModel):
    """리뷰 팩 요약 — 목록용."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str
    title: str
    purpose: str
    project_ids: list[str]
    scenario_ids: list[str]


class ReviewPackRollup(BaseModel):
    """회의 헤드라인 — 항목·근거 태세 집계 (정수 건수, 점수 아님)."""

    model_config = ConfigDict(extra="forbid")

    scenario_count: int
    risk_items: int
    issue_items: int
    evidence_gap_items: int
    measured: int
    predicted: int
    absent: int


class ReviewPackDocument(BaseModel):
    """리뷰 팩 조립 파생 뷰 — 저장되지 않는 조립 결과."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str
    title: str
    purpose: str
    project_ids: list[str]
    scenarios: list[ActionDraft]
    rollup: ReviewPackRollup
    provenance_note: str


class ReviewPackService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo
        self._draft = ActionDraftService(repo)

    def _packs(self) -> list[ReviewPack]:
        return [p for p in self._repo.list("review_packs") if isinstance(p, ReviewPack)]

    def list_packs(self) -> list[ReviewPackSummary]:
        return [
            ReviewPackSummary(
                pack_id=p.id,
                title=p.title,
                purpose=p.purpose,
                project_ids=p.project_ids,
                scenario_ids=p.scenario_ids,
            )
            for p in sorted(self._packs(), key=lambda p: p.title)
        ]

    def assemble(self, pack_id: str) -> ReviewPackDocument:
        pack = next((p for p in self._packs() if p.id == pack_id), None)
        if pack is None:
            raise ReviewPackNotFoundError(f"리뷰 팩 없음: {pack_id}")

        drafts: list[ActionDraft] = []
        for scenario_id in pack.scenario_ids:
            try:
                drafts.append(self._draft.draft(scenario_id))
            except Exception:
                # 팩에 삭제된/미존재 시나리오가 섞여도 나머지는 조립한다.
                continue

        risk = issue = gap = measured = predicted = absent = 0
        for d in drafts:
            for section in d.sections:
                if section.kind == "risk":
                    risk += len(section.items)
                elif section.kind == "issue":
                    issue += len(section.items)
                elif section.kind == "evidence_gap":
                    gap += len(section.items)
            if d.evidence_posture is not None:
                measured += d.evidence_posture.measured
                predicted += d.evidence_posture.predicted
                absent += d.evidence_posture.absent

        rollup = ReviewPackRollup(
            scenario_count=len(drafts),
            risk_items=risk,
            issue_items=issue,
            evidence_gap_items=gap,
            measured=measured,
            predicted=predicted,
            absent=absent,
        )
        return ReviewPackDocument(
            pack_id=pack.id,
            title=pack.title,
            purpose=pack.purpose,
            project_ids=pack.project_ids,
            scenarios=drafts,
            rollup=rollup,
            provenance_note=_PROVENANCE,
        )
