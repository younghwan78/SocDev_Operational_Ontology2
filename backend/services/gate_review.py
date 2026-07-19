"""마일스톤 게이트 판정 — exit_criteria의 결정론 충족 판정 (설계 23).

파생 뷰다 (저장하지 않음). 판정은 met/not_met/not_evaluable 3값 + 근거 ref
목록이며 점수·가중치·자동 차단이 없다 — 게이트는 판정을 보여줄 뿐 아무것도
막지 않는다 (조언 시스템 지위). LLM 무관, 동일 입력 동일 출력.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import Issue, Test
from backend.ontology.evidence import EvidenceCatalogEntry
from backend.ontology.glossary import value_label
from backend.ontology.project import GateCriterion, ProjectMilestone

VERDICT_MET = "met"
VERDICT_NOT_MET = "not_met"
VERDICT_NOT_EVALUABLE = "not_evaluable"

# 종결 상태 = process_model ISSUE_STAGES의 해결·종결 단계 (설계 23 §2.1).
CLOSED_STATUSES = {"resolved", "closed", "done"}

# min_severity 필터 순서 — severity 도메인. 순위 숫자는 내부 비교 전용이다
# (점수 아님 — 화면·응답에 노출하지 않는다).
_SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]


class GateBasisRef(BaseModel):
    """판정 근거 한 건 — 위험 지도 basis와 같은 문법."""

    model_config = ConfigDict(extra="forbid")

    ref_collection: str
    ref_id: str
    note_ko: str


class GateCriterionVerdict(BaseModel):
    """기준 하나의 판정 — 서술+판정+근거."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: str
    kind: str
    kind_ko: str
    description: str
    verdict: str  # met | not_met | not_evaluable
    verdict_ko: str
    note_ko: str
    basis: list[GateBasisRef] = Field(default_factory=list)


class MilestoneGateReview(BaseModel):
    """마일스톤 하나의 게이트 판정 묶음 — 정수 집계 (점수 아님)."""

    model_config = ConfigDict(extra="forbid")

    milestone_id: str
    milestone_title: str
    project_id: str
    week: int | None
    met: int
    not_met: int
    not_evaluable: int
    criteria: list[GateCriterionVerdict]


def _verdict_ko(verdict: str) -> str:
    return value_label("gate_verdict", verdict) or verdict


def _kind_ko(kind: str) -> str:
    return value_label("gate_criterion_kind", kind) or kind


