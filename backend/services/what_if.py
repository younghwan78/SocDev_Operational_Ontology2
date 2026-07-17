"""what-if 주입 — 가정 실험, ephemeral overlay (16_digital_twin_followups.md §5).

"이 이슈가 해결되면/안 풀리면 무엇이 달라지나"에 결정론으로 답한다.
저장소에는 어떤 경우에도 쓰지 않는다 — 가정을 적용한 overlay 저장소를 만들어
기존 RiskService 룰로 재계산하고 baseline과의 차이만 돌려준다.
판정 룰을 새로 만들지 않는다: 룰이 하나면 가정 실험과 실제 지도가 절대 어긋나지 않는다.

모든 가정은 assumption으로 명시되고 confidence는 medium을 넘지 않는다.
SimulationRun(56 보존 계약)은 사용하지 않으며 감사 기록도 만들지 않는다 —
결정론 계산이라 동일 입력으로 언제든 재현된다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.loaders.protocols import RepositoryProtocol
from backend.loaders.repository import InMemoryRepository
from backend.ontology import COLLECTIONS, OntologyObject
from backend.ontology.glossary import value_label
from backend.services.heatmap_diff import (  # noqa: F401 — 스키마 호환 re-export
    WhatIfCellChange,
    WhatIfRowChange,
    diff_heatmaps,
)
from backend.services.risk import RiskService

# 가정 종류 → (컬렉션, 대상 필드, 값 도메인, 한국어 라벨)
_ASSUMPTION_KINDS: dict[str, tuple[str, str, str, str]] = {
    "issue_status": ("issues", "status", "issue_status", "이슈 상태 가정"),
    "event_schedule_signal": (
        "development_events",
        "schedule_signal",
        "schedule_signal",
        "이벤트 일정 신호 가정",
    ),
}


class UnknownTargetError(Exception):
    pass


class InvalidAssumptionError(Exception):
    pass


class WhatIfAssumption(BaseModel):
    """가정 1건 — 필드 치환(기존 2종) 또는 주입/시프트(Q2 확장 2종).

    kind별 필수 필드 (설계 17 §3):
    - issue_status / event_schedule_signal: value
    - new_issue: target_id(미존재 id) + scenario_ids/ip_ids 각 1건 이상
    - issue_week_shift: week_delta (대상 이슈에 due_week가 있어야 한다)
    """

    model_config = ConfigDict(extra="forbid")

    kind: str  # issue_status | event_schedule_signal | new_issue | issue_week_shift
    target_id: str
    value: str | None = None
    note: str | None = None  # 사용자가 붙이는 가정 사유
    # Q2 확장 필드
    week_delta: int | None = None
    scenario_ids: list[str] = Field(default_factory=list)
    ip_ids: list[str] = Field(default_factory=list)
    severity: str | None = None
    title: str | None = None
    project_id: str | None = None  # new_issue — 비면 첫 시나리오의 첫 관련 프로젝트


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumptions: list[WhatIfAssumption] = Field(min_length=1, max_length=10)


class AppliedAssumption(BaseModel):
    """적용된 가정의 에코 — assumption 지위와 confidence 상한을 명시한다."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    kind_ko: str
    target_id: str
    target_title: str
    field: str
    from_value: str | None
    to_value: str
    note: str | None = None
    basis_type: str = "assumption"  # 근거가 아니라 가정이다
    confidence: str = "medium"  # 가정 기반 — high 금지


