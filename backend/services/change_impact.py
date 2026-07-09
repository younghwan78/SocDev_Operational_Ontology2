"""변경 영향 서비스 — "이 IP/knob/capability/모드를 바꾸면 어디에 영향이 가나?"

internal_docs/design/03_course_correction.md §4.2의 결정론 그래프 순회만 사용한다:

    선택 IP → scenario_ip_requirements → 영향 시나리오 → primary_kpis
    선택 IP → ip_dependency_rules → 연쇄 IP (조건 표시)
    선택 knob → ip_knobs.affected_kpis / related_scenarios / 방향성
    영향 시나리오 → 과거 이슈/이벤트 (같은 IP 조합) → 유사 사례
    영향 도메인 → 역할 책임 경계(CLAUDE.md §2.2) → 검토 관점 체크리스트

모든 영향 항목은 근거 객체 ref를 동반한다. 근거 없는 연결은 만들지 않는다
(capability↔요구 매칭은 보수적 토큰 부분집합 일치만 사용). 수치 점수·자동 결정 없음.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import DevelopmentEvent, Issue
from backend.ontology.ip import IPBaseSpec, IPBlock, IPCapability, IPDependencyRule, IPKnob
from backend.ontology.role import RoleAgent
from backend.ontology.scenario import (
    KPIDefinition,
    Scenario,
    ScenarioIPRequirement,
    ScenarioRequest,
)
from backend.resolve.entity_resolution import IPAliasIndex
from backend.services.common import BasisItem
from backend.services.risk import event_related_ips

_RISKY_SCHEDULE_SIGNALS = {"at_risk", "delayed", "window_closing"}
_CLOSED_REQUEST_STATUSES = {"closed", "done"}
_TOP_PRIORITIES = {"P0", "P1"}

_CATEGORY_ORDER: dict[str, int] = {
    "functional_mm_ip": 0,
    "compute_ip": 1,
    "system_influence_block": 2,
}

# CLAUDE.md §2.2 역할 순서 — 체크리스트 표시 순서로 사용.
_ROLE_ORDER = [
    "product_planning",
    "soc_architecture",
    "system_engineering",
    "hw_development",
    "sw_development",
    "pm",
    "management",
]

REASON_LABELS: dict[str, str] = {
    "ip_requirement": "시나리오 IP 요구",
    "knob_related": "knob 관련 시나리오",
    "uses_ip": "IP 사용/의존",
}

DIRECTION_LABELS: dict[str, str] = {
    "outgoing": "선택 IP가 의존 (부하/조건 전파)",
    "incoming": "선택 IP에 의존 (동작 영향)",
}


class UnknownIPError(Exception):
    pass


class InvalidSelectionError(Exception):
    pass


class KnobEffect(BaseModel):
    """선택 knob의 방향성 요약 — ip_knobs 원본 그대로."""

    model_config = ConfigDict(extra="forbid")

    knob_id: str
    name: str
    category: str
    control_domain: str
    description: str
    power_direction: str
    latency_direction: str
    bandwidth_direction: str
    risk_direction: str
    affected_kpis: list[str] = Field(default_factory=list)
    related_scenarios: list[str] = Field(default_factory=list)
    confidence: str
    source_ref: str


class CapabilityInfo(BaseModel):
    """선택 capability 요약."""

    model_config = ConfigDict(extra="forbid")

    capability_id: str
    name: str
    category: str
    support_status: str
    condition: str | None = None
    confidence: str
    source_ref: str


class ImpactSubject(BaseModel):
    """무엇을 바꾸는가 — 분석 대상."""

    model_config = ConfigDict(extra="forbid")

    ip_id: str
    ip_name: str
    ip_category: str
    knob: KnobEffect | None = None
    capability: CapabilityInfo | None = None
    mode: str | None = None
    summary: str


class ImpactedScenario(BaseModel):
    """영향 시나리오 — 근거 목록 동반."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    scenario_name: str
    project_ids: list[str] = Field(default_factory=list)
    kpi_ids: list[str] = Field(default_factory=list)
    reasons: list[BasisItem]


