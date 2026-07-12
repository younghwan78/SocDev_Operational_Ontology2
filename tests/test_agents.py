"""Advisory 체인 테스트 — LLM 실호출 없이 provider 계약/체인/검증을 검증한다."""

import json
from pathlib import Path

import httpx
import pytest
from backend.agents.deterministic import generate_deterministic_draft
from backend.agents.providers.base import ProviderError, ProviderResult
from backend.agents.providers.openai_compat import OpenAICompatProvider
from backend.agents.run_store import InMemoryRunStore
from backend.agents.runner import AdvisoryRunner
from backend.agents.validators import DraftParseError, parse_draft, validate_draft
from backend.loaders.repository import InMemoryRepository
from backend.ontology.common import Confidence
from backend.ontology.role import RoleAgent
from backend.services.scenario_analysis import ScenarioAnalysisService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SCENARIO = "uhd60_recording_eis_on"


@pytest.fixture(scope="module")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


@pytest.fixture(scope="module")
def analysis(repo):
    return ScenarioAnalysisService(repo).analyze(SCENARIO)


class FailingProvider:
    """항상 실패하는 provider — fallback 경로 테스트용."""

    name = "failing"
    is_external = False

    def generate(self, prompt: str, timeout_s: float) -> ProviderResult:
        raise ProviderError("의도된 실패")


class CannedProvider:
    """준비된 텍스트를 돌려주는 provider — 검증 경로 테스트용."""

    name = "canned"
    is_external = True

    def __init__(self, text: str) -> None:
        self._text = text

    def generate(self, prompt: str, timeout_s: float) -> ProviderResult:
        return ProviderResult(text=self._text, provider=self.name, model_name="canned-1", duration_ms=1)


def valid_draft_json(basis_id: str) -> str:
    return json.dumps(
        {
            "summary": "요약",
            "concerns": [
                {
                    "description": "UHD60 EIS 전력 격차 근거가 이전 프로젝트 측정뿐이라 현세대 판단 근거가 부족하다",
                    "description_derivation": "evidence_gaps 항목에서 도출",
                    "supporting_basis": [basis_id],
                    "confidence": "medium",
                }
            ],
            "required_evidence": ["현세대 전력 측정"],
            "recommendation": "측정 확보 후 재검토",
            "confidence": "medium",
            "missing_information": [],
            "derivation_summary": "테스트 초안",
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------- validator


def test_deterministic_draft_passes_validation_for_all_roles(repo, analysis) -> None:
    known = repo.ids("scenarios", "development_events", "evidence_catalog", "scenario_requests")
    known.update(gap.ref_id for gap in analysis.evidence_gaps)
    for gap in analysis.evidence_gaps:
        known.update(gap.source_refs)
    for role in repo.list("roles"):
        assert isinstance(role, RoleAgent)
        draft = generate_deterministic_draft(role, analysis)
        assert validate_draft(draft, known) == [], role.id
        assert draft.confidence is not Confidence.HIGH, "결정론 조언은 high를 내지 않는다"


def test_validator_rejects_ungrounded_concern() -> None:
    draft = parse_draft(valid_draft_json("basis_x"))
    draft.concerns[0].supporting_basis = []
    problems = validate_draft(draft, {"basis_x"})
    assert any("supporting_basis" in p for p in problems)


def test_validator_rejects_unresolvable_basis() -> None:
    draft = parse_draft(valid_draft_json("없는_id"))
    problems = validate_draft(draft, {"다른_id"})
    assert any("미해석" in p for p in problems)


def test_validator_rejects_high_confidence_with_weak_evidence() -> None:
    draft = parse_draft(valid_draft_json("basis_x"))
    draft.concerns[0].confidence = Confidence.LOW
    draft.confidence = Confidence.HIGH
    problems = validate_draft(draft, {"basis_x"})
    assert any("high" in p for p in problems)


def test_validator_rejects_generic_statement() -> None:
    draft = parse_draft(valid_draft_json("basis_x"))
    draft.concerns[0].description = "추가 분석이 필요합니다 그러므로 검토하겠습니다"
    problems = validate_draft(draft, {"basis_x"})
    assert any("일반론" in p for p in problems)


# ------------------------------------------------------------------- parser


def test_parse_draft_handles_code_fence() -> None:
    text = f"```json\n{valid_draft_json('b1')}\n```"
    assert parse_draft(text).summary == "요약"


def test_parse_draft_rejects_non_json() -> None:
    with pytest.raises(DraftParseError):
        parse_draft("조언: 그냥 텍스트입니다")


# ------------------------------------------------------------------- chain


def test_chain_falls_back_to_deterministic(repo) -> None:
    runner = AdvisoryRunner(
        repo, InMemoryRunStore(), providers=[FailingProvider()], timeout_s=1
    )
    run = runner.run(SCENARIO, role_ids=["pm"])
    assert run.status == "completed"
    assert len(run.advisories) == 1
    assert run.advisories[0].provider == "deterministic"
    assert any("failing" in note for note in run.validation_notes)


def test_chain_accepts_valid_llm_output(repo, analysis) -> None:
    basis_id = analysis.evidence_gaps[0].ref_id
    runner = AdvisoryRunner(
        repo,
        InMemoryRunStore(),
        providers=[CannedProvider(valid_draft_json(basis_id))],
        timeout_s=1,
    )
    run = runner.run(SCENARIO, role_ids=["pm"])
    assert run.advisories[0].provider == "canned"
    assert run.advisories[0].model_name == "canned-1"


def test_chain_rejects_invalid_llm_output_then_falls_back(repo) -> None:
    bad = valid_draft_json("존재하지_않는_근거_id")
    runner = AdvisoryRunner(
        repo, InMemoryRunStore(), providers=[CannedProvider(bad)], timeout_s=1
    )
    run = runner.run(SCENARIO, role_ids=["pm"])
    assert run.advisories[0].provider == "deterministic"
    assert any("검증 거부" in note or "미해석" in note for note in run.validation_notes)


def test_external_llm_policy_switch(repo) -> None:
    """allow_external_llm=False면 외부 provider(claude_cli 등)를 건너뛴다."""
    external = CannedProvider(valid_draft_json("x"))  # is_external=True
    runner = AdvisoryRunner(
        repo, InMemoryRunStore(), providers=[external], allow_external_llm=False, timeout_s=1
    )
    run = runner.run(SCENARIO, role_ids=["pm"])
    assert run.advisories[0].provider == "deterministic"


def test_audit_record_saved(repo) -> None:
    store = InMemoryRunStore()
    runner = AdvisoryRunner(repo, store, providers=[], timeout_s=1)
    run = runner.run(SCENARIO, role_ids=["pm", "management"])
    stored = store.list_for_scenario(SCENARIO)
    assert [r.id for r in stored] == [run.id]
    assert stored[0].input_hash == run.input_hash
    assert stored[0].requested_roles == ["pm", "management"]
    assert stored[0].duration_ms >= 0


def test_advisories_are_korean(repo) -> None:
    """조언 텍스트에 한국어가 포함되어야 한다 (한국어 출력 원칙)."""
    runner = AdvisoryRunner(repo, InMemoryRunStore(), providers=[], timeout_s=1)
    run = runner.run(SCENARIO, role_ids=["system_engineering"])
    advisory = run.advisories[0]
    has_hangul = any("가" <= ch <= "힣" for ch in advisory.summary)
    assert has_hangul


# --------------------------------------------------------- openai_compat


def test_openai_compat_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "응답 텍스트"}}]},
        )

    provider = OpenAICompatProvider(
        base_url="http://onprem.test/v1",
        model="onprem-model",
        transport=httpx.MockTransport(handler),
    )
    result = provider.generate("프롬프트", timeout_s=5)
    assert result.text == "응답 텍스트"
    assert result.provider == "openai_compat"
    assert result.model_name == "onprem-model"


