"""Ask SoC 러너 테스트 — 검색/검증 관문/결정론 fallback.

수용 기준: 프리셋 5종에 근거 인용 답변, validator 미통과 답변 미표시,
LLM 미가용 시 검색 결과만으로 동작.
"""

import json
from pathlib import Path

import pytest
from backend.agents.ask_runner import PRESET_QUESTIONS, AskRunner
from backend.agents.providers.base import ProviderError, ProviderResult
from backend.loaders.repository import InMemoryRepository

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_fixtures(FIXTURES)


@pytest.fixture(scope="module")
def deterministic_runner(repo) -> AskRunner:
    """LLM 미가용 상황 — provider 체인이 비어 있다."""
    return AskRunner(repo, providers=[])


class FakeProvider:
    name = "fake"
    is_external = False

    def __init__(self, payload: object, fail: bool = False):
        self._payload = payload
        self._fail = fail

    def generate(self, prompt: str, timeout_s: float) -> ProviderResult:
        if self._fail:
            raise ProviderError("가짜 실패")
        text = self._payload if isinstance(self._payload, str) else json.dumps(self._payload)
        return ProviderResult(text=text, provider=self.name, model_name="fake-1", duration_ms=1)


def test_presets_answerable_without_llm(deterministic_runner) -> None:
    """수용 기준 — 데모 질문 5종이 LLM 없이도 근거 인용 답변을 받는다."""
    assert len(PRESET_QUESTIONS) == 5
    for preset in PRESET_QUESTIONS:
        result = deterministic_runner.ask(preset["question"])
        assert result.provider == "deterministic"
        assert result.cards, preset["id"]
        assert result.citations, "근거 인용 없는 답변 금지"
        assert set(result.citations) <= {c.ref_id for c in result.cards}


def test_uhd60_question_ranks_specific_scenario_first(deterministic_runner) -> None:
    result = deterministic_runner.ask("UHD60 recording에서 현재 가장 위험한 IP는 무엇인가?")
    top = result.cards[0]
    assert top.collection == "scenarios"
    assert top.ref_id == "uhd60_recording_eis_on"
    assert top.status_ko and "위험 등급" in top.status_ko


def test_risk_intent_without_specific_match_uses_heatmap(deterministic_runner) -> None:
    result = deterministic_runner.ask("지금 multimedia scenario 중 risk가 가장 높은 것은 무엇인가?")
    top_scenarios = [c for c in result.cards if c.collection == "scenarios"][:3]
    assert top_scenarios, "위험 지도 상위 시나리오가 편입돼야 한다"
    assert all(c.status_ko and "높음" in c.status_ko for c in top_scenarios)


def test_no_match_returns_empty_citations(deterministic_runner) -> None:
    result = deterministic_runner.ask("존재하지않는키워드질의문자열")
    assert result.cards == []
    assert result.citations == []
    assert result.provider == "deterministic"


def test_valid_llm_answer_adopted(repo) -> None:
    question = "UHD60 recording에서 현재 가장 위험한 IP는 무엇인가?"
    cards = AskRunner(repo, providers=[])._search(question)
    payload = {
        "answer": "UHD60 EIS 시나리오에서 ISP/MFC/DPU 셀이 높음 등급으로 판정되어 있습니다.",
        "citations": [cards[0].ref_id],
        "confidence": "medium",
        "derivation": "위험 지도 셀 등급에서 도출",
    }
    runner = AskRunner(repo, providers=[FakeProvider(payload)])
    result = runner.ask(question)
    assert result.provider == "fake"
    assert result.citations == [cards[0].ref_id]
    assert result.validation_notes == []


def test_invalid_citation_rejected_falls_back(repo) -> None:
    """검증 관문 — 수집되지 않은 객체 인용은 거부되고 결정론으로 내려간다."""
    payload = {
        "answer": "이 답변은 수집 목록에 없는 객체를 인용합니다. 길이는 충분히 깁니다.",
        "citations": ["없는_객체_id"],
        "confidence": "high",
        "derivation": "지어냄",
    }
    runner = AskRunner(repo, providers=[FakeProvider(payload)])
    result = runner.ask("UHD60 recording 위험")
    assert result.provider == "deterministic"
    assert any("검증 거부" in note for note in result.validation_notes)


def test_high_confidence_needs_two_citations(repo) -> None:
    question = "UHD60 recording 위험"
    cards = AskRunner(repo, providers=[])._search(question)
    payload = {
        "answer": "인용이 하나뿐인데 high confidence를 주장하는 답변입니다.",
        "citations": [cards[0].ref_id],
        "confidence": "high",
        "derivation": "약한 근거",
    }
    runner = AskRunner(repo, providers=[FakeProvider(payload)])
    result = runner.ask(question)
    assert result.provider == "deterministic"
    assert any("high confidence 금지" in note for note in result.validation_notes)


def test_provider_error_falls_back_with_note(repo) -> None:
    runner = AskRunner(repo, providers=[FakeProvider(None, fail=True)])
    result = runner.ask("ISP power issue")
    assert result.provider == "deterministic"
    assert any("실행 실패" in note for note in result.validation_notes)


def test_deterministic_same_question_same_result(deterministic_runner) -> None:
    a = deterministic_runner.ask("ISP 관련 power issue는 과거 어떤 scenario에서 반복되었나?")
    b = deterministic_runner.ask("ISP 관련 power issue는 과거 어떤 scenario에서 반복되었나?")
    assert a.model_dump(exclude={"duration_ms"}) == b.model_dump(exclude={"duration_ms"})
