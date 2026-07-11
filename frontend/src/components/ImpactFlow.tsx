/**
 * 영향 전파 지도 (G1) — 변경 영향 결과를 계층형 흐름 그래프로 렌더링.
 *
 *   [연쇄 IP] ↔ [분석 대상] → [영향 시나리오] → [영향 KPI]
 *
 * 순수 SVG(간선) + 절대 배치 HTML 버튼(노드) — 외부 그래프 라이브러리 없음.
 * 간선 = 근거 규칙(색 구분): 근거 없는 연결은 백엔드가 만들지 않으므로 간선도 없다.
 * 노드 클릭 → 상세/근거 패널 (hover 시 연결 경로만 강조).
 */
import { useLayoutEffect, useRef, useState } from "react";
import type { ChangeImpactResult } from "../api/client";
import { ko } from "../i18n/ko";

const t = ko.change_impact;

export type FlowNodeId = string; // "subject" | "sc:<id>" | "kpi:<id>" | "dep:<rule_id>"

const MAX_COLUMN_NODES = 18;
const ROW_H = 46;
const NODE_H = 36;
const PAD_TOP = 30;
const PAD_BOTTOM = 10;
const MIN_WIDTH = 640;

// 열 배치 (컨테이너 폭 비율) — 간선이 보이도록 열 사이 여백을 남긴다.
const COLS = {
  dep: { x: 0.0, w: 0.15 },
  subject: { x: 0.2, w: 0.16 },
  scenario: { x: 0.42, w: 0.28 },
  kpi: { x: 0.77, w: 0.23 },
} as const;

type NodeBox = {
  id: FlowNodeId;
  kind: "dep" | "subject" | "scenario" | "kpi";
  label: string;
  meta?: string;
  aria: string;
  x: number;
  y: number;
  w: number;
};

