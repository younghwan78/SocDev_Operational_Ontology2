/**
 * 근거 탐색 — E4 폴리싱: URL=상태, 가용성 칩 건수, 제목 검색,
 * 신뢰 사다리 세그먼트 클릭=강도 필터 (사다리가 곧 필터 UI).
 */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchEvidence,
  fetchEvidenceLadder,
  fetchProjects,
  type EvidenceLadder,
  type EvidenceStrengthItem,
} from "../api/client";
import { SourceBadge } from "../components/SourceBadge";
import { useLabels } from "../hooks/useLabels";
import { useValueLabels } from "../hooks/useValueLabels";
import { ErrorState } from "../components/ErrorState";
import { ko } from "../i18n/ko";

const t = ko.evidence;
const tl = ko.evidence_ladder;

const AVAILABILITY_BADGE: Record<string, string> = {
  available: "badge-ok",
  partial: "badge-warn",
  missing: "badge-danger",
  planned: "badge-info",
};

const TIER_BADGE: Record<string, string> = {
  measured_direct: "badge-ok",
  measured_analogous: "badge-ok",
  emulated: "badge-info",
  predicted: "badge-warn",
  absent: "badge-danger",
};

const AVAILABILITY_OPTIONS = ["available", "partial", "missing", "planned"];

