/**
 * 변경 영향 화면 — "이 IP/knob을 바꾸면 어디에 영향이 가나?"
 * IP → knob/capability/모드 선택 → 분석 실행 → 4분면(영향 시나리오/KPI/연쇄 IP/
 * 역할별 검토 체크리스트) + 과거 유사 사례. 결정론 결과만 표시하며 모든 항목에 근거가 붙는다.
 */
import { useQuery } from "@tanstack/react-query";
import { useState, type CSSProperties, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchChangeImpact,
  fetchChangeImpactOptions,
  type BasisItem,
  type ChangeImpactParams,
  type ChangeImpactResult,
  type ChecklistItem,
  type SimilarCase,
} from "../api/client";
import { CollapsibleList } from "../components/CollapsibleList";
import { ImpactFlow, type FlowNodeId } from "../components/ImpactFlow";
import { SplitHandle, useSidePanelWidth } from "../components/SplitLayout";
import { useLabels } from "../hooks/useLabels";
import { useValueLabels } from "../hooks/useValueLabels";
import { Busy } from "../components/Busy";
import { ko } from "../i18n/ko";

const t = ko.change_impact;

const DIRECTION_BADGE: Record<string, string> = {
  increase: "badge-danger",
  decrease: "badge-ok",
  mixed: "badge-warn",
};
const DIRECTION_LABEL: Record<string, string> = {
  increase: t.dir_increase,
  decrease: t.dir_decrease,
  mixed: t.dir_mixed,
};

