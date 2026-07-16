-- what-if 가정 세트 — 운영 기록 (ask_log와 같은 지위, append-only).
-- 온톨로지 데이터가 아니다: 세트를 불러와도 적용은 ephemeral overlay 경유.
CREATE TABLE IF NOT EXISTS whatif_sets (
    id         text        NOT NULL PRIMARY KEY,
    name       text        NOT NULL,
    project_id text,
    created_at timestamptz NOT NULL,
    payload    jsonb       NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_whatif_sets_created ON whatif_sets (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_whatif_sets_project ON whatif_sets (project_id);
