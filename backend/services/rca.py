"""이슈 분석(RCA) 서비스 — "이 이슈의 원인은? 정말 해결됐나? 재발하나?"

internal_docs/design/04_stage10_rca_design.md §3의 결정론 파생 뷰.
이슈를 증상→영향→원인→조치→검증 테스트→잔존 리스크→재사용 교훈의 7단 체인으로
펼치고, 각 노드에 근거 뱃지(green/red/yellow)를 붙인다.

**"close됐는데 검증 테스트가 없다"를 빨갛게 드러내는 것이 이 뷰의 존재 이유다.**
원인 후보는 데이터에 기록된 것만 표시한다 — LLM 원인 추론 없음.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.ingest.history import ObjectVersion, extract_status_transitions
from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import Issue, Test
from backend.ontology.glossary import enum_label, value_label
from backend.ontology.ip import IPBlock
from backend.ontology.scenario import Scenario

STEP_LABELS: dict[str, str] = {
    "symptom": "증상",
    "impact": "영향 범위",
    "root_cause": "원인",
    "action": "조치",
    "verification": "검증 테스트",
    "residual_risk": "잔존 리스크",
    "lesson": "재사용 교훈",
}

VERIFICATION_LABELS: dict[str, str] = {
    "verified": "검증됨",
    "unverified": "검증 미완",
    "no_tests": "검증 테스트 없음",
}

_CLOSED_STATUSES = {"closed", "resolved", "done"}

# J3 신선도 룰 (14_ingest_reality_gaps.md §2) — 미해결 + N주 무활동 = 정체.
# 수치 점수가 아니라 날짜 사실에 근거한 정성 신호다. 기준 주차는 데이터의
# 최신 활동 주차(결정론) — 벽시계를 쓰지 않아 fixture 우주에서도 성립한다.
_STALE_WEEKS = 4

# P1 전이 이력 룰 (16_digital_twin_followups.md §2) — transaction time 축.
# 기준 시점은 이슈 컬렉션 버전 로그의 최신 recorded_at — 역시 벽시계 불사용.
_STALE_DAYS = 28


class VersionSourceProtocol(Protocol):
    """버전 로그 읽기 계약 — IngestService가 충족한다 (P1·P2 공유)."""

    def collection_versions(self, collection: str) -> list[ObjectVersion]: ...


@dataclass
class _TransitionSignal:
    """이슈 하나의 전이 이력 파생 신호 — 전부 사실 서술 재료."""

    reopened: bool = False
    reopen_note: str | None = None
    last_activity_at: str | None = None
    stale: bool = False
    stale_note: str | None = None


def _parse_instant(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

TEST_TYPE_LABELS: dict[str, str] = {
    "regression": "회귀",
    "scenario": "시나리오",
    "cts_vts": "CTS/VTS",
    "power": "전력",
}

TEST_RESULT_LABELS: dict[str, str] = {
    "passed": "통과",
    "failed": "실패",
    "blocked": "차단",
    "planned": "계획",
}


class IssueNotFoundError(Exception):
    pass


class RCAItem(BaseModel):
    """RCA 노드 안의 개별 항목 — 원본 객체 참조 동반."""

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    ref_id: str | None = None
    ref_collection: str | None = None
    badge: str | None = None  # 항목 단위 보조 뱃지 (예: 테스트 결과)
    source_refs: list[str] = Field(default_factory=list)


class RCANode(BaseModel):
    """RCA 체인의 한 단계 — 근거 뱃지와 사유를 갖는다."""

    model_config = ConfigDict(extra="forbid")

    step: str
    step_ko: str
    badge: str  # green | red | yellow
    badge_reason_ko: str
    items: list[RCAItem] = Field(default_factory=list)


class IssueSummary(BaseModel):
    """이슈 목록 항목 — 검증 상태 뱃지 포함."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    title: str
    issue_type: str
    status: str
    # 이슈 자체 심각도 (optional) — 목록의 우선순위 판단 보조 (I3).
    severity: str | None = None
    project_id: str
    confidence: str
    scenario_ids: list[str] = Field(default_factory=list)
    verification: str  # verified | unverified | no_tests
    verification_ko: str
    closed_without_verification: bool
    # J3 신선도·일정 신호 — 판정 근거(주차)를 문구에 명시한다.
    stale: bool = False
    overdue: bool = False
    freshness_ko: str | None = None
    # P1 전이 이력 신호 — 버전 로그가 있는 이슈(반입/커넥터 유래)만 채워진다.
    reopened: bool = False
    last_activity_at: str | None = None


