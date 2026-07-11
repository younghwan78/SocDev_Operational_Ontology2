-- Ask SoC 질의/답변 로그 — 감사 기록 + FAQ 집계 원천 (agent_runs와 같은 지위).
CREATE TABLE IF NOT EXISTS ask_log (
    id         text        NOT NULL PRIMARY KEY,
    normalized text        NOT NULL,
    provider   text        NOT NULL,
    confidence text        NOT NULL,
    created_at timestamptz NOT NULL,
    payload    jsonb       NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ask_log_created ON ask_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ask_log_normalized ON ask_log (normalized);
