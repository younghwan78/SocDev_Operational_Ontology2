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
from backend.agents.providers.embedding import EmbeddingProvider, build_embedding_provider
from backend.agents.runner import DETERMINISTIC, apply_external_policy, build_provider_chain
from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import DevelopmentEvent, Issue, Test
from backend.ontology.glossary import object_label, value_label
from backend.ontology.ip import IPBlock
from backend.ontology.scenario import Scenario, ScenarioRequest
from backend.services.rca import RCAService
from backend.services.risk import RiskService

MAX_CARDS = 8
MAX_SEMANTIC_CARDS = 3  # D3: 벡터 후보는 카드 상한 안에서 최대 3장
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

# A1 한↔영 도메인 용어 브리지 — fixture/사내 데이터의 영어 텍스트와 한국어 질문을
# 잇는 큐레이션 사전 (도메인 일반 지식, synthetic ID 아님). 그룹 내 전 방향 확장.
_DOMAIN_TERM_GROUPS: list[tuple[str, ...]] = [
    ("전력", "power"),
    ("발열", "열", "thermal", "temperature"),
    ("대역폭", "bandwidth"),
    ("지연", "latency"),
    ("화질", "quality"),
    ("이슈", "문제", "issue"),
    ("검증", "verification"),
    ("테스트", "test"),
    ("녹화", "촬영", "recording"),
    ("재생", "playback"),
    ("미리보기", "preview"),
    ("일정", "schedule"),
    ("근거", "증거", "evidence"),
    ("요청", "request"),
    ("결정", "decision"),
    ("카메라", "camera"),
    ("디스플레이", "display"),
    ("오디오", "audio"),
    ("코덱", "codec"),
    ("안정성", "stability"),
    ("면적", "area"),
    ("클럭", "clock"),
    ("주파수", "frequency"),
    ("메모리", "memory"),
]
_DOMAIN_SYNONYMS: dict[str, set[str]] = {}
for _group in _DOMAIN_TERM_GROUPS:
    for _term in _group:
        _DOMAIN_SYNONYMS.setdefault(_term, set()).update(t for t in _group if t != _term)

