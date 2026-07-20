"""게이트 콘솔 파생 뷰 — A0 판정 배너 (설계 26 G1).

"다음 게이트를 통과할 수 있는가"에 3초 안에 답하는 홈 화면의 데이터 계약.
저장하지 않는 결정론 조립이다: 게이트 판정(설계 23 GateReviewService) +
이슈 연결률(W2 LINK_FIELDS) + 반입 신선도(배치 기록)를 과제 단위로 묶는다.

원칙 (설계 26 §5 G1):
- GO/NO-GO 단어를 쓰지 않는다 — 판정은 조언이지 차단이 아니다 (설계 23).
- 게이트 자동 선택과 지배 요인은 룰을 명시한 결정론이다 (동일 입력 동일 출력).
- 신뢰도 줄은 "이 판정이 못 보는 것"을 배너 스스로 말하게 한다.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.ingest.mappings import field_values
from backend.ingest.service import IngestBatch
from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import Issue, Test
from backend.ontology.project import Project
from backend.services.gate_review import (
    VERDICT_NOT_MET,
    GateCriterionVerdict,
    GateReviewService,
    MilestoneGateReview,
)
from backend.services.source_map import LINK_FIELDS


class BatchSourceProtocol(Protocol):
    """반입 배치 목록 읽기 계약 — 신선도(최근 배치 시각) 산출에만 쓴다."""

    def list_batches(self) -> list[IngestBatch]: ...


# 지배 요인 선정 룰 (설계 26 G1): 미충족 기준 중 kind 우선순위
# (이슈 수 최다 → 근거 누락 → 검증 없는 종결) → 위반 건수 내림차순 → id 순.
_DOMINANT_KIND_ORDER = ["max_open_issues", "required_evidence", "verified_closure"]

_SELECTION_RULE_KO = (
    "게이트 자동 선택: 기준 주차(데이터의 최신 활동 주차) 이후 최근접 마일스톤 — "
    "exit 기준이 정의된 마일스톤만 대상."
)

TRUST_NOTE_KO = (
    "연결률과 반입 시각은 이 판정의 시야 한계다 — 링크 없는 이슈는 게이트 "
    "근거에 나타나지 않고, 반입 이후의 변화는 판정에 반영되지 않았다."
)


class GateDominantFactor(BaseModel):
    """미충족 기준 중 결정론 대표 1건 — 배너 헤드라인과 드릴 목적지."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: str
    kind: str
    kind_ko: str
    headline_ko: str  # "미해결 이슈 3건" — 배너 한 줄에 들어가는 요약
    drill: str  # issues | evidence — now-what 링크 목적지 힌트


class GateConsoleReview(BaseModel):
    """게이트 하나의 콘솔 표현 — 판정 묶음 + 배너 문구 + 지배 요인."""

    model_config = ConfigDict(extra="forbid")

    review: MilestoneGateReview
    verdict_line_ko: str
    dominant: GateDominantFactor | None = None


class GateTrustLine(BaseModel):
    """판정 신뢰도 줄 — 이슈 연결률 + 반입 신선도 (점수 아님)."""

    model_config = ConfigDict(extra="forbid")

    issue_total: int
    issue_linked: int
    latest_batch_at: str | None  # ISO — None이면 반입 기록 없음 (시드 전용)
    note_ko: str = TRUST_NOTE_KO