export function ChangeImpactPage() {
  const options = useQuery({
    queryKey: ["change-impact-options"],
    queryFn: fetchChangeImpactOptions,
  });
  // 데모 스토리 등 외부 딥링크(?ip=&knob=...)로 사전 구성 실행을 지원한다.
  const [searchParams, setSearchParams] = useSearchParams();
  const initialIp = searchParams.get("ip") ?? "";
  const [ipId, setIpId] = useState(initialIp);
  const [knobId, setKnobId] = useState(searchParams.get("knob") ?? "");
  const [capabilityId, setCapabilityId] = useState(searchParams.get("capability") ?? "");
  const [mode, setMode] = useState(searchParams.get("mode") ?? "");
  const [params, setParams] = useState<ChangeImpactParams | null>(
    initialIp
      ? {
          ipId: initialIp,
          knobId: searchParams.get("knob") ?? undefined,
          capabilityId: searchParams.get("capability") ?? undefined,
          mode: searchParams.get("mode") ?? undefined,
        }
      : null,
  );

  const result = useQuery({
    queryKey: ["change-impact", params],
    queryFn: () => fetchChangeImpact(params!),
    enabled: params !== null,
  });

  if (options.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (options.isError) return <p className="status-msg">{ko.app.error}</p>;

  const selected = options.data.ips.find((ip) => ip.ip_id === ipId);

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">{t.subtitle}</p>

      {/* G2: 질의가 곧 문장 — 폼 자체가 분석의 의미를 설명한다. */}
      <div className="card query-card">
        <div className="query-sentence">
          <select
            id="ci-ip"
            className="q-select q-select-ip"
            aria-label={t.select_ip}
            value={ipId}
            onChange={(event) => {
              setIpId(event.target.value);
              setKnobId("");
              setCapabilityId("");
              setMode("");
            }}
          >
            <option value="">{t.q_ip_placeholder}</option>
            {options.data.ips.map((ip) => (
              <option key={ip.ip_id} value={ip.ip_id}>
                {ip.ip_name}
              </option>
            ))}
          </select>
          <span className="q-text">{t.q_of}</span>
          <select
            id="ci-knob"
            className="q-select"
            aria-label={t.select_knob}
            value={knobId}
            onChange={(event) => setKnobId(event.target.value)}
            disabled={!selected || (selected.knobs ?? []).length === 0}
          >
            <option value="">{t.all_knobs}</option>
            {(selected?.knobs ?? []).map((knob) => (
              <option key={knob.id} value={knob.id}>
                {knob.name}
              </option>
            ))}
          </select>
          <span className="q-text">{t.q_dot}</span>
          <select
            id="ci-capability"
            className="q-select"
            aria-label={t.select_capability}
            value={capabilityId}
            onChange={(event) => setCapabilityId(event.target.value)}
            disabled={!selected || (selected.capabilities ?? []).length === 0}
          >
            <option value="">{t.all_capabilities}</option>
            {(selected?.capabilities ?? []).map((capability) => (
              <option key={capability.id} value={capability.id}>
                {capability.name}
              </option>
            ))}
          </select>
          <span className="q-text">{t.q_obj}</span>
          <select
            id="ci-mode"
            className="q-select"
            aria-label={t.select_mode}
            value={mode}
            onChange={(event) => setMode(event.target.value)}
            disabled={!selected || (selected.modes ?? []).length === 0}
          >
            <option value="">{t.all_modes}</option>
            {(selected?.modes ?? []).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <span className="q-text">{t.q_in}</span>
          <span className="q-text">{t.q_tail}</span>
          <button
            type="button"
            className="run-btn"
            disabled={!ipId}
            onClick={() => {
              setParams({
                ipId,
                knobId: knobId || undefined,
                capabilityId: capabilityId || undefined,
                mode: mode || undefined,
              });
              // URL=상태: 실행한 분석을 링크로 공유·재현할 수 있게 역동기화.
              setSearchParams(
                (previous) => {
                  const next = new URLSearchParams(previous);
                  next.set("ip", ipId);
                  for (const [key, value] of [
                    ["knob", knobId],
                    ["capability", capabilityId],
                    ["mode", mode],
                  ] as const) {
                    if (value) next.set(key, value);
                    else next.delete(key);
                  }
                  return next;
                },
                { replace: true },
              );
            }}
          >
            {t.run}
          </button>
        </div>
      </div>

      {params === null && <p className="status-msg">{t.idle_hint}</p>}
      {result.isFetching && <Busy message={ko.app.loading} />}
      {result.isError && (
        <p className="status-msg" role="alert">
          {t.analysis_failed}
        </p>
      )}
      {params !== null && result.data && !result.isFetching && (
        <div aria-live="polite">
          <ImpactResult result={result.data} />
        </div>
      )}
    </div>
  );
}

/** G2: 계기판 요약 스트립 — 규모를 먼저 보여주고, 클릭하면 해당 섹션으로 이동. */
function StatStrip({ result }: { result: ChangeImpactResult }) {
  const stats = [
    { id: "ci-flow", label: t.quadrant_scenarios, count: result.impacted_scenarios.length },
    { id: "ci-flow", label: t.quadrant_kpis, count: result.impacted_kpis.length },
    { id: "ci-flow", label: t.quadrant_chained, count: result.chained_ips.length },
    { id: "ci-checklist", label: t.stat_roles, count: result.checklist.length },
    { id: "ci-similar", label: t.similar_cases, count: result.similar_cases.length },
  ];
  return (
    <div className="stat-strip">
      {stats.map((stat) => (
        <button
          key={stat.label}
          type="button"
          className="stat"
          onClick={() =>
            document
              .getElementById(stat.id)
              ?.scrollIntoView({ behavior: "smooth", block: "start" })
          }
        >
          <b>{stat.count}</b>
          <span>{stat.label}</span>
        </button>
      ))}
    </div>
  );
}

function ImpactResult({ result }: { result: ChangeImpactResult }) {
  const label = useLabels();
  const valueLabel = useValueLabels();
  // 노드 선택도 URL 상태 — 분석+선택 상태를 링크로 공유·재현.
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedNode = searchParams.get("node");
  const setSelectedNode = (id: FlowNodeId | null) =>
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (id) next.set("node", id);
        else next.delete("node");
        return next;
      },
      { replace: true },
    );
  const sidePanel = useSidePanelWidth("ci-side-width");
  const { subject } = result;
  return (
    <div>
      <div className="card">
        <div className="head">
          <span className="title" title={subject.ip_id}>
            {subject.summary}
          </span>
          <span className="badge badge-info">{result.note_ko}</span>
        </div>
        {subject.knob && (
          <p className="desc" title={subject.knob.knob_id}>
            {t.knob_effect}:{" "}
            <DirectionBadge name={t.dir_power} value={subject.knob.power_direction} />{" "}
            <DirectionBadge name={t.dir_latency} value={subject.knob.latency_direction} />{" "}
            <DirectionBadge name={t.dir_bandwidth} value={subject.knob.bandwidth_direction} />{" "}
            <DirectionBadge name={t.dir_risk} value={subject.knob.risk_direction} /> ·{" "}
            {subject.knob.description}
          </p>
        )}
        {subject.capability && (
          <p className="desc" title={subject.capability.capability_id}>
            {subject.capability.name} ({subject.capability.category} ·{" "}
            {subject.capability.support_status})
            {subject.capability.condition ? ` — ${subject.capability.condition}` : ""}
          </p>
        )}
      </div>

      <StatStrip result={result} />

      {/* G1: 영향 전파 지도 + 근거 패널 — 위험 지도와 동일한 상호작용 문법 */}
      <div
        className="risk-layout risk-layout-split"
        style={{ "--side-w": `${sidePanel.width}px` } as CSSProperties}
      >
        <div className="card" id="ci-flow">
          <div className="head">
            <h2 className="card-title">{t.flow_title}</h2>
            <span className="section-note">{t.flow_hint}</span>
          </div>
          <ImpactFlow
            result={result}
            label={label}
            selected={selectedNode}
            onSelect={setSelectedNode}
          />
        </div>
        <SplitHandle
          width={sidePanel.width}
          onResize={sidePanel.update}
          onReset={sidePanel.reset}
          label={ko.risk.panel_resize}
        />
        <div className="risk-side">
          <ImpactBasisPanel
            result={result}
            nodeId={selectedNode}
            label={label}
            onSelect={setSelectedNode}
          />
        </div>
      </div>

      <div className="quadrant-grid">
        <ChecklistCard checklist={result.checklist} exportText={result.export_text} />

        <div className="card" id="ci-similar">
        <h2 className="card-title">
          {t.similar_cases} ({result.similar_cases.length})
        </h2>
        {result.similar_cases.length === 0 && <p className="desc">{t.no_items}</p>}
        <CollapsibleList
          items={result.similar_cases}
          limit={5}
          render={(item: SimilarCase, index: number) => (
            <div key={`${item.ref_id}-${index}`} className="list-item">
              <div className="head">
                <span
                  className={`badge ${item.kind === "issue" ? "badge-danger" : "badge-info"}`}
                >
                  {item.kind_ko}
                </span>
                <span className="title" title={item.ref_id}>
                  {item.title}
                </span>
                <span className="badge badge-info" title={item.status}>
                  {valueLabel("issue_status", item.status)}
                </span>
              </div>
              <p className="desc">{item.why_similar}</p>
              {(item.scenario_ids ?? []).length > 0 && (
                <p className="desc">
                  {ko.risk.related_scenarios}:{" "}
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
          )}
        />
        </div>
      </div>
    </div>
  );
}

/** G1: 노드 상세/근거 패널 — 그래프 선택에 따라 시나리오·KPI·연쇄 IP·대상 상세를 보인다. */
function ImpactBasisPanel({
  result,
  nodeId,
  label,
  onSelect,
}: {
  result: ChangeImpactResult;
  nodeId: FlowNodeId | null;
  label: (id: string) => string;
  onSelect: (id: FlowNodeId | null) => void;
}) {
  const confidenceLabel: Record<string, string> = {
    high: ko.risk.grade_high,
    medium: ko.risk.grade_medium,
    low: ko.risk.grade_low,
  };

  const kpiChip = (kpiId: string, viaKnob: boolean) => (
    <button
      key={kpiId}
      type="button"
      className={`chip chip-btn ${viaKnob ? "chip-knob" : ""}`}
      title={kpiId}
      onClick={() => onSelect(`kpi:${kpiId}`)}
    >
      {label(kpiId)}
      {viaKnob ? " ★" : ""}
    </button>
  );

  let body: ReactNode = <p className="desc">{t.panel_pick}</p>;

  if (nodeId === "subject") {
    body = (
      <div>
        <div className="head">
          <span className="title" title={result.subject.ip_id}>
            {result.subject.summary}
          </span>
        </div>
        <p className="subhead">
          {t.panel_all_scenarios} ({result.impacted_scenarios.length})
        </p>
        <div className="chip-row">
          {result.impacted_scenarios.map((scenario) => (
            <button
              key={scenario.scenario_id}
              type="button"
              className="chip chip-btn"
              title={scenario.scenario_id}
              onClick={() => onSelect(`sc:${scenario.scenario_id}`)}
            >
              {scenario.scenario_name}
            </button>
          ))}
        </div>
        <p className="subhead">
          {t.panel_all_kpis} ({result.impacted_kpis.length})
        </p>
        <div className="chip-row">
          {result.impacted_kpis.map((kpi) => kpiChip(kpi.kpi_id, kpi.via_knob ?? false))}
        </div>
      </div>
    );
  } else if (nodeId?.startsWith("sc:")) {
    const scenario = result.impacted_scenarios.find(
      (candidate) => candidate.scenario_id === nodeId.slice(3),
    );
    if (scenario) {
      body = (
        <div>
          <div className="head">
            <span className="title" title={scenario.scenario_id}>
              {scenario.scenario_name}
            </span>
          </div>
          {scenario.reasons.map((reason: BasisItem, index: number) => (
            <p key={index} className="desc" title={reason.ref_id}>
              <span className="badge badge-info">{reason.rule_ko}</span> {reason.description}
            </p>
          ))}
          {(scenario.kpi_ids ?? []).length > 0 && (
            <>
              <p className="subhead">{t.panel_kpis}</p>
              <div className="chip-row">
                {(scenario.kpi_ids ?? []).map((kpiId) => kpiChip(kpiId, false))}
              </div>
            </>
          )}
          <Link
            to={`/scenarios/${scenario.scenario_id}/overview`}
            className="chip-link"
            title={scenario.scenario_id}
          >
            {ko.risk.open_scenario}
          </Link>
        </div>
      );
    }
  } else if (nodeId?.startsWith("kpi:")) {
    const kpi = result.impacted_kpis.find((candidate) => candidate.kpi_id === nodeId.slice(4));
    if (kpi) {
      body = (
        <div>
          <div className="head">
            <span className="title" title={kpi.kpi_id}>
              {label(kpi.kpi_id)}
            </span>
            {kpi.via_knob && <span className="badge badge-warn">{t.via_knob}</span>}
            {kpi.unit && (
              <span className="badge badge-info">
                {t.unit}: {kpi.unit}
              </span>
            )}
          </div>
          {(kpi.scenario_ids ?? []).length > 0 && (
            <>
              <p className="subhead">{t.panel_scenarios}</p>
              <div className="chip-row">
                {(kpi.scenario_ids ?? []).map((scenarioId) => (
                  <button
                    key={scenarioId}
                    type="button"
                    className="chip chip-btn"
                    title={scenarioId}
                    onClick={() => onSelect(`sc:${scenarioId}`)}
                  >
                    {label(scenarioId)}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      );
    }
  } else if (nodeId?.startsWith("dep:")) {
    const dep = result.chained_ips.find((candidate) => candidate.rule_id === nodeId.slice(4));
    if (dep) {
      body = (
        <div>
          <div className="head">
            <span className="title" title={dep.ip_id}>
              {dep.ip_name}
            </span>
            <span className="badge badge-warn">{dep.direction_ko}</span>
          </div>
          <p className="desc" title={dep.rule_id}>
            {t.condition}: {dep.condition}
          </p>
          <p className="desc">{dep.rationale}</p>
          <p className="desc" title={dep.relationship}>
            {t.dep_confidence}:{" "}
            <span className="badge badge-info">
              {confidenceLabel[dep.confidence] ?? dep.confidence}
            </span>
          </p>
        </div>
      );
    }
  }

  return (
    <div className="card">
      <h2 className="card-title">{t.panel_title}</h2>
      {body}
    </div>
  );
}

function DirectionBadge({ name, value }: { name: string; value: string }) {
  return (
    <span className={`badge ${DIRECTION_BADGE[value] ?? "badge-info"}`}>
      {name} {DIRECTION_LABEL[value] ?? value}
    </span>
  );
}

function ChecklistCard({
  checklist,
  exportText,
}: {
  checklist: ChecklistItem[];
  exportText: string;
}) {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(exportText);
      setCopied(t.copied);
    } catch {
      setCopied(t.copy_failed);
    }
  };
  return (
    <div className="card" id="ci-checklist">
      <div className="head">
        <h2 className="card-title">
          {t.quadrant_checklist} ({checklist.length})
        </h2>
        <button type="button" className="link-btn" onClick={copy}>
          {t.copy_checklist}
        </button>
        {copied && <span className="badge badge-ok">{copied}</span>}
      </div>
      {checklist.length === 0 && <p className="desc">{t.no_items}</p>}
      {checklist.map((item) => (
        <div key={item.role_id} className="list-item">
          <div className="head">
            <span className="badge badge-info" title={item.role_id}>
              {item.role_name}
            </span>
          </div>
          <p className="desc">{item.perspective}</p>
          <CollapsibleList
            items={item.basis}
            limit={3}
            render={(basis: BasisItem, index: number) => (
              <p key={index} className="desc basis-line" title={basis.ref_id}>
                <span className="badge badge-warn">{basis.rule_ko}</span> {basis.description}
              </p>
            )}
          />
        </div>
      ))}
    </div>
  );
}
