"""위험 지도 서비스 — 시나리오×IP 정성 위험 등급 파생 뷰 (저장하지 않음).

원점 문서의 Milestone Risk Early Warning 복원 (docs/design/03_course_correction.md §4.1).
결정론 룰만 사용한다: 미해결 이슈, 확신도 차단 근거, 일정 신호, 이벤트 심각도,
P1 요청 상태, 과거 유사 패턴. 출력은 높음/중간/낮음 정성 등급 + 판정 근거 목록이며
수치 리스크 점수는 산출하지 않는다 (CLAUDE.md §6.3 승인 범위).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import DevelopmentEvent, Issue
from backend.ontology.evidence import EvidenceCatalogEntry
from backend.ontology.ip import IPBlock
from backend.ontology.scenario import Scenario, ScenarioRequest
from backend.services.common import BasisItem

GRADE_LABELS: dict[str, str] = {"high": "높음", "medium": "중간", "low": "낮음"}
_GRADE_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}

RULE_LABELS: dict[str, str] = {
    "open_issue": "미해결 이슈",
    "confidence_blocked": "확신도 차단 근거",
    "schedule_risk": "일정 위험 신호",
    "high_severity_event": "고심각도 이벤트",
    "required_evidence_open": "요구 근거 미충족",
    "past_issue_pattern": "과거 유사 이슈",
    "priority_request_blocked": "우선 요청 근거 부족",
    "priority_request_open": "우선 요청 진행 중",
    "evidence_gap_accumulation": "근거 공백 누적",
    "no_signal": "위험 신호 없음",
}

_CLOSED_ISSUE_STATUSES = {"closed", "resolved", "done"}
_CONFIDENCE_CAP_NORMALIZE = {"l": "low", "m": "medium", "h": "high"}
_CLOSED_REQUEST_STATUSES = {"closed", "done"}
_RISKY_SCHEDULE_SIGNALS = {"at_risk", "delayed", "window_closing"}
_RISKY_SEVERITIES = {"high", "critical"}
_TOP_PRIORITIES = {"P0", "P1"}
_GAP_ACCUMULATION_THRESHOLD = 3
_FOCUS_LIMIT = 5

_CATEGORY_ORDER: dict[str, int] = {
    "functional_mm_ip": 0,
    "compute_ip": 1,
    "system_influence_block": 2,
}


# 등급 판정 근거 — 파생 뷰 공용 계약(services/common.py) 재사용.
RiskBasisItem = BasisItem


class RiskCell(BaseModel):
    """시나리오×IP 셀 — 정성 등급 + 판정 근거. 수치 점수 없음."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    ip_id: str
    grade: str
    grade_ko: str
    basis: list[RiskBasisItem]


class HeatmapColumn(BaseModel):
    """heatmap 열 — 시나리오가 참조하는 IP/시스템 블록."""

    model_config = ConfigDict(extra="forbid")

    ip_id: str
    ip_name: str
    category: str


class ScenarioRiskRow(BaseModel):
    """heatmap 행 — 시나리오 종합 등급 + 관련 IP 셀."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    scenario_name: str
    project_ids: list[str]
    overall_grade: str
    overall_grade_ko: str
    overall_basis: list[RiskBasisItem]
    cells: list[RiskCell]


class WeeklyFocusItem(BaseModel):
    """이번 주 주목 항목 — P1 요청·확신도 차단·근거 공백 우선."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    kind_ko: str
    ref_id: str
    ref_collection: str
    title: str
    description: str
    week: int | None = None
    project_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class RiskHeatmap(BaseModel):
    """위험 지도 파생 뷰 — 홈 화면의 첫 응답."""

    model_config = ConfigDict(extra="forbid")

    columns: list[HeatmapColumn]
    rows: list[ScenarioRiskRow]
    focus: list[WeeklyFocusItem]


def _worst(grades: list[str]) -> str:
    if not grades:
        return "low"
    return min(grades, key=lambda g: _GRADE_RANK[g])


def _confidence_cap(raw: str) -> str:
    """56 축약 표기(H/M/L)를 정규화한 확신도 상한."""
    lowered = raw.lower()
    return _CONFIDENCE_CAP_NORMALIZE.get(lowered, lowered)


