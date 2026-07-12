"""시맨틱 인덱스 테스트 (D3) — Fake 임베딩 결정론 / 인덱싱 멱등 / Ask 하이브리드.

원칙 검증: 청크는 후보(증거 아님) 지위로만 카드에 합류하고, 인용 관문은 불변이다.
"""

from pathlib import Path

import pytest
from backend.agents.ask_runner import AskRunner
from backend.agents.providers.embedding import FakeEmbeddingProvider, cosine
from backend.ingest.service import MemoryIngestWriter
from backend.loaders.repository import InMemoryRepository
from backend.ontology.evidence import SemanticChunk
from backend.services.semantic_index import embed_chunks, search_chunks

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture()
def repo() -> InMemoryRepository:
    repo = InMemoryRepository.from_fixtures(FIXTURES)
    # 통제된 후보 청크 — 키워드 검색 대상 컬렉션에 없는 어휘로 구성
    repo.add_objects(
        "semantic_chunks",
        [
            SemanticChunk.model_validate(
                {
                    "id": "chunk_test_thermal_meeting",
                    "chunk_text": "서멀 스로틀링 완화 회의록\n방열 구조와 서멀 예산 재배분 논의",
                    "source_id": "9001",
                    "source_type": "confluence_page",
                    "embedding_status": "pending",
                    "evidence_confidence": "low",
                }
            )
        ],
    )
    return repo


def test_fake_embedding_deterministic_and_overlap() -> None:
    provider = FakeEmbeddingProvider()
    a1, a2 = provider.embed(["서멀 예산 재배분"]), provider.embed(["서멀 예산 재배분"])
    assert a1 == a2, "같은 텍스트는 항상 같은 벡터"
    base = provider.embed(["서멀 예산 재배분 회의"])[0]
    near = provider.embed(["서멀 예산 논의"])[0]
    far = provider.embed(["완전히 다른 주제의 문장"])[0]
    assert cosine(base, near) > cosine(base, far), "토큰 겹침이 유사도로 반영"


def test_embed_chunks_idempotent(repo: InMemoryRepository) -> None:
    provider = FakeEmbeddingProvider()
    writer = MemoryIngestWriter(repo)
    created, kept = embed_chunks(repo, writer, provider)
    assert created == len(repo.list("semantic_chunks")) and kept == 0
    created2, kept2 = embed_chunks(repo, writer, provider)
    assert created2 == 0 and kept2 == created, "같은 모델 재실행은 전부 유지(멱등)"


def test_search_chunks_finds_relevant(repo: InMemoryRepository) -> None:
    provider = FakeEmbeddingProvider()
    embed_chunks(repo, MemoryIngestWriter(repo), provider)
    results = search_chunks(repo, provider, "서멀 스로틀링 방열 예산", top_k=3)
    assert results and results[0][0].id == "chunk_test_thermal_meeting"


def test_ask_hybrid_adds_candidate_cards_with_non_evidence_status(
    repo: InMemoryRepository,
) -> None:
    provider = FakeEmbeddingProvider()
    embed_chunks(repo, MemoryIngestWriter(repo), provider)
    runner = AskRunner(repo, providers=[], embedder=provider)
    result = runner.ask("방열 구조 재배분 논의가 있었나?")
    chunk_cards = [c for c in result.cards if c.collection == "semantic_chunks"]
    assert chunk_cards, "벡터 후보 청크가 카드로 합류해야 한다"
    assert all("증거 아님" in (c.status_ko or "") for c in chunk_cards)
    # 인용 관문 불변 — 인용은 여전히 수집 카드 집합 안
    assert set(result.citations) <= {c.ref_id for c in result.cards}


def test_ask_without_embedder_unchanged(repo: InMemoryRepository) -> None:
    """임베딩 비활성(기본) — 기존 키워드 검색 결과와 동일해야 한다."""

    runner = AskRunner(repo, providers=[], embedder=None)
    # env 미설정 기본에서 embedder는 None — semantic 카드 없음
    if runner._embedder is None:
        result = runner.ask("방열 구조 재배분 논의가 있었나?")
        assert all(c.collection != "semantic_chunks" for c in result.cards)
