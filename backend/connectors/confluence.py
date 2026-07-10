"""Confluence read-only 커넥터 — 페이지 → SemanticChunk 검색 후보 반입.

페이지는 **검색 후보**일 뿐 증거가 아니다 (CLAUDE.md §3 — supporting_basis 편입 전
인용 불가). `semantic_chunks` 매핑으로 ingest 배치 진입, origin=integrated.

설계: internal_docs/design/12_jira_connector.md §2.3
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from backend.ingest.service import IngestReport, IngestService
from backend.ontology.common import SourceOrigin


class ConfluenceError(Exception):
    pass


@runtime_checkable
class ConfluenceClientProtocol(Protocol):
    def fetch_pages(self) -> list[dict[str, Any]]: ...


class FakeConfluenceClient:
    """fixture JSON(payload) 기반 — 사외/테스트 검증 경로."""

    def __init__(self, payload_path: Path) -> None:
        self._path = payload_path

    def fetch_pages(self) -> list[dict[str, Any]]:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        pages = data.get("pages", data if isinstance(data, list) else [])
        if not isinstance(pages, list):
            raise ConfluenceError("payload에 pages 배열이 없습니다")
        return pages


class ConfluenceConnector:
    def __init__(self, client: ConfluenceClientProtocol) -> None:
        self._client = client

    def rows(self) -> tuple[list[dict[str, str]], list[str]]:
        rows: list[dict[str, str]] = []
        refs: list[str] = []
        for page in self._client.fetch_pages():
            page_id = str(page.get("id", ""))
            rows.append(
                {
                    "청크 ID": f"chunk_confluence_{page_id}",
                    "본문": f"{page.get('title', '')}\n{page.get('body', '')}".strip(),
                    "출처 ID": page_id,
                    "출처 유형": "confluence_page",
                    "프로젝트 ID": str(page.get("project_id", "")),
                }
            )
            refs.append(f"confluence:{page_id}")
        return rows, refs

    def sync(
        self, ingest: IngestService, *, source_name: str = "confluence-sync"
    ) -> IngestReport:
        rows, refs = self.rows()
        return ingest.ingest_rows(
            source_name,
            rows,
            "semantic_chunks",
            origin=SourceOrigin.INTEGRATED,
            row_refs=refs,
        )
