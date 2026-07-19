"""JIRA read-only 커넥터 — 이슈 JSON → ingest 행 정규화.

- 필드 매핑은 코드가 아니라 설정 YAML(`jira_field_map.yaml`) — 사내 스키마 확정 시
  코드 수정 없이 값만 교체한다. 컬럼 대상은 기존 ingest 매핑의 한국어 열 이름.
- 커넥터는 직접 저장 금지: `IngestService.ingest_rows(origin=INTEGRATED)`로만 진입.
- 자격 증명은 환경변수만 (JIRA_BASE_URL / JIRA_API_TOKEN) — 코드/설정에 비밀 없음.

설계: internal_docs/design/12_jira_connector.md
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

from backend.ingest.service import IngestReport, IngestService
from backend.ontology.common import SourceOrigin

DEFAULT_FIELD_MAP = Path(__file__).with_name("jira_field_map.yaml")


class ConnectorError(Exception):
    pass


@runtime_checkable
class JiraClientProtocol(Protocol):
    """JIRA 검색 계약 — 실 REST 또는 fixture payload."""

    def search_issues(self) -> list[dict[str, Any]]: ...


class FakeJiraClient:
    """fixture JSON(payload) 기반 클라이언트 — 사외/테스트 검증 경로."""

    def __init__(self, payload_path: Path) -> None:
        self._path = payload_path

    def search_issues(self) -> list[dict[str, Any]]:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        issues = data.get("issues", data if isinstance(data, list) else [])
        if not isinstance(issues, list):
            raise ConnectorError("payload에 issues 배열이 없습니다")
        return issues


def incremental_jql(base_jql: str, since_iso: str | None) -> str:
    """증분 동기화 JQL — 마지막 동기화 이후 갱신분만 (같은 키의 주기적 update 대응)."""
    if not since_iso:
        return base_jql
    # JIRA JQL은 "yyyy-MM-dd HH:mm" 형식 — ISO의 T/초 이하를 정리한다.
    stamp = since_iso.replace("T", " ")[:16]
    clause = f'updated >= "{stamp}"'
    return f"({base_jql}) AND {clause}" if base_jql.strip() else clause


class JiraHttpClient:
    """실 JIRA REST 클라이언트 (얇음) — 사내 검증 대상, 테스트 비대상.

    환경변수: {prefix}JIRA_BASE_URL, {prefix}JIRA_API_TOKEN — 그룹별 인스턴스는
    env_prefix로 분리한다 (예: prefix "CAMERA_" → CAMERA_JIRA_BASE_URL).
    pagination: startAt 순회로 전량 수집 (대량 인스턴스 대응).
    """

    def __init__(self, jql: str, max_results: int = 100, env_prefix: str = "") -> None:
        self._base_url = os.environ.get(f"{env_prefix}JIRA_BASE_URL")
        self._token = os.environ.get(f"{env_prefix}JIRA_API_TOKEN")
        if not self._base_url or not self._token:
            raise ConnectorError(
                f"{env_prefix}JIRA_BASE_URL/{env_prefix}JIRA_API_TOKEN 환경변수가 필요합니다"
            )
        self._jql = jql
        self._max_results = max_results

    def _page(self, start_at: int) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode(
            {"jql": self._jql, "maxResults": self._max_results, "startAt": start_at}
        )
        request = urllib.request.Request(
            f"{self._base_url}/rest/api/2/search?{query}",
            headers={"Authorization": f"Bearer {self._token}"},
        )
        with urllib.request.urlopen(request) as response:  # noqa: S310 — 사내 배포 URL
            payload = json.load(response)
        issues = payload.get("issues", [])
        return issues if isinstance(issues, list) else []

    def search_issues(self) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        start_at = 0
        while True:
            page = self._page(start_at)
            collected.extend(page)
            if len(page) < self._max_results:
                return collected
            start_at += self._max_results


@dataclass(frozen=True)
class JiraFieldMap:
    """설정 YAML — ingest 한국어 열 ← JIRA dotted 경로 + 값 정규화 + 고정값.

    week_columns: 날짜 필드(updated/duedate 등)를 ISO 주차로 변환하는 열 —
    J3 신선도·일정 신호의 입력 (14_ingest_reality_gaps.md §2).
    """

    issue_mapping: str
    columns: dict[str, str]
    value_maps: dict[str, dict[str, str]] = field(default_factory=dict)
    constants: dict[str, str] = field(default_factory=dict)
    week_columns: dict[str, str] = field(default_factory=dict)  # 열 ← 날짜 dotted 경로

    @classmethod
    def load(cls, path: Path | None = None) -> JiraFieldMap:
        raw = yaml.safe_load((path or DEFAULT_FIELD_MAP).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or "columns" not in raw:
            raise ConnectorError("필드 매핑 YAML에 columns가 필요합니다")
        return cls(
            issue_mapping=str(raw.get("issue_mapping", "issues")),
            columns={str(k): str(v) for k, v in raw["columns"].items()},
            value_maps={
                str(col): {str(k): str(v) for k, v in mapping.items()}
                for col, mapping in (raw.get("value_maps") or {}).items()
            },
            constants={str(k): str(v) for k, v in (raw.get("constants") or {}).items()},
            week_columns={
                str(k): str(v) for k, v in (raw.get("week_columns") or {}).items()
            },
        )


def iso_week(value: str) -> str:
    """ISO 날짜/시각 문자열 → ISO 주차 문자열. 파싱 불가는 빈 문자열(열 생략)."""
    from datetime import date

    try:
        return str(date.fromisoformat(value.strip()[:10]).isocalendar().week)
    except ValueError:
        return ""


def extract_path(payload: dict[str, Any], dotted: str) -> str:
    """dotted 경로로 dict/list를 내려간다 — 누락은 빈 문자열(행 검증이 거부 처리)."""
    node: Any = payload
    for part in dotted.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return ""
        if node is None:
            return ""
    return str(node)


class JiraConnector:
    def __init__(self, client: JiraClientProtocol, field_map: JiraFieldMap) -> None:
        self._client = client
        self._map = field_map

    def rows(self) -> tuple[list[dict[str, str]], list[str]]:
        """JIRA 이슈 → (ingest 행, 외부 키 refs). 정규화만 — 저장 없음."""
        rows: list[dict[str, str]] = []
        refs: list[str] = []
        for issue in self._client.search_issues():
            row: dict[str, str] = dict(self._map.constants)
            for column, dotted in self._map.columns.items():
                value = extract_path(issue, dotted)
                normalized = self._map.value_maps.get(column, {}).get(value, value)
                row[column] = normalized
            for column, dotted in self._map.week_columns.items():
                row[column] = iso_week(extract_path(issue, dotted))
            rows.append(row)
            refs.append(f"jira:{issue.get('key', row.get('이슈 ID', '?'))}")
        return rows, refs

    def sync(
        self,
        ingest: IngestService,
        *,
        source_name: str = "jira-sync",
        recorded_at: datetime | None = None,
    ) -> IngestReport:
        # recorded_at은 리허설 리플레이 전용 주입 시계 (설계 25) — 실 동기화는 미지정.
        rows, refs = self.rows()
        return ingest.ingest_rows(
            source_name,
            rows,
            self._map.issue_mapping,
            origin=SourceOrigin.INTEGRATED,
            row_refs=refs,
            recorded_at=recorded_at,
        )
