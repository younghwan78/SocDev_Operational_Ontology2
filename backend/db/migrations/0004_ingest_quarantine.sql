-- J1 2단계: 반입 보류 풀(quarantine) — 거부 행을 저장해 큐레이션 대기열로.
-- 온톨로지 컬렉션이 아니라 ingest 계층의 스테이징이다 (14_ingest_reality_gaps.md §2 J1).
CREATE TABLE IF NOT EXISTS ingest_quarantine (
    id           text        PRIMARY KEY,
    batch_id     text        NOT NULL,
    mapping_name text        NOT NULL,
    row_number   integer     NOT NULL,
    object_id    text,                    -- 행의 id 열 값 (있으면 — 재반입 성공 시 해소 매칭)
    row_data     jsonb       NOT NULL,    -- 원본 열 값 그대로 (수정용 CSV 재구성)
    reason       text        NOT NULL,
    status       text        NOT NULL,    -- pending | resolved
    created_at   timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quarantine_status ON ingest_quarantine (status, mapping_name);
