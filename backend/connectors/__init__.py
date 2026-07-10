"""read-only 커넥터 — 외부 시스템(JIRA/Confluence) → ingest 배치.

커넥터는 직접 저장하지 않는다: 행 정규화 후 IngestService로만 진입한다
(설계: internal_docs/design/12_jira_connector.md).
"""
