"""Ask SoC 질의 러너 — 검색(결정론) → 관련 객체 수집 → LLM 근거 인용 답변.

internal_docs/design/03_course_correction.md §4.4:
질의 → 온톨로지 키워드 검색 → 관련 객체 수집(결정론: 위험 등급/검증 상태 요약 포함)
→ LLM이 카드 ID를 인용하는 한국어 답변 생성(기존 provider 체인 재사용)
→ 검증 관문 통과분만 표시. **LLM 미가용 시 검색 결과 요약만으로 동작한다.**

인용은 수집된 카드 ID로 한정한다 — 검색되지 않은 객체를 근거로 쓸 수 없다.
"""

from __future__ import annotations

import json
import re
import time

from pydantic import BaseModel, ConfigDict, Field

from backend.agents.providers.base import LLMProvider, ProviderError
from backend.agents.runner import DETERMINISTIC, build_provider_chain
from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import DevelopmentEvent, Issue, Test
from backend.ontology.glossary import object_label
from backend.ontology.ip import IPBlock, IPKnob
from backend.ontology.scenario import Scenario, ScenarioGroup, ScenarioRequest
from backend.services.rca import RCAService
from backend.services.risk import RiskService

MAX_CARDS = 8
MIN_ANSWER_LENGTH = 20

# 원점 문서 §7.3 데모 질문 5종 (한국어화)
PRESET_QUESTIONS: list[dict[str, str]] = [
    {"id": "preset_risky_ip", "question": "UHD60 recording에서 현재 가장 위험한 IP는 무엇인가?"},
    {"id": "preset_isp_power_history", "question": "ISP 관련 power issue는 과거 어떤 scenario에서 반복되었나?"},
    {"id": "preset_8k30_impact", "question": "8K30 recording을 추가하면 어떤 IP와 KPI가 영향을 받는가?"},
    {"id": "preset_thermal_evidence", "question": "UHD60 thermal issue가 해결됐다고 판단할 evidence는 무엇인가?"},
    {"id": "preset_top_risk_scenario", "question": "지금 multimedia scenario 중 risk가 가장 높은 것은 무엇인가?"},
]

# 검색 대상 컬렉션 → (모델, 텍스트 필드들)
_SEARCH_FIELDS: dict[str, list[str]] = {
    "scenarios": ["name", "description", "domain"],
    "scenario_groups": ["name", "purpose"],
    "ip_blocks": ["name", "domain", "notes"],
    "ip_knobs": ["name", "description", "control_domain"],
    "issues": ["title", "symptom", "issue_type"],
    "tests": ["title", "summary", "test_type"],
    "development_events": ["title", "description"],
    "scenario_requests": ["title"],
    "evidence_catalog": ["title", "source_system"],
    "kpi_definitions": ["group"],
}

# 영상 해상도 통용 표기 확장 — synthetic ID가 아닌 도메인 일반 지식.
_TOKEN_SYNONYMS: dict[str, list[str]] = {
    "4k": ["uhd"],
    "4k60": ["uhd60", "uhd", "60"],
    "4k30": ["uhd30", "uhd", "30"],
    "2k": ["fhd"],
    "risk": ["위험"],
}


class AskCard(BaseModel):
    """질의 관련 객체 카드 — 답변 인용의 대상."""

    model_config = ConfigDict(extra="forbid")

    ref_id: str
    collection: str
    collection_ko: str
    title: str
    snippet: str
    status_ko: str | None = None  # 위험 등급/검증 상태 등 결정론 요약
    matched_terms: list[str] = Field(default_factory=list)


class AskResult(BaseModel):
    """질의 응답 파생 뷰 — 저장하지 않음 (감사 노트 포함)."""

    model_config = ConfigDict(extra="forbid")

    question: str
    provider: str
    model_name: str | None = None
    answer: str
    confidence: str
    derivation: str
    citations: list[str] = Field(default_factory=list)
    cards: list[AskCard]
    validation_notes: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    note_ko: str = "근거 인용 답변이며 결정이 아닙니다 · 인용은 수집된 객체로 한정"


def _tokens(text: str) -> set[str]:
    # 라틴/숫자 run과 한글 run을 분리 추출 — "recording에서" → {recording, 에서}
    tokens = {t for t in re.findall(r"[0-9a-z]+|[가-힣]+", text.lower()) if len(t) >= 2}
    expanded = set(tokens)
    for token in tokens:
        expanded.update(_TOKEN_SYNONYMS.get(token, []))
        # "8k30" → "8k", "k30" 형태 분해 (해상도·프레임 표기)
        match = re.fullmatch(r"(\d+k)(\d+)", token)
        if match:
            expanded.update({match.group(1), f"k{match.group(2)}", match.group(2)})
    return expanded


class _ParsedAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    answer: str
    citations: list[str] = Field(default_factory=list)
    confidence: str = "low"
    derivation: str = ""


