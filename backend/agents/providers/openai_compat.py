"""사내 on-premise OpenAI 호환 provider — 2차 fallback.

설정: SOC_ONPREM_BASE_URL / SOC_ONPREM_MODEL / SOC_ONPREM_API_KEY (선택).
"""

from __future__ import annotations

import os
import time

import httpx

from backend.agents.providers.base import ProviderError, ProviderResult


class OpenAICompatProvider:
    """chat/completions 호환 endpoint 호출. 사내 배포이므로 외부 LLM이 아니다."""

    name = "openai_compat"
    is_external = False

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url or os.environ.get("SOC_ONPREM_BASE_URL")
        self._model = model or os.environ.get("SOC_ONPREM_MODEL", "onprem-default")
        self._api_key = api_key or os.environ.get("SOC_ONPREM_API_KEY")
        self._transport = transport

    def generate(self, prompt: str, timeout_s: float) -> ProviderResult:
        if not self._base_url:
            raise ProviderError("사내 LLM base URL 미설정 (SOC_ONPREM_BASE_URL)")

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        started = time.monotonic()
        try:
            with httpx.Client(
                base_url=self._base_url,
                headers=headers,
                timeout=timeout_s,
                transport=self._transport,
            ) as client:
                response = client.post(
                    "/chat/completions",
                    json={
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                    },
                )
        except httpx.HTTPError as exc:
            raise ProviderError(f"사내 LLM 호출 실패: {exc}") from exc
        duration_ms = int((time.monotonic() - started) * 1000)

        if response.status_code != 200:
            raise ProviderError(f"사내 LLM 응답 코드 {response.status_code}: {response.text[:300]}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderError(f"사내 LLM 응답 형식 오류: {response.text[:200]}") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("사내 LLM 응답 내용 없음")

        return ProviderResult(
            text=content,
            provider=self.name,
            model_name=self._model,
            duration_ms=duration_ms,
        )
