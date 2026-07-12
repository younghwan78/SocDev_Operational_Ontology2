"""시맨틱 인덱스 — SemanticChunk 임베딩 생성·저장과 벡터 후보 검색 (D3).

원칙 (CLAUDE.md §3): 검색된 청크는 **후보**이지 증거가 아니다. 이 모듈은 후보를
찾는 것까지만 하고, 인용·검증 관문은 Ask 러너의 기존 규칙이 그대로 담당한다.

저장은 기존 `semantic_vectors` 계약(JSONB payload)을 쓴다 — 수천 건 규모까지는
파이썬 코사인 top-k가 충분하며, pgvector 네이티브 인덱스 전환은 사내 규모 확인 후
(Stage 18 잔여)로 남긴다.
"""

from __future__ import annotations

import uuid

from backend.agents.providers.embedding import EmbeddingProvider, cosine
from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.common import SourceMeta, SourceOrigin
from backend.ontology.evidence import SemanticChunk, SemanticVector


def _chunk_text_for_embedding(chunk: SemanticChunk) -> str:
    # 본문 + 연결 힌트(시나리오/IP id) — 검색 질의와 겹칠 여지를 넓힌다.
    return " ".join([chunk.chunk_text, *chunk.scenario_ids, *chunk.ip_ids])


def embed_chunks(repo: RepositoryProtocol, writer, provider: EmbeddingProvider) -> tuple[int, int]:
    """청크 전수 임베딩 — (신규 생성, 기존 유지) 반환. 같은 모델이면 재계산하지 않는다."""
    chunks = [c for c in repo.list("semantic_chunks") if isinstance(c, SemanticChunk)]
    to_embed: list[SemanticChunk] = []
    kept = 0
    for chunk in chunks:
        existing = repo.get("semantic_vectors", f"vec_{chunk.id}")
        if (
            isinstance(existing, SemanticVector)
            and existing.vector_model == provider.model_name
        ):
            kept += 1
            continue
        to_embed.append(chunk)
    if not to_embed:
        return 0, kept

    embeddings = provider.embed([_chunk_text_for_embedding(c) for c in to_embed])
    vectors = [
        SemanticVector(
            id=f"vec_{chunk.id}",
            chunk_id=chunk.id,
            embedding=embedding,
            vector_model=provider.model_name,
            vector_dimension=provider.dimension,
            source_ref=f"embed:{provider.name}:{chunk.id}",
            source=SourceMeta(
                origin=SourceOrigin.INTEGRATED, ref=f"embed:{provider.name}:{chunk.id}"
            ),
        )
        for chunk, embedding in zip(to_embed, embeddings, strict=True)
    ]
    # 같은 id 재생성(모델 교체) 대비 제거 후 저장 — upsert 의미론과 일치.
    writer.remove_by_ids("semantic_vectors", [v.id for v in vectors])
    writer.add_objects("semantic_vectors", vectors, f"embed_{uuid.uuid4().hex[:8]}")
    return len(vectors), kept


def search_chunks(
    repo: RepositoryProtocol,
    provider: EmbeddingProvider,
    question: str,
    top_k: int = 3,
    min_similarity: float = 0.30,
) -> list[tuple[SemanticChunk, float]]:
    """질문 벡터와 저장된 청크 벡터의 코사인 top-k — 후보 반환 (증거 아님)."""
    vectors = [
        v
        for v in repo.list("semantic_vectors")
        if isinstance(v, SemanticVector) and v.vector_model == provider.model_name
    ]
    if not vectors:
        return []
    query = provider.embed([question])[0]
    scored: list[tuple[SemanticChunk, float]] = []
    for vector in vectors:
        similarity = cosine(query, vector.embedding)
        if similarity < min_similarity:
            continue
        chunk = repo.get("semantic_chunks", vector.chunk_id)
        if isinstance(chunk, SemanticChunk):
            scored.append((chunk, similarity))
    scored.sort(key=lambda item: (-item[1], item[0].id))
    return scored[:top_k]
