import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  fetchKPICatalog,
  fetchKPISeries,
  type ProjectKPISeries,
  type ScenarioAnalysis,
} from "../../api/client";
import { useLabels } from "../../hooks/useLabels";
import { useValueLabels } from "../../hooks/useValueLabels";
import { ko } from "../../i18n/ko";

const t = ko.scenario_detail;

const GAP_BADGE: Record<string, string> = {
  missing_evidence: "badge-danger",
  unavailable_catalog: "badge-warn",
  required_evidence_open: "badge-warn",
  confidence_blocked: "badge-danger",
};

export function OverviewTab({ analysis }: { analysis: ScenarioAnalysis }) {
  const { scenario } = analysis;
  const label = useLabels();
  const valueLabel = useValueLabels();
  return (
    <div>
      <div className="card">
        <h2 className="card-title">{t.section_basic}</h2>
        <dl className="kv">
          <dt>{t.description}</dt>
          <dd>{scenario.description}</dd>
          <dt>{t.domain}</dt>
          <dd>{scenario.domain}</dd>
          <dt>{t.scenario_class}</dt>
          <dd>{scenario.scenario_class}</dd>
          <dt>{t.group}</dt>
          <dd>{analysis.scenario_group?.name ?? scenario.scenario_group_id}</dd>
          <dt>{t.projects}</dt>
          <dd>
            <span className="chip-row">
              {(scenario.project_relevance ?? []).map((projectId) => (
                <span key={projectId} className="chip" title={projectId}>
                  {label(projectId)}
                </span>
              ))}
            </span>
          </dd>
        </dl>
      </div>

      <div className="card">
        <h2 className="card-title">{t.section_gaps}</h2>
        {analysis.evidence_gaps.length === 0 ? (
          <p className="section-note">{t.gap_none}</p>
        ) : (
          analysis.evidence_gaps.map((gap, index) => (
            <div key={`${gap.ref_id}-${index}`} className="list-item">
              <div className="head">
                <span className={`badge ${GAP_BADGE[gap.kind] ?? "badge-info"}`}>
                  {gap.kind_ko}
                </span>
                <span className="id">{gap.ref_id}</span>
              </div>
              <p className="desc">{gap.description}</p>
            </div>
          ))
        )}
      </div>

      <div className="card">
        <h2 className="card-title">{t.section_kpi}</h2>
        <div className="chip-row">
          {analysis.kpis.map((kpi) => (
            <span key={kpi.id} className="chip">
              {kpi.id} ({kpi.unit}, {kpi.direction})
            </span>
          ))}
        </div>
      </div>

      {analysis.kpis.length > 0 && (
        <KPISeriesSection
          scenarioId={scenario.id}
          kpiIds={analysis.kpis.map((kpi) => kpi.id)}
        />
      )}

      <div className="card">
        <h2 className="card-title">{t.section_ip}</h2>
        <div className="chip-row">
          {(scenario.uses_ip_blocks ?? []).map((ipId) => (
            <span key={ipId} className="chip" title={ipId}>
              {label(ipId)}
            </span>
          ))}
          {(scenario.depends_on_system_blocks ?? []).map((blockId) => (
            <span key={blockId} className="chip" title={blockId}>
              {label(blockId)}
            </span>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">{t.section_requests}</h2>
        {analysis.requests.map((request) => (
          <div key={request.id} className="list-item">
            <div className="head">
              <span className="badge badge-info" title={request.priority}>
                {valueLabel("request_priority", request.priority)}
              </span>
              <span className="title">{request.title}</span>
            </div>
            <p className="desc">
              {t.request_week}: {ko.scenario_detail.week_prefix}
              {request.requested_week} · {t.request_status}:{" "}
              <span title={request.status}>{valueLabel("request_status", request.status)}</span> ·{" "}
              {t.confidence}: {request.confidence}
            </p>
          </div>
        ))}
      </div>

      {analysis.issues.length > 0 && (
        <div className="card">
          <h2 className="card-title">{t.section_issues}</h2>
          {analysis.issues.map((issue) => (
            <div key={issue.id} className="list-item">
              <div className="head">
                <span className="badge badge-danger" title={issue.issue_type}>
                  {valueLabel("issue_type", issue.issue_type)}
                </span>
                <span className="title">{issue.title}</span>
                <span className="badge badge-info" title={issue.status}>
                  {valueLabel("issue_status", issue.status)}
                </span>
              </div>
              <p className="desc">{issue.symptom}</p>
            </div>
          ))}
        </div>
      )}

      {analysis.variants.length > 0 && (
        <div className="card">
          <h2 className="card-title">{t.section_variants}</h2>
          <div className="chip-row">
            {analysis.variants.map((variant) => (
              <span key={variant.id} className="chip">
                {variant.id} ({variant.mode})
              </span>
            ))}
          </div>
        </div>
      )}

      {(analysis.measurement_evidence.length > 0 ||
        analysis.measurement_requirements.length > 0) && (
        <div className="card">
          <h2 className="card-title">{t.section_measurements}</h2>
          {analysis.measurement_evidence.map((item) => (
            <div key={item.id} className="list-item">
              <div className="head">
                <span className="badge badge-ok">{t.measurement_evidence}</span>
                <span className="title">{item.title}</span>
              </div>
              <p className="desc">{item.qualitative_result}</p>
            </div>
          ))}
          {analysis.measurement_requirements.map((item) => (
            <div key={item.id} className="list-item">
              <div className="head">
                <span className="badge badge-warn">{t.measurement_requirements}</span>
                <span className="title">{item.title}</span>
              </div>
              <p className="desc">{item.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const TREND_BADGE: Record<string, string> = {
  improved: "badge-ok",
  worsened: "badge-danger",
};

/** P3 KPI 시계열 — 주차×프로젝트 표 + 추세 사실 서술 (수치 점수 아님). */
function KPISeriesSection({
  scenarioId,
  kpiIds,
}: {
  scenarioId: string;
  kpiIds: string[];
}) {
  const label = useLabels();
  const valueLabel = useValueLabels();
  // 선택 후보 = primary KPI ∪ 이 시나리오에 관측이 존재하는 KPI (반입 유래 포함).
  // 기본 선택은 관측이 있는 KPI 우선 — 빈 차트로 시작하지 않는다.
  const catalog = useQuery({ queryKey: ["kpi-catalog"], queryFn: fetchKPICatalog });
  const observed = (catalog.data ?? []).filter((entry) =>
    (entry.scenario_ids ?? []).includes(scenarioId),
  );
  const observedIds = observed.map((entry) => entry.kpi_id);
  const allIds = [...new Set([...kpiIds, ...observedIds])];
  const [selected, setSelected] = useState<string | null>(null);
  const kpiId =
    selected && allIds.includes(selected) ? selected : (observedIds[0] ?? allIds[0]);
  const series = useQuery({
    queryKey: ["kpi-series", kpiId, scenarioId],
    queryFn: () => fetchKPISeries(kpiId, scenarioId),
    enabled: Boolean(kpiId),
  });

  const data = series.data;
  const projects = data?.series ?? [];
  const weeks = [...new Set(projects.flatMap((s) => s.points.map((p) => p.week)))].sort(
    (a, b) => a - b,
  );

  return (
    <div className="card">
      <h2 className="card-title">{t.kpi_series_title}</h2>
      <p className="section-note">{t.kpi_series_note}</p>
      <div className="chip-row">
        {allIds.map((id) => {
          const entry = observed.find((candidate) => candidate.kpi_id === id);
          return (
            <button
              key={id}
              type="button"
              className={`chip chip-btn ${id === kpiId ? "active" : ""}`}
              onClick={() => setSelected(id)}
            >
              {id}
              {entry ? ` · ${entry.observation_count}` : ""}
            </button>
          );
        })}
      </div>
      {series.isPending && <p className="status-msg">{ko.app.loading}</p>}
      {(series.isError || (data && projects.length === 0)) && (
        <p className="desc">{t.kpi_series_empty}</p>
      )}
      {data && projects.length > 0 && (
        <>
          {/* Q4: ≥2 시리즈면 범례 필수 — 색은 프로젝트(entity)에 고정, 필터와 무관 */}
          {projects.length > 1 && (
            <div className="kpi-legend">
              {projects.map((project, index) => (
                <span key={project.project_id} title={project.project_id}>
                  <span
                    className="dot"
                    style={{ background: `var(--chart-${Math.min(index + 1, 4)})` }}
                  />
                  {label(project.project_id)}
                </span>
              ))}
            </div>
          )}
          <KPIChart
            kpiId={data.kpi_id}
            unit={data.unit}
            projects={projects}
            label={label}
            valueLabel={valueLabel}
          />
          <div className="heatmap-scroll">
            <table className="heatmap">
              <thead>
                <tr>
                  <th>{t.kpi_series_week}</th>
                  {projects.map((project) => (
                    <th key={project.project_id} title={project.project_id}>
                      {label(project.project_id)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {weeks.map((week) => (
                  <tr key={week}>
                    <th>W{week}</th>
                    {projects.map((project) => {
                      const point = project.points.find((p) => p.week === week);
                      return (
                        <td
                          key={project.project_id}
                          title={
                            point?.measurement_stage
                              ? `${valueLabel("measurement_stage", point.measurement_stage)} · ${point.observation_id}`
                              : ""
                          }
                        >
                          {point ? `${point.value}${point.unit ?? ""}` : "·"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {projects.map((project) => (
            <p key={project.project_id} className="desc">
              <span className={`badge ${TREND_BADGE[project.trend] ?? "badge-info"}`}>
                {t.kpi_series_trend}: {project.trend_ko}
              </span>{" "}
              {label(project.project_id)} — {project.trend_note_ko}
            </p>
          ))}
        </>
      )}
    </div>
  );
}

/** y축 눈금 — 1/2/5×10^n 근사 (결정론). */
function niceTicks(min: number, max: number, count = 4): number[] {
  const span = max - min;
  if (span <= 0) return [min];
  const raw = span / count;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => count * s >= span) ?? 10 * pow;
  const ticks: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step / 1e6; v += step) {
    ticks.push(Number(v.toFixed(6)));
  }
  return ticks;
}

/**
 * Q4 KPI 라인 차트 — 라이브러리 없는 inline SVG (설계 17 §5).
 * 색은 CSS 변수(--chart-N, 양 테마 검증 팔레트), 텍스트는 텍스트 토큰만 사용.
 * 표가 계약이고 차트는 보조 — 데이터 소스는 표와 동일하다.
 */
function KPIChart({
  kpiId,
  unit,
  projects,
  label,
  valueLabel,
}: {
  kpiId: string;
  unit: string | null | undefined;
  projects: ProjectKPISeries[];
  label: (id: string) => string;
  valueLabel: (domain: string, value: string | null | undefined) => string;
}) {
  const allPoints = projects.flatMap((s) => s.points);
  if (allPoints.length === 0) return null;

  const W = 640;
  const H = 220;
  const m = { top: 10, right: 100, bottom: 26, left: 58 };
  let minW = Math.min(...allPoints.map((p) => p.week));
  let maxW = Math.max(...allPoints.map((p) => p.week));
  if (minW === maxW) {
    minW -= 1;
    maxW += 1;
  }
  let minV = Math.min(...allPoints.map((p) => p.value));
  let maxV = Math.max(...allPoints.map((p) => p.value));
  const pad = (maxV - minV) * 0.12 || Math.abs(maxV) * 0.05 || 1;
  minV -= pad;
  maxV += pad;

  const x = (week: number) => m.left + ((week - minW) / (maxW - minW)) * (W - m.left - m.right);
  const y = (value: number) =>
    H - m.bottom - ((value - minV) / (maxV - minV)) * (H - m.top - m.bottom);
  const yTicks = niceTicks(minV, maxV);
  const xTicks = [...new Set(allPoints.map((p) => p.week))].sort((a, b) => a - b);
  const unitText = unit ?? "";
  const aria = `${kpiId} 시계열 차트 — ${projects
    .map((s) => `${label(s.project_id)} 관측 ${s.points.length}건`)
    .join(", ")}`;

  return (
    <div className="kpi-chart-wrap">
      <svg
        className="kpi-chart"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={aria}
      >
        {yTicks.map((tick) => (
          <g key={tick}>
            <line
              className="grid-line"
              x1={m.left}
              x2={W - m.right}
              y1={y(tick)}
              y2={y(tick)}
            />
            <text className="axis-text" x={m.left - 6} y={y(tick) + 3} textAnchor="end">
              {tick}
            </text>
          </g>
        ))}
        {xTicks.map((week) => (
          <text
            key={week}
            className="axis-text"
            x={x(week)}
            y={H - m.bottom + 16}
            textAnchor="middle"
          >
            W{week}
          </text>
        ))}
        {unitText && (
          <text className="axis-text" x={m.left - 6} y={m.top} textAnchor="end">
            {unitText}
          </text>
        )}
        {projects.map((project, index) => {
          const color = `var(--chart-${Math.min(index + 1, 4)})`;
          const points = project.points;
          const last = points[points.length - 1];
          return (
            <g key={project.project_id}>
              {points.length > 1 && (
                <polyline
                  className="series-line"
                  stroke={color}
                  points={points.map((p) => `${x(p.week)},${y(p.value)}`).join(" ")}
                />
              )}
              {points.map((p) => (
                <g key={p.observation_id}>
                  <circle
                    className="series-dot"
                    cx={x(p.week)}
                    cy={y(p.value)}
                    r={4}
                    fill={color}
                  />
                  {/* hover 히트 타깃 — 마크보다 크게, title=툴팁 */}
                  <circle className="hit-target" cx={x(p.week)} cy={y(p.value)} r={10}>
                    <title>
                      {`${label(project.project_id)} · W${p.week} · ${p.value}${p.unit ?? unitText}` +
                        (p.measurement_stage
                          ? ` · ${valueLabel("measurement_stage", p.measurement_stage)}`
                          : "")}
                    </title>
                  </circle>
                </g>
              ))}
              {/* 선택적 직접 라벨 — 시리즈 끝점에 프로젝트명 (텍스트 토큰 사용) */}
              <text className="end-label" x={x(last.week) + 10} y={y(last.value) + 4}>
                {label(project.project_id)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
