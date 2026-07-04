"""Advisory Runner — 컨텍스트 조립 → provider 체인 → 검증 → 감사 기록.

체인: 설정된 LLM provider들을 순서대로 시도하고, 전부 실패하면
결정론 어드바이저가 최종 fallback으로 항상 응답한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import UTC, datetime

from backend.agents.deterministic import generate_deterministic_draft
from backend.agents.prompts import build_context, build_prompt
from backend.agents.providers.base import LLMProvider, ProviderError
from backend.agents.providers.claude_cli import ClaudeCLIProvider
from backend.agents.providers.openai_compat import OpenAICompatProvider
from backend.agents.run_store import RunStoreProtocol
from backend.agents.validators import AdvisoryDraft, DraftParseError, parse_draft, validate_draft
from backend.loaders.protocols import RepositoryProtocol
from backend.ontology import COLLECTIONS
from backend.ontology.relation import AgentRun
from backend.ontology.role import RoleAdvisory, RoleAgent
from backend.services.scenario_analysis import ScenarioAnalysis, ScenarioAnalysisService

DETERMINISTIC = "deterministic"

PROVIDERS_ENV = "SOC_ADVISORY_PROVIDERS"  # 예: "claude_cli,openai_compat"
ALLOW_EXTERNAL_ENV = "SOC_ALLOW_EXTERNAL_LLM"  # "false"면 외부(사외) LLM 건너뜀
TIMEOUT_ENV = "SOC_ADVISORY_TIMEOUT_S"


def build_provider_chain() -> list[LLMProvider]:
    """환경 설정에서 LLM provider 체인을 구성한다 (결정론 fallback은 runner 내장)."""
    names = [
        name.strip()
        for name in os.environ.get(PROVIDERS_ENV, "claude_cli,openai_compat").split(",")
        if name.strip() and name.strip() != DETERMINISTIC
    ]
    registry: dict[str, type] = {
        "claude_cli": ClaudeCLIProvider,
        "openai_compat": OpenAICompatProvider,
    }
    chain: list[LLMProvider] = []
    for name in names:
        provider_cls = registry.get(name)
        if provider_cls is not None:
            chain.append(provider_cls())
    return chain


class AdvisoryRunner:
    def __init__(
        self,
        repo: RepositoryProtocol,
        run_store: RunStoreProtocol,
        providers: list[LLMProvider] | None = None,
        allow_external_llm: bool | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self._repo = repo
        self._run_store = run_store
        self._providers = build_provider_chain() if providers is None else providers
        if allow_external_llm is None:
            allow_external_llm = os.environ.get(ALLOW_EXTERNAL_ENV, "true").lower() != "false"
        self._allow_external = allow_external_llm
        self._timeout_s = timeout_s or float(os.environ.get(TIMEOUT_ENV, "180"))
        self._analysis_service = ScenarioAnalysisService(repo)

    def _active_providers(self) -> list[LLMProvider]:
        if self._allow_external:
            return self._providers
        return [p for p in self._providers if not p.is_external]

    def _known_ids(self, analysis: ScenarioAnalysis) -> set[str]:
        """supporting_basis 해석에 쓸 ID 집합 — 저장 객체 + 컨텍스트 파생 ID."""
        ids = self._repo.ids(*COLLECTIONS.keys())
        ids.update(self._repo.propagation_ids())
        ids.update(gap.ref_id for gap in analysis.evidence_gaps)
        for gap in analysis.evidence_gaps:
            ids.update(gap.source_refs)
        for event in analysis.events:
            ids.update(need.evidence_need_id for need in event.required_evidence)
        return ids

    def run(self, scenario_id: str, role_ids: list[str] | None = None) -> AgentRun:
        started = time.monotonic()
        analysis = self._analysis_service.analyze(scenario_id)
        context = build_context(analysis)
        known_ids = self._known_ids(analysis)

        roles = [
            role
            for role in self._repo.list("roles")
            if isinstance(role, RoleAgent) and (role_ids is None or role.id in role_ids)
        ]

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        input_hash = hashlib.sha256(
            json.dumps(context, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        advisories: list[RoleAdvisory] = []
        notes: list[str] = []

        for role in roles:
            draft, provider_name, model_name = self._generate_for_role(
                role, context, analysis, known_ids, notes
            )
            advisories.append(
                RoleAdvisory(
                    run_id=run_id,
                    scenario_id=scenario_id,
                    role_id=role.id,
                    provider=provider_name,
                    model_name=model_name,
                    summary=draft.summary,
                    concerns=draft.concerns,
                    required_evidence=draft.required_evidence,
                    recommendation=draft.recommendation,
                    confidence=draft.confidence,
                    missing_information=draft.missing_information,
                    derivation_summary=draft.derivation_summary,
                )
            )

        run = AgentRun(
            id=run_id,
            scenario_id=scenario_id,
            status="completed",
            input_hash=input_hash,
            requested_roles=[role.id for role in roles],
            advisories=advisories,
            validation_notes=notes,
            duration_ms=int((time.monotonic() - started) * 1000),
            created_at=datetime.now(UTC).isoformat(),
        )
        self._run_store.save(run)
        return run

    def _generate_for_role(
        self,
        role: RoleAgent,
        context: dict,
        analysis: ScenarioAnalysis,
        known_ids: set[str],
        notes: list[str],
    ) -> tuple[AdvisoryDraft, str, str | None]:
        prompt = build_prompt(role, context)
        for provider in self._active_providers():
            try:
                result = provider.generate(prompt, self._timeout_s)
            except ProviderError as exc:
                notes.append(f"{role.id}/{provider.name}: 실행 실패 — {exc}")
                continue
            try:
                draft = parse_draft(result.text)
            except DraftParseError as exc:
                notes.append(f"{role.id}/{provider.name}: 파싱 실패 — {exc}")
                continue
            problems = validate_draft(draft, known_ids)
            if problems:
                notes.append(
                    f"{role.id}/{provider.name}: 검증 거부 — {'; '.join(problems[:3])}"
                )
                continue
            return draft, result.provider, result.model_name

        # 최종 fallback — 결정론 어드바이저는 항상 응답한다
        draft = generate_deterministic_draft(role, analysis)
        problems = validate_draft(draft, known_ids)
        if problems:
            notes.append(f"{role.id}/{DETERMINISTIC}: 검증 경고 — {'; '.join(problems[:3])}")
        return draft, DETERMINISTIC, None