class ImpactedKPI(BaseModel):
    """영향 KPI — 유래(knob/시나리오) 표시."""

    model_config = ConfigDict(extra="forbid")

    kpi_id: str
    unit: str | None = None
    direction: str | None = None
    via_knob: bool = False
    scenario_ids: list[str] = Field(default_factory=list)


class ChainedIP(BaseModel):
    """연쇄 IP — ip_dependency_rules 기반, 조건 표시."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    ip_id: str
    ip_name: str
    direction: str
    direction_ko: str
    relationship: str
    condition: str
    rationale: str
    confidence: str
    source_ref: str


class ChecklistItem(BaseModel):
    """역할 관점 검토 항목 — 트리거 근거가 있을 때만 생성 (일반론 금지)."""

    model_config = ConfigDict(extra="forbid")

    role_id: str
    role_name: str
    perspective: str
    basis: list[BasisItem]


class SimilarCase(BaseModel):
    """과거 유사 사례 — 같은 IP 조합의 이슈/이벤트."""

    model_config = ConfigDict(extra="forbid")

    kind: str  # issue | event
    kind_ko: str
    ref_id: str
    title: str
    status: str
    why_similar: str
    scenario_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)


class ChangeImpactResult(BaseModel):
    """변경 영향 분석 — 4분면 + 유사 사례 파생 뷰 (저장하지 않음)."""

    model_config = ConfigDict(extra="forbid")

    subject: ImpactSubject
    impacted_scenarios: list[ImpactedScenario]
    impacted_kpis: list[ImpactedKPI]
    chained_ips: list[ChainedIP]
    checklist: list[ChecklistItem]
    similar_cases: list[SimilarCase]
    export_text: str
    note_ko: str = "결정이 아닌 검토 안내입니다 · 수치 점수 없음"


class IPOption(BaseModel):
    """변경 영향 폼 옵션 — IP별 선택 가능한 knob/capability/모드."""

    model_config = ConfigDict(extra="forbid")

    ip_id: str
    ip_name: str
    category: str
    knobs: list[dict[str, str]] = Field(default_factory=list)
    capabilities: list[dict[str, str]] = Field(default_factory=list)
    modes: list[str] = Field(default_factory=list)


class ChangeImpactOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ips: list[IPOption]


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if t}


def _capability_tokens(cap: IPCapability) -> set[str]:
    tokens = _tokens(cap.id.removeprefix("cap_")) | _tokens(cap.name)
    for value in cap.values:
        tokens |= _tokens(value)
    if cap.value:
        tokens |= _tokens(cap.value)
    return tokens


def _capability_matches_requirement(cap: IPCapability, requirement: ScenarioIPRequirement) -> bool:
    """보수적 매칭 — 요구 capability의 모든 토큰이 capability 토큰에 포함될 때만."""
    required = _tokens(requirement.required_capability)
    return bool(required) and required <= _capability_tokens(cap)


class ChangeImpactService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    # ---- 조회 헬퍼 ----

    def _ip(self, ip_id: str) -> IPBlock:
        obj = self._repo.get("ip_blocks", ip_id)
        if not isinstance(obj, IPBlock):
            raise UnknownIPError(f"IP 블록 없음: {ip_id}")
        return obj

    def _list(self, collection: str, model: type) -> list:
        return [o for o in self._repo.list(collection) if isinstance(o, model)]

    def _roles(self) -> dict[str, RoleAgent]:
        return {r.id: r for r in self._list("roles", RoleAgent)}

    # ---- 폼 옵션 ----

    def options(self) -> ChangeImpactOptions:
        knobs = self._list("ip_knobs", IPKnob)
        caps = self._list("ip_capabilities", IPCapability)
        specs = self._list("ip_base_specs", IPBaseSpec)
        options: list[IPOption] = []
        for ip in sorted(
            self._list("ip_blocks", IPBlock),
            key=lambda b: (_CATEGORY_ORDER.get(b.category, 9), b.name, b.id),
        ):
            modes: list[str] = []
            for spec in specs:
                if spec.ip_id == ip.id:
                    modes.extend(m for m in spec.supported_modes if m not in modes)
            options.append(
                IPOption(
                    ip_id=ip.id,
                    ip_name=ip.name,
                    category=ip.category,
                    knobs=[
                        {"id": k.id, "name": k.name, "category": k.category}
                        for k in knobs
                        if k.ip_id == ip.id
                    ],
                    capabilities=[
                        {"id": c.id, "name": c.name, "category": c.category}
                        for c in caps
                        if c.ip_id == ip.id
                    ],
                    modes=modes,
                )
            )
        return ChangeImpactOptions(ips=options)

    # ---- 분석 ----

    def analyze(
        self,
        ip_id: str,
        knob_id: str | None = None,
        capability_id: str | None = None,
        mode: str | None = None,
    ) -> ChangeImpactResult:
        ip = self._ip(ip_id)

        knob: IPKnob | None = None
        if knob_id:
            obj = self._repo.get("ip_knobs", knob_id)
            if not isinstance(obj, IPKnob) or obj.ip_id != ip_id:
                raise InvalidSelectionError(f"knob '{knob_id}'는 IP '{ip_id}' 소속이 아님")
            knob = obj

        capability: IPCapability | None = None
        if capability_id:
            obj = self._repo.get("ip_capabilities", capability_id)
            if not isinstance(obj, IPCapability) or obj.ip_id != ip_id:
                raise InvalidSelectionError(
                    f"capability '{capability_id}'는 IP '{ip_id}' 소속이 아님"
                )
            capability = obj

        if mode:
            supported: set[str] = set()
            for spec in self._list("ip_base_specs", IPBaseSpec):
                if spec.ip_id == ip_id:
                    supported.update(spec.supported_modes)
            if mode not in supported:
                raise InvalidSelectionError(f"모드 '{mode}'는 IP '{ip_id}'가 지원하지 않음")

        scenarios = {s.id: s for s in self._list("scenarios", Scenario)}
        requirements = [
            r
            for r in self._list("scenario_ip_requirements", ScenarioIPRequirement)
            if r.ip_id == ip_id and r.scenario_id in scenarios
        ]

        impacted = self._impacted_scenarios(ip, scenarios, requirements, knob, capability, mode)
        impacted_ids = [s.scenario_id for s in impacted]
        kpis = self._impacted_kpis(impacted, knob)
        chained = self._chained_ips(ip)
        similar = self._similar_cases(ip, impacted_ids)
        checklist = self._checklist(ip, impacted, chained, knob, requirements, impacted_ids)
        subject = self._subject(ip, knob, capability, mode)
        return ChangeImpactResult(
            subject=subject,
            impacted_scenarios=impacted,
            impacted_kpis=kpis,
            chained_ips=chained,
            checklist=checklist,
            similar_cases=similar,
            export_text=self._export_text(subject, impacted, kpis, chained, checklist, similar),
        )

    def _subject(
        self,
        ip: IPBlock,
        knob: IPKnob | None,
        capability: IPCapability | None,
        mode: str | None,
    ) -> ImpactSubject:
        parts = [ip.name]
        if knob:
            parts.append(f"knob {knob.name}")
        if capability:
            parts.append(f"capability {capability.name}")
        if mode:
            parts.append(f"모드 {mode}")
        return ImpactSubject(
            ip_id=ip.id,
            ip_name=ip.name,
            ip_category=ip.category,
            knob=(
                KnobEffect(
                    knob_id=knob.id,
                    name=knob.name,
                    category=knob.category,
                    control_domain=knob.control_domain,
                    description=knob.description,
                    power_direction=knob.power_direction,
                    latency_direction=knob.latency_direction,
                    bandwidth_direction=knob.bandwidth_direction,
                    risk_direction=knob.risk_direction,
                    affected_kpis=knob.affected_kpis,
                    related_scenarios=knob.related_scenarios,
                    confidence=str(knob.confidence),
                    source_ref=knob.source_ref,
                )
                if knob
                else None
            ),
            capability=(
                CapabilityInfo(
                    capability_id=capability.id,
                    name=capability.name,
                    category=capability.category,
                    support_status=capability.support_status,
                    condition=capability.condition,
                    confidence=str(capability.confidence),
                    source_ref=capability.source_ref,
                )
                if capability
                else None
            ),
            mode=mode,
            summary=" · ".join(parts),
        )

    def _impacted_scenarios(
        self,
        ip: IPBlock,
        scenarios: dict[str, Scenario],
        requirements: list[ScenarioIPRequirement],
        knob: IPKnob | None,
        capability: IPCapability | None,
        mode: str | None,
    ) -> list[ImpactedScenario]:
        reasons_by_scenario: dict[str, list[BasisItem]] = {}

        def add(scenario_id: str, item: BasisItem) -> None:
            reasons_by_scenario.setdefault(scenario_id, []).append(item)

        # 대상 한정 근거: 요구(모드/capability 필터), knob 관련 시나리오.
        for req in requirements:
            if mode and req.required_mode != mode:
                continue
            if capability and not _capability_matches_requirement(capability, req):
                continue
            add(
                req.scenario_id,
                BasisItem(
                    rule="ip_requirement",
                    rule_ko=REASON_LABELS["ip_requirement"],
                    ref_id=req.id,
                    ref_collection="scenario_ip_requirements",
                    description=(
                        f"요구 capability '{req.required_capability}' / 모드 "
                        f"'{req.required_mode}' ({req.requirement_level}) — {req.rationale}"
                    ),
                    source_refs=[req.source_ref],
                ),
            )
        if knob:
            for scenario_id in knob.related_scenarios:
                if scenario_id in scenarios:
                    add(
                        scenario_id,
                        BasisItem(
                            rule="knob_related",
                            rule_ko=REASON_LABELS["knob_related"],
                            ref_id=knob.id,
                            ref_collection="ip_knobs",
                            description=f"knob '{knob.name}'의 관련 시나리오로 명시됨",
                            source_refs=[knob.source_ref],
                        ),
                    )

        # 구체 선택(knob/capability/모드)이 링크를 만들었으면 그 시나리오로 한정,
        # 아니면 IP 수준(사용/의존 + 전체 요구)으로 확장한다.
        subject_specific = bool(reasons_by_scenario) and bool(knob or capability or mode)
        if not subject_specific:
            for req in requirements:
                add(
                    req.scenario_id,
                    BasisItem(
                        rule="ip_requirement",
                        rule_ko=REASON_LABELS["ip_requirement"],
                        ref_id=req.id,
                        ref_collection="scenario_ip_requirements",
                        description=(
                            f"요구 capability '{req.required_capability}' / 모드 "
                            f"'{req.required_mode}' ({req.requirement_level}) — {req.rationale}"
                        ),
                        source_refs=[req.source_ref],
                    ),
                )
            for scenario in scenarios.values():
                if ip.id in scenario.uses_ip_blocks or ip.id in scenario.depends_on_system_blocks:
                    add(
                        scenario.id,
                        BasisItem(
                            rule="uses_ip",
                            rule_ko=REASON_LABELS["uses_ip"],
                            ref_id=scenario.id,
                            ref_collection="scenarios",
                            description=f"시나리오가 '{ip.name}'을(를) 사용/의존",
                            source_refs=scenario.source_basis,
                        ),
                    )

        result: list[ImpactedScenario] = []
        for scenario_id, reasons in reasons_by_scenario.items():
            scenario = scenarios[scenario_id]
            deduped: list[BasisItem] = []
            seen: set[tuple[str, str]] = set()
            for item in reasons:
                key = (item.rule, item.ref_id)
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
            result.append(
                ImpactedScenario(
                    scenario_id=scenario_id,
                    scenario_name=scenario.name,
                    project_ids=scenario.project_relevance,
                    kpi_ids=scenario.primary_kpis,
                    reasons=deduped,
                )
            )
        return sorted(result, key=lambda s: (-len(s.reasons), s.scenario_name, s.scenario_id))

    def _impacted_kpis(
        self, impacted: list[ImpactedScenario], knob: IPKnob | None
    ) -> list[ImpactedKPI]:
        definitions = {k.id: k for k in self._list("kpi_definitions", KPIDefinition)}
        collected: dict[str, ImpactedKPI] = {}
        if knob:
            for kpi_id in knob.affected_kpis:
                definition = definitions.get(kpi_id)
                collected[kpi_id] = ImpactedKPI(
                    kpi_id=kpi_id,
                    unit=definition.unit if definition else None,
                    direction=definition.direction if definition else None,
                    via_knob=True,
                )
        for scenario in impacted:
            for kpi_id in scenario.kpi_ids:
                entry = collected.get(kpi_id)
                if entry is None:
                    definition = definitions.get(kpi_id)
                    entry = ImpactedKPI(
                        kpi_id=kpi_id,
                        unit=definition.unit if definition else None,
                        direction=definition.direction if definition else None,
                    )
                    collected[kpi_id] = entry
                if scenario.scenario_id not in entry.scenario_ids:
                    entry.scenario_ids.append(scenario.scenario_id)
        return sorted(
            collected.values(), key=lambda k: (not k.via_knob, -len(k.scenario_ids), k.kpi_id)
        )

    def _chained_ips(self, ip: IPBlock) -> list[ChainedIP]:
        blocks = {b.id: b for b in self._list("ip_blocks", IPBlock)}
        chained: list[ChainedIP] = []
        for rule in self._list("ip_dependency_rules", IPDependencyRule):
            if rule.ip_id == ip.id and rule.depends_on_ip_id in blocks:
                direction = "outgoing"
                target = blocks[rule.depends_on_ip_id]
            elif rule.depends_on_ip_id == ip.id and rule.ip_id in blocks:
                direction = "incoming"
                target = blocks[rule.ip_id]
            else:
                continue
            chained.append(
                ChainedIP(
                    rule_id=rule.id,
                    ip_id=target.id,
                    ip_name=target.name,
                    direction=direction,
                    direction_ko=DIRECTION_LABELS[direction],
                    relationship=rule.relationship,
                    condition=rule.condition,
                    rationale=rule.rationale,
                    confidence=str(rule.confidence),
                    source_ref=rule.source_ref,
                )
            )
        return sorted(chained, key=lambda c: (c.direction, c.ip_name, c.rule_id))

    def _similar_cases(self, ip: IPBlock, impacted_ids: list[str]) -> list[SimilarCase]:
        impacted_set = set(impacted_ids)
        cases: list[SimilarCase] = []
        for issue in self._list("issues", Issue):
            scope_ips = set(issue.affected_scope.ip_blocks) | set(issue.affected_scope.system_blocks)
            if ip.id not in scope_ips:
                continue
            shared = [s for s in issue.affected_scope.scenarios if s in impacted_set]
            why = f"같은 IP '{ip.name}' 영향 범위의 과거 이슈"
            if shared:
                why += f" — 영향 시나리오 {len(shared)}건 겹침"
            cases.append(
                SimilarCase(
                    kind="issue",
                    kind_ko="과거 이슈",
                    ref_id=issue.id,
                    title=issue.title,
                    status=issue.status,
                    why_similar=why,
                    scenario_ids=shared,
                    source_refs=issue.evidence_refs,
                )
            )
        alias_index = IPAliasIndex(self._repo)
        for event in self._list("development_events", DevelopmentEvent):
            if ip.id not in event_related_ips(event, alias_index):
                continue
            shared = [s for s in event.linked_scenario_ids if s in impacted_set]
            if not shared:
                continue
            cases.append(
                SimilarCase(
                    kind="event",
                    kind_ko="과거 이벤트",
                    ref_id=event.id,
                    title=event.title,
                    status=event.status,
                    why_similar=(
                        f"'{ip.name}' 관련 이벤트 — 영향 시나리오 {len(shared)}건 겹침"
                        f" (심각도 {event.severity})"
                    ),
                    scenario_ids=shared,
                    source_refs=event.source_basis,
                )
            )
        return sorted(cases, key=lambda c: (c.kind != "issue", -len(c.scenario_ids), c.ref_id))

    def _checklist(
        self,
        ip: IPBlock,
        impacted: list[ImpactedScenario],
        chained: list[ChainedIP],
        knob: IPKnob | None,
        requirements: list[ScenarioIPRequirement],
        impacted_ids: list[str],
    ) -> list[ChecklistItem]:
        roles = self._roles()
        impacted_set = set(impacted_ids)
        items: dict[str, ChecklistItem] = {}

        def basis_from(
            rule: str, rule_ko: str, ref_id: str, collection: str, description: str,
            source_refs: list[str],
        ) -> BasisItem:
            return BasisItem(
                rule=rule, rule_ko=rule_ko, ref_id=ref_id, ref_collection=collection,
                description=description, source_refs=source_refs,
            )

        def add(role_id: str, perspective: str, basis: list[BasisItem]) -> None:
            if not basis or role_id not in roles:
                return  # 근거 없는 체크리스트 항목 금지
            items[role_id] = ChecklistItem(
                role_id=role_id,
                role_name=roles[role_id].name,
                perspective=perspective,
                basis=basis,
            )

        # System Engineering — 시나리오-IP-KPI 링크 재검증 (책임: audit_scenario_ip_kpi_links)
        if impacted:
            kpi_ids = sorted({k for s in impacted for k in s.kpi_ids})[:5]
            add(
                "system_engineering",
                (
                    f"영향 시나리오 {len(impacted)}건의 시나리오–IP–KPI 연결과 "
                    f"KPI 요구({', '.join(kpi_ids)})의 근거 공백을 재검증"
                ),
                [
                    basis_from(
                        "impacted_scenario", "영향 시나리오", s.scenario_id, "scenarios",
                        s.scenario_name, [],
                    )
                    for s in impacted[:5]
                ],
            )

        # SoC Architecture — 연쇄 IP 의존 조건 검토 (책임: analyze_feature_tradeoff)
        if chained:
            add(
                "soc_architecture",
                (
                    f"연쇄 IP {len(chained)}건({', '.join(c.ip_name for c in chained[:4])})의 "
                    "의존 조건과 대역폭/QoS 마진에 대한 아키텍처 트레이드오프 검토"
                ),
                [
                    basis_from(
                        "dependency_rule", "IP 의존 규칙", c.rule_id, "ip_dependency_rules",
                        f"{c.ip_name}: {c.condition}", [c.source_ref],
                    )
                    for c in chained
                ],
            )

        # HW Development — 구현 영향, 아키텍처 결정은 소유하지 않음 (feedback_items 경로)
        hw_basis: list[BasisItem] = []
        if knob:
            hw_basis.append(
                basis_from(
                    "knob", "제어 knob", knob.id, "ip_knobs",
                    f"{knob.name} ({knob.control_domain}) — 리스크 방향 {knob.risk_direction}",
                    [knob.source_ref],
                )
            )
        hw_basis += [
            basis_from(
                "required_requirement", "필수 IP 요구", r.id, "scenario_ip_requirements",
                f"{r.required_capability}/{r.required_mode}", [r.source_ref],
            )
            for r in requirements
            if r.requirement_level == "required"
        ]
        if hw_basis:
            add(
                "hw_development",
                (
                    "구현 옵션과 면적·전력·타이밍 영향 검토 — 아키텍처 결정은 직접 소유하지 "
                    "않으며, 차기 SoC 개선 필요 발견 시 feedback_items로 System Engineering/"
                    "SoC Architecture에 전달"
                ),
                hw_basis,
            )

        # SW Development — 드라이버/HAL 제어 경로 (knob은 드라이버 제어 항목)
        if knob:
            add(
                "sw_development",
                (
                    f"knob '{knob.name}'({knob.control_domain}) 제어 경로의 드라이버/HAL 변경 "
                    "영향과 워크어라운드 검토 — 개선 필요는 feedback_items로 전달"
                ),
                [
                    basis_from(
                        "knob", "제어 knob", knob.id, "ip_knobs", knob.description,
                        [knob.source_ref],
                    )
                ],
            )

        # Product Planning — 영향 시나리오에 걸린 P0/P1 고객·요청 확인
        open_requests = [
            r
            for r in self._list("scenario_requests", ScenarioRequest)
            if r.status not in _CLOSED_REQUEST_STATUSES
            and r.priority in _TOP_PRIORITIES
            and (
                (r.scenario_id and r.scenario_id in impacted_set)
                or set(r.scenario_ids) & impacted_set
            )
        ]
        if open_requests:
            add(
                "product_planning",
                (
                    f"영향 시나리오에 걸린 {open_requests[0].priority} 등 우선 요청 "
                    f"{len(open_requests)}건의 고객 요구 충족 여부 확인"
                ),
                [
                    basis_from(
                        "priority_request", "우선 요청", r.id, "scenario_requests",
                        f"{r.priority} · {r.title} (상태 {r.status})", r.source_refs,
                    )
                    for r in sorted(open_requests, key=lambda r: (r.priority, r.id))[:5]
                ],
            )

        # PM — 일정 위험 신호가 있는 이벤트 추적
        schedule_events = [
            e
            for e in self._list("development_events", DevelopmentEvent)
            if e.schedule_signal in _RISKY_SCHEDULE_SIGNALS
            and set(e.linked_scenario_ids) & impacted_set
        ]
        if schedule_events:
            signals = sorted({e.schedule_signal for e in schedule_events if e.schedule_signal})
            add(
                "pm",
                (
                    f"일정 신호({', '.join(signals)})가 있는 이벤트 {len(schedule_events)}건 "
                    "기준으로 이번 변경의 일정 영향 추적"
                ),
                [
                    basis_from(
                        "schedule_event", "일정 위험 이벤트", e.id, "development_events",
                        f"{e.title} ({e.schedule_signal})", e.source_basis,
                    )
                    for e in sorted(schedule_events, key=lambda e: e.id)[:5]
                ],
            )

        # Management — 리스크 방향 증가 또는 우선 요청 존재 시 트레이드오프 요약 확인
        mgmt_basis: list[BasisItem] = []
        if knob and knob.risk_direction == "increase":
            mgmt_basis.append(
                basis_from(
                    "risk_direction", "리스크 방향", knob.id, "ip_knobs",
                    f"knob '{knob.name}' 리스크 방향 increase", [knob.source_ref],
                )
            )
        mgmt_basis += [
            basis_from(
                "priority_request", "우선 요청", r.id, "scenario_requests",
                f"{r.priority} · {r.title}", r.source_refs,
            )
            for r in open_requests
            if r.priority == "P0"
        ]
        if mgmt_basis:
            add(
                "management",
                "역할 산출물과 리스크/일정 요약 기준의 트레이드오프 검토 — 구현 세부 결정 아님",
                mgmt_basis,
            )

        return [items[r] for r in _ROLE_ORDER if r in items]

    def _export_text(
        self,
        subject: ImpactSubject,
        impacted: list[ImpactedScenario],
        kpis: list[ImpactedKPI],
        chained: list[ChainedIP],
        checklist: list[ChecklistItem],
        similar: list[SimilarCase],
    ) -> str:
        lines = [f"[변경 영향 분석] {subject.summary}"]
        lines.append(f"영향 시나리오 ({len(impacted)}):")
        lines += [
            f"  - {s.scenario_name} ({', '.join(r.rule_ko for r in s.reasons)})"
            for s in impacted
        ]
        lines.append(f"영향 KPI ({len(kpis)}): " + ", ".join(k.kpi_id for k in kpis))
        lines.append(f"연쇄 IP ({len(chained)}):")
        lines += [f"  - {c.ip_name} [{c.direction_ko}] {c.condition}" for c in chained]
        lines.append("검토 체크리스트:")
        for item in checklist:
            refs = ", ".join(b.ref_id for b in item.basis[:3])
            lines.append(f"  - [{item.role_name}] {item.perspective} (근거: {refs})")
        lines.append(f"과거 유사 사례 ({len(similar)}):")
        lines += [f"  - [{c.kind_ko}] {c.title} — {c.why_similar}" for c in similar]
        lines.append("※ 결정이 아닌 검토 안내입니다 · 수치 점수 없음")
        return "\n".join(lines)