class AskRunner:
    def __init__(
        self,
        repo: RepositoryProtocol,
        providers: list[LLMProvider] | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self._repo = repo
        self._providers = build_provider_chain() if providers is None else providers
        self._timeout_s = timeout_s
        self._risk = RiskService(repo)
        self._rca = RCAService(repo)

    # ---- 검색 (결정론) ----

    def _search(self, question: str) -> list[AskCard]:
        query_tokens = _tokens(question)
        scored: dict[str, tuple[int, AskCard]] = {}
        heatmap = self._risk.heatmap()
        risk_rows = {r.scenario_id: r for r in heatmap.rows}
        verification = {s.issue_id: s for s in self._rca.list_issues()}

        def put(key: str, weight: int, card: AskCard) -> None:
            existing = scored.get(key)
            if existing is None or existing[0] < weight:
                scored[key] = (weight, card)

        for collection, fields in _SEARCH_FIELDS.items():
            for obj in self._repo.list(collection):
                haystack_parts = [obj.id]
                for field in fields:
                    value = getattr(obj, field, None)
                    if isinstance(value, str):
                        haystack_parts.append(value)
                if isinstance(obj, IPBlock):
                    haystack_parts.extend(obj.aliases)
                object_tokens = _tokens(" ".join(haystack_parts))
                matched = sorted(query_tokens & object_tokens)
                if not matched:
                    continue
                title = getattr(obj, "title", None) or getattr(obj, "name", None) or obj.id
                snippet_source = (
                    getattr(obj, "symptom", None)
                    or getattr(obj, "description", None)
                    or getattr(obj, "summary", None)
                    or getattr(obj, "purpose", None)
                    or ""
                )
                status_ko = self._status_ko(obj, risk_rows, verification)
                # 제목 일치 가중 — 제목에 걸린 토큰은 2배로 센다 (수치 점수 아님, 정렬용 순위)
                title_tokens = _tokens(str(title))
                weight = len(matched) + len(query_tokens & title_tokens)
                put(
                    f"{collection}:{obj.id}",
                    weight,
                    AskCard(
                        ref_id=obj.id,
                        collection=collection,
                        collection_ko=object_label(type(obj).__name__) or collection,
                        title=str(title),
                        snippet=str(snippet_source)[:160],
                        status_ko=status_ko,
                        matched_terms=matched,
                    ),
                )

        # 위험/risk 의도 질의 — 구체 시나리오 매치가 없을 때만 위험 지도 상위를 편입한다.
        has_specific_scenario = any(
            key.startswith("scenarios:") and weight >= 3
            for key, (weight, _) in scored.items()
        )
        if query_tokens & {"risk", "위험", "위험한", "위험도"} and not has_specific_scenario:
            for boost, row in enumerate(heatmap.rows[:3]):
                scenario = self._repo.get("scenarios", row.scenario_id)
                if not isinstance(scenario, Scenario):
                    continue
                put(
                    f"scenarios:{row.scenario_id}",
                    10 - boost,
                    AskCard(
                        ref_id=row.scenario_id,
                        collection="scenarios",
                        collection_ko=object_label("Scenario") or "scenarios",
                        title=row.scenario_name,
                        snippet=scenario.description[:160],
                        status_ko=self._status_ko(scenario, risk_rows, verification),
                        matched_terms=["risk"],
                    ),
                )

        ordered = sorted(scored.items(), key=lambda entry: (-entry[1][0], entry[0]))
        return [card for _, (_, card) in ordered[:MAX_CARDS]]

    def _status_ko(self, obj: object, risk_rows: dict, verification: dict) -> str | None:
        """카드에 붙는 결정론 상태 요약 — 위험 등급/검증 상태/일정 신호."""
        if isinstance(obj, Scenario):
            row = risk_rows.get(obj.id)
            if row:
                worst = [c for c in row.cells if c.grade == row.overall_grade]
                ips = ", ".join(c.ip_id for c in worst[:3])
                return f"위험 등급 {row.overall_grade_ko}" + (f" (셀: {ips})" if ips else "")
        if isinstance(obj, Issue):
            summary = verification.get(obj.id)
            if summary:
                alert = " · 종결됐지만 미검증" if summary.closed_without_verification else ""
                return f"상태 {obj.status} · {summary.verification_ko}{alert}"
        if isinstance(obj, Test):
            return f"결과 {obj.result}"
        if isinstance(obj, DevelopmentEvent) and obj.schedule_signal:
            return f"일정 신호 {obj.schedule_signal}"
        if isinstance(obj, ScenarioRequest):
            return f"{obj.priority} · 상태 {obj.status}"
        if isinstance(obj, (IPKnob, ScenarioGroup)):
            return None
        return None

    # ---- LLM 답변 ----

    def _prompt(self, question: str, cards: list[AskCard]) -> str:
        card_payload = [
            {
                "id": card.ref_id,
                "type": card.collection,
                "title": card.title,
                "snippet": card.snippet,
                "status": card.status_ko,
            }
            for card in cards
        ]
        return (
            "당신은 Multimedia SoC 개발 운영 온톨로지의 질의 응답기다.\n"
            "아래 '수집된 객체' 목록만 근거로 사용해 질문에 한국어로 답하라.\n"
            "규칙: (1) citations에는 목록의 id만 넣는다 (2) 목록에 없는 사실을 지어내지 않는다 "
            "(3) 근거가 부족하면 confidence를 low/medium으로 낮추고 부족하다고 말한다 "
            "(4) 결정을 내리지 말고 검토 관점을 제시한다.\n"
            f"질문: {question}\n"
            f"수집된 객체: {json.dumps(card_payload, ensure_ascii=False)}\n"
            '출력(JSON만): {"answer": "한국어 답변", "citations": ["id", ...], '
            '"confidence": "low|medium|high", "derivation": "도출 과정 한 문장"}'
        )

    def _parse(self, text: str) -> _ParsedAnswer:
        stripped = text.strip()
        fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
        candidate = fence.group(1) if fence else stripped
        if not candidate.startswith("{"):
            start, end = candidate.find("{"), candidate.rfind("}")
            if start == -1 or end <= start:
                raise ValueError("응답에서 JSON 객체를 찾지 못함")
            candidate = candidate[start : end + 1]
        return _ParsedAnswer.model_validate(json.loads(candidate))

    def _validate(self, parsed: _ParsedAnswer, card_ids: set[str]) -> list[str]:
        problems: list[str] = []
        if len(parsed.answer.strip()) < MIN_ANSWER_LENGTH:
            problems.append("답변이 너무 짧음")
        if not parsed.citations:
            problems.append("인용(citations) 비어 있음 — 근거 없는 답변 금지")
        unresolved = [c for c in parsed.citations if c not in card_ids]
        if unresolved:
            problems.append(f"수집된 객체 밖의 인용: {unresolved[:3]}")
        if parsed.confidence not in ("low", "medium", "high"):
            problems.append(f"confidence 값 위반: {parsed.confidence}")
        if parsed.confidence == "high" and len([c for c in parsed.citations if c in card_ids]) < 2:
            problems.append("인용 2건 미만의 high confidence 금지")
        return problems

    def _deterministic_answer(self, cards: list[AskCard]) -> _ParsedAnswer:
        """LLM 미가용/거부 시 — 검색 결과만으로 구성하는 요약 답변."""
        if not cards:
            return _ParsedAnswer(
                answer="질문과 연결되는 온톨로지 객체를 찾지 못했습니다. 키워드를 바꿔 보세요.",
                citations=[],
                confidence="low",
                derivation="키워드 검색 결과 없음",
            )
        lines = ["질문과 관련해 수집된 객체 기준의 요약입니다:"]
        for card in cards[:5]:
            status = f" — {card.status_ko}" if card.status_ko else ""
            lines.append(f"· [{card.collection_ko}] {card.title}{status}")
        lines.append("상세 근거는 아래 카드에서 확인하세요.")
        return _ParsedAnswer(
            answer="\n".join(lines),
            citations=[card.ref_id for card in cards[:5]],
            confidence="low",
            derivation="키워드 검색과 결정론 상태 요약으로 구성 (LLM 미개입)",
        )

    # ---- 실행 ----

    def ask(self, question: str) -> AskResult:
        started = time.monotonic()
        cards = self._search(question)
        card_ids = {card.ref_id for card in cards}
        notes: list[str] = []
        prompt = self._prompt(question, cards)

        parsed: _ParsedAnswer | None = None
        provider_name = DETERMINISTIC
        model_name: str | None = None
        if cards:  # 카드가 없으면 인용할 것이 없으므로 LLM을 부르지 않는다
            for provider in self._providers:
                try:
                    result = provider.generate(prompt, self._timeout_s)
                except ProviderError as exc:
                    notes.append(f"{provider.name}: 실행 실패 — {exc}")
                    continue
                try:
                    candidate = self._parse(result.text)
                except (ValueError, json.JSONDecodeError) as exc:
                    notes.append(f"{provider.name}: 파싱 실패 — {exc}")
                    continue
                problems = self._validate(candidate, card_ids)
                if problems:
                    notes.append(f"{provider.name}: 검증 거부 — {'; '.join(problems[:3])}")
                    continue
                parsed = candidate
                provider_name = result.provider
                model_name = result.model_name
                break

        if parsed is None:
            parsed = self._deterministic_answer(cards)

        return AskResult(
            question=question,
            provider=provider_name,
            model_name=model_name,
            answer=parsed.answer,
            confidence=parsed.confidence,
            derivation=parsed.derivation,
            citations=parsed.citations,
            cards=cards,
            validation_notes=notes,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