class RCAChain(BaseModel):
    """이슈 RCA 파생 뷰 — 7단 세로 흐름 (저장하지 않음)."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    title: str
    issue_type: str
    status: str
    project_id: str
    confidence: str
    verification: str
    verification_ko: str
    closed_without_verification: bool
    alert_ko: str | None = None
    # P1: 종결됐다 다시 열린 이슈 — 전이 근거 문구 동반.
    reopened: bool = False
    reopen_note_ko: str | None = None
    nodes: list[RCANode]
    # J4: 관련 문서 후보 — 이슈의 외부 문서 참조 + 이 이슈를 언급하는 검색 청크.
    # 후보 지위(증거 아님) — supporting_basis 편입은 큐레이션을 거친다.
    doc_refs: list[str] = Field(default_factory=list)
    doc_candidates: list[RCAItem] = Field(default_factory=list)


def _verification_status(issue: Issue, tests: list[Test]) -> str:
    if not tests:
        return "no_tests"
    if all(t.result == "passed" for t in tests):
        return "verified"
    return "unverified"


class RCAService:
    def __init__(
        self, repo: RepositoryProtocol, versions: VersionSourceProtocol | None = None
    ) -> None:
        self._repo = repo
        # 버전 소스가 없으면(순수 fixture 환경) 주차 기반 판정만으로 폴백한다.
        self._versions = versions

    def _issues(self) -> list[Issue]:
        return [i for i in self._repo.list("issues") if isinstance(i, Issue)]

    def _issue_tests(self, issue: Issue) -> list[Test]:
        """이슈를 검증하는 테스트 — 이슈의 명시 링크와 테스트 쪽 역링크의 합집합."""
        collected: dict[str, Test] = {}
        for test_id in issue.verifying_test_ids:
            obj = self._repo.get("tests", test_id)
            if isinstance(obj, Test):
                collected[obj.id] = obj
        for obj in self._repo.list("tests"):
            if isinstance(obj, Test) and issue.id in obj.verifies_issue_ids:
                collected[obj.id] = obj
        return sorted(collected.values(), key=lambda t: t.id)

    def _reference_week(self) -> int | None:
        """기준 주차 = 데이터의 최신 활동 주차 — 벽시계 없는 결정론 '지금'."""
        weeks: list[int] = []
        for issue in self._issues():
            weeks += [
                w for w in (issue.resolved_week, issue.updated_week, issue.due_week) if w
            ]
        for obj in self._repo.list("tests"):
            if isinstance(obj, Test) and obj.executed_week:
                weeks.append(obj.executed_week)
        for obj in self._repo.list("development_events"):
            week = getattr(obj, "week", None)
            if week:
                weeks.append(week)
        return max(weeks, default=None)

    @staticmethod
    def _freshness(
        issue: Issue, reference_week: int | None
    ) -> tuple[bool, bool, str | None]:
        """J3 정체/지연 판정 — (stale, overdue, 판정 근거 문구)."""
        if reference_week is None or issue.status in _CLOSED_STATUSES:
            return False, False, None
        notes: list[str] = []
        stale = bool(
            issue.updated_week is not None
            and reference_week - issue.updated_week >= _STALE_WEEKS
        )
        if stale:
            notes.append(
                f"정체 — 최근 활동 W{issue.updated_week}, 기준 W{reference_week}"
                f" ({_STALE_WEEKS}주 이상 무활동)"
            )
        overdue = bool(issue.due_week is not None and issue.due_week < reference_week)
        if overdue:
            notes.append(f"지연 — 목표 W{issue.due_week} 경과 (기준 W{reference_week})")
        return stale, overdue, " · ".join(notes) or None

    def _transition_signals(self) -> dict[str, _TransitionSignal]:
        """P1 — 이슈 버전 로그에서 재개·전이 기반 정체를 뽑는다 (컬렉션 1회 조회).

        transaction time 축의 사실 서술이다: 기준 시점은 로그의 최신 recorded_at
        (벽시계 불사용 — 동일 로그 동일 출력).
        """
        if self._versions is None:
            return {}
        versions = self._versions.collection_versions("issues")
        if not versions:
            return {}
        by_object: dict[str, list[ObjectVersion]] = {}
        for entry in versions:
            by_object.setdefault(entry.object_id, []).append(entry)
        reference = max(v.recorded_at for v in versions)
        reference_dt = _parse_instant(reference)

        signals: dict[str, _TransitionSignal] = {}
        for object_id, entries in by_object.items():
            signal = _TransitionSignal()
            for transition in extract_status_transitions(entries):
                if (
                    transition.from_status in _CLOSED_STATUSES
                    and transition.to_status not in _CLOSED_STATUSES
                ):
                    from_ko = value_label("issue_status", transition.from_status) or (
                        transition.from_status
                    )
                    to_ko = value_label("issue_status", transition.to_status) or (
                        transition.to_status
                    )
                    signal.reopened = True
                    signal.reopen_note = (
                        f"재개 — '{from_ko}'→'{to_ko}' "
                        f"(v{transition.version}, {transition.recorded_at[:10]})"
                    )
            last = max(entry.recorded_at for entry in entries)
            signal.last_activity_at = last
            last_dt = _parse_instant(last)
            if (
                reference_dt is not None
                and last_dt is not None
                and (reference_dt - last_dt).days >= _STALE_DAYS
            ):
                signal.stale = True
                signal.stale_note = (
                    f"정체 — 마지막 기록 활동 {last[:10]} "
                    f"(기준 {reference[:10]}, {_STALE_DAYS}일 이상 무활동)"
                )
            signals[object_id] = signal
        return signals

    # ---- 이슈 목록 ----

    def list_issues(
        self, project_id: str | None = None, verification: str | None = None
    ) -> list[IssueSummary]:
        summaries: list[IssueSummary] = []
        reference_week = self._reference_week()
        transition_signals = self._transition_signals()
        for issue in self._issues():
            if project_id and issue.project_id != project_id:
                continue
            tests = self._issue_tests(issue)
            status = _verification_status(issue, tests)
            if verification and status != verification:
                continue
            closed_unverified = issue.status in _CLOSED_STATUSES and status != "verified"
            stale, overdue, freshness_ko = self._freshness(issue, reference_week)
            # P1: 전이 이력 신호와 결합 — 어느 근거로 판정됐는지 문구에 남는다.
            signal = transition_signals.get(issue.id)
            notes = [freshness_ko] if freshness_ko else []
            if signal is not None:
                if signal.stale and issue.status not in _CLOSED_STATUSES:
                    stale = True
                    if signal.stale_note:
                        notes.append(signal.stale_note)
                if signal.reopened and signal.reopen_note:
                    notes.append(signal.reopen_note)
            summaries.append(
                IssueSummary(
                    issue_id=issue.id,
                    title=issue.title,
                    issue_type=issue.issue_type,
                    status=issue.status,
                    severity=issue.severity,
                    project_id=issue.project_id,
                    confidence=str(issue.confidence),
                    scenario_ids=issue.affected_scope.scenarios,
                    verification=status,
                    verification_ko=VERIFICATION_LABELS[status],
                    closed_without_verification=closed_unverified,
                    stale=stale,
                    overdue=overdue,
                    freshness_ko=" · ".join(notes) or None,
                    reopened=bool(signal and signal.reopened),
                    last_activity_at=signal.last_activity_at if signal else None,
                )
            )
        # 경고(닫혔는데 미검증)가 먼저, 그다음 프로젝트/ID 순 — 결정론 정렬.
        summaries.sort(
            key=lambda s: (not s.closed_without_verification, s.project_id, s.issue_id)
        )
        return summaries

    # ---- RCA 체인 ----

    def chain(self, issue_id: str) -> RCAChain:
        obj = self._repo.get("issues", issue_id)
        if not isinstance(obj, Issue):
            raise IssueNotFoundError(f"이슈 없음: {issue_id}")
        issue = obj
        tests = self._issue_tests(issue)
        verification = _verification_status(issue, tests)
        closed_unverified = issue.status in _CLOSED_STATUSES and verification != "verified"

        nodes = [
            self._symptom_node(issue),
            self._impact_node(issue),
            self._cause_node(issue),
            self._action_node(issue),
            self._verification_node(issue, tests),
            self._residual_node(issue),
            self._lesson_node(issue),
        ]
        alert_ko = None
        if closed_unverified:
            alert_ko = (
                "이슈가 종결 상태이지만 검증 테스트가 없습니다"
                if verification == "no_tests"
                else "이슈가 종결 상태이지만 검증 테스트가 전부 통과하지 않았습니다"
            )
        signal = self._transition_signals().get(issue.id)
        return RCAChain(
            issue_id=issue.id,
            title=issue.title,
            issue_type=issue.issue_type,
            status=issue.status,
            project_id=issue.project_id,
            confidence=str(issue.confidence),
            verification=verification,
            verification_ko=VERIFICATION_LABELS[verification],
            closed_without_verification=closed_unverified,
            alert_ko=alert_ko,
            reopened=bool(signal and signal.reopened),
            reopen_note_ko=signal.reopen_note if signal else None,
            nodes=nodes,
            doc_refs=issue.doc_refs,
            doc_candidates=self._doc_candidates(issue),
        )

    def _doc_candidates(self, issue: Issue) -> list[RCAItem]:
        """J4 — 이 이슈를 언급하는 검색 청크(Confluence 등). 후보이지 증거가 아니다."""
        from backend.ontology.evidence import SemanticChunk

        items: list[RCAItem] = []
        for obj in self._repo.list("semantic_chunks"):
            if not isinstance(obj, SemanticChunk) or issue.id not in obj.related_issue_ids:
                continue
            preview = obj.chunk_text.replace("\n", " ")
            items.append(
                RCAItem(
                    title=obj.source_id,
                    description=preview[:160] + ("…" if len(preview) > 160 else ""),
                    ref_id=obj.id,
                    ref_collection="semantic_chunks",
                )
            )
        return sorted(items, key=lambda item: item.ref_id or "")

    def _symptom_node(self, issue: Issue) -> RCANode:
        has_evidence = bool(issue.evidence_refs)
        return RCANode(
            step="symptom",
            step_ko=STEP_LABELS["symptom"],
            badge="green" if has_evidence else "red",
            badge_reason_ko=(
                f"근거 {len(issue.evidence_refs)}건 연결" if has_evidence else "증상을 뒷받침하는 근거 없음"
            ),
            items=[
                RCAItem(
                    title=issue.title,
                    description=issue.symptom,
                    ref_id=issue.id,
                    ref_collection="issues",
                    source_refs=issue.evidence_refs,
                )
            ],
        )

    def _impact_node(self, issue: Issue) -> RCANode:
        scope = issue.affected_scope
        items: list[RCAItem] = []
        for scenario_id in scope.scenarios:
            scenario = self._repo.get("scenarios", scenario_id)
            items.append(
                RCAItem(
                    title=scenario.name if isinstance(scenario, Scenario) else scenario_id,
                    description="영향 시나리오",
                    ref_id=scenario_id,
                    ref_collection="scenarios",
                )
            )
        for ip_id in scope.ip_blocks + scope.system_blocks:
            block = self._repo.get("ip_blocks", ip_id)
            items.append(
                RCAItem(
                    title=block.name if isinstance(block, IPBlock) else ip_id,
                    description="영향 IP/시스템 블록",
                    ref_id=ip_id,
                    ref_collection="ip_blocks",
                )
            )
        if scope.kpis:
            items.append(
                RCAItem(title=", ".join(scope.kpis), description="영향 KPI", ref_id=issue.id)
            )
        recorded = bool(scope.scenarios or scope.ip_blocks or scope.system_blocks)
        return RCANode(
            step="impact",
            step_ko=STEP_LABELS["impact"],
            badge="green" if recorded else "red",
            badge_reason_ko=(
                "영향 시나리오/IP가 기록됨" if recorded else "영향 범위가 기록되지 않음"
            ),
            items=items,
        )

    def _cause_node(self, issue: Issue) -> RCANode:
        items: list[RCAItem] = []
        for index, cause in enumerate(issue.root_causes):
            label = enum_label("RootCauseType", cause.cause_type.value) or cause.cause_type.value
            items.append(
                RCAItem(
                    title=label,
                    description=cause.description,
                    ref_id=f"{issue.id}#root_cause_{index}",
                    ref_collection="issues",
                    badge="green" if cause.evidence_refs else "yellow",
                    source_refs=cause.evidence_refs,
                )
            )
        for candidate in issue.root_cause_candidates:
            items.append(
                RCAItem(
                    title="원인 후보 (미확정)",
                    description=candidate,
                    ref_id=issue.id,
                    ref_collection="issues",
                    badge="yellow",
                )
            )
        if issue.root_causes and all(c.evidence_refs for c in issue.root_causes):
            badge, reason = "green", "구조화된 원인이 근거와 함께 기록됨"
        elif issue.root_causes or issue.root_cause_candidates:
            badge, reason = "yellow", "원인이 후보 단계이거나 근거가 붙지 않음"
        else:
            badge, reason = "red", "기록된 원인이 없음"
        return RCANode(
            step="root_cause",
            step_ko=STEP_LABELS["root_cause"],
            badge=badge,
            badge_reason_ko=reason,
            items=items,
        )

    def _action_node(self, issue: Issue) -> RCANode:
        items: list[RCAItem] = []
        if issue.fix_type:
            items.append(
                RCAItem(
                    title=f"조치 ({issue.fix_type})",
                    description=issue.fix_description or "",
                    ref_id=issue.id,
                    ref_collection="issues",
                    badge="green",
                )
            )
        if issue.workaround:
            items.append(
                RCAItem(
                    title="임시 우회 (workaround)",
                    description=issue.workaround,
                    ref_id=issue.id,
                    ref_collection="issues",
                    badge="yellow",
                )
            )
        if issue.fix_type:
            badge, reason = "green", "조치가 기록됨"
        elif issue.workaround:
            badge, reason = "yellow", "임시 우회만 기록됨 — 정식 조치 없음"
        elif issue.status in _CLOSED_STATUSES:
            badge, reason = "red", "종결됐지만 조치 기록이 없음"
        else:
            badge, reason = "yellow", "조치 미기록 (진행 중)"
        return RCANode(
            step="action",
            step_ko=STEP_LABELS["action"],
            badge=badge,
            badge_reason_ko=reason,
            items=items,
        )

    def _verification_node(self, issue: Issue, tests: list[Test]) -> RCANode:
        items = [
            RCAItem(
                title=test.title,
                description=(
                    f"{TEST_TYPE_LABELS.get(test.test_type, test.test_type)} · "
                    f"결과 {TEST_RESULT_LABELS.get(test.result, test.result)}"
                    + (f" · W{test.executed_week}" if test.executed_week is not None else "")
                    + f" — {test.summary}"
                ),
                ref_id=test.id,
                ref_collection="tests",
                badge=(
                    "green"
                    if test.result == "passed"
                    else "yellow" if test.result in ("planned", "blocked") else "red"
                ),
                source_refs=test.linked_evidence_ids,
            )
            for test in tests
        ]
        if not tests:
            badge = "red"
            reason = "검증 테스트 없음 — 해결 여부를 확인할 수 없음"
        elif all(t.result == "passed" for t in tests):
            badge = "green"
            reason = f"테스트 {len(tests)}건 전부 통과"
        else:
            badge = "yellow"
            unpassed = sum(1 for t in tests if t.result != "passed")
            reason = f"테스트 {len(tests)}건 중 {unpassed}건 미통과(실패/계획/차단)"
        return RCANode(
            step="verification",
            step_ko=STEP_LABELS["verification"],
            badge=badge,
            badge_reason_ko=reason,
            items=items,
        )

    def _residual_node(self, issue: Issue) -> RCANode:
        recorded = bool(issue.residual_risk)
        return RCANode(
            step="residual_risk",
            step_ko=STEP_LABELS["residual_risk"],
            badge="green" if recorded else "yellow",
            badge_reason_ko="잔존 리스크가 기록됨" if recorded else "잔존 리스크 미기록",
            items=(
                [
                    RCAItem(
                        title="잔존 리스크",
                        description=issue.residual_risk or "",
                        ref_id=issue.id,
                        ref_collection="issues",
                    )
                ]
                if recorded
                else []
            ),
        )

    def _lesson_node(self, issue: Issue) -> RCANode:
        recorded = bool(issue.reusable_lesson)
        return RCANode(
            step="lesson",
            step_ko=STEP_LABELS["lesson"],
            badge="green" if recorded else "yellow",
            badge_reason_ko="재사용 교훈이 기록됨" if recorded else "재사용 교훈 미기록",
            items=(
                [
                    RCAItem(
                        title="재사용 교훈",
                        description=issue.reusable_lesson or "",
                        ref_id=issue.id,
                        ref_collection="issues",
                    )
                ]
                if recorded
                else []
            ),
        )
