-- Stage 2: 온톨로지 코어 테이블 (Phase3-lite 패턴)
-- 관계 컬럼(필터용) + JSONB payload(전체 모델) + relations + pgvector-ready semantic_chunks

CREATE TABLE IF NOT EXISTS ontology_objects (
    collection    text        NOT NULL,
    id            text        NOT NULL,
    project_id    text,
    scenario_id   text,
    position      integer     NOT NULL DEFAULT 0,
    payload       jsonb       NOT NULL,
    source_origin text        NOT NULL DEFAULT 'synthetic',
    source_ref    text,
    ingested_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (collection, id)
);

CREATE INDEX IF NOT EXISTS idx_ontology_objects_collection ON ontology_objects (collection, position);
CREATE INDEX IF NOT EXISTS idx_ontology_objects_project ON ontology_objects (project_id);
CREATE INDEX IF NOT EXISTS idx_ontology_objects_scenario ON ontology_objects (scenario_id);
CREATE INDEX IF NOT EXISTS idx_ontology_objects_payload ON ontology_objects USING gin (payload);

-- 온톨로지 그래프 골격 — traceability 질의 전용 투영
CREATE TABLE IF NOT EXISTS relations (
    id            text  NOT NULL PRIMARY KEY,
    source_id     text  NOT NULL,
    source_type   text  NOT NULL,
    relation_type text  NOT NULL,
    target_id     text  NOT NULL,
    target_type   text  NOT NULL,
    confidence    text  NOT NULL,
    payload       jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_relations_source ON relations (source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations (target_id);

-- pgvector-ready 시맨틱 청크 — embedding 컬럼은 pgvector 도입 Stage에서 추가
CREATE TABLE IF NOT EXISTS semantic_chunks (
    id         text  NOT NULL PRIMARY KEY,
    project_id text,
    chunk_text text  NOT NULL,
    payload    jsonb NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_semantic_chunks_project ON semantic_chunks (project_id);