def test_openai_compat_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="내부 오류")

    provider = OpenAICompatProvider(
        base_url="http://onprem.test/v1", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderError):
        provider.generate("프롬프트", timeout_s=5)


def test_openai_compat_missing_base_url() -> None:
    provider = OpenAICompatProvider(base_url=None)
    provider._base_url = None  # env 무시
    with pytest.raises(ProviderError):
        provider.generate("프롬프트", timeout_s=5)


def test_feedback_items_role_contract() -> None:
    """B3 §2.2 — feedback은 HW/SW 발신, SE/Arch 수신, 근거 필수 (validator 강제)."""
    from backend.agents.validators import AdvisoryDraft, validate_draft

    base = {
        "summary": "요약",
        "concerns": [
            {
                "description": "UHD60 전력 근거가 이전 세대 실측뿐이라 마진 판단이 어렵다",
                "description_derivation": "evidence_catalog 항목에서 도출",
                "supporting_basis": ["known_ref"],
                "confidence": "medium",
            }
        ],
        "recommendation": "검토 권고",
        "confidence": "medium",
        "feedback_items": [
            {
                "target_role": "system_engineering",
                "description": "차기 SoC에서 ISP 전력 계측 포인트를 스펙에 포함해야 한다",
                "description_derivation": "전력 근거 공백에서 도출",
                "supporting_basis": ["known_ref"],
                "confidence": "medium",
            }
        ],
    }
    draft = AdvisoryDraft.model_validate(base)
    assert validate_draft(draft, {"known_ref"}, role_id="hw_development") == []
    problems = validate_draft(draft, {"known_ref"}, role_id="pm")
    assert any("HW/SW Development 역할만" in p for p in problems)
    bad_target = AdvisoryDraft.model_validate(
        {**base, "feedback_items": [{**base["feedback_items"][0], "target_role": "pm"}]}
    )
    problems = validate_draft(bad_target, {"known_ref"}, role_id="hw_development")
    assert any("수신 역할 위반" in p for p in problems)
    bad_basis = AdvisoryDraft.model_validate(
        {
            **base,
            "feedback_items": [
                {**base["feedback_items"][0], "supporting_basis": ["없는_id"]}
            ],
        }
    )
    problems = validate_draft(bad_basis, {"known_ref"}, role_id="sw_development")
    assert any("미해석" in p for p in problems)
