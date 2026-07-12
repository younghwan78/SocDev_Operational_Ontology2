"""임베딩 provider — Ask 하이브리드 검색의 벡터 축 (D3, Stage 18 사외 선행분).

- Fake: 결정론 해시 bag-of-tokens 벡터 — 사외/테스트. 토큰이 겹치면 코사인이
  올라가는 성질만 보장한다 (의미 임베딩의 대역).
- OnPrem: 사내 OpenAI 호환 /embeddings — 사내 검증 대상(테스트 비대상).
기본은 비활성(SOC_EMBED_PROVIDER 미설정) — Ask는 키워드 검색만으로 동작한다.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.request
from typing import Protocol, runtime_checkable

EMBED_PROVIDER_ENV = "SOC_EMBED_PROVIDER"  # fake | openai_compat | (미설정=비활성)


class EmbeddingError(Exception):
    pass


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str
    model_name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[0-9a-z]+|[가-힣]+", text.lower()) if len(t) >= 2]


class FakeEmbeddingProvider:
    """결정론 해시 임베딩 — 같은 텍스트는 항상 같은 벡터, 토큰 겹침 ∝ 유사도."""

    name = "fake"
    model_name = "fake-hash-64"
    dimension = 64

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in _tokens(text):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = digest[0] % self.dimension
                sign = 1.0 if digest[1] % 2 == 0 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / norm for v in vector])
        return vectors


class OnPremEmbeddingProvider:
    """사내 OpenAI 호환 /embeddings — 사내 검증 대상 (Fake 경로가 테스트를 담당)."""

    name = "openai_compat"

    def __init__(self) -> None:
        self._base_url = os.environ.get("SOC_ONPREM_BASE_URL")
        self._api_key = os.environ.get("SOC_ONPREM_API_KEY")
        self.model_name = os.environ.get("SOC_ONPREM_EMBED_MODEL", "onprem-embed")
        self.dimension = int(os.environ.get("SOC_ONPREM_EMBED_DIM", "1024"))
        if not self._base_url:
            raise EmbeddingError("SOC_ONPREM_BASE_URL 환경변수가 필요합니다")

    def embed(self, texts: list[str]) -> list[list[float]]:
        request = urllib.request.Request(
            f"{self._base_url}/embeddings",
            data=json.dumps({"model": self.model_name, "input": texts}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key or ''}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 — 사내 URL
            payload = json.load(response)
        return [item["embedding"] for item in payload.get("data", [])]


def build_embedding_provider(name: str | None = None) -> EmbeddingProvider | None:
    """env 기반 provider 구성 — 미설정이면 None(키워드 검색만)."""
    resolved = name or os.environ.get(EMBED_PROVIDER_ENV, "")
    if resolved == "fake":
        return FakeEmbeddingProvider()
    if resolved == "openai_compat":
        return OnPremEmbeddingProvider()
    return None


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)
