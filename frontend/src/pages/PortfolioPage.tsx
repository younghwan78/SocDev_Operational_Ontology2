/**
 * 포트폴리오 현황 — 과제 요약 + 주목 레인(6종) + 시나리오×과제 매트릭스.
 * E1 폴리싱: 레인 상황판(숫자 카드=필터), 과제 칩 필터, URL=상태,
 * phase 한국어 라벨, 매트릭스 근거 공백 우선 정렬.
 */
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchAsOfPortfolio,
  fetchPortfolio,
  type AsOfMeta,
  type AttentionItem,
  type PortfolioOverview,
} from "../api/client";
import { CollapsibleList } from "../components/CollapsibleList";
import { useLabels } from "../hooks/useLabels";
import { useValueLabels } from "../hooks/useValueLabels";
import { ErrorState } from "../components/ErrorState";
import { ko } from "../i18n/ko";

const t = ko.portfolio;

const LANE_BADGE: Record<string, string> = {
  evidence_blocked: "badge-danger",
  definition_needed: "badge-warn",
  confidence_blocked: "badge-danger",
  propagation_review: "badge-info",
  de_risk_candidate: "badge-warn",
  management_attention: "badge-danger",
};
const DANGER_LANES = new Set(["evidence_blocked", "confidence_blocked", "management_attention"]);