# 범용 토큰 — 거의 모든 객체에 등장해 변별력이 없다. 가중 하향 + 단독 매치 배제.
_GENERIC_TOKENS = {
    "ip", "soc", "kpi", "블록", "무엇", "관련",
    "scenario", "시나리오", "multimedia", "멀티미디어",
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
    # 상태의 시각 성격(danger/warn/ok/info) — 프론트가 한국어 문자열을 파싱하지 않게 한다.
    status_kind: str | None = None
    matched_terms: list[str] = Field(default_factory=list)


class AskPreview(BaseModel):
    """A3 즉시 프리뷰 — 결정론 검색 결과만 (LLM 대기 없이 카드를 먼저 보여준다)."""

    model_config = ConfigDict(extra="forbid")

    question: str
    cards: list[AskCard]
    unmatched_terms: list[str] = Field(default_factory=list)


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
    # A1: 검색이 놓친 의미 토큰 — 사용자가 질문을 고칠 수 있는 힌트.
    unmatched_terms: list[str] = Field(default_factory=list)
    # B4: 질의 로그 캐시 응답 여부 — 같은 질문·같은 카드 지문이면 LLM 재호출 없이 재사용.
    cached: bool = False
    validation_notes: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    note_ko: str = "근거 인용 답변이며 결정이 아닙니다 · 인용은 수집된 객체로 한정"


def _tokens(text: str) -> set[str]:
    # 라틴/숫자 run과 한글 run을 분리 추출 — "recording에서" → {recording, 에서}
    tokens = {t for t in re.findall(r"[0-9a-z]+|[가-힣]+", text.lower()) if len(t) >= 2}
    expanded = set(tokens)
    for token in tokens:
        expanded.update(_TOKEN_SYNONYMS.get(token, []))
        expanded.update(_DOMAIN_SYNONYMS.get(token, set()))
        # "8k30" → "8k", "k30" 형태 분해 (해상도·프레임 표기)
        match = re.fullmatch(r"(\d+k)(\d+)", token)
        if match:
            expanded.update({match.group(1), f"k{match.group(2)}", match.group(2)})
    return expanded


def _meaningful_query_tokens(question: str) -> set[str]:
    """미매치 보고 대상 — 라틴/숫자 토큰과 도메인 사전에 있는 한국어 토큰만.
    (조사·일반 한국어 어절을 노이즈로 보고하지 않기 위한 제한.)"""
    raw = {t for t in re.findall(r"[0-9a-z]+|[가-힣]+", question.lower()) if len(t) >= 2}
    return {
        t
        for t in raw
        if (re.fullmatch(r"[0-9a-z]+", t) or t in _DOMAIN_SYNONYMS) and t not in _GENERIC_TOKENS
    }


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
        embedder: EmbeddingProvider | None = None,
    ) -> None:
        self._repo = repo
        # allow_external_llm 정책은 Ask 경로에도 동일 적용 (B1 — Advisory와 같은 관문).
        # 명시 providers(테스트)는 이미 정책 판단을 거친 것으로 본다.
        self._providers = (
            apply_external_policy(build_provider_chain()) if providers is None else providers
        )
        # D3 하이브리드: 임베딩 provider는 env 기반(기본 비활성) — 키워드 검색은 불변.
        self._embedder = embedder if embedder is not None else build_embedding_provider()
        self._timeout_s = timeout_s
        self._risk = RiskService(repo)
        self._rca = RCAService(repo)

    # ---- 검색 (결정론) ----

    def _search(self, question: str) -> tuple[list[AskCard], list[str]]:
        """(카드, 미매치 토큰) — 미매치는 질문 개선 힌트로 화면에 노출된다."""
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
                status_ko, status_kind = self._status(obj, risk_rows, verification)
                # 가중(정렬용 순위, 수치 점수 아님): 변별력 있는 토큰 2, 범용 토큰 1,
                # 제목 일치는 변별 토큰만 2배 추가 — "ip" 같은 범용어 단독 승리를 막는다.
                title_tokens = _tokens(str(title))
                specific = [m for m in matched if m not in _GENERIC_TOKENS]
                weight = 2 * len(specific) + (len(matched) - len(specific))
                weight += 2 * len(
                    {m for m in (query_tokens & title_tokens) if m not in _GENERIC_TOKENS}
                )
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
                        status_kind=status_kind,
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
                        status_ko=(status := self._status(scenario, risk_rows, verification))[0],
                        status_kind=status[1],
                        matched_terms=["risk"],
                    ),
                )

        # 변별 토큰 매치 카드가 있으면 범용 토큰 단독 매치 카드는 제외한다.
        entries = list(scored.items())
        has_specific = any(
            any(m not in _GENERIC_TOKENS for m in card.matched_terms)
            for _, (_, card) in entries
        )
        if has_specific:
            entries = [
                (key, value)
                for key, value in entries
                if any(m not in _GENERIC_TOKENS for m in value[1].matched_terms)
            ]
        ordered = sorted(entries, key=lambda entry: (-entry[1][0], entry[0]))
        cards = [card for _, (_, card) in ordered[:MAX_CARDS]]
        cards = self._merge_semantic_candidates(question, cards)

        # 미매치 토큰 — 확장(동의어/브리지)까지 고려해 진짜 못 찾은 것만 보고한다.
        matched_union = {term for card in cards for term in card.matched_terms}
        unmatched = sorted(
            token
            for token in _meaningful_query_tokens(question)
            if not (
                token in matched_union
                or (
                    _DOMAIN_SYNONYMS.get(token, set())
                    | set(_TOKEN_SYNONYMS.get(token, []))
                )
                & matched_union
            )
        )
        return cards, unmatched

    def _merge_semantic_candidates(self, question: str, cards: list[AskCard]) -> list[AskCard]:
        """D3 하이브리드 — 벡터 후보 청크를 키워드 카드와 별도로 최대 3장 합류.

        청크는 후보 지위(증거 아님)를 상태 문구로 명시한다. 임베딩 미구성/실패는
        조용히 건너뛴다 — 키워드 검색 결과는 불변이며, 인용 관문 규칙도 그대로다.
        """
        if self._embedder is None:
            return cards
        try:
            from backend.services.semantic_index import search_chunks

            matches = search_chunks(self._repo, self._embedder, question, MAX_SEMANTIC_CARDS)
        except Exception:  # noqa: BLE001 — 후보 채널 실패가 질의를 막으면 안 된다
            return cards
        existing_ids = {card.ref_id for card in cards}
        for chunk, similarity in matches:
            if chunk.id in existing_ids or len(cards) >= MAX_CARDS + MAX_SEMANTIC_CARDS:
                continue
            preview = chunk.chunk_text.split("\n", 1)[0]
            cards.append(
                AskCard(
                    ref_id=chunk.id,
                    collection="semantic_chunks",
                    collection_ko=object_label("SemanticChunk") or "semantic_chunks",
                    title=preview[:60] or chunk.source_id,
                    snippet=chunk.chunk_text.replace("\n", " ")[:160],
                    status_ko=f"문서 후보 · 증거 아님 (유사도 {similarity:.2f})",
                    status_kind="info",
                    matched_terms=["semantic"],
                )
            )
        return cards

    def _status(
        self, obj: object, risk_rows: dict, verification: dict
    ) -> tuple[str | None, str | None]:
        """카드의 결정론 상태 요약 + 시각 성격 — 서술은 라벨, 코드는 쓰지 않는다 (B2)."""
        if isinstance(obj, Scenario):
            row = risk_rows.get(obj.id)
            if row:
                worst = [c for c in row.cells if c.grade == row.overall_grade]
                ips = ", ".join(c.ip_id for c in worst[:3])
                kind = {"high": "danger", "medium": "warn"}.get(row.overall_grade, "ok")
                return (
                    f"위험 등급 {row.overall_grade_ko}" + (f" (셀: {ips})" if ips else ""),
                    kind,
                )
        if isinstance(obj, Issue):
            summary = verification.get(obj.id)
            if summary:
                alert = " · 종결됐지만 미검증" if summary.closed_without_verification else ""
                status_label = value_label("issue_status", obj.status) or obj.status
                kind = (
                    "danger"
                    if summary.closed_without_verification
                    else ("ok" if summary.verification == "verified" else "warn")
                )
                return f"상태 {status_label} · {summary.verification_ko}{alert}", kind
        if isinstance(obj, Test):
            result_label = value_label("test_result", obj.result) or obj.result
            kind = {"failed": "danger", "passed": "ok"}.get(obj.result, "info")
            return f"결과 {result_label}", kind
        if isinstance(obj, DevelopmentEvent) and obj.schedule_signal:
            signal_label = (
                value_label("schedule_signal", obj.schedule_signal) or obj.schedule_signal
            )
            kind = (
                "warn"
                if obj.schedule_signal in ("at_risk", "delayed", "window_closing")
                else "info"
            )
            return f"일정 신호 {signal_label}", kind
        if isinstance(obj, ScenarioRequest):
            status_label = value_label("request_status", obj.status) or obj.status
            return f"{obj.priority} · 상태 {status_label}", (
                "warn" if obj.priority == "P0" else "info"
            )
        return None, None

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
            "(4) 결정을 내리지 말고 검토 관점을 제시한다 "
            "(5) answer의 각 주장 문장 끝에 근거 객체 id를 대괄호로 표기한다 "
            "(예: '... 스파이크 이력이 있다 [issue_x].') — 목록의 id만 사용.\n"
            f"질문: {question}\n"
            f"수집된 객체: {json.dumps(card_payload, ensure_ascii=False)}\n"
            '출력(JSON만): {"answer": "한국어 답변 (문장 끝 [id] 인용 마커)", '
            '"citations": ["id", ...], '
            '"confidence": "low|medium|high", "derivation": "도출 과정 한 문장"}'
        )

    @staticmethod
    def _inline_citation_ids(answer: str) -> list[str]:
        """답변 본문의 [id] 인용 마커 — 검증 관문과 프론트 각주 렌더링의 공통 계약."""
        return re.findall(r"\[([a-z0-9_]+)\]", answer)

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
        # A2: 본문 인라인 마커도 같은 관문 — 카드 밖 id 마커는 거부한다.
        bad_markers = [m for m in self._inline_citation_ids(parsed.answer) if m not in card_ids]
        if bad_markers:
            problems.append(f"본문 인용 마커가 수집된 객체 밖: {bad_markers[:3]}")
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

    def preview(self, question: str) -> AskPreview:
        """결정론 검색만 — POST /ask 완료 전 카드를 즉시 표시하기 위한 경로."""
        cards, unmatched = self._search(question)
        return AskPreview(question=question, cards=cards, unmatched_terms=unmatched)

    def ask(self, question: str) -> AskResult:
        started = time.monotonic()
        cards, unmatched = self._search(question)
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
                # 본문 마커 인용을 citations에 합류 — 목록과 본문이 어긋나지 않게.
                inline = [
                    m for m in self._inline_citation_ids(candidate.answer) if m in card_ids
                ]
                parsed = candidate.model_copy(
                    update={"citations": list(dict.fromkeys(candidate.citations + inline))}
                )
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
            unmatched_terms=unmatched,
            validation_notes=notes,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