class IssueSignalChange(BaseModel):
    """이슈 신호 delta (Q2) — 주차 기반 신호(상태/정체/지연/검증)의 변화 사실."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    title: str
    appeared: bool = False  # 가정 주입(new_issue)으로 overlay에만 존재
    changes: list[str] = Field(default_factory=list)  # "지연: 아니오 → 예" 형식
    projected_note_ko: str | None = None  # overlay 쪽 판정 근거 문구


class WhatIfResult(BaseModel):
    """가정 실험 결과 — 변화만 돌려주고, 변화 없음도 명시한다."""

    model_config = ConfigDict(extra="forbid")

    assumptions: list[AppliedAssumption]
    changed_rows: list[WhatIfRowChange]
    unchanged_scenario_count: int
    # Q2: 위험 지도에 안 보이는 신호 변화 (지연/정체/검증/상태 + 가정 이슈 등장)
    changed_issue_signals: list[IssueSignalChange] = Field(default_factory=list)
    note_ko: str


class WhatIfCandidate(BaseModel):
    """가정 후보 — 기존 신호에서 도출한 '실험해볼 가치가 있는 질문' (설계 18 §3).

    제안이지 결정이 아니다: 우선순위 점수 없이 룰 순서+id로 정렬하며,
    (kind, target_id, value/week_delta)를 그대로 POST /what-if에 넣을 수 있다.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # "{rule}:{target_id}" — 결정론
    rule: str
    rule_ko: str
    kind: str
    target_id: str
    target_title: str
    project_id: str | None = None
    value: str | None = None
    week_delta: int | None = None  # week-shift 후보의 기본값 — UI에서 조정 가능
    label_ko: str
    basis_note_ko: str  # 왜 이 후보인가 — 발화한 신호의 사실 서술


class WhatIfCandidateList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[WhatIfCandidate]
    note_ko: str


