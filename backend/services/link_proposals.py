"""링크 제안 — 미연결 이슈의 시나리오/IP 링크 후보를 결정론으로 제안 (설계 24).

link-recovery(설계 22 후속 ⑥)의 사외 선행분. 파생 뷰다 — 저장·자동 반영
없음: 링크는 항상 원천(JIRA 필드/반입 CSV)에서 고쳐져 ingest로 재진입한다.
모든 제안은 basis 문장을 동반한다 (어떤 토큰이 어디서 일치했는지).
LLM/임베딩 제안(Stage 18)은 같은 계약에 추가 룰로 플러그인한다.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import Issue
from backend.ontology.glossary import field_label
from backend.ontology.ip import IPBlock
from backend.ontology.scenario import Scenario
from backend.resolve.entity_resolution import IPAliasIndex

RULE_IP_ALIAS = "ip_alias_token"
RULE_SCENARIO_TOKEN = "scenario_token"
RULE_SCENARIO_USES_IP = "scenario_uses_ip"

RULE_LABELS = {
    RULE_IP_ALIAS: "IP 별칭 토큰",
    RULE_SCENARIO_TOKEN: "시나리오 토큰",
    RULE_SCENARIO_USES_IP: "시나리오 사용 IP",
}

FIELD_SCENARIOS = "affected_scope.scenarios"
FIELD_IP_BLOCKS = "affected_scope.ip_blocks"

# R2 변별력 필터 — 짧은/범용 토큰은 제안 근거가 되지 못한다.
_MIN_TOKEN_LEN = 3
_STOPWORDS = {"the", "and", "for", "with", "mode", "on", "off", "test", "high", "low"}
# 한 토큰이 이보다 많은 시나리오에 걸리면 비변별로 제외한다.
_MAX_SCENARIOS_PER_TOKEN = 3

def text_tokens(*values: str) -> set[str]:
    """자유 텍스트(제목/증상/이름) 단어 토큰 — 공백·구두점·`_` 분해, 소문자.

    normalize_tokens(entity_resolution)는 식별자 전용(공백 미분해)이라
    자유 텍스트에는 이 토크나이저를 쓴다. 매칭 자체는 IPAliasIndex.resolve_all
    (내부 정규화)과 시나리오 역인덱스가 수행한다.
    """
    tokens: set[str] = set()
    for value in values:
        for word in re.split(r"[^0-9a-zA-Z가-힣]+", value.lower()):
            if word:
                tokens.add(word)
    return tokens


APPLY_NOTE_KO = (
    "제안은 결정론 토큰 일치 후보다 — 자동 반영되지 않는다. 반영은 원천에서: "
    "JIRA 유래 이슈는 JIRA 필드 기입 후 재동기화, CSV 반입 이슈는 원본 CSV의 "
    "영향 시나리오/영향 IP 열 보강 후 재반입(upsert)."
)


class LinkProposal(BaseModel):
    """제안 한 건 — 룰 이름과 basis 문장이 확신도의 전부다 (수치 없음)."""

    model_config = ConfigDict(extra="forbid")

    field: str  # affected_scope.scenarios | affected_scope.ip_blocks
    field_ko: str
    target_id: str
    rule: str
    rule_ko: str
    basis_note_ko: str


class IssueLinkProposals(BaseModel):
    """이슈 하나의 제안 묶음."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    issue_title: str
    project_id: str
    proposals: list[LinkProposal]


class LinkProposalReport(BaseModel):
    """링크 제안 파생 뷰 — 제안 있는 이슈만."""

    model_config = ConfigDict(extra="forbid")

    issues: list[IssueLinkProposals] = Field(default_factory=list)
    apply_note_ko: str = APPLY_NOTE_KO


def _field_ko(path: str) -> str:
    leaf = path.split(".")[-1]
    label = field_label("AffectedScope", leaf)
    return label or path


class _ScenarioTokenIndex:
    """시나리오 id+name 토큰 → 시나리오 역인덱스 (변별 토큰만)."""

    def __init__(self, scenarios: list[Scenario]) -> None:
        by_token: dict[str, list[Scenario]] = {}
        for scenario in scenarios:
            for token in text_tokens(scenario.id, scenario.name):
                if len(token) < _MIN_TOKEN_LEN or token in _STOPWORDS:
                    continue
                entries = by_token.setdefault(token, [])
                if scenario not in entries:
                    entries.append(scenario)
        # 너무 많은 시나리오에 걸리는 토큰은 비변별 — 제안 근거에서 제외.
        self._by_token = {
            token: entries
            for token, entries in by_token.items()
            if len(entries) <= _MAX_SCENARIOS_PER_TOKEN
        }

    def match(self, token: str) -> list[Scenario]:
        return self._by_token.get(token, [])