class GateReviewService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def for_projects(self, project_ids: list[str]) -> list[MilestoneGateReview]:
        """exit_criteria가 있는 마일스톤만 — week 순(미상은 뒤), id 순."""
        milestones = [
            m
            for m in self._repo.list("project_milestones")
            if isinstance(m, ProjectMilestone)
            and m.project_id in project_ids
            and m.exit_criteria
        ]
        milestones.sort(key=lambda m: (m.week is None, m.week or 0, m.id))
        return [self._review(m) for m in milestones]

    def _review(self, milestone: ProjectMilestone) -> MilestoneGateReview:
        verdicts = [
            self._judge(milestone.project_id, criterion)
            for criterion in milestone.exit_criteria
        ]
        return MilestoneGateReview(
            milestone_id=milestone.id,
            milestone_title=milestone.title,
            project_id=milestone.project_id,
            week=milestone.week,
            met=sum(1 for v in verdicts if v.verdict == VERDICT_MET),
            not_met=sum(1 for v in verdicts if v.verdict == VERDICT_NOT_MET),
            not_evaluable=sum(
                1 for v in verdicts if v.verdict == VERDICT_NOT_EVALUABLE
            ),
            criteria=verdicts,
        )

    def _judge(self, project_id: str, criterion: GateCriterion) -> GateCriterionVerdict:
        if criterion.kind == "max_open_issues":
            verdict, note, basis = self._judge_max_open_issues(project_id, criterion)
        elif criterion.kind == "required_evidence":
            verdict, note, basis = self._judge_required_evidence(project_id, criterion)
        elif criterion.kind == "verified_closure":
            verdict, note, basis = self._judge_verified_closure(project_id, criterion)
        else:
            verdict = VERDICT_NOT_EVALUABLE
            note = f"미등재 기준 유형 '{criterion.kind}' — 판정 룰이 없다."
            basis = []
        return GateCriterionVerdict(
            criterion_id=criterion.criterion_id,
            kind=criterion.kind,
            kind_ko=_kind_ko(criterion.kind),
            description=criterion.description,
            verdict=verdict,
            verdict_ko=_verdict_ko(verdict),
            note_ko=note,
            basis=basis,
        )

    # --- kind별 판정 ---

    def _issues(self, project_id: str, scenario_ids: list[str]) -> list[Issue]:
        issues = [
            i
            for i in self._repo.list("issues")
            if isinstance(i, Issue) and i.project_id == project_id
        ]
        if scenario_ids:
            wanted = set(scenario_ids)
            issues = [
                i for i in issues if wanted & set(i.affected_scope.scenarios)
            ]
        return issues

    def _judge_max_open_issues(
        self, project_id: str, criterion: GateCriterion
    ) -> tuple[str, str, list[GateBasisRef]]:
        limit = criterion.max_open_issues if criterion.max_open_issues is not None else 0
        open_issues = [
            i
            for i in self._issues(project_id, criterion.scenario_ids)
            if i.status not in CLOSED_STATUSES
        ]
        unrated = 0
        if criterion.min_severity is not None:
            if criterion.min_severity not in _SEVERITY_ORDER:
                return (
                    VERDICT_NOT_EVALUABLE,
                    f"미등재 심각도 '{criterion.min_severity}' — 필터를 적용할 수 없다.",
                    [],
                )
            threshold = _SEVERITY_ORDER.index(criterion.min_severity)
            unrated = sum(1 for i in open_issues if i.severity is None)
            # 심각도 미기재 이슈는 계수하지 않는다 — 근거 없는 추정 금지, 대신 note로 명시.
            open_issues = [
                i
                for i in open_issues
                if i.severity is not None
                and i.severity in _SEVERITY_ORDER
                and _SEVERITY_ORDER.index(i.severity) >= threshold
            ]
        basis = [
            GateBasisRef(
                ref_collection="issues",
                ref_id=issue.id,
                note_ko=f"미해결 이슈 '{issue.title}' (상태 "
                f"{value_label('issue_status', issue.status) or issue.status}"
                + (
                    f", 심각도 {value_label('severity', issue.severity) or issue.severity}"
                    if issue.severity
                    else ""
                )
                + ")",
            )
            for issue in open_issues
        ]
        note = f"미해결 {len(open_issues)}건 / 허용 {limit}건"
        if criterion.min_severity is not None:
            note += (
                f" (심각도 {value_label('severity', criterion.min_severity) or criterion.min_severity}"
                " 이상만 계수"
            )
            if unrated:
                note += f", 심각도 미기재 {unrated}건 제외"
            note += ")"
        verdict = VERDICT_MET if len(open_issues) <= limit else VERDICT_NOT_MET
        return verdict, note, basis

    def _judge_required_evidence(
        self, project_id: str, criterion: GateCriterion
    ) -> tuple[str, str, list[GateBasisRef]]:
        if not criterion.evidence_types:
            return (
                VERDICT_NOT_EVALUABLE,
                "요구 근거 유형(evidence_types)이 비어 있다 — 기준 정의를 채워야 한다.",
                [],
            )
        entries = [
            e
            for e in self._repo.list("evidence_catalog")
            if isinstance(e, EvidenceCatalogEntry) and e.project_id == project_id
        ]
        if criterion.scenario_ids:
            wanted = set(criterion.scenario_ids)
            entries = [e for e in entries if e.scenario_id in wanted]
        basis: list[GateBasisRef] = []
        missing: list[str] = []
        for evidence_type in criterion.evidence_types:
            available = [
                e
                for e in entries
                if e.evidence_type == evidence_type and e.availability == "available"
            ]
            if available:
                basis += [
                    GateBasisRef(
                        ref_collection="evidence_catalog",
                        ref_id=e.id,
                        note_ko=f"가용 근거 '{e.title}' (유형 {evidence_type})",
                    )
                    for e in available
                ]
            else:
                missing.append(evidence_type)
                basis.append(
                    GateBasisRef(
                        ref_collection="evidence_catalog",
                        ref_id=f"missing:{evidence_type}",
                        note_ko=f"요구 유형 '{evidence_type}'의 가용(available) 근거 없음",
                    )
                )
        if missing:
            note = f"요구 근거 유형 {len(criterion.evidence_types)}종 중 {len(missing)}종 누락"
            return VERDICT_NOT_MET, note, basis
        return (
            VERDICT_MET,
            f"요구 근거 유형 {len(criterion.evidence_types)}종 전부 가용",
            basis,
        )

    def _judge_verified_closure(
        self, project_id: str, criterion: GateCriterion
    ) -> tuple[str, str, list[GateBasisRef]]:
        closed = [
            i
            for i in self._issues(project_id, criterion.scenario_ids)
            if i.status in CLOSED_STATUSES
        ]
        if not closed:
            return VERDICT_MET, "종결 이슈 없음 — 위반 대상이 없다.", []
        passed_tests = {
            t.id
            for t in self._repo.list("tests")
            if isinstance(t, Test) and t.result == "passed"
        }
        violations = [
            issue
            for issue in closed
            if not (set(issue.verifying_test_ids) & passed_tests)
        ]
        basis = [
            GateBasisRef(
                ref_collection="issues",
                ref_id=issue.id,
                note_ko=f"종결 이슈 '{issue.title}' — 통과한 검증 테스트 연결 없음",
            )
            for issue in violations
        ]
        note = f"종결 {len(closed)}건 중 검증 없는 종결 {len(violations)}건"
        verdict = VERDICT_MET if not violations else VERDICT_NOT_MET
        return verdict, note, basis