class WhatIfService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def run(self, assumptions: list[WhatIfAssumption]) -> WhatIfResult:
        overlay, applied = self._overlay(assumptions)
        baseline = RiskService(self._repo).heatmap()
        projected = RiskService(overlay).heatmap()
        # 비교 로직은 as-of diff와 공유 (heatmap_diff — 설계 20 §3).
        changed, unchanged = diff_heatmaps(baseline, projected)
        return WhatIfResult(
            assumptions=applied,
            changed_rows=changed,
            unchanged_scenario_count=unchanged,
            changed_issue_signals=self._issue_signal_delta(overlay),
            note_ko=(
                "가정 기반 재계산 — 실데이터가 아니며 저장되지 않는다. "
                "판정 룰은 위험 지도·이슈 신호와 동일하다 (결정론, 동일 입력 동일 출력)."
            ),
        )

    def validate(self, assumptions: list[WhatIfAssumption]) -> list[AppliedAssumption]:
        """가정 세트 검증 (X2) — overlay 조립만 수행하고 결과는 버린다.

        오류 계약은 run()과 동일 (미존재 대상/미등재 값 등). 깨진 가정 세트가
        저장되는 것을 막는 관문이다.
        """
        _, applied = self._overlay(assumptions)
        return applied

    def candidates(self, project_id: str | None = None) -> WhatIfCandidateList:
        """가정 후보 도출 (설계 18 §3) — 기존 신호 읽기만, 룰 신설·점수 없음.

        룰 순서 → target_id 정렬 (결정론). 한 이슈가 여러 룰에 걸리면 각각
        후보가 된다 — 룰이 곧 질문이므로 중복이 아니다.
        """
        from backend.ontology.event import DevelopmentEvent, Issue
        from backend.services.rca import _CLOSED_STATUSES, RCAService

        summaries = RCAService(self._repo).list_issues()
        if project_id:
            summaries = [s for s in summaries if s.project_id == project_id]
        issues_by_id = {
            o.id: o for o in self._repo.list("issues") if isinstance(o, Issue)
        }

        unverified: list[WhatIfCandidate] = []
        open_high: list[WhatIfCandidate] = []
        due_shift: list[WhatIfCandidate] = []
        for summary in sorted(summaries, key=lambda s: s.issue_id):
            if summary.closed_without_verification:
                unverified.append(
                    WhatIfCandidate(
                        id=f"unverified_close:{summary.issue_id}",
                        rule="unverified_close",
                        rule_ko="검증 없는 종결",
                        kind="issue_status",
                        target_id=summary.issue_id,
                        target_title=summary.title,
                        project_id=summary.project_id,
                        value="open",
                        label_ko="가정: 이 종결이 잘못이라면(다시 열리면)?",
                        basis_note_ko=(
                            f"종결 상태이지만 {summary.verification_ko} — "
                            "해결 여부를 확인할 수 없다"
                        ),
                    )
                )
            is_open = summary.status not in _CLOSED_STATUSES
            if is_open and summary.severity == "high":
                open_high.append(
                    WhatIfCandidate(
                        id=f"open_high_resolve:{summary.issue_id}",
                        rule="open_high_resolve",
                        rule_ko="미해결 고심각",
                        kind="issue_status",
                        target_id=summary.issue_id,
                        target_title=summary.title,
                        project_id=summary.project_id,
                        value="resolved",
                        label_ko="가정: 이 이슈가 해결되면?",
                        basis_note_ko="미해결 상태 · 심각도 높음 — 해결 시 지도가 얼마나 풀리는지 실험",
                    )
                )
            issue = issues_by_id.get(summary.issue_id)
            if is_open and issue is not None and issue.due_week is not None:
                due_shift.append(
                    WhatIfCandidate(
                        id=f"due_week_shift:{summary.issue_id}",
                        rule="due_week_shift",
                        rule_ko="목표 주차 보유",
                        kind="issue_week_shift",
                        target_id=summary.issue_id,
                        target_title=summary.title,
                        project_id=summary.project_id,
                        week_delta=-2,
                        label_ko="가정: 목표 주차가 당겨지면(기본 −2주)?",
                        basis_note_ko=f"목표 W{issue.due_week} 보유 — 일정 이동이 지연 신호를 바꾸는지 실험",
                    )
                )

        events: list[WhatIfCandidate] = []
        for event in sorted(self._repo.list("development_events"), key=lambda o: o.id):
            if not isinstance(event, DevelopmentEvent):
                continue
            if project_id and event.project_id != project_id:
                continue
            signal = event.schedule_signal
            if signal not in {"at_risk", "window_closing"}:
                continue
            signal_ko = value_label("schedule_signal", signal) or signal
            events.append(
                WhatIfCandidate(
                    id=f"event_at_risk:{event.id}",
                    rule="event_at_risk",
                    rule_ko="위험 일정 이벤트",
                    kind="event_schedule_signal",
                    target_id=event.id,
                    target_title=event.title,
                    project_id=event.project_id,
                    value="on_track",
                    label_ko="가정: 이 이벤트가 정상 진행되면?",
                    basis_note_ko=f"일정 신호 '{signal_ko}' — 정상 진행 가정 시 지도 변화 실험",
                )
            )

        return WhatIfCandidateList(
            candidates=[*unverified, *open_high, *due_shift, *events],
            note_ko=(
                "기존 신호에서 결정론으로 도출한 실험 후보 — 제안이지 결정이 "
                "아니며, 우선순위 점수는 없다 (룰 순서 + id 정렬)."
            ),
        )

    def _issue_signal_delta(
        self, overlay: InMemoryRepository
    ) -> list[IssueSignalChange]:
        """주차 기반 이슈 신호의 delta — 룰은 RCAService 재사용 (신설 없음).

        버전 소스는 넘기지 않는다: 전이 이력은 가정과 무관하게 동일하므로
        비교 대상이 아니다 (주차 기반 신호만 가정의 영향을 받는다).
        """
        from backend.services.rca import RCAService

        baseline = {s.issue_id: s for s in RCAService(self._repo).list_issues()}
        projected = {s.issue_id: s for s in RCAService(overlay).list_issues()}
        yes_no = {True: "예", False: "아니오"}
        changes: list[IssueSignalChange] = []
        for issue_id in sorted(set(baseline) | set(projected)):
            before = baseline.get(issue_id)
            after = projected.get(issue_id)
            if after is None:
                continue  # 가정은 이슈를 없애지 않는다 — 방어적으로 건너뜀
            if before is None:
                changes.append(
                    IssueSignalChange(
                        issue_id=issue_id,
                        title=after.title,
                        appeared=True,
                        projected_note_ko=after.freshness_ko,
                    )
                )
                continue
            diffs: list[str] = []
            if before.status != after.status:
                before_ko = value_label("issue_status", before.status) or before.status
                after_ko = value_label("issue_status", after.status) or after.status
                diffs.append(f"상태: {before_ko} → {after_ko}")
            if before.stale != after.stale:
                diffs.append(f"정체: {yes_no[before.stale]} → {yes_no[after.stale]}")
            if before.overdue != after.overdue:
                diffs.append(f"지연: {yes_no[before.overdue]} → {yes_no[after.overdue]}")
            if before.verification != after.verification:
                diffs.append(
                    f"검증: {before.verification_ko} → {after.verification_ko}"
                )
            if diffs:
                changes.append(
                    IssueSignalChange(
                        issue_id=issue_id,
                        title=after.title,
                        changes=diffs,
                        projected_note_ko=after.freshness_ko,
                    )
                )
        return changes

    def _overlay(
        self, assumptions: list[WhatIfAssumption]
    ) -> tuple[InMemoryRepository, list[AppliedAssumption]]:
        """가정을 적용한 ephemeral 저장소 — 원 저장소는 불변."""
        collections: dict[str, list[OntologyObject]] = {
            key: list(self._repo.list(key)) for key in COLLECTIONS
        }
        applied: list[AppliedAssumption] = []
        for assumption in assumptions:
            if assumption.kind == "new_issue":
                applied.append(self._apply_new_issue(collections, assumption))
            elif assumption.kind == "issue_week_shift":
                applied.append(self._apply_week_shift(collections, assumption))
            elif assumption.kind in _ASSUMPTION_KINDS:
                applied.append(self._apply_field(collections, assumption))
            else:
                known = sorted([*_ASSUMPTION_KINDS, "new_issue", "issue_week_shift"])
                raise InvalidAssumptionError(
                    f"알 수 없는 가정 종류: {assumption.kind} (가능: {', '.join(known)})"
                )
        return InMemoryRepository(collections), applied

    @staticmethod
    def _apply_field(
        collections: dict[str, list[OntologyObject]], assumption: WhatIfAssumption
    ) -> AppliedAssumption:
        """기존 2종 — 실재 객체의 단일 필드를 등재 값으로 치환."""
        collection, field, domain, kind_ko = _ASSUMPTION_KINDS[assumption.kind]
        if not assumption.value:
            raise InvalidAssumptionError(f"'{assumption.kind}' 가정에는 value가 필요하다")
        if value_label(domain, assumption.value) is None:
            raise InvalidAssumptionError(
                f"'{domain}' 도메인에 등재되지 않은 값: {assumption.value!r}"
            )
        target = next(
            (o for o in collections[collection] if o.id == assumption.target_id), None
        )
        if target is None:
            raise UnknownTargetError(f"{collection}에 없는 대상: {assumption.target_id}")
        updated = target.model_copy(update={field: assumption.value})
        collections[collection] = [
            updated if o.id == assumption.target_id else o
            for o in collections[collection]
        ]
        return AppliedAssumption(
            kind=assumption.kind,
            kind_ko=kind_ko,
            target_id=assumption.target_id,
            target_title=str(getattr(target, "title", target.id)),
            field=field,
            from_value=(
                str(current) if (current := getattr(target, field, None)) else None
            ),
            to_value=assumption.value,
            note=assumption.note,
        )

    @staticmethod
    def _apply_new_issue(
        collections: dict[str, list[OntologyObject]], assumption: WhatIfAssumption
    ) -> AppliedAssumption:
        """Q2 — 가정 이슈 주입: overlay에만 존재, 실데이터 id와 충돌 금지."""
        from backend.ontology.event import Issue
        from backend.ontology.scenario import Scenario

        if any(o.id == assumption.target_id for o in collections["issues"]):
            raise InvalidAssumptionError(
                f"이미 존재하는 이슈 id: {assumption.target_id} — "
                "신규 이슈 주입은 미존재 id여야 한다 (실데이터와 충돌 금지)"
            )
        if not assumption.scenario_ids or not assumption.ip_ids:
            raise InvalidAssumptionError(
                "new_issue에는 scenario_ids와 ip_ids가 각 1건 이상 필요하다 "
                "(영향 범위 없는 가정은 효과가 없다)"
            )
        scenario_index = {o.id: o for o in collections["scenarios"]}
        ip_index = {o.id for o in collections["ip_blocks"]}
        for scenario_id in assumption.scenario_ids:
            if scenario_id not in scenario_index:
                raise InvalidAssumptionError(f"없는 시나리오: {scenario_id}")
        for ip_id in assumption.ip_ids:
            if ip_id not in ip_index:
                raise InvalidAssumptionError(f"없는 IP/시스템 블록: {ip_id}")
        if assumption.severity and value_label("severity", assumption.severity) is None:
            raise InvalidAssumptionError(
                f"'severity' 도메인에 등재되지 않은 값: {assumption.severity!r}"
            )
        status = assumption.value or "open"
        if value_label("issue_status", status) is None:
            raise InvalidAssumptionError(
                f"'issue_status' 도메인에 등재되지 않은 값: {status!r}"
            )
        project_id = assumption.project_id
        if project_id is None:
            first = scenario_index[assumption.scenario_ids[0]]
            relevance = getattr(first, "project_relevance", []) if isinstance(
                first, Scenario
            ) else []
            if not relevance:
                raise InvalidAssumptionError(
                    "project_id를 정할 수 없다 — 시나리오에 관련 프로젝트가 없으니 "
                    "project_id를 명시하라"
                )
            project_id = relevance[0]

        injected = Issue.model_validate(
            {
                "id": assumption.target_id,
                "project_id": project_id,
                "title": assumption.title or "가정 이슈 (what-if)",
                "issue_type": "defect",
                "status": status,
                "severity": assumption.severity,
                "symptom": assumption.note or "가정 이슈 — what-if 주입",
                "confidence": "low",  # 가정 — 근거 없는 확신 금지
                "affected_scope": {
                    "scenarios": assumption.scenario_ids,
                    "ip_blocks": assumption.ip_ids,
                },
                "source": {
                    "origin": "synthetic",
                    "ref": f"whatif:{assumption.target_id}",
                },
            }
        )
        collections["issues"] = [*collections["issues"], injected]
        return AppliedAssumption(
            kind="new_issue",
            kind_ko="신규 이슈 주입 가정",
            target_id=assumption.target_id,
            target_title=injected.title,
            field="status",
            from_value=None,
            to_value=status,
            note=assumption.note,
        )

    @staticmethod
    def _apply_week_shift(
        collections: dict[str, list[OntologyObject]], assumption: WhatIfAssumption
    ) -> AppliedAssumption:
        """Q2 — 목표 주차 시프트: due_week를 delta만큼 이동 (지연 신호 가정 실험)."""
        from backend.ontology.event import Issue

        if assumption.week_delta is None:
            raise InvalidAssumptionError("issue_week_shift에는 week_delta가 필요하다")
        target = next(
            (o for o in collections["issues"] if o.id == assumption.target_id), None
        )
        if target is None:
            raise UnknownTargetError(f"issues에 없는 대상: {assumption.target_id}")
        if not isinstance(target, Issue) or target.due_week is None:
            raise InvalidAssumptionError(
                f"이슈 {assumption.target_id}에 due_week가 없다 — 시프트할 사실이 없다"
            )
        shifted = target.due_week + assumption.week_delta
        updated = target.model_copy(update={"due_week": shifted})
        collections["issues"] = [
            updated if o.id == assumption.target_id else o
            for o in collections["issues"]
        ]
        return AppliedAssumption(
            kind="issue_week_shift",
            kind_ko="목표 주차 시프트 가정",
            target_id=assumption.target_id,
            target_title=target.title,
            field="due_week",
            from_value=str(target.due_week),
            to_value=str(shifted),
            note=assumption.note,
        )
