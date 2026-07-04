-- Stage 5: advisory 실행 감사 기록

CREATE TABLE IF NOT EXISTS agent_runs (
    id          text        NOT NULL PRIMARY KEY,
    scenario_id text        NOT NULL,
    status      text        NOT NULL,
    input_hash  text        NOT NULL,
    created_at  timestamptz NOT NULL,
    payload     jsonb       NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_scenario ON agent_runs (scenario_id, created_at DESC);