class LinkProposalService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def report(self, project_id: str | None = None) -> LinkProposalReport:
        scenarios = [
            s for s in self._repo.list("scenarios") if isinstance(s, Scenario)
        ]
        scenario_by_id = {s.id: s for s in scenarios}
        scenario_index = _ScenarioTokenIndex(scenarios)
        ip_index = IPAliasIndex(self._repo)
        known_ips = {
            b.id for b in self._repo.list("ip_blocks") if isinstance(b, IPBlock)
        } or None  # ip_blocks가 비면 R3 대상 검증을 생략한다

        issues = [
            i
            for i in self._repo.list("issues")
            if isinstance(i, Issue)
            and (project_id is None or i.project_id == project_id)
        ]
        results: list[IssueLinkProposals] = []
        for issue in sorted(issues, key=lambda i: i.id):
            proposals = self._propose(
                issue, scenario_index, scenario_by_id, ip_index, known_ips
            )
            if proposals:
                results.append(
                    IssueLinkProposals(
                        issue_id=issue.id,
                        issue_title=issue.title,
                        project_id=issue.project_id,
                        proposals=proposals,
                    )
                )
        return LinkProposalReport(issues=results)

    def _propose(
        self,
        issue: Issue,
        scenario_index: _ScenarioTokenIndex,
        scenario_by_id: dict[str, Scenario],
        ip_index: IPAliasIndex,
        known_ips: set[str] | None,
    ) -> list[LinkProposal]:
        tokens = sorted(text_tokens(issue.title, issue.symptom))
        proposals: list[LinkProposal] = []

        # R2 — 시나리오 토큰 (시나리오 링크가 비어 있을 때만).
        if not issue.affected_scope.scenarios:
            seen: set[str] = set()
            for token in tokens:
                for scenario in scenario_index.match(token):
                    if scenario.id in seen:
                        continue
                    if (
                        scenario.project_relevance
                        and issue.project_id not in scenario.project_relevance
                    ):
                        continue
                    seen.add(scenario.id)
                    proposals.append(
                        LinkProposal(
                            field=FIELD_SCENARIOS,
                            field_ko=_field_ko(FIELD_SCENARIOS),
                            target_id=scenario.id,
                            rule=RULE_SCENARIO_TOKEN,
                            rule_ko=RULE_LABELS[RULE_SCENARIO_TOKEN],
                            basis_note_ko=(
                                f"제목/증상 토큰 '{token}' ↔ 시나리오 '{scenario.name}'"
                            ),
                        )
                    )

        # R1 — IP 별칭 토큰 + R3 — 기존 연결 시나리오의 사용 IP (IP가 빌 때만).
        if not issue.affected_scope.ip_blocks:
            seen_ips: set[str] = set()
            for token in tokens:
                for ip_id in sorted(ip_index.resolve_all(token)):
                    if ip_id in seen_ips:
                        continue
                    seen_ips.add(ip_id)
                    proposals.append(
                        LinkProposal(
                            field=FIELD_IP_BLOCKS,
                            field_ko=_field_ko(FIELD_IP_BLOCKS),
                            target_id=ip_id,
                            rule=RULE_IP_ALIAS,
                            rule_ko=RULE_LABELS[RULE_IP_ALIAS],
                            basis_note_ko=f"제목/증상 토큰 '{token}' ↔ IP 별칭/이름",
                        )
                    )
            for scenario_id in issue.affected_scope.scenarios:
                linked_scenario = scenario_by_id.get(scenario_id)
                if linked_scenario is None:
                    continue
                for ip_id in linked_scenario.uses_ip_blocks:
                    if ip_id in seen_ips:
                        continue
                    if known_ips is not None and ip_id not in known_ips:
                        continue
                    seen_ips.add(ip_id)
                    proposals.append(
                        LinkProposal(
                            field=FIELD_IP_BLOCKS,
                            field_ko=_field_ko(FIELD_IP_BLOCKS),
                            target_id=ip_id,
                            rule=RULE_SCENARIO_USES_IP,
                            rule_ko=RULE_LABELS[RULE_SCENARIO_USES_IP],
                            basis_note_ko=(
                                f"연결된 시나리오 '{linked_scenario.name}'의 사용 IP"
                            ),
                        )
                    )

        proposals.sort(key=lambda p: (p.field, p.target_id, p.rule))
        return proposals
