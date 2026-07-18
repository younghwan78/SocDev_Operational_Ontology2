/**
 * 출처 지도 — E5 폴리싱: 상단 상황판, 컬렉션 밀도 개선(단일 막대·건수순 정렬·
 * 범례 1회), IP 별칭 도메인 한국어화.
 */
import { useQuery } from "@tanstack/react-query";
import {
  fetchEntityResolution,
  fetchSourceMap,
  type AliasEntry,
  type CollectionCoverage,
  type UnmatchedToken,
} from "../api/client";
import { useLabels } from "../hooks/useLabels";
import { useValueLabels } from "../hooks/useValueLabels";
import { ErrorState } from "../components/ErrorState";
import { ko } from "../i18n/ko";

const t = ko.source_map;

export function SourceMapPage() {
  const query = useQuery({ queryKey: ["source-map"], queryFn: fetchSourceMap });
  const entity = useQuery({ queryKey: ["entity-resolution"], queryFn: fetchEntityResolution });
  const label = useLabels();
  const valueLabel = useValueLabels();

  if (query.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (query.isError)
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;

  const { collections, totals } = query.data;
  const realTotal = totals.imported + totals.integrated;
  const sorted = [...collections].sort((a, b) => b.total - a.total);

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">{t.subtitle}</p>

      {/* E5 상황판 — 전체/합성/반입/연동 */}
      <div className="stat-strip">
        <span className="stat">
          <b>{totals.total}</b>
          <span>{t.total}</span>
        </span>
        <span className="stat">
          <b>{totals.synthetic}</b>
          <span>{t.origin_synthetic}</span>
        </span>
        <span className="stat">
          <b>{totals.imported}</b>
          <span>{t.origin_imported}</span>
        </span>
        <span className="stat">
          <b>{totals.integrated}</b>
          <span>{t.origin_integrated}</span>
        </span>
      </div>

      <div className="card">
        <h2 className="card-title">{t.total_summary}</h2>
        <p className="desc">{totals.real_data_note}</p>
        <OriginBar
          synthetic={totals.synthetic}
          imported={totals.imported}
          integrated={totals.integrated}
          total={totals.total}
        />
        {realTotal === 0 && <p className="desc">{t.note_synthetic_ok}</p>}
      </div>

      <div className="card">
        <h2 className="card-title">
          {t.by_collection} ({sorted.length})
        </h2>
        <p className="section-note">{t.by_collection_note}</p>
        <div className="source-grid">
          {sorted.map((c) => (
            <CollectionRow
              key={c.collection}
              coverage={c}
              maxTotal={sorted[0]?.total ?? 1}
            />
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">{t.entity_section}</h2>
        <p className="section-note">{t.entity_subtitle}</p>
        {entity.isPending && <p className="status-msg">{ko.app.loading}</p>}
        {entity.isError && (
          <ErrorState error={entity.error} onRetry={() => void entity.refetch()} />
        )}
        {entity.data && (
          <>
            <h3 className="subhead">{t.alias_table}</h3>
            <div className="source-collection-list">
              {entity.data.aliases.map((a) => (
                <AliasRow
                  key={a.ip_id}
                  entry={a}
                  name={label(a.ip_id)}
                  domainLabel={valueLabel("ip_domain", a.domain)}
                />
              ))}
            </div>
            <h3 className="subhead">{t.unmatched_queue}</h3>
            <p className="desc">{t.unmatched_hint}</p>
            {entity.data.unmatched.length === 0 ? (
              <p className="status-msg">{t.unmatched_none}</p>
            ) : (
              <div className="chip-row">
                {entity.data.unmatched.map((u) => (
                  <UnmatchedChip key={u.token} token={u} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function AliasRow({
  entry,
  name,
  domainLabel,
}: {
  entry: AliasEntry;
  name: string;
  domainLabel: string;
}) {
  return (
    <div className="list-item" title={entry.ip_id}>
      <div className="head">
        <span className="title">{name}</span>
        <span className="chip" title={entry.domain}>
          {t.alias_domain}: {domainLabel}
        </span>
      </div>
      <p className="desc">
        {t.alias_aliases}:{" "}
        {entry.aliases.length > 0 ? entry.aliases.join(", ") : t.alias_none}
      </p>
    </div>
  );
}

function UnmatchedChip({ token }: { token: UnmatchedToken }) {
  return (
    <span
      className="badge badge-warn"
      title={`${t.unmatched_occurrences} ${token.occurrences} · ${token.sample_refs.join(", ")}`}
    >
      {token.token} ({token.occurrences})
    </span>
  );
}

/** E5+: 막대 길이=건수(최대 대비) — 컬렉션 간 규모가 한눈에 비교되고,
 * 숫자는 막대 끝에 붙어 시선 이동이 없다 (이슈 상황판 분포 막대와 동일 문법). */
function CollectionRow({
  coverage,
  maxTotal,
}: {
  coverage: CollectionCoverage;
  maxTotal: number;
}) {
  const summary = `${t.origin_synthetic} ${coverage.synthetic}, ${t.origin_imported} ${coverage.imported}, ${t.origin_integrated} ${coverage.integrated}`;
  return (
    <div className="source-row" title={`${coverage.collection} — ${summary}`}>
      <span className="source-name">{coverage.collection_ko}</span>
      <span className="source-bar-area">
        <span
          className="origin-track source-track"
          role="img"
          aria-label={summary}
          style={{ width: `${(coverage.total / Math.max(maxTotal, 1)) * 100}%` }}
        >
          {coverage.synthetic > 0 && (
            <span className="origin-seg origin-synthetic" style={{ flex: coverage.synthetic }} />
          )}
          {coverage.imported > 0 && (
            <span className="origin-seg origin-imported" style={{ flex: coverage.imported }} />
          )}
          {coverage.integrated > 0 && (
            <span className="origin-seg origin-integrated" style={{ flex: coverage.integrated }} />
          )}
        </span>
        <span className="source-count">{coverage.total}</span>
        {coverage.without_ref > 0 && (
          <span className="badge badge-warn" title={t.without_ref_hint}>
            {t.without_ref} {coverage.without_ref}
          </span>
        )}
      </span>
    </div>
  );
}

function OriginBar({
  synthetic,
  imported,
  integrated,
  total,
}: {
  synthetic: number;
  imported: number;
  integrated: number;
  total: number;
}) {
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0);
  const summary = `${t.origin_synthetic} ${synthetic}, ${t.origin_imported} ${imported}, ${t.origin_integrated} ${integrated}`;
  return (
    <div className="origin-bar" role="img" aria-label={summary}>
      <div className="origin-track">
        {synthetic > 0 && (
          <span className="origin-seg origin-synthetic" style={{ width: `${pct(synthetic)}%` }} />
        )}
        {imported > 0 && (
          <span className="origin-seg origin-imported" style={{ width: `${pct(imported)}%` }} />
        )}
        {integrated > 0 && (
          <span className="origin-seg origin-integrated" style={{ width: `${pct(integrated)}%` }} />
        )}
      </div>
      <div className="origin-legend">
        <span className="origin-key">
          <span className="origin-dot origin-synthetic" /> {t.origin_synthetic} {synthetic}
        </span>
        <span className="origin-key">
          <span className="origin-dot origin-imported" /> {t.origin_imported} {imported}
        </span>
        <span className="origin-key">
          <span className="origin-dot origin-integrated" /> {t.origin_integrated} {integrated}
        </span>
      </div>
    </div>
  );
}
