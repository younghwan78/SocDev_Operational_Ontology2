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
    cards, _ = AskRunner(repo, providers=[])._search(question)
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
    cards, _ = AskRunner(repo, providers=[])._search(question)
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


def test_korean_domain_terms_bridge_to_english(deterministic_runner) -> None:
    """A1 — 한국어 도메인 용어(전력/발열)가 영어 데이터에 닿는다."""
    result = deterministic_runner.ask("전력 문제가 반복된 IP는 무엇인가?")
    assert result.cards, "전력→power 브리지로 카드가 수집돼야 한다"
    # 범용 토큰(ip) 단독 매치였던 면적(area) 카드가 상위를 차지하지 않는다.
    top_ids = [c.ref_id for c in result.cards[:4]]
    assert "new_ip_area_cost" not in top_ids
    matched_all = {m for c in result.cards for m in c.matched_terms}
    assert "power" in matched_all
    assert result.unmatched_terms == []


def test_unmatched_terms_reported(deterministic_runner) -> None:
    result = deterministic_runner.ask("magicfoo 관련 전력 이슈?")
    assert "magicfoo" in result.unmatched_terms


def test_inline_marker_outside_cards_rejected(repo) -> None:
    """A2 — 본문 [id] 마커가 수집 목록 밖이면 검증 관문이 거부한다."""
    cards, _ = AskRunner(repo, providers=[])._search("UHD60 recording 위험")
    payload = {
        "answer": "이 시나리오는 위험합니다 [fabricated_object_id]. 길이는 충분히 확보되어 있습니다.",
        "citations": [cards[0].ref_id],
        "confidence": "medium",
        "derivation": "본문 마커 위조",
    }
    runner = AskRunner(repo, providers=[FakeProvider(payload)])
    result = runner.ask("UHD60 recording 위험")
    assert result.provider == "deterministic"
    assert any("본문 인용 마커" in note for note in result.validation_notes)


def test_inline_markers_merged_into_citations(repo) -> None:
    """A2 — 본문 마커가 citations 목록에 합류한다 (본문·목록 불일치 방지)."""
    cards, _ = AskRunner(repo, providers=[])._search("UHD60 recording 위험")
    first, second = cards[0].ref_id, cards[1].ref_id
    payload = {
        "answer": f"첫 근거에서 위험이 확인됩니다 [{first}]. 두 번째 근거도 이를 뒷받침합니다 [{second}].",
        "citations": [first],  # 목록에는 하나만 — 본문 마커가 보충
        "confidence": "medium",
        "derivation": "테스트",
    }
    runner = AskRunner(repo, providers=[FakeProvider(payload)])
    result = runner.ask("UHD60 recording 위험")
    assert result.provider == "fake"
    assert result.citations == [first, second]


def test_ask_log_and_faq_roundtrip(monkeypatch) -> None:
    """A5 — 질의가 로그에 남고 FAQ가 횟수 기준으로 집계된다 (LLM 없이)."""
    from backend.agents.runner import PROVIDERS_ENV
    from backend.api.app import create_app
    from fastapi.testclient import TestClient

    monkeypatch.setenv(PROVIDERS_ENV, "deterministic")  # 규칙: 테스트는 LLM 없이
    client = TestClient(create_app())
    for _ in range(2):
        response = client.post("/api/v1/ask", json={"question": "전력 문제가 반복된 IP는?"})
        assert response.status_code == 200
    client.post("/api/v1/ask", json={"question": "발열 이슈가 있었던 시나리오는?"})

    history = client.get("/api/v1/ask/history").json()
    assert len(history) == 3
    assert history[0]["question"] == "발열 이슈가 있었던 시나리오는?"
    assert history[0]["answer"], "답변 전문이 보존돼야 한다"

    faq = client.get("/api/v1/ask/faq").json()
    assert faq[0]["question"] == "전력 문제가 반복된 IP는?"
    assert faq[0]["count"] == 2
    assert faq[0]["answer_preview"]

    preview = client.get("/api/v1/ask/preview", params={"q": "전력 문제"}).json()
    assert preview["cards"], "프리뷰는 결정론 카드를 즉시 반환한다"
