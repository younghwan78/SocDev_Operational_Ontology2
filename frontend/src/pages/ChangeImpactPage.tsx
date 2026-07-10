/**
 * 변경 영향 화면 — "이 IP/knob을 바꾸면 어디에 영향이 가나?"
 * IP → knob/capability/모드 선택 → 분석 실행 → 4분면(영향 시나리오/KPI/연쇄 IP/
 * 역할별 검토 체크리스트) + 과거 유사 사례. 결정론 결과만 표시하며 모든 항목에 근거가 붙는다.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
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
import { useLabels } from "../hooks/useLabels";
import { useValueLabels } from "../hooks/useValueLabels";
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
  const [searchParams] = useSearchParams();
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

      <div className="card">
        <div className="filter-row">
          <span className="filter-label">{t.select_ip}</span>
          <select
            value={ipId}
            onChange={(event) => {
              setIpId(event.target.value);
              setKnobId("");
              setCapabilityId("");
              setMode("");
            }}
          >
            <option value="">{t.none_option}</option>
            {options.data.ips.map((ip) => (
              <option key={ip.ip_id} value={ip.ip_id}>
                {ip.ip_name}
              </option>
            ))}
          </select>
          <span className="filter-label">{t.select_knob}</span>
          <select
            value={knobId}
            onChange={(event) => setKnobId(event.target.value)}
            disabled={!selected || (selected.knobs ?? []).length === 0}
          >
            <option value="">{t.none_option}</option>
            {(selected?.knobs ?? []).map((knob) => (
              <option key={knob.id} value={knob.id}>
                {knob.name}
              </option>
            ))}
          </select>
          <span className="filter-label">{t.select_capability}</span>
          <select
            value={capabilityId}
            onChange={(event) => setCapabilityId(event.target.value)}
            disabled={!selected || (selected.capabilities ?? []).length === 0}
          >
            <option value="">{t.none_option}</option>
            {(selected?.capabilities ?? []).map((capability) => (
              <option key={capability.id} value={capability.id}>
                {capability.name}
              </option>
            ))}
          </select>
          <span className="filter-label">{t.select_mode}</span>
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value)}
            disabled={!selected || (selected.modes ?? []).length === 0}
          >
            <option value="">{t.none_option}</option>
            {(selected?.modes ?? []).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="run-btn"
            disabled={!ipId}
            onClick={() =>
              setParams({
                ipId,
                knobId: knobId || undefined,
                capabilityId: capabilityId || undefined,
                mode: mode || undefined,
              })
            }
          >
            {t.run}
          </button>
        </div>
      </div>

      {params === null && <p className="status-msg">{t.idle_hint}</p>}
      {result.isFetching && <p className="status-msg">{ko.app.loading}</p>}
      {result.isError && <p className="status-msg">{ko.app.error}</p>}
      {params !== null && result.data && !result.isFetching && (
        <ImpactResult result={result.data} />
      )}
    </div>
  );
}

function ImpactResult({ result }: { result: ChangeImpactResult }) {
  const label = useLabels();
  const valueLabel = useValueLabels();
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

      <div className="quadrant-grid">
        <div className="card">
          <h2 className="card-title">
            {t.quadrant_scenarios} ({result.impacted_scenarios.length})
          </h2>
          {result.impacted_scenarios.length === 0 && <p className="desc">{t.no_items}</p>}
          <CollapsibleList
            items={result.impacted_scenarios}
            limit={5}
            render={(scenario) => (
              <div key={scenario.scenario_id} className="list-item">
                <div className="head">
                  <Link
                    to={`/scenarios/${scenario.scenario_id}/overview`}
                    className="chip-link"
                    title={scenario.scenario_id}
                  >
                    {scenario.scenario_name}
                  </Link>
                </div>
                {scenario.reasons.map((reason: BasisItem, index: number) => (
                  <p key={index} className="desc" title={reason.ref_id}>
                    <span className="badge badge-info">{reason.rule_ko}</span>{" "}
                    {reason.description}
                  </p>
                ))}
              </div>
            )}
          />
        </div>

        <div className="card">
          <h2 className="card-title">
            {t.quadrant_kpis} ({result.impacted_kpis.length})
          </h2>
          {result.impacted_kpis.length === 0 && <p className="desc">{t.no_items}</p>}
          <div className="chip-row">
            {result.impacted_kpis.map((kpi) => (
              <span
                key={kpi.kpi_id}
                className={`chip ${kpi.via_knob ? "chip-knob" : ""}`}
                title={
                  (kpi.via_knob ? `${t.via_knob} · ` : "") +
                  (kpi.unit ? `${t.unit}: ${kpi.unit}` : kpi.kpi_id)
                }
              >
                {kpi.kpi_id}
                {kpi.via_knob ? " ★" : ""}
              </span>
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="card-title">
            {t.quadrant_chained} ({result.chained_ips.length})
          </h2>
          {result.chained_ips.length === 0 && <p className="desc">{t.no_items}</p>}
          {result.chained_ips.map((chained) => (
            <div key={chained.rule_id} className="list-item">
              <div className="head">
                <span className="title" title={chained.ip_id}>
                  {chained.ip_name}
                </span>
                <span className="badge badge-warn">{chained.direction_ko}</span>
              </div>
              <p className="desc" title={chained.rule_id}>
                {t.condition}: {chained.condition} — {chained.rationale}
              </p>
            </div>
          ))}
        </div>

        <ChecklistCard checklist={result.checklist} exportText={result.export_text} />
      </div>

      <div className="card">
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
    <div className="card">
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
