"""Evidence-grounded 검증 관문 — provider와 무관하게 항상 실행된다.

통과하지 못한 출력은 채택되지 않고 체인의 다음 provider로 넘어간다.
"""

from __future__ import annotations

import json
import re

from pydantic import Field, ValidationError

from backend.ontology.common import Confidence, GroundedStatement, OntologyModel


class AdvisoryDraft(OntologyModel):
    """provider 출력 파싱 계약 — 내용 필드만 (식별자는 runner가 부여)."""

    summary: str
    concerns: list[GroundedStatement] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    recommendation: str
    confidence: Confidence
    missing_information: list[str] = Field(default_factory=list)
    derivation_summary: str | None = None


class DraftParseError(Exception):
    """provider 텍스트에서 AdvisoryDraft를 추출하지 못함."""


def parse_draft(text: str) -> AdvisoryDraft:
    """LLM 텍스트 응답에서 JSON을 추출해 계약으로 검증한다."""
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    candidate = fence.group(1) if fence else stripped
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise DraftParseError("응답에서 JSON 객체를 찾지 못함")
        candidate = candidate[start : end + 1]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise DraftParseError(f"JSON 파싱 실패: {exc}") from exc
    try:
        return AdvisoryDraft.model_validate(payload)
    except ValidationError as exc:
        raise DraftParseError(f"AdvisoryDraft 계약 위반: {exc}") from exc


# 일반론 감지 — 이 표현만으로 끝나는 서술은 거부한다 (56 AGENTS.md 규칙 승계)
GENERIC_ONLY_PATTERNS = [
    r"^추가\s*분석이\s*필요[하합]",
    r"^리스크가\s*있[어으]",
    r"^검토가\s*필요[하합]",
    r"^성능에\s*영향[을이]\s*줄\s*수\s*있",
]

MIN_DESCRIPTION_LENGTH = 15


def validate_draft(draft: AdvisoryDraft, known_ids: set[str]) -> list[str]:
    """검증 실패 사유 목록을 반환한다. 비어 있으면 통과."""
    problems: list[str] = []

    if not draft.concerns:
        problems.append("우려(concerns)가 없음 — 근거 문장 최소 1건 필요")

    weak_evidence = False
    for index, concern in enumerate(draft.concerns):
        label = f"concerns[{index}]"
        if not concern.supporting_basis:
            problems.append(f"{label}: supporting_basis 비어 있음")
            continue
        resolved = [basis for basis in concern.supporting_basis if basis in known_ids]
        if not resolved:
            problems.append(
                f"{label}: supporting_basis 전부 미해석 — {concern.supporting_basis}"
            )
        if len(concern.description.strip()) < MIN_DESCRIPTION_LENGTH:
            problems.append(f"{label}: 서술이 너무 짧음")
        for pattern in GENERIC_ONLY_PATTERNS:
            if re.match(pattern, concern.description.strip()):
                problems.append(f"{label}: 일반론 서술 거부 — '{concern.description[:30]}'")
        if concern.confidence is Confidence.LOW:
            weak_evidence = True

    if draft.confidence is Confidence.HIGH and (weak_evidence or draft.missing_information):
        problems.append("근거가 약한 상태의 high confidence 금지")

    return problems
