-- 시간 모델 T1 (15_temporal_model.md §4.1): append-only 객체 버전 로그.
-- 이 테이블에는 UPDATE/DELETE가 없다 — rollback도 retracted 버전을 추가할 뿐이다.

CREATE TABLE IF NOT EXISTS object_versions (
    seq               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    collection        text        NOT NULL,
    object_id         text        NOT NULL,
    version           integer     NOT NULL,   -- (collection, object_id)별 1부터 증가
    change_kind       text        NOT NULL,   -- created | updated | retracted
    recorded_at       timestamptz NOT NULL,
    batch_id          text,                   -- ingest 배치 / 'seed:<ts>' — 계보
    source_origin     text        NOT NULL,
    source_updated_at timestamptz,            -- 원천 주장 시각 (optional)
    changed_fields    text[]      NOT NULL DEFAULT '{}',
    payload           jsonb,                  -- 변경 후 전체 스냅샷. retracted는 NULL
    UNIQUE (collection, object_id, version)
);

CREATE INDEX IF NOT EXISTS idx_object_versions_object
    ON object_versions (collection, object_id, version);
CREATE INDEX IF NOT EXISTS idx_object_versions_recorded
    ON object_versions (recorded_at);
