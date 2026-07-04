"""Claude CLI provider — 1차 엔진. headless 실행(claude -p --output-format json)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from backend.agents.providers.base import ProviderError, ProviderResult


class ClaudeCLIProvider:
    """구독 기반 Claude CLI를 headless로 호출한다. 외부 LLM으로 분류된다."""

    name = "claude_cli"
    is_external = True

    def __init__(self, executable: str = "claude", model: str | None = None) -> None:
        self._executable = executable
        self._model = model or os.environ.get("SOC_CLAUDE_MODEL")

    def generate(self, prompt: str, timeout_s: float) -> ProviderResult:
        if shutil.which(self._executable) is None:
            raise ProviderError(f"Claude CLI 실행 파일 없음: {self._executable}")

        command = [self._executable, "-p", prompt, "--output-format", "json"]
        if self._model:
            command += ["--model", self._model]

        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(f"Claude CLI 타임아웃 ({timeout_s}s)") from exc
        duration_ms = int((time.monotonic() - started) * 1000)

        if completed.returncode != 0:
            raise ProviderError(f"Claude CLI 종료 코드 {completed.returncode}: {completed.stderr[:300]}")
        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Claude CLI 출력 JSON 파싱 실패: {completed.stdout[:200]}") from exc
        if envelope.get("is_error"):
            raise ProviderError(f"Claude CLI 오류 응답: {str(envelope.get('result'))[:300]}")

        result_text = envelope.get("result")
        if not isinstance(result_text, str) or not result_text.strip():
            raise ProviderError("Claude CLI 응답에 result 텍스트 없음")

        return ProviderResult(
            text=result_text,
            provider=self.name,
            model_name=self._model or "claude-default",
            duration_ms=duration_ms,
        )
