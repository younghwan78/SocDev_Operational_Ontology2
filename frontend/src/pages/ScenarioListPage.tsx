/**
 * 시나리오 목록 — E2 폴리싱: 도메인 한국어 칩(건수)·검색·URL=상태 +
 * 위험 지도 종합 등급 배지(어느 시나리오부터 볼지 목록에서 판단).
 */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fetchProjects, fetchRiskHeatmap, fetchScenarios } from "../api/client";
import { useLabels } from "../hooks/useLabels";
import { useValueLabels } from "../hooks/useValueLabels";
import { ko } from "../i18n/ko";

const t = ko.scenario_list;

const GRADE_BADGE: Record<string, string> = {
  high: "badge-danger",
  medium: "badge-warn",
  low: "badge-ok",
};

export function ScenarioListPage() {
  // URL=상태 — 필터/검색을 공유·재현.
  const [searchParams, setSearchParams] = useSearchParams();
  const projectFilter = searchParams.get("project") ?? undefined;
  const domainFilter = searchParams.get("domain");
  const urlQuery = searchParams.get("q") ?? "";
  const [queryDraft, setQueryDraft] = useState(urlQuery);
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
  useEffect(() => {
    const timer = setTimeout(() => {
      if (queryDraft !== urlQuery) updateParams({ q: queryDraft || null });
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryDraft]);

  const label = useLabels();
  const valueLabel = useValueLabels();
  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const scenarios = useQuery({
    queryKey: ["scenarios", projectFilter],
    queryFn: () => fetchScenarios(projectFilter),
  });
  // 위험 지도 종합 등급 — 목록 카드의 우선순위 신호 (결정론 재사용).
  const heatmap = useQuery({ queryKey: ["risk-heatmap", undefined], queryFn: () => fetchRiskHeatmap() });
  const gradeByScenario = new Map(
    (heatmap.data?.rows ?? []).map((row) => [row.scenario_id, row]),
  );

  if (scenarios.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (scenarios.isError)
    return (
      <p className="status-msg">
        {ko.app.error}{" "}
        <button className="chip-link" onClick={() => scenarios.refetch()}>
          {ko.app.retry}
        </button>
      </p>
    );

  const all = scenarios.data;
  const domainCounts = new Map<string, number>();
  for (const scenario of all)
    domainCounts.set(scenario.domain, (domainCounts.get(scenario.domain) ?? 0) + 1);
  const query = urlQuery.trim().toLowerCase();
  const visible = all.filter(
    (scenario) =>
      (!domainFilter || scenario.domain === domainFilter) &&
      (!query ||
        scenario.name.toLowerCase().includes(query) ||
        (scenario.description ?? "").toLowerCase().includes(query)),
  );

  return (
    <div>
      <h1>{t.title}</h1>
      <div className="filter-row">
        <span className="filter-label">{t.filter_label}</span>
        <button
          className={`chip chip-btn ${projectFilter === undefined ? "active" : ""}`}
          onClick={() => updateParams({ project: null })}
        >
          {t.filter_all}
        </button>
        {(projects.data ?? []).map((project) => (
          <button
            key={project.id}
            title={project.id}
            className={`chip chip-btn ${projectFilter === project.id ? "active" : ""}`}
            onClick={() => updateParams({ project: project.id })}
          >
            {project.name}
          </button>
        ))}
        <span className="filter-label">{t.domain_label}</span>
        {[...domainCounts.entries()]
          .sort((a, b) => b[1] - a[1])
          .map(([domain, count]) => (
            <button
              key={domain}
              title={domain}
              className={`chip chip-btn ${domainFilter === domain ? "active" : ""}`}
              onClick={() =>
                updateParams({ domain: domainFilter === domain ? null : domain })
              }
            >
              {valueLabel("scenario_domain", domain)} ({count})
            </button>
          ))}
        <label className="filter-label" htmlFor="scenario-search">
          {t.search_label}
        </label>
        <input
          id="scenario-search"
          type="search"
          className="search-input"
          value={queryDraft}
          placeholder={t.search_placeholder}
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => setQueryDraft(event.target.value)}
        />
      </div>
      {visible.length === 0 ? (
        <p className="status-msg">{ko.app.empty}</p>
      ) : (
        <div className="scenario-grid">
          {visible.map((scenario) => {
            const risk = gradeByScenario.get(scenario.id);
            return (
              <Link
                key={scenario.id}
                to={`/scenarios/${scenario.id}/overview`}
                className="card scenario-card"
              >
                <div className="name">
                  {risk && (
                    <span
                      className={`badge ${GRADE_BADGE[risk.overall_grade] ?? "badge-info"}`}
                      title={`${t.risk_prefix}: ${risk.overall_grade_ko}`}
                    >
                      {risk.overall_grade_ko}
                    </span>
                  )}{" "}
                  {scenario.name}
                </div>
                <div className="meta" title={`${scenario.scenario_group_id} · ${scenario.domain}`}>
                  {t.group_prefix}: {label(scenario.scenario_group_id)} ·{" "}
                  {valueLabel("scenario_domain", scenario.domain)} ·{" "}
                  {t.ip_count_prefix} {(scenario.uses_ip_blocks ?? []).length} ·{" "}
                  {t.sys_count_prefix} {(scenario.depends_on_system_blocks ?? []).length}
                </div>
                <div className="chip-row">
                  {(scenario.primary_kpis ?? []).slice(0, 5).map((kpi) => (
                    <span key={kpi} className="chip">
                      {kpi}
                    </span>
                  ))}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