class ProjectGateConsole(BaseModel):
    """과제 하나의 게이트 콘솔 — 자동 선택 + 전 게이트 판정 (드롭다운 전환용)."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    project_name: str
    selected_milestone_id: str | None  # None = 게이트 미지정 (정직 표기)
    selection_note_ko: str
    reviews: list[GateConsoleReview] = Field(default_factory=list)
    trust: GateTrustLine


class GateConsole(BaseModel):
    """게이트 콘솔 전체 — 과제별 A0 판정 배너의 데이터."""

    model_config = ConfigDict(extra="forbid")

    reference_week: int | None
    rule_note_ko: str = _SELECTION_RULE_KO
    projects: list[ProjectGateConsole] = Field(default_factory=list)


class GateConsoleService:
    def __init__(
        self, repo: RepositoryProtocol, batches: BatchSourceProtocol | None = None
    ) -> None:
        self._repo = repo
        self._batches = batches
        self._gates = GateReviewService(repo)

    def console(self) -> GateConsole:
        reference_week = self._reference_week()
        latest_batch = self._latest_batch_at()
        projects = sorted(
            (p for p in self._repo.list("projects") if isinstance(p, Project)),
            key=lambda p: p.id,
        )
        return GateConsole(
            reference_week=reference_week,
            projects=[
                self._project_console(project, reference_week, latest_batch)
                for project in projects
            ],
        )

    # --- 과제 단위 조립 ---

    def _project_console(
        self, project: Project, reference_week: int | None, latest_batch: str | None
    ) -> ProjectGateConsole:
        reviews = [
            GateConsoleReview(
                review=review,
                verdict_line_ko=self._verdict_line(review),
                dominant=self._dominant(review),
            )
            for review in self._gates.for_projects([project.id])
        ]
        selected_id, note = self._select(reviews, reference_week)
        return ProjectGateConsole(
            project_id=project.id,
            project_name=project.name,
            selected_milestone_id=selected_id,
            selection_note_ko=note,
            reviews=reviews,
            trust=self._trust(project.id, latest_batch),
        )

    def _select(
        self, reviews: list[GateConsoleReview], reference_week: int | None
    ) -> tuple[str | None, str]:
        """자동 선택 룰 — 기준 주차 이후 최근접. 못 고르면 이유를 말한다."""
        if not reviews:
            return None, "게이트 미지정 — exit 기준이 정의된 마일스톤이 없다."
        dated = [r for r in reviews if r.review.week is not None]
        if not dated:
            return None, (
                "게이트 주차 미지정 — 마일스톤에 주차가 없어 자동 선택할 수 없다."
            )
        if reference_week is not None:
            upcoming = [r for r in dated if (r.review.week or 0) >= reference_week]
            if upcoming:
                pick = min(upcoming, key=lambda r: (r.review.week or 0, r.review.milestone_id))
                return pick.review.milestone_id, (
                    f"자동 선택: 기준 주차 W{reference_week} 이후 최근접 게이트 "
                    f"(W{pick.review.week})."
                )
            pick = max(dated, key=lambda r: (r.review.week or 0, r.review.milestone_id))
            return pick.review.milestone_id, (
                f"모든 게이트 주차가 기준 주차 W{reference_week} 이전 — "
                f"가장 최근 게이트(W{pick.review.week})를 표시한다."
            )
        pick = min(dated, key=lambda r: (r.review.week or 0, r.review.milestone_id))
        return pick.review.milestone_id, (
            "기준 주차 산출 불가(활동 주차 데이터 없음) — 최초 주차 게이트를 표시한다."
        )

    # --- 배너 문구 · 지배 요인 (결정론 룰) ---

    def _verdict_line(self, review: MilestoneGateReview) -> str:
        total = len(review.criteria)
        if review.not_met > 0:
            dominant = self._dominant(review)
            headline = dominant.headline_ko if dominant else "미충족 기준 존재"
            return f"미충족 {review.not_met}/{total} — 지배 요인: {headline}"
        if review.not_evaluable == total:
            return f"판정 불가 {review.not_evaluable}건 — 기준 정의·데이터 보강 필요"
        if review.not_evaluable > 0:
            return (
                f"충족 {review.met}/{total} — 판정 불가 {review.not_evaluable}건 "
                "(그만큼은 이 판정이 못 본다)"
            )
        return f"전 기준 충족 {review.met}/{total}"

    def _dominant(self, review: MilestoneGateReview) -> GateDominantFactor | None:
        failed = [c for c in review.criteria if c.verdict == VERDICT_NOT_MET]
        if not failed:
            return None

        def rank(c: GateCriterionVerdict) -> tuple[int, int, str]:
            kind_rank = (
                _DOMINANT_KIND_ORDER.index(c.kind)
                if c.kind in _DOMINANT_KIND_ORDER
                else len(_DOMINANT_KIND_ORDER)
            )
            return (kind_rank, -self._violations(c), c.criterion_id)

        pick = min(failed, key=rank)
        count = self._violations(pick)
        if pick.kind == "max_open_issues":
            headline, drill = f"미해결 이슈 {count}건", "issues"
        elif pick.kind == "required_evidence":
            headline, drill = f"요구 근거 누락 {count}종", "evidence"
        elif pick.kind == "verified_closure":
            headline, drill = f"검증 없는 종결 {count}건", "issues"
        else:
            headline, drill = f"{pick.kind_ko} 미충족", "issues"
        return GateDominantFactor(
            criterion_id=pick.criterion_id,
            kind=pick.kind,
            kind_ko=pick.kind_ko,
            headline_ko=headline,
            drill=drill,
        )

    @staticmethod
    def _violations(criterion: GateCriterionVerdict) -> int:
        """위반 건수 — required_evidence는 누락 유형만 센다 (가용 근거는 위반 아님)."""
        if criterion.kind == "required_evidence":
            return sum(
                1 for b in criterion.basis if b.ref_id.startswith("missing:")
            )
        return len(criterion.basis)

    # --- 신뢰도 줄 ---

    def _trust(self, project_id: str, latest_batch: str | None) -> GateTrustLine:
        issues = [
            i
            for i in self._repo.list("issues")
            if isinstance(i, Issue) and i.project_id == project_id
        ]
        paths = LINK_FIELDS["issues"]
        linked = 0
        for issue in issues:
            dump = issue.model_dump(mode="json")
            if any(field_values(dump, path) for path in paths):
                linked += 1
        return GateTrustLine(
            issue_total=len(issues),
            issue_linked=linked,
            latest_batch_at=latest_batch,
        )

    def _latest_batch_at(self) -> str | None:
        if self._batches is None:
            return None
        stamps = [
            batch.created_at
            for batch in self._batches.list_batches()
            if batch.status == "completed"
        ]
        return max(stamps, default=None)

    def _reference_week(self) -> int | None:
        """기준 주차 = 데이터의 최신 활동 주차 — 벽시계 없는 결정론 '지금' (RCA와 동일 룰)."""
        weeks: list[int] = []
        for issue in self._repo.list("issues"):
            if isinstance(issue, Issue):
                weeks += [
                    w
                    for w in (issue.resolved_week, issue.updated_week, issue.due_week)
                    if w
                ]
        for obj in self._repo.list("tests"):
            if isinstance(obj, Test) and obj.executed_week:
                weeks.append(obj.executed_week)
        for obj in self._repo.list("development_events"):
            week = getattr(obj, "week", None)
            if week:
                weeks.append(week)
        return max(weeks, default=None)
