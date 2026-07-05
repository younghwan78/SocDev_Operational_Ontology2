/**
 * 위험 지도 홈 — "지금 어떤 시나리오/IP가 위험한가? 근거는?"에 첫 화면에서 답한다.
 * 행=시나리오, 열=IP/시스템 블록, 셀=정성 등급(●◐○). 모든 등급은 근거 패널로 drill-down.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  fetchProjects,
  fetchRiskHeatmap,
  type BasisItem,
  type ScenarioRiskRow,
  type WeeklyFocusItem,
} from "../api/client";
import { CollapsibleList } from "../components/CollapsibleList";
import { useLabels } from "../hooks/useLabels";
import { ko } from "../i18n/ko";

const t = ko.risk;

const GRADE_SYMBOL: Record<string, string> = { high: "●", medium: "◐", low: "○" };
const GRADE_CLASS: Record<string, string> = {
  high: "risk-high",
  medium: "risk-medium",
  low: "risk-low",
};
const FOCUS_BADGE: Record<string, string> = {
  priority_request: "badge-danger",
  confidence_blocked: "badge-danger",
  schedule_risk: "badge-warn",
};

type Selection = { scenarioId: string; ipId: string | null };

export function RiskMapPage() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const projectId = selectedProject ?? projects.data?.[0]?.id;
  const heatmap = useQuery({
    queryKey: ["risk-heatmap", projectId],
    queryFn: () => fetchRiskHeatmap(projectId),
    enabled: Boolean(projectId),
  });
  const [selection, setSelection] = useState<Selection | null>(null);
  const [askDraft, setAskDraft] = useState("");
  const navigate = useNavigate();
  const label = useLabels();

  if (projects.isPending || heatmap.isPending)
    return <p className="status-msg">{ko.app.loading}</p>;
  if (projects.isError || heatmap.isError)
    return <p className="status-msg">{ko.app.error}</p>;

  const { columns, rows, focus } = heatmap.data;
  const selectedRow = selection
    ? rows.find((row) => row.scenario_id === selection.scenarioId)
    : undefined;

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">
        {t.subtitle} · {t.note}
      </p>

      <form
        className="ask-form home-ask"
        onSubmit={(event) => {
          event.preventDefault();
          if (askDraft.trim()) navigate(`/ask?q=${encodeURIComponent(askDraft.trim())}`);
        }}
      >
        <input
          type="text"
          className="ask-input"
          value={askDraft}
          placeholder={ko.ask.placeholder}
          onChange={(event) => setAskDraft(event.target.value)}
        />
        <button type="submit" className="run-btn" disabled={!askDraft.trim()}>
          {ko.ask.home_search_hint}
        </button>
      </form>

      <div className="filter-row">
        {(projects.data ?? []).map((project) => (
          <button
            key={project.id}
            type="button"
            title={project.id}
            className={`chip chip-btn ${project.id === projectId ? "active" : ""}`}
            onClick={() => {
              setSelectedProject(project.id);
              setSelection(null);
            }}
          >
            {project.name}
          </button>
        ))}
        <span className="legend">
          <span className="risk-high">{GRADE_SYMBOL.high}</span> {t.grade_high}{" "}
          <span className="risk-medium">{GRADE_SYMBOL.medium}</span> {t.grade_medium}{" "}
          <span className="risk-low">{GRADE_SYMBOL.low}</span> {t.grade_low}
        </span>
      </div>

      <div className="risk-layout">
        <div className="card heatmap-card">
          <div className="heatmap-scroll">
            <table className="heatmap">
              <thead>
                <tr>
                  <th className="heatmap-scenario">{t.scenario_column}</th>
                  {columns.map((column) => (
                    <th key={column.ip_id} title={column.ip_id}>
                      {column.ip_name}
                    </th>
                  ))}
                  <th>{t.overall_column}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <HeatmapRow
                    key={row.scenario_id}
                    row={row}
                    columnIds={columns.map((column) => column.ip_id)}
                    selection={selection}
                    onSelect={setSelection}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="risk-side">
          <BasisPanel row={selectedRow} selection={selection} label={label} />
          <FocusCard focus={focus} label={label} />
        </div>
      </div>
    </div>
  );
}

function HeatmapRow({
  row,
  columnIds,
  selection,
  onSelect,
}: {
  row: ScenarioRiskRow;
  columnIds: string[];
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
}) {
  const cellByIp = new Map(row.cells.map((cell) => [cell.ip_id, cell]));
  const isSelected = (ipId: string | null) =>
    selection?.scenarioId === row.scenario_id && selection?.ipId === ipId;
  return (
    <tr>
      <th className="heatmap-scenario" title={row.scenario_id}>
        <button
          type="button"
          className={`cell-btn scenario-name ${isSelected(null) ? "cell-selected" : ""}`}
          onClick={() => onSelect({ scenarioId: row.scenario_id, ipId: null })}
        >
          {row.scenario_name}
        </button>
      </th>
      {columnIds.map((ipId) => {
        const cell = cellByIp.get(ipId);
        if (!cell)
          return (
            <td key={ipId} className="heatmap-na" title={t.not_applicable}>
              ·
            </td>
          );
        return (
          <td key={ipId}>
            <button
              type="button"
              title={`${cell.grade_ko} — ${row.scenario_id} × ${ipId}`}
              className={`cell-btn ${GRADE_CLASS[cell.grade]} ${
                isSelected(ipId) ? "cell-selected" : ""
              }`}
              onClick={() => onSelect({ scenarioId: row.scenario_id, ipId })}
            >
              {GRADE_SYMBOL[cell.grade]}
            </button>
          </td>
        );
      })}
      <td>
        <button
          type="button"
          title={`${row.overall_grade_ko} — ${row.scenario_id}`}
          className={`cell-btn ${GRADE_CLASS[row.overall_grade]} ${
            isSelected(null) ? "cell-selected" : ""
          }`}
          onClick={() => onSelect({ scenarioId: row.scenario_id, ipId: null })}
        >
          {GRADE_SYMBOL[row.overall_grade]}
        </button>
      </td>
    </tr>
  );
}

function BasisPanel({
  row,
  selection,
  label,
}: {
  row: ScenarioRiskRow | undefined;
  selection: Selection | null;
  label: (id: string) => string;
}) {
  if (!row || !selection) {
    return (
      <div className="card">
        <h2 className="card-title">{t.panel_title}</h2>
        <p className="desc">{t.panel_hint}</p>
      </div>
    );
  }
  const cell = selection.ipId
    ? row.cells.find((candidate) => candidate.ip_id === selection.ipId)
    : undefined;
  const grade = cell ? cell.grade : row.overall_grade;
  const gradeKo = cell ? cell.grade_ko : row.overall_grade_ko;
  const basis = cell ? cell.basis : row.overall_basis;
  const scope = selection.ipId ? label(selection.ipId) : t.panel_overall;

  return (
    <div className="card">
      <h2 className="card-title">{t.panel_title}</h2>
      <div className="head">
        <span className={`badge ${GRADE_CLASS[grade]}-badge`}>{gradeKo}</span>
        <span className="title" title={row.scenario_id}>
          {row.scenario_name} · {scope}
        </span>
      </div>
      <CollapsibleList
        items={basis}
        limit={5}
        render={(item: BasisItem, index: number) => (
          <div key={`${item.rule}-${item.ref_id}-${index}`} className="list-item">
            <div className="head">
              <span className="badge badge-info">{item.rule_ko}</span>
            </div>
            <p className="desc" title={item.ref_id}>
              {item.description}
            </p>
          </div>
        )}
      />
      <Link to={`/scenarios/${row.scenario_id}/overview`} className="chip-link">
        {t.open_scenario}
      </Link>
    </div>
  );
}

function FocusCard({
  focus,
  label,
}: {
  focus: WeeklyFocusItem[];
  label: (id: string) => string;
}) {
  return (
    <div className="card">
      <h2 className="card-title">{t.focus_title}</h2>
      {focus.length === 0 && <p className="desc">{t.focus_empty}</p>}
      {focus.map((item, index) => (
        <div key={`${item.ref_id}-${index}`} className="list-item">
          <div className="head">
            <span className={`badge ${FOCUS_BADGE[item.kind] ?? "badge-info"}`}>
              {item.kind_ko}
            </span>
            <span className="title" title={item.ref_id}>
              {item.title}
            </span>
          </div>
          <p className="desc">{item.description}</p>
          {(item.scenario_ids ?? []).length > 0 && (
            <p className="desc">
              {t.related_scenarios}:{" "}
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
        </div>
      ))}
    </div>
  );
}
