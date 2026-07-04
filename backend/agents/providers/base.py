"""LLM Provider 계약 — 체인의 모든 엔진이 구현하는 인터페이스."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class ProviderError(Exception):
    """provider 실행 실패 — 체인은 다음 provider로 넘어간다."""


@dataclass
class ProviderResult:
    """provider 원시 응답."""

    text: str
    provider: str
    model_name: str | None
    duration_ms: int


@runtime_checkable
class LLMProvider(Protocol):
    """텍스트 생성 provider 계약."""

    name: str
    is_external: bool  # 외부(사외) LLM 여부 — allow_external_llm 정책 대상

    def generate(self, prompt: str, timeout_s: float) -> ProviderResult:
        """프롬프트에 대한 응답을 생성한다. 실패 시 ProviderError."""
        ...