export function EvidencePage() {
  // URL=상태 — 필터/검색 공유·재현.
  const [searchParams, setSearchParams] = useSearchParams();
  const projectFilter = searchParams.get("project") ?? undefined;
  const availabilityFilter = searchParams.get("availability");
  const tierFilter = searchParams.get("tier");
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

  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  // 가용성/강도는 클라이언트 필터 — 칩 건수가 항상 전체 분포를 보게 한다.
  const evidence = useQuery({
    queryKey: ["evidence", projectFilter],
    queryFn: () => fetchEvidence({ projectId: projectFilter }),
  });
  const ladder = useQuery({
    queryKey: ["evidence-ladder", projectFilter],
    queryFn: () => fetchEvidenceLadder({ projectId: projectFilter }),
  });
  const label = useLabels();
  const valueLabel = useValueLabels();

  const strengthById = new Map<string, EvidenceStrengthItem>(
    (ladder.data?.entries ?? []).map((item) => [item.evidence_id, item]),
  );

  if (evidence.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (evidence.isError)
    return <ErrorState error={evidence.error} onRetry={() => void evidence.refetch()} />;

  const all = evidence.data;
  const availabilityCounts = new Map<string, number>();
  for (const entry of all)
    availabilityCounts.set(
      entry.availability,
      (availabilityCounts.get(entry.availability) ?? 0) + 1,
    );
  const query = urlQuery.trim().toLowerCase();
  const visible = all.filter(
    (entry) =>
      (!availabilityFilter || entry.availability === availabilityFilter) &&
      (!tierFilter || strengthById.get(entry.id)?.tier === tierFilter) &&
      (!query || entry.title.toLowerCase().includes(query)),
  );

  return (
    <div>
      <h1>{t.title}</h1>
      <div className="filter-row">
        <span className="filter-label">{ko.scenario_list.filter_label}</span>
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
        <span className="filter-label">{t.filter_availability}</span>
        <button
          className={`chip chip-btn ${availabilityFilter === null ? "active" : ""}`}
          onClick={() => updateParams({ availability: null })}
        >
          {t.filter_all}
        </button>
        {AVAILABILITY_OPTIONS.map((option) => (
          <button
            key={option}
            className={`chip chip-btn ${availabilityFilter === option ? "active" : ""}`}
            onClick={() =>
              updateParams({ availability: availabilityFilter === option ? null : option })
            }
            title={option}
          >
            {valueLabel("availability", option)} ({availabilityCounts.get(option) ?? 0})
          </button>
        ))}
        <label className="filter-label" htmlFor="evidence-search">
          {t.search_label}
        </label>
        <input
          id="evidence-search"
          type="search"
          className="search-input"
          value={queryDraft}
          placeholder={t.search_placeholder}
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => setQueryDraft(event.target.value)}
        />
      </div>

      {ladder.data && (
        <LadderPanel
          ladder={ladder.data}
          activeTier={tierFilter}
          onTierToggle={(tier) => updateParams({ tier: tierFilter === tier ? null : tier })}
        />
      )}

      <div className="card">
        <h2 className="card-title">
          {t.list_title} ({visible.length})
        </h2>
        {visible.length === 0 && <p className="status-msg">{ko.app.empty}</p>}
        {visible.map((entry) => (
          <div key={entry.id} className="list-item">
            <div className="head">
              <SourceBadge origin={entry.source?.origin} />
              {strengthById.get(entry.id) && (
                <span
                  className={`badge ${TIER_BADGE[strengthById.get(entry.id)!.tier] ?? "badge-info"}`}
                  title={strengthById.get(entry.id)!.basis[0]?.description ?? ""}
                >
                  {tl.strength}: {strengthById.get(entry.id)!.tier_ko}
                </span>
              )}
              <span
                className={`badge ${AVAILABILITY_BADGE[entry.availability] ?? "badge-info"}`}
                title={entry.availability}
              >
                {valueLabel("availability", entry.availability)}
              </span>
              <span className="title">{entry.title}</span>
              {entry.is_measurement && <span className="badge badge-ok">{t.measurement}</span>}
              {entry.is_prediction && <span className="badge badge-warn">{t.prediction}</span>}
              <span className="chip" title={entry.project_id}>
                {label(entry.project_id)}
              </span>
            </div>
            <p className="desc">
              {t.limitation}: {entry.known_limitation} · {t.source_system}: {entry.source_system}
            </p>
            <p className="desc">
              <Link
                to={`/scenarios/${entry.scenario_id}/overview`}
                className="chip-link"
                title={entry.scenario_id}
              >
                {t.scenario_link}: {label(entry.scenario_id)}
              </Link>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function LadderPanel({
  ladder,
  activeTier,
  onTierToggle,
}: {
  ladder: EvidenceLadder;
  activeTier: string | null;
  onTierToggle: (tier: string) => void;
}) {
  const total = ladder.totals.total;
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0);
  const shown = ladder.distribution.filter((b) => b.count > 0);
  return (
    <div className="card">
      <h2 className="card-title">{tl.title}</h2>
      <p className="section-note">
        {tl.subtitle} · {tl.filter_hint}
      </p>
      <div className="ladder-headline">
        <span>
          {tl.headline_measured} <b>{ladder.totals.measured}</b> {tl.of_total} {total}
        </span>
        <span>
          {tl.headline_predicted} <b>{ladder.totals.predicted}</b>
        </span>
        <span>
          {tl.headline_absent} <b>{ladder.totals.absent}</b>
        </span>
      </div>
      <div
        className="ladder-track"
        role="group"
        aria-label={shown.map((b) => `${b.tier_ko} ${b.count}`).join(", ")}
      >
        {shown.map((b) => (
          <button
            key={b.tier}
            type="button"
            className={`ladder-seg tier-${b.tier} ${activeTier === b.tier ? "ladder-active" : ""}`}
            style={{ width: `${pct(b.count)}%` }}
            title={`${b.tier_ko} ${b.count} — ${tl.filter_hint}`}
            aria-pressed={activeTier === b.tier}
            onClick={() => onTierToggle(b.tier)}
          />
        ))}
      </div>
      <div className="origin-legend">
        {ladder.distribution.map((b) => (
          <button
            key={b.tier}
            type="button"
            className={`origin-key ladder-key ${activeTier === b.tier ? "ladder-key-active" : ""}`}
            onClick={() => onTierToggle(b.tier)}
          >
            <span className={`origin-dot tier-${b.tier}`} />
            {b.tier_ko} {b.count}
          </button>
        ))}
      </div>
    </div>
  );
}
