-- Stage 7: Excel/CSV 반입 배치 기록

CREATE TABLE IF NOT EXISTS ingest_batches (
    id                text        NOT NULL PRIMARY KEY,
    filename          text        NOT NULL,
    mapping_name      text        NOT NULL,
    target_collection text        NOT NULL,
    accepted_count    integer     NOT NULL,
    rejected_count    integer     NOT NULL,
    status            text        NOT NULL,
    created_at        timestamptz NOT NULL,
    payload           jsonb       NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ingest_batches_created ON ingest_batches (created_at DESC);
