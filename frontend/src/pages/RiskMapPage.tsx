/**
 * 위험 지도 홈 — "지금 어떤 시나리오/IP가 위험한가? 근거는?"에 첫 화면에서 답한다.
 * 행=시나리오, 열=IP/시스템 블록, 셀=정성 등급(●◐○). 모든 등급은 근거 패널로 drill-down.
 */
import { useQuery } from "@tanstack/react-query";
import { useState, type CSSProperties } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  fetchAsOfRiskHeatmap,
  fetchProjects,
  fetchRiskHeatmap,
  fetchWhatIfCandidates,
  runWhatIf,
  type AsOfMeta,
  type BasisItem,
  type HeatmapColumn,
  type RiskHeatmap,
  type ScenarioRiskRow,
  type WeeklyFocusItem,
  type WhatIfAssumptionInput,
  type WhatIfCandidate,
  type WhatIfResult,
  type WhatIfRowChange,
} from "../api/client";
import { CollapsibleList } from "../components/CollapsibleList";
import { PostureChip } from "../components/PostureChip";
import { SplitHandle, useSidePanelWidth } from "../components/SplitLayout";
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

const WHATIF_LIMIT = 10;

/** URL `whatif` 파라미터 → 가정 배열 — 파싱 실패는 빈 세트로 취급 (URL=상태). */
function parseWhatIfParam(raw: string | null): WhatIfAssumptionInput[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is WhatIfAssumptionInput =>
        typeof item === "object" && item !== null && "kind" in item && "target_id" in item,
    );
  } catch {
    return [];
  }
}

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
  // P2 T3 as-of: URL의 asof(datetime-local 값)가 있으면 시점 재구성 뷰로 전환.
  const asOfParam = searchParams.get("asof");
  const asOfTs = asOfParam ? new Date(asOfParam).toISOString() : null;
  // W2 (설계 18) 가정 실험 워크벤치: URL whatif=가정 세트(JSON) — 링크 공유가 곧 재현.
  const whatIfParam = searchParams.get("whatif");
  const assumptions = parseWhatIfParam(whatIfParam);
  const [panelOpen, setPanelOpen] = useState(assumptions.length > 0);
  const setAssumptions = (next: WhatIfAssumptionInput[]) =>
    // asof와 상호 배타 (설계 18 §4) — 과거 상태 위에 가정을 얹지 않는다.
    updateParams({ whatif: next.length > 0 ? JSON.stringify(next) : null, asof: null });
  const whatIf = useQuery<WhatIfResult>({
    queryKey: ["whatif-run", whatIfParam],
    queryFn: () => runWhatIf(assumptions),
    enabled: assumptions.length > 0 && !asOfTs,
  });
  const candidates = useQuery({
    queryKey: ["whatif-candidates", projectId],
    queryFn: () => fetchWhatIfCandidates(projectId),
    enabled: panelOpen && Boolean(projectId),
  });
  const heatmap = useQuery<{ heatmap: RiskHeatmap; meta: AsOfMeta | null }>({
    queryKey: ["risk-heatmap", projectId, asOfTs],
    queryFn: async () => {
      if (asOfTs) {
        const result = await fetchAsOfRiskHeatmap(asOfTs, projectId);
        return { heatmap: result.heatmap, meta: result.meta };
      }
      return { heatmap: await fetchRiskHeatmap(projectId), meta: null };
    },
    enabled: Boolean(projectId),
  });
  const [askDraft, setAskDraft] = useState("");
  const navigate = useNavigate();
  const label = useLabels();
  const valueLabel = useValueLabels();
  const sidePanel = useSidePanelWidth("risk-side-width");

  if (projects.isPending || heatmap.isPending)
    return <p className="status-msg">{ko.app.loading}</p>;
  if (projects.isError || heatmap.isError)
    return <p className="status-msg">{ko.app.error}</p>;

  const { columns, rows, focus } = heatmap.data.heatmap;
  const asOfMeta = heatmap.data.meta;
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
  // 가정 오버레이 — 변경 행만 투영 표기, 나머지는 평소와 동일 (정직한 구분).
  const whatIfResult = assumptions.length > 0 && !asOfTs ? whatIf.data : undefined;
  const changedRowById = new Map<string, WhatIfRowChange>(
    (whatIfResult?.changed_rows ?? []).map((change) => [change.scenario_id, change]),
  );
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
        <label className="filter-label" htmlFor="asof-input">
          {t.asof_label}
        </label>
        <input
          id="asof-input"
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
            {t.asof_clear}
          </button>
        )}
        <button
          type="button"
          className={`chip chip-btn ${panelOpen || assumptions.length > 0 ? "active" : ""}`}
          onClick={() => setPanelOpen(!panelOpen)}
        >
          ⚗ {t.whatif_toggle}
          {assumptions.length > 0 ? ` · ${assumptions.length}` : ""}
        </button>
      </div>

      {/* as-of 정직성 배너 — 무엇이 사실이고 무엇이 가정/근사인지 숨기지 않는다 */}
      {asOfMeta && (
        <p className="section-note rca-banner">
          ⏱ {t.asof_banner}: {new Date(asOfMeta.as_of).toLocaleString("ko-KR")} —{" "}
          {t.asof_replayed} {asOfMeta.replayed_versions} · {t.asof_assumed}{" "}
          {asOfMeta.precapture_assumed_objects} · {t.asof_approx}{" "}
          {asOfMeta.approximated_objects} · {t.asof_excluded} {asOfMeta.excluded_objects}
          <br />
          {asOfMeta.note_ko}
        </p>
      )}

      {/* 가정 실험 배너 — 실데이터가 아님을 상시 명시 (설계 18 §4) */}
      {assumptions.length > 0 && asOfTs && (
        <p className="section-note rca-banner">⚗ {t.whatif_asof_conflict}</p>
      )}
      {assumptions.length > 0 && !asOfTs && (
        <p className="section-note rca-banner">
          ⚗ {assumptions.length}
          {t.whatif_banner}
          {whatIfResult && (
            <>
              {" "}
              · {t.whatif_result_changed} {whatIfResult.changed_rows.length} ·{" "}
              {t.whatif_result_unchanged} {whatIfResult.unchanged_scenario_count}
            </>
          )}
        </p>
      )}

      {panelOpen && (
        <WhatIfWorkbench
          candidates={candidates.data?.candidates ?? []}
          candidatesNote={candidates.data?.note_ko}
          candidatesPending={candidates.isPending}
          assumptions={assumptions}
          result={whatIfResult}
          resultPending={assumptions.length > 0 && !asOfTs && whatIf.isPending}
          rows={rows}
          columns={columns}
          onChange={setAssumptions}
        />
      )}

      <div
        className="risk-layout risk-layout-split"
        style={{ "--side-w": `${sidePanel.width}px` } as CSSProperties}
      >
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
                    change={changedRowById.get(row.scenario_id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <SplitHandle
          width={sidePanel.width}
          onResize={sidePanel.update}
          onReset={sidePanel.reset}
          label={t.panel_resize}
        />
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
  change,
}: {
  row: ScenarioRiskRow;
  columns: HeatmapColumn[];
  catStarts: Set<number>;
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
  change?: WhatIfRowChange;
}) {
  const cellByIp = new Map(row.cells.map((cell) => [cell.ip_id, cell]));
  // W2 가정 오버레이 — 투영 등급은 기준과 항상 구분 표기한다 (점선 링 + title).
  const projectedByIp = new Map((change?.changed_cells ?? []).map((c) => [c.ip_id, c]));
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
        const projected = projectedByIp.get(ipId);
        if (projected)
          return (
            <td key={ipId} className={tdClass}>
              <button
                type="button"
                title={`${t.whatif_projected_cell}: ${projected.baseline_grade_ko} → ${projected.projected_grade_ko} — ${row.scenario_id} × ${ipId}`}
                aria-label={`${row.scenario_name} × ${ipId} ${t.whatif_projected_cell}: ${projected.baseline_grade_ko} → ${projected.projected_grade_ko}`}
                className={`cell-btn cell-projected ${GRADE_CLASS[projected.projected_grade]} ${
                  isSelected(ipId) ? "cell-selected" : ""
                }`}
                onClick={() => onSelect({ scenarioId: row.scenario_id, ipId })}
              >
                {GRADE_SYMBOL[projected.projected_grade]}
              </button>
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
        {change && change.projected_grade !== change.baseline_grade ? (
          <button
            type="button"
            title={`${t.whatif_projected_cell}: ${change.baseline_grade_ko} → ${change.projected_grade_ko} — ${row.scenario_id}`}
            className={`cell-btn cell-projected ${GRADE_CLASS[change.projected_grade]} ${
              isSelected(null) ? "cell-selected" : ""
            }`}
            onClick={() => onSelect({ scenarioId: row.scenario_id, ipId: null })}
          >
            {GRADE_SYMBOL[change.projected_grade]}
          </button>
        ) : (
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
        )}
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

const GRADE_BADGE: Record<string, string> = {
  high: "risk-high-badge",
  medium: "risk-medium-badge",
  low: "risk-low-badge",
};

/** W2 (설계 18) — 가정 실험 워크벤치: 후보 제안 + 바스켓 + 신규 이슈 주입 폼. */
function WhatIfWorkbench({
  candidates,
  candidatesNote,
  candidatesPending,
  assumptions,
  result,
  resultPending,
  rows,
  columns,
  onChange,
}: {
  candidates: WhatIfCandidate[];
  candidatesNote?: string;
  candidatesPending: boolean;
  assumptions: WhatIfAssumptionInput[];
  result?: WhatIfResult;
  resultPending: boolean;
  rows: ScenarioRiskRow[];
  columns: HeatmapColumn[];
  onChange: (next: WhatIfAssumptionInput[]) => void;
}) {
  const valueLabel = useValueLabels();
  // week-shift 후보의 delta 조정값 — 추가 전 로컬 상태 (기본값은 후보가 제공).
  const [deltas, setDeltas] = useState<Record<string, string>>({});
  const [issueTitle, setIssueTitle] = useState("");
  const [scenarioSel, setScenarioSel] = useState<string[]>([]);
  const [ipSel, setIpSel] = useState<string[]>([]);
  const [severity, setSeverity] = useState("high");

  const limitReached = assumptions.length >= WHATIF_LIMIT;
  const isAdded = (candidate: WhatIfCandidate) =>
    assumptions.some(
      (a) => a.kind === candidate.kind && a.target_id === candidate.target_id,
    );
  const addCandidate = (candidate: WhatIfCandidate) => {
    const delta =
      candidate.kind === "issue_week_shift"
        ? Number(deltas[candidate.id] ?? candidate.week_delta ?? -2)
        : undefined;
    onChange([
      ...assumptions,
      {
        kind: candidate.kind,
        target_id: candidate.target_id,
        value: candidate.value ?? undefined,
        week_delta: Number.isFinite(delta) ? delta : candidate.week_delta,
        note: candidate.label_ko,
      },
    ]);
  };
  const removeAt = (index: number) =>
    onChange(assumptions.filter((_, i) => i !== index));
  const toggle = (list: string[], id: string, set: (next: string[]) => void) =>
    set(list.includes(id) ? list.filter((v) => v !== id) : [...list, id]);
  const submitNewIssue = () => {
    if (!issueTitle.trim() || scenarioSel.length === 0 || ipSel.length === 0) return;
    onChange([
      ...assumptions,
      {
        kind: "new_issue",
        target_id: `whatif_new_${Date.now().toString(36)}`,
        title: issueTitle.trim(),
        scenario_ids: scenarioSel,
        ip_ids: ipSel,
        severity,
        note: issueTitle.trim(),
      },
    ]);
    setIssueTitle("");
    setScenarioSel([]);
    setIpSel([]);
  };
  // 에코가 현재 가정 세트와 정합할 때만 에코 라벨 사용 (stale 응답 방지).
  const echo =
    result && result.assumptions.length === assumptions.length
      ? result.assumptions
      : null;

  return (
    <div className="card whatif-workbench">
      <div className="head">
        <h2 className="card-title">⚗ {t.whatif_panel_title}</h2>
        <span className="badge badge-warn">{ko.issues.whatif_assumption_badge}</span>
      </div>
      <p className="section-note">{t.whatif_panel_note}</p>

      <h3 className="card-subtitle">{t.whatif_active_title}</h3>
      {assumptions.length === 0 && <p className="desc">{t.whatif_active_empty}</p>}
      {assumptions.map((assumption, index) => (
        <div key={`${assumption.kind}-${assumption.target_id}-${index}`} className="list-item">
          <div className="head">
            <span className="badge badge-warn">
              {echo ? echo[index].kind_ko : assumption.kind}
            </span>
            <span className="title" title={assumption.target_id}>
              {echo ? echo[index].target_title : assumption.target_id}
            </span>
            {echo && (
              <span className="desc">
                {echo[index].from_value ?? "—"} → {echo[index].to_value}
              </span>
            )}
            <button
              type="button"
              className="chip chip-btn"
              aria-label={t.whatif_remove}
              onClick={() => removeAt(index)}
            >
              ✕
            </button>
          </div>
          {assumption.note && <p className="desc">{assumption.note}</p>}
        </div>
      ))}
      {limitReached && <p className="desc">{t.whatif_limit_note}</p>}
      {assumptions.length > 0 && (
        <button type="button" className="chip chip-btn" onClick={() => onChange([])}>
          {t.whatif_clear_all}
        </button>
      )}

      {resultPending && <p className="status-msg">{ko.app.loading}</p>}
      {result && assumptions.length > 0 && (
        <div>
          {result.changed_rows.length === 0 && (
            <p className="desc">
              {t.whatif_result_no_change} ({t.whatif_result_unchanged}:{" "}
              {result.unchanged_scenario_count})
            </p>
          )}
          {(result.changed_issue_signals ?? []).length > 0 && (
            <div>
              <h3 className="card-subtitle">{t.whatif_signals_title}</h3>
              {(result.changed_issue_signals ?? []).map((signal) => (
                <p key={signal.issue_id} className="desc" title={signal.issue_id}>
                  {signal.title}
                  {signal.appeared
                    ? ` — ${t.whatif_appeared}`
                    : `: ${(signal.changes ?? []).join(" · ")}`}
                  {signal.projected_note_ko ? ` (${signal.projected_note_ko})` : ""}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      <h3 className="card-subtitle">{t.whatif_candidates_title}</h3>
      {candidatesPending && <p className="status-msg">{ko.app.loading}</p>}
      {!candidatesPending && candidates.length === 0 && (
        <p className="desc">{t.whatif_candidates_empty}</p>
      )}
      <div className="whatif-cand-list">
        {candidates.map((candidate) => (
          <div key={candidate.id} className="list-item">
            <div className="head">
              <span className="badge badge-info">{candidate.rule_ko}</span>
              <span className="title" title={candidate.target_id}>
                {candidate.target_title}
              </span>
              {candidate.kind === "issue_week_shift" && (
                <label className="filter-label">
                  {t.whatif_week_delta}
                  <input
                    type="number"
                    className="whatif-delta-input"
                    value={deltas[candidate.id] ?? String(candidate.week_delta ?? -2)}
                    onChange={(event) =>
                      setDeltas({ ...deltas, [candidate.id]: event.target.value })
                    }
                  />
                </label>
              )}
              <button
                type="button"
                className="chip chip-btn"
                disabled={isAdded(candidate) || limitReached}
                onClick={() => addCandidate(candidate)}
              >
                {isAdded(candidate) ? t.whatif_added : t.whatif_add}
              </button>
            </div>
            <p className="desc">
              {candidate.label_ko} — {candidate.basis_note_ko}
            </p>
          </div>
        ))}
      </div>
      {candidatesNote && <p className="section-note">{candidatesNote}</p>}

      <h3 className="card-subtitle">{t.whatif_new_issue_title}</h3>
      <p className="section-note">{t.whatif_new_issue_note}</p>
      <input
        type="text"
        className="search-input whatif-title-input"
        placeholder={t.whatif_new_issue_label}
        value={issueTitle}
        onChange={(event) => setIssueTitle(event.target.value)}
      />
      <p className="desc">{t.whatif_new_issue_scenarios}</p>
      <div className="filter-row">
        {rows.map((row) => (
          <button
            key={row.scenario_id}
            type="button"
            title={row.scenario_id}
            className={`chip chip-btn ${scenarioSel.includes(row.scenario_id) ? "active" : ""}`}
            onClick={() => toggle(scenarioSel, row.scenario_id, setScenarioSel)}
          >
            {row.scenario_name}
          </button>
        ))}
      </div>
      <p className="desc">{t.whatif_new_issue_ips}</p>
      <div className="filter-row">
        {columns.map((column) => (
          <button
            key={column.ip_id}
            type="button"
            title={column.ip_id}
            className={`chip chip-btn ${ipSel.includes(column.ip_id) ? "active" : ""}`}
            onClick={() => toggle(ipSel, column.ip_id, setIpSel)}
          >
            {column.ip_name}
          </button>
        ))}
      </div>
      <p className="desc">{t.whatif_new_issue_severity}</p>
      <div className="filter-row">
        {["high", "medium", "low"].map((value) => (
          <button
            key={value}
            type="button"
            className={`chip chip-btn ${severity === value ? "active" : ""}`}
            onClick={() => setSeverity(value)}
          >
            <span className={`badge ${GRADE_BADGE[value]}`}>
              {valueLabel("severity", value)}
            </span>
          </button>
        ))}
      </div>
      <button
        type="button"
        className="run-btn"
        disabled={
          !issueTitle.trim() || scenarioSel.length === 0 || ipSel.length === 0 || limitReached
        }
        onClick={submitNewIssue}
      >
        {t.whatif_new_issue_submit}
      </button>
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