export function PortfolioPage() {
  const label = useLabels();
  const valueLabel = useValueLabels();
  // URL=상태 — 레인/과제 필터를 공유·재현할 수 있게 한다.
  const [searchParams, setSearchParams] = useSearchParams();
  const laneFilter = searchParams.get("lane");
  const projectFilter = searchParams.get("project");
  // Q3 as-of: URL의 asof가 있으면 시점 재구성 뷰 (위험 지도와 동일 패턴).
  const asOfParam = searchParams.get("asof");
  const asOfTs = asOfParam ? new Date(asOfParam).toISOString() : null;
  const portfolio = useQuery<{ overview: PortfolioOverview; meta: AsOfMeta | null }>({
    queryKey: ["portfolio", asOfTs],
    queryFn: async () => {
      if (asOfTs) {
        const result = await fetchAsOfPortfolio(asOfTs);
        return { overview: result.overview, meta: result.meta };
      }
      return { overview: await fetchPortfolio(), meta: null };
    },
  });
  const updateParams = (patch: Record<string, string | null>) => {
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        for (const [key, value] of Object.entries(patch)) {
          if (value === null) next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );
  };

  if (portfolio.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (portfolio.isError)
    return <ErrorState error={portfolio.error} onRetry={() => void portfolio.refetch()} />;

  const { projects, attention, matrix } = portfolio.data.overview;
  const asOfMeta = portfolio.data.meta;
  const byProject = (projectIds: string[] | null | undefined) =>
    !projectFilter || (projectIds ?? []).includes(projectFilter);
  const visibleAttention = attention.filter((item) => byProject(item.project_ids));
  const lanes = [...new Set(visibleAttention.map((item) => item.lane))];
  const visibleLanes = laneFilter ? lanes.filter((lane) => lane === laneFilter) : lanes;
  // 근거 공백이 있는 시나리오 먼저 — 볼 이유가 있는 것부터.
  const visibleMatrix = matrix
    .filter((cell) => byProject(cell.project_ids))
    .sort((a, b) => b.gap_count - a.gap_count || a.scenario_name.localeCompare(b.scenario_name));

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">{t.note}</p>

      <div className="filter-row">
        <label className="filter-label" htmlFor="portfolio-asof-input">
          {ko.risk.asof_label}
        </label>
        <input
          id="portfolio-asof-input"
          type="datetime-local"
          className="search-input"
          value={asOfParam ?? ""}
          onChange={(event) => updateParams({ asof: event.target.value || null })}
        />
        {asOfParam && (
          <button
            type="button"
            className="chip chip-btn"
            onClick={() => updateParams({ asof: null })}
          >
            {ko.risk.asof_clear}
          </button>
        )}
      </div>
      {asOfMeta && (
        <p className="section-note rca-banner">
          ⏱ {ko.risk.asof_banner}: {new Date(asOfMeta.as_of).toLocaleString("ko-KR")} —{" "}
          {ko.risk.asof_replayed} {asOfMeta.replayed_versions} · {ko.risk.asof_assumed}{" "}
          {asOfMeta.precapture_assumed_objects} · {ko.risk.asof_approx}{" "}
          {asOfMeta.approximated_objects} · {ko.risk.asof_excluded}{" "}
          {asOfMeta.excluded_objects}
          <br />
          {asOfMeta.note_ko}
        </p>
      )}

      <div className="scenario-grid">
        {projects.map((summary) => (
          <button
            key={summary.project.id}
            type="button"
            className={`card project-card ${
              projectFilter === summary.project.id ? "project-active" : ""
            }`}
            title={summary.project.id}
            onClick={() =>
              updateParams({
                project: projectFilter === summary.project.id ? null : summary.project.id,
              })
            }
          >
            <div className="name">
              {summary.project.name}{" "}
              <span className="badge badge-info" title={summary.project.phase}>
                {valueLabel("project_phase", summary.project.phase)}
              </span>
            </div>
            <dl className="kv">
              <dt>{t.milestones}</dt>
              <dd>{summary.milestone_count}</dd>
              <dt>{t.open_requests}</dt>
              <dd>{summary.open_request_count}</dd>
              <dt>{t.events}</dt>
              <dd>{summary.event_count}</dd>
            </dl>
            <p className="desc">{t.project_filter_hint}</p>
          </button>
        ))}
      </div>

      {/* E1 상황판 — 레인별 건수, 클릭=필터 */}
      <div className="stat-strip">
        <button
          type="button"
          className={`stat ${!laneFilter ? "stat-active" : ""}`}
          onClick={() => updateParams({ lane: null })}
        >
          <b>{visibleAttention.length}</b>
          <span>{t.lane_all}</span>
        </button>
        {lanes.map((lane) => {
          const items = visibleAttention.filter((item) => item.lane === lane);
          return (
            <button
              key={lane}
              type="button"
              className={`stat ${DANGER_LANES.has(lane) ? "stat-danger" : ""} ${
                laneFilter === lane ? "stat-active" : ""
              }`}
              onClick={() => updateParams({ lane: laneFilter === lane ? null : lane })}
            >
              <b>{items.length}</b>
              <span>{items[0]?.lane_ko ?? lane}</span>
            </button>
          );
        })}
      </div>

      <div className="card">
        <h2 className="card-title">{t.attention_section}</h2>
        {visibleLanes.length === 0 && <p className="desc">{ko.app.empty}</p>}
        {visibleLanes.map((lane) => {
          const items = visibleAttention.filter((item) => item.lane === lane);
          return (
            <div key={lane} className="timeline-week">
              <div className="week-label">
                {items[0].lane_ko} ({items.length})
              </div>
              <CollapsibleList
                items={items}
                limit={laneFilter ? 15 : 5}
                render={(item: AttentionItem, index: number) => (
                  <AttentionRow key={`${item.ref_id}-${index}`} item={item} label={label} />
                )}
              />
            </div>
          );
        })}
      </div>

      <div className="card">
        <h2 className="card-title">
          {t.matrix_section} ({visibleMatrix.length})
        </h2>
        <p className="section-note">{t.matrix_note}</p>
        <div className="scenario-grid">
          {visibleMatrix.map((cell) => (
            <Link
              key={cell.scenario_id}
              to={`/scenarios/${cell.scenario_id}/overview`}
              className="card scenario-card"
              title={cell.scenario_id}
            >
              <div className="name">{cell.scenario_name}</div>
              <div className="chip-row">
                {cell.project_ids.map((projectId) => (
                  <span key={projectId} className="chip" title={projectId}>
                    {label(projectId)}
                  </span>
                ))}
              </div>
              <p className="desc">
                {t.matrix_requests} {cell.request_count} · {t.matrix_events} {cell.event_count}{" "}
                ·{" "}
                <span className={cell.gap_count > 0 ? "badge badge-danger" : "badge badge-ok"}>
                  {t.matrix_gaps} {cell.gap_count}
                </span>
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function AttentionRow({
  item,
  label,
}: {
  item: AttentionItem;
  label: (id: string) => string;
}) {
  const valueLabel = useValueLabels();
  return (
    <div className="list-item">
      <div className="head">
        <span className={`badge ${LANE_BADGE[item.lane] ?? "badge-info"}`}>{item.lane_ko}</span>
        <span className="title" title={item.ref_id}>
          {item.title}
        </span>
        {(item.project_ids ?? []).map((projectId) => (
          <span key={projectId} className="chip" title={projectId}>
            {label(projectId)}
          </span>
        ))}
      </div>
      <p className="desc">{item.description}</p>
      {(item.scenario_ids ?? []).length > 0 && (
        <p className="desc">
          {ko.portfolio.related_scenarios}:{" "}
          {(item.scenario_ids ?? []).map((scenarioId) => (
            <Link
              key={scenarioId}
              to={`/scenarios/${scenarioId}/overview`}
              className="chip-link"
              title={scenarioId}
            >
              {label(scenarioId)}
            </Link>
          ))}
        </p>
      )}
      {(item.suggested_review_roles ?? []).length > 0 && (
        <p className="desc">
          {ko.portfolio.suggested_roles}:{" "}
          {(item.suggested_review_roles ?? []).map((roleId) => valueLabel("role", roleId)).join(", ")}
        </p>
      )}
    </div>
  );
}