def ip_match_tokens(ip: IPBlock) -> set[str]:
    """이벤트 affected_domains와 대조할 IP 토큰 — 데이터(도메인/별칭)에서 파생."""
    tokens = {ip.domain.lower(), ip.name.lower()}
    tokens.update(part for part in ip.domain.lower().split("_") if part)
    tokens.update(alias.lower() for alias in ip.aliases)
    return tokens


def event_related_ips(event: DevelopmentEvent, blocks: list[IPBlock]) -> set[str]:
    """이벤트가 관련되는 IP 판별 — 도메인/별칭 일치 또는 후보 옵션의 명시 참조."""
    option_ips = {
        ip_id for option in event.candidate_options for ip_id in option.related_ip_ids
    }
    domains = {d.lower() for d in event.affected_domains}
    matched: set[str] = set()
    for ip in blocks:
        if ip.id in option_ips or domains & ip_match_tokens(ip):
            matched.add(ip.id)
    return matched


class RiskService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    # ---- 공통 수집 ----

    def _scenarios(self) -> list[Scenario]:
        return [s for s in self._repo.list("scenarios") if isinstance(s, Scenario)]

    def _ip_blocks(self) -> dict[str, IPBlock]:
        return {
            b.id: b for b in self._repo.list("ip_blocks") if isinstance(b, IPBlock)
        }

    def _columns(self, scenarios: list[Scenario]) -> list[IPBlock]:
        """열 = 시나리오가 실제 참조하는 IP/시스템 블록 (synthetic ID 하드코딩 없음)."""
        referenced: set[str] = set()
        for scenario in scenarios:
            referenced.update(scenario.uses_ip_blocks)
            referenced.update(scenario.depends_on_system_blocks)
        blocks = [b for b in self._ip_blocks().values() if b.id in referenced]
        return sorted(
            blocks, key=lambda b: (_CATEGORY_ORDER.get(b.category, 9), b.name, b.id)
        )

    def _issues(self) -> list[Issue]:
        return [i for i in self._repo.list("issues") if isinstance(i, Issue)]

    def _events(self) -> list[DevelopmentEvent]:
        return [
            e
            for e in self._repo.list("development_events")
            if isinstance(e, DevelopmentEvent)
        ]

    def _requests(self) -> list[ScenarioRequest]:
        return [
            r
            for r in self._repo.list("scenario_requests")
            if isinstance(r, ScenarioRequest)
        ]

    def _catalog(self) -> list[EvidenceCatalogEntry]:
        return [
            e
            for e in self._repo.list("evidence_catalog")
            if isinstance(e, EvidenceCatalogEntry)
        ]

    # ---- 셀 판정 룰 ----

    def _cell_basis(
        self,
        scenario: Scenario,
        ip: IPBlock,
        issues: list[Issue],
        scenario_events: list[tuple[DevelopmentEvent, set[str]]],
    ) -> tuple[str, list[RiskBasisItem]]:
        basis: list[RiskBasisItem] = []
        grades: list[str] = []

        for issue in issues:
            if scenario.id not in issue.affected_scope.scenarios:
                continue
            issue_ips = set(issue.affected_scope.ip_blocks) | set(
                issue.affected_scope.system_blocks
            )
            if ip.id not in issue_ips:
                continue
            if issue.status in _CLOSED_ISSUE_STATUSES:
                grades.append("medium")
                basis.append(
                    RiskBasisItem(
                        rule="past_issue_pattern",
                        rule_ko=RULE_LABELS["past_issue_pattern"],
                        ref_id=issue.id,
                        ref_collection="issues",
                        description=(
                            f"같은 시나리오·IP 조합의 과거 이슈 '{issue.title}' "
                            f"(상태 {issue.status}) — 재발 가능성 검토 대상"
                        ),
                        source_refs=issue.evidence_refs,
                    )
                )
            else:
                grades.append("high")
                basis.append(
                    RiskBasisItem(
                        rule="open_issue",
                        rule_ko=RULE_LABELS["open_issue"],
                        ref_id=issue.id,
                        ref_collection="issues",
                        description=(
                            f"미해결 이슈 '{issue.title}' (유형 {issue.issue_type}, "
                            f"상태 {issue.status}) — 증상: {issue.symptom}"
                        ),
                        source_refs=issue.evidence_refs,
                    )
                )

        for event, matched_ips in scenario_events:
            if ip.id not in matched_ips:
                continue
            severe = event.severity in _RISKY_SEVERITIES
            if event.schedule_signal in _RISKY_SCHEDULE_SIGNALS:
                grades.append("high" if severe else "medium")
                basis.append(
                    RiskBasisItem(
                        rule="schedule_risk",
                        rule_ko=RULE_LABELS["schedule_risk"],
                        ref_id=event.id,
                        ref_collection="development_events",
                        description=(
                            f"이벤트 '{event.title}'의 일정 신호 {event.schedule_signal}"
                            f" (심각도 {event.severity})"
                        ),
                        source_refs=event.source_basis,
                    )
                )
            elif severe:
                grades.append("medium")
                basis.append(
                    RiskBasisItem(
                        rule="high_severity_event",
                        rule_ko=RULE_LABELS["high_severity_event"],
                        ref_id=event.id,
                        ref_collection="development_events",
                        description=(
                            f"고심각도({event.severity}) 이벤트 '{event.title}' 진행 중"
                        ),
                        source_refs=event.source_basis,
                    )
                )
            for need in event.required_evidence:
                if need.availability == "available":
                    continue
                if need.blocks_confidence_above:
                    cap = _confidence_cap(need.blocks_confidence_above)
                    # 확신도 차단 가중: 상한이 low로 묶이면 높음, medium 이상이면 중간.
                    grades.append("high" if cap == "low" else "medium")
                    basis.append(
                        RiskBasisItem(
                            rule="confidence_blocked",
                            rule_ko=RULE_LABELS["confidence_blocked"],
                            ref_id=event.id,
                            ref_collection="development_events",
                            description=(
                                f"근거 '{need.evidence_need_id}' 미가용 — 확신도 상한 "
                                f"{cap}: {need.reason}"
                            ),
                            source_refs=need.source_refs,
                        )
                    )
                else:
                    grades.append("medium")
                    basis.append(
                        RiskBasisItem(
                            rule="required_evidence_open",
                            rule_ko=RULE_LABELS["required_evidence_open"],
                            ref_id=event.id,
                            ref_collection="development_events",
                            description=(
                                f"이벤트 '{event.title}'의 요구 근거 미충족: {need.reason}"
                            ),
                            source_refs=need.source_refs,
                        )
                    )

        if not basis:
            basis.append(
                RiskBasisItem(
                    rule="no_signal",
                    rule_ko=RULE_LABELS["no_signal"],
                    ref_id=scenario.id,
                    ref_collection="scenarios",
                    description=(
                        f"'{ip.name}'에 연결된 미해결 이슈·일정 위험·근거 공백이 "
                        "감지되지 않음"
                    ),
                    source_refs=scenario.source_basis,
                )
            )
        return _worst(grades), basis


    # ---- 시나리오 종합 판정 룰 ----

    def _scenario_level_basis(
        self,
        scenario: Scenario,
        requests: list[ScenarioRequest],
        catalog: list[EvidenceCatalogEntry],
    ) -> tuple[list[str], list[RiskBasisItem]]:
        basis: list[RiskBasisItem] = []
        grades: list[str] = []
        gap_count = 0

        for request in requests:
            related = request.scenario_id == scenario.id or scenario.id in request.scenario_ids
            if not related or request.status in _CLOSED_REQUEST_STATUSES:
                continue
            if request.priority not in _TOP_PRIORITIES:
                gap_count += len(request.missing_evidence)
                continue
            if request.missing_evidence:
                # P0은 즉시 높음, P1은 중간 — 하드 신호(이슈/일정/확신도 차단)와
                # 결합될 때 종합 등급이 높음으로 올라간다.
                grades.append("high" if request.priority == "P0" else "medium")
                gap_count += len(request.missing_evidence)
                basis.append(
                    RiskBasisItem(
                        rule="priority_request_blocked",
                        rule_ko=RULE_LABELS["priority_request_blocked"],
                        ref_id=request.id,
                        ref_collection="scenario_requests",
                        description=(
                            f"{request.priority} 요청 '{request.title}' (상태 {request.status})에 "
                            f"누락 근거 {len(request.missing_evidence)}건: "
                            f"{'; '.join(request.missing_evidence)}"
                        ),
                        source_refs=request.source_refs,
                    )
                )
            else:
                grades.append("medium")
                basis.append(
                    RiskBasisItem(
                        rule="priority_request_open",
                        rule_ko=RULE_LABELS["priority_request_open"],
                        ref_id=request.id,
                        ref_collection="scenario_requests",
                        description=(
                            f"{request.priority} 요청 '{request.title}' 진행 중 "
                            f"(상태 {request.status})"
                        ),
                        source_refs=request.source_refs,
                    )
                )

        unavailable = [
            entry
            for entry in catalog
            if entry.scenario_id == scenario.id and entry.availability != "available"
        ]
        gap_count += len(unavailable)
        if gap_count >= _GAP_ACCUMULATION_THRESHOLD:
            refs = unavailable[:1]
            basis.append(
                RiskBasisItem(
                    rule="evidence_gap_accumulation",
                    rule_ko=RULE_LABELS["evidence_gap_accumulation"],
                    ref_id=refs[0].id if refs else scenario.id,
                    ref_collection="evidence_catalog" if refs else "scenarios",
                    description=(
                        f"미해결 근거 공백 누적 {gap_count}건 "
                        f"(누락 근거 요청 + 미가용 카탈로그)"
                    ),
                    source_refs=[entry.source_ref for entry in unavailable],
                )
            )
            grades.append("medium")
        return grades, basis

    # ---- 이번 주 주목 ----

    def _focus(
        self,
        scenarios: list[Scenario],
        requests: list[ScenarioRequest],
        events: list[DevelopmentEvent],
        project_id: str | None,
    ) -> list[WeeklyFocusItem]:
        scenario_ids = {s.id for s in scenarios}
        items: list[tuple[int, int, str, WeeklyFocusItem]] = []

        for request in requests:
            if request.status in _CLOSED_REQUEST_STATUSES:
                continue
            if request.priority not in _TOP_PRIORITIES or not request.missing_evidence:
                continue
            if project_id and request.origin_project_id != project_id:
                continue
            related = [
                s
                for s in ([request.scenario_id] if request.scenario_id else [])
                + list(request.scenario_ids)
                if s in scenario_ids
            ]
            items.append(
                (
                    0,
                    -(request.requested_week or 0),
                    request.id,
                    WeeklyFocusItem(
                        kind="priority_request",
                        kind_ko="우선 요청 근거 부족",
                        ref_id=request.id,
                        ref_collection="scenario_requests",
                        title=request.title,
                        description=(
                            f"{request.priority} · 상태 {request.status} · 누락 근거 "
                            f"{len(request.missing_evidence)}건: "
                            f"{'; '.join(request.missing_evidence)}"
                        ),
                        week=request.requested_week,
                        project_ids=[request.origin_project_id],
                        scenario_ids=related,
                        source_refs=request.source_refs,
                    ),
                )
            )

        for event in events:
            if project_id and event.project_id != project_id:
                continue
            linked = [s for s in event.linked_scenario_ids if s in scenario_ids]
            for need in event.required_evidence:
                if need.availability == "available" or not need.blocks_confidence_above:
                    continue
                items.append(
                    (
                        1,
                        -(event.week or 0),
                        f"{event.id}:{need.evidence_need_id}",
                        WeeklyFocusItem(
                            kind="confidence_blocked",
                            kind_ko="확신도 차단",
                            ref_id=event.id,
                            ref_collection="development_events",
                            title=event.title,
                            description=(
                                f"근거 '{need.evidence_need_id}' 미가용 — 확신도 상한 "
                                f"{need.blocks_confidence_above}: {need.reason}"
                            ),
                            week=event.week,
                            project_ids=[event.project_id],
                            scenario_ids=linked,
                            source_refs=need.source_refs,
                        ),
                    )
                )
            if event.schedule_signal in _RISKY_SCHEDULE_SIGNALS and event.severity in _RISKY_SEVERITIES:
                items.append(
                    (
                        2,
                        -(event.week or 0),
                        event.id,
                        WeeklyFocusItem(
                            kind="schedule_risk",
                            kind_ko="일정 위험",
                            ref_id=event.id,
                            ref_collection="development_events",
                            title=event.title,
                            description=(
                                f"일정 신호 {event.schedule_signal} · 심각도 {event.severity}"
                            ),
                            week=event.week,
                            project_ids=[event.project_id],
                            scenario_ids=linked,
                            source_refs=event.source_basis,
                        ),
                    )
                )

        items.sort(key=lambda entry: (entry[0], entry[1], entry[2]))
        return [item for _, _, _, item in items[:_FOCUS_LIMIT]]

    # ---- 조립 ----

    def heatmap(self, project_id: str | None = None) -> RiskHeatmap:
        all_scenarios = self._scenarios()
        scenarios = all_scenarios
        if project_id:
            scenarios = [s for s in scenarios if project_id in s.project_relevance]
        # 열은 프로젝트 필터와 무관하게 고정 — 탭 전환 시 heatmap 구조가 흔들리지 않는다.
        columns = self._columns(all_scenarios)
        column_map = {c.id: c for c in columns}
        issues = self._issues()
        events = self._events()
        requests = self._requests()
        catalog = self._catalog()

        event_ip_cache: dict[str, set[str]] = {
            e.id: event_related_ips(e, columns) for e in events
        }

        rows: list[ScenarioRiskRow] = []
        for scenario in scenarios:
            scenario_events = [
                (e, event_ip_cache[e.id])
                for e in events
                if scenario.id in e.linked_scenario_ids
            ]
            issue_ip_ids = {
                ip_id
                for issue in issues
                if scenario.id in issue.affected_scope.scenarios
                for ip_id in (
                    issue.affected_scope.ip_blocks + issue.affected_scope.system_blocks
                )
            }
            relevant_ips = [
                column_map[ip_id]
                for ip_id in column_map
                if ip_id in set(scenario.uses_ip_blocks)
                | set(scenario.depends_on_system_blocks)
                | issue_ip_ids
            ]

            cells: list[RiskCell] = []
            for ip in sorted(
                relevant_ips,
                key=lambda b: (_CATEGORY_ORDER.get(b.category, 9), b.name, b.id),
            ):
                grade, basis = self._cell_basis(scenario, ip, issues, scenario_events)
                cells.append(
                    RiskCell(
                        scenario_id=scenario.id,
                        ip_id=ip.id,
                        grade=grade,
                        grade_ko=GRADE_LABELS[grade],
                        basis=basis,
                    )
                )

            level_grades, level_basis = self._scenario_level_basis(
                scenario, requests, catalog
            )
            overall = _worst([c.grade for c in cells] + level_grades)
            seen: set[tuple[str, str]] = set()
            overall_basis: list[RiskBasisItem] = []
            for item in level_basis + [
                b
                for c in cells
                if c.grade == overall
                for b in c.basis
                if b.rule != "no_signal"
            ]:
                key = (item.rule, item.ref_id)
                if key in seen:
                    continue
                seen.add(key)
                overall_basis.append(item)
            if not overall_basis:
                overall_basis.append(
                    RiskBasisItem(
                        rule="no_signal",
                        rule_ko=RULE_LABELS["no_signal"],
                        ref_id=scenario.id,
                        ref_collection="scenarios",
                        description="시나리오 전반에서 미해결 위험 신호가 감지되지 않음",
                        source_refs=scenario.source_basis,
                    )
                )
            rows.append(
                ScenarioRiskRow(
                    scenario_id=scenario.id,
                    scenario_name=scenario.name,
                    project_ids=scenario.project_relevance,
                    overall_grade=overall,
                    overall_grade_ko=GRADE_LABELS[overall],
                    overall_basis=overall_basis,
                    cells=cells,
                )
            )

        rows.sort(
            key=lambda r: (_GRADE_RANK[r.overall_grade], r.scenario_name, r.scenario_id)
        )
        return RiskHeatmap(
            columns=[
                HeatmapColumn(ip_id=c.id, ip_name=c.name, category=c.category)
                for c in columns
            ],
            rows=rows,
            focus=self._focus(scenarios, requests, events, project_id),
        )