type Edge = {
  key: string;
  from: FlowNodeId;
  to: FlowNodeId;
  cls: string;
  arrow?: boolean;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

const REASON_EDGE_CLASS: Record<string, string> = {
  ip_requirement: "edge-req",
  knob_related: "edge-knob",
  uses_ip: "edge-uses",
};

function bezier(edge: Edge): string {
  const dx = (edge.x2 - edge.x1) * 0.45;
  return `M ${edge.x1} ${edge.y1} C ${edge.x1 + dx} ${edge.y1}, ${edge.x2 - dx} ${edge.y2}, ${edge.x2} ${edge.y2}`;
}

export function ImpactFlow({
  result,
  label,
  selected,
  onSelect,
}: {
  result: ChangeImpactResult;
  label: (id: string) => string;
  selected: FlowNodeId | null;
  onSelect: (id: FlowNodeId | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(MIN_WIDTH);
  const [hovered, setHovered] = useState<FlowNodeId | null>(null);

  useLayoutEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const measure = () => setWidth(Math.max(element.clientWidth, MIN_WIDTH));
    measure();
    if (typeof ResizeObserver === "undefined") return; // jsdom 등
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const scenarios = result.impacted_scenarios.slice(0, MAX_COLUMN_NODES);
  const kpis = result.impacted_kpis.slice(0, MAX_COLUMN_NODES);
  const deps = result.chained_ips.slice(0, MAX_COLUMN_NODES);
  const truncated =
    result.impacted_scenarios.length > scenarios.length ||
    result.impacted_kpis.length > kpis.length ||
    result.chained_ips.length > deps.length;

  const maxRows = Math.max(1, deps.length, scenarios.length, kpis.length);
  const height = PAD_TOP + maxRows * ROW_H + PAD_BOTTOM;
  const columnY = (count: number, index: number) =>
    PAD_TOP + ((maxRows - count) * ROW_H) / 2 + index * ROW_H + (ROW_H - NODE_H) / 2;

  const col = (key: keyof typeof COLS) => ({
    x: COLS[key].x * width,
    w: COLS[key].w * width,
  });

  // ---- 노드 배치 ----
  const nodes: NodeBox[] = [];
  const subjectCol = col("subject");
  const subjectNode: NodeBox = {
    id: "subject",
    kind: "subject",
    label: result.subject.ip_name,
    meta: [
      result.subject.knob?.name,
      result.subject.capability?.name,
      result.subject.mode ?? undefined,
    ]
      .filter(Boolean)
      .join(" · "),
    aria: `${t.col_subject}: ${result.subject.summary}`,
    x: subjectCol.x,
    y: columnY(1, 0),
    w: subjectCol.w,
  };
  nodes.push(subjectNode);

  const depCol = col("dep");
  deps.forEach((dep, index) => {
    nodes.push({
      id: `dep:${dep.rule_id}`,
      kind: "dep",
      label: dep.ip_name,
      aria: `${t.quadrant_chained}: ${dep.ip_name} — ${dep.direction_ko}`,
      x: depCol.x,
      y: columnY(deps.length, index),
      w: depCol.w,
    });
  });

  const scenarioCol = col("scenario");
  scenarios.forEach((scenario, index) => {
    nodes.push({
      id: `sc:${scenario.scenario_id}`,
      kind: "scenario",
      label: scenario.scenario_name,
      meta: `${scenario.reasons.length}`,
      aria: `${t.quadrant_scenarios}: ${scenario.scenario_name} (${t.reasons} ${scenario.reasons.length})`,
      x: scenarioCol.x,
      y: columnY(scenarios.length, index),
      w: scenarioCol.w,
    });
  });

  const kpiCol = col("kpi");
  kpis.forEach((kpi, index) => {
    nodes.push({
      id: `kpi:${kpi.kpi_id}`,
      kind: "kpi",
      label: label(kpi.kpi_id),
      meta: kpi.via_knob ? "★" : undefined,
      aria: `${t.quadrant_kpis}: ${label(kpi.kpi_id)}${kpi.via_knob ? ` (${t.via_knob})` : ""}`,
      x: kpiCol.x,
      y: columnY(kpis.length, index),
      w: kpiCol.w,
    });
  });

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const center = (node: NodeBox) => node.y + NODE_H / 2;

  // ---- 간선 ----
  const edges: Edge[] = [];
  for (const dep of deps) {
    const node = byId.get(`dep:${dep.rule_id}`);
    if (!node) continue;
    const incoming = dep.direction === "incoming"; // 선택 IP에 의존 → 대상으로 향하는 화살표
    edges.push({
      key: `dep-${dep.rule_id}`,
      from: incoming ? node.id : "subject",
      to: incoming ? "subject" : node.id,
      cls: "edge-dep",
      arrow: true,
      x1: incoming ? node.x + node.w : subjectNode.x,
      y1: incoming ? center(node) : center(subjectNode),
      x2: incoming ? subjectNode.x : node.x + node.w,
      y2: incoming ? center(subjectNode) : center(node),
    });
  }
  const scenarioSet = new Set(scenarios.map((scenario) => scenario.scenario_id));
  for (const scenario of scenarios) {
    const node = byId.get(`sc:${scenario.scenario_id}`);
    if (!node) continue;
    const rule = scenario.reasons[0]?.rule ?? "uses_ip";
    edges.push({
      key: `sc-${scenario.scenario_id}`,
      from: "subject",
      to: node.id,
      cls: REASON_EDGE_CLASS[rule] ?? "edge-uses",
      x1: subjectNode.x + subjectNode.w,
      y1: center(subjectNode),
      x2: node.x,
      y2: center(node),
    });
  }
  for (const kpi of kpis) {
    const kpiNode = byId.get(`kpi:${kpi.kpi_id}`);
    if (!kpiNode) continue;
    for (const scenarioId of kpi.scenario_ids ?? []) {
      if (!scenarioSet.has(scenarioId)) continue;
      const scenarioNode = byId.get(`sc:${scenarioId}`);
      if (!scenarioNode) continue;
      edges.push({
        key: `kpi-${kpi.kpi_id}-${scenarioId}`,
        from: scenarioNode.id,
        to: kpiNode.id,
        cls: "edge-kpi",
        x1: scenarioNode.x + scenarioNode.w,
        y1: center(scenarioNode),
        x2: kpiNode.x,
        y2: center(kpiNode),
      });
    }
    if (kpi.via_knob) {
      edges.push({
        key: `viaknob-${kpi.kpi_id}`,
        from: "subject",
        to: kpiNode.id,
        cls: "edge-viaknob",
        x1: subjectNode.x + subjectNode.w,
        y1: center(subjectNode),
        x2: kpiNode.x,
        y2: center(kpiNode),
      });
    }
  }

  // ---- hover 강조: 연결된 노드/간선만 남기고 감쇠 ----
  const focus = hovered ?? selected;
  let visibleNodes: Set<FlowNodeId> | null = null;
  if (focus && byId.has(focus)) {
    visibleNodes = new Set([focus]);
    for (const edge of edges) {
      if (edge.from === focus) visibleNodes.add(edge.to);
      if (edge.to === focus) visibleNodes.add(edge.from);
    }
  }
  const nodeDimmed = (id: FlowNodeId) => (visibleNodes ? !visibleNodes.has(id) : false);
  const edgeDimmed = (edge: Edge) =>
    visibleNodes ? !(edge.from === focus || edge.to === focus) : false;

  const columnHeaders = [
    { key: "dep", label: t.quadrant_chained, count: result.chained_ips.length },
    { key: "subject", label: t.col_subject, count: null },
    { key: "scenario", label: t.quadrant_scenarios, count: result.impacted_scenarios.length },
    { key: "kpi", label: t.quadrant_kpis, count: result.impacted_kpis.length },
  ] as const;

  return (
    <div>
      <div ref={containerRef} className="flow-canvas" style={{ height }}>
        <svg
          className="flow-edges"
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          aria-hidden="true"
        >
          <defs>
            <marker
              id="flow-arrow"
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 8 4 L 0 8 z" className="flow-arrow-head" />
            </marker>
          </defs>
          {edges.map((edge) => (
            <path
              key={edge.key}
              d={bezier(edge)}
              className={`flow-edge ${edge.cls} ${edgeDimmed(edge) ? "edge-dim" : ""}`}
              markerEnd={edge.arrow ? "url(#flow-arrow)" : undefined}
            />
          ))}
        </svg>
        {columnHeaders.map((header) => (
          <span
            key={header.key}
            className="flow-col-head"
            style={{ left: COLS[header.key].x * width, width: COLS[header.key].w * width }}
          >
            {header.label}
            {header.count !== null ? ` (${header.count})` : ""}
          </span>
        ))}
        {nodes.map((node) => (
          <button
            key={node.id}
            type="button"
            className={`flow-node flow-${node.kind} ${selected === node.id ? "flow-selected" : ""} ${
              nodeDimmed(node.id) ? "flow-dim" : ""
            }`}
            style={{ left: node.x, top: node.y, width: node.w, height: NODE_H }}
            aria-label={node.aria}
            aria-pressed={selected === node.id}
            onClick={() => onSelect(selected === node.id ? null : node.id)}
            onMouseEnter={() => setHovered(node.id)}
            onMouseLeave={() => setHovered(null)}
            onFocus={() => setHovered(node.id)}
            onBlur={() => setHovered(null)}
          >
            <span className="flow-label">{node.label}</span>
            {node.meta && <span className="flow-meta">{node.meta}</span>}
          </button>
        ))}
      </div>
      <div className="flow-legend">
        <span className="lg lg-req">{t.lg_req}</span>
        <span className="lg lg-knob">{t.lg_knob}</span>
        <span className="lg lg-uses">{t.lg_uses}</span>
        <span className="lg lg-viaknob">{t.lg_viaknob}</span>
        <span className="lg lg-dep">{t.lg_dep}</span>
      </div>
      {truncated && <p className="section-note">{t.flow_truncated}</p>}
    </div>
  );
}
