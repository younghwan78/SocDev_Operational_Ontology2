/**
 * 위험 지도 홈 — "지금 어떤 시나리오/IP가 위험한가? 근거는?"에 첫 화면에서 답한다.
 * 행=시나리오, 열=IP/시스템 블록, 셀=정성 등급(●◐○). 모든 등급은 근거 패널로 drill-down.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  fetchProjects,
  fetchRiskHeatmap,
  type BasisItem,
  type HeatmapColumn,
  type ScenarioRiskRow,
  type WeeklyFocusItem,
} from "../api/client";
import { CollapsibleList } from "../components/CollapsibleList";
import { PostureChip } from "../components/PostureChip";
import { useLabels } from "../hooks/useLabels";
import { useValueLabels } from "../hooks/useValueLabels";
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

/** 카테고리 열 그룹 — 백엔드가 카테고리 순으로 정렬해 내려주므로 연속 구간으로 묶인다. */
function groupColumns(columns: HeatmapColumn[]) {
  const groups: { category: string; columns: HeatmapColumn[] }[] = [];
  for (const column of columns) {
    const last = groups[groups.length - 1];
    if (last && last.category === column.category) last.columns.push(column);
    else groups.push({ category: column.category, columns: [column] });
  }
  return groups;
}

/** 열 카테고리 시각 클래스 — 미지의 카테고리는 무틴트. */
const CAT_CLASS: Record<string, string> = {
  functional_mm_ip: "cat-func",
  compute_ip: "cat-comp",
  system_influence_block: "cat-sys",
};

export function RiskMapPage() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  // URL=상태: 탭/선택/등급 필터를 URL에 반영 — 새로고침·공유가 화면을 재현한다.
  const [searchParams, setSearchParams] = useSearchParams();
  const projectId = searchParams.get("project") ?? projects.data?.[0]?.id;
  const gradeFilter = searchParams.get("grade") ?? "all";
  const cellParam = searchParams.get("cell");
  const selection: Selection | null = cellParam
    ? {
        scenarioId: cellParam.split(":")[0],
        ipId: cellParam.split(":")[1] === "overall" ? null : (cellParam.split(":")[1] ?? null),
      }
    : null;
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
  const setSelection = (next: Selection | null) =>
    updateParams({ cell: next ? `${next.scenarioId}:${next.ipId ?? "overall"}` : null });
  const heatmap = useQuery({
    queryKey: ["risk-heatmap", projectId],
    queryFn: () => fetchRiskHeatmap(projectId),
    enabled: Boolean(projectId),
  });
  const [askDraft, setAskDraft] = useState("");
  const navigate = useNavigate();
  const label = useLabels();
  const valueLabel = useValueLabels();

  if (projects.isPending || heatmap.isPending)
    return <p className="status-msg">{ko.app.loading}</p>;
  if (projects.isError || heatmap.isError)
    return <p className="status-msg">{ko.app.error}</p>;

  const { columns, rows, focus } = heatmap.data;
  const columnGroups = groupColumns(columns);
  // 그룹 경계 열 인덱스 — 좌측 구분선으로 카테고리 경계를 표시한다.
  const catStarts = new Set<number>();
  let offset = 0;
  for (const group of columnGroups) {
    if (offset > 0) catStarts.add(offset);
    offset += group.columns.length;
  }
  const visibleRows =
    gradeFilter === "high"
      ? rows.filter((row) => row.overall_grade === "high")
      : gradeFilter === "medium"
        ? rows.filter((row) => row.overall_grade !== "low")
        : rows;
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
            onClick={() => updateParams({ project: project.id, cell: null })}
          >
            {project.name}
          </button>
        ))}
      </div>

      <div className="risk-layout">
        <div className="card heatmap-card">
          <div className="head heatmap-toolbar">
            <span className="legend">
              <span className="risk-high">{GRADE_SYMBOL.high}</span> {t.grade_high}{" "}
              <span className="risk-medium">{GRADE_SYMBOL.medium}</span> {t.grade_medium}{" "}
              <span className="risk-low">{GRADE_SYMBOL.low}</span> {t.grade_low}
            </span>
            {(
              [
                ["all", t.grade_filter_all],
                ["medium", t.grade_filter_medium_up],
                ["high", t.grade_filter_high],
              ] as const
            ).map(([value, chipLabel]) => (
              <button
                key={value}
                type="button"
                className={`chip chip-btn ${gradeFilter === value ? "active" : ""}`}
                onClick={() => updateParams({ grade: value === "all" ? null : value })}
              >
                {chipLabel}
              </button>
            ))}
          </div>
          <div className="heatmap-scroll">
            <table className="heatmap">
              <thead>
                <tr className="cat-row">
                  <th className="heatmap-scenario" rowSpan={2}>
                    {t.scenario_column}
                  </th>
                  {columnGroups.map((group) => (
                    <th
                      key={group.category}
                      colSpan={group.columns.length}
                      className={`cat-head ${CAT_CLASS[group.category] ?? ""}`}
                      title={group.category}
                    >
                      {valueLabel("ip_category", group.category)}
                    </th>
                  ))}
                  <th className="heatmap-overall" rowSpan={2}>
                    {t.overall_column}
                  </th>
                </tr>
                <tr className="col-row">
                  {columns.map((column, index) => (
                    <th
                      key={column.ip_id}
                      title={column.ip_id}
                      className={`${CAT_CLASS[column.category] ?? ""} ${
                        catStarts.has(index) ? "cat-start" : ""
                      }`}
                    >
                      {column.ip_name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => (
                  <HeatmapRow
                    key={row.scenario_id}
                    row={row}
                    columns={columns}
                    catStarts={catStarts}
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
  columns,
  catStarts,
  selection,
  onSelect,
}: {
  row: ScenarioRiskRow;
  columns: HeatmapColumn[];
  catStarts: Set<number>;
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
        {row.evidence_posture && (
          <PostureChip
            measured={row.evidence_posture.measured}
            predicted={row.evidence_posture.predicted}
            absent={row.evidence_posture.absent}
            note={row.evidence_posture.note_ko}
          />
        )}
      </th>
      {columns.map((column, index) => {
        const ipId = column.ip_id;
        const tdClass = `${CAT_CLASS[column.category] ?? ""} ${
          catStarts.has(index) ? "cat-start" : ""
        }`;
        const cell = cellByIp.get(ipId);
        if (!cell)
          return (
            <td key={ipId} className={`heatmap-na ${tdClass}`} title={t.not_applicable}>
              ·
            </td>
          );
        return (
          <td key={ipId} className={tdClass}>
            <button
              type="button"
              title={`${cell.grade_ko} — ${row.scenario_id} × ${ipId}`}
              aria-label={`${row.scenario_name} × ${ipId} ${cell.grade_ko}`}
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
      <td className="heatmap-overall">
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
      {row.evidence_posture && (
        <p className="desc">
          {t.posture}: {t.posture_measured} {row.evidence_posture.measured} ·{" "}
          {t.posture_predicted} {row.evidence_posture.predicted} · {t.posture_absent}{" "}
          {row.evidence_posture.absent} — {row.evidence_posture.note_ko}
        </p>
      )}
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
