/**
 * 출처 지도 — E5 폴리싱: 상단 상황판, 컬렉션 밀도 개선(단일 막대·건수순 정렬·
 * 범례 1회), IP 별칭 도메인 한국어화.
 */
import { useQuery } from "@tanstack/react-query";
import {
  fetchEntityResolution,
  fetchIngestBatches,
  fetchSourceMap,
  type AliasEntry,
  type CollectionCoverage,
  type LinkCoverage,
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
  const batches = useQuery({ queryKey: ["ingest-batches"], queryFn: fetchIngestBatches });
  const label = useLabels();
  const valueLabel = useValueLabels();

  if (query.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (query.isError)
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;

  const { collections, totals } = query.data;
  const links = query.data.links ?? [];
  const realTotal = totals.imported + totals.integrated;
  const sorted = [...collections].sort((a, b) => b.total - a.total);
  // W2: 연결률이 기록된 완료 배치만 — list는 최신순, 추이는 과거→최신으로 표기.
  const linkageTrend = (batches.data ?? [])
    .filter((b) => b.status === "completed" && (b.linkage_total ?? 0) > 0)
    .slice(0, 8)
    .reverse();

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

      {/* W2 (설계 22): 온톨로지 연결률 — 트윈 충실도. 기준선 표시일 뿐 판정·경고가 아니다. */}
      {links.length > 0 && (
        <div className="card">
          <h2 className="card-title">{ko.link_coverage.section}</h2>
          <p className="section-note">
            {query.data.link_note_ko} · {ko.link_coverage.target}
          </p>
          <div className="source-grid">
            {links.map((link) => (
              <LinkCoverageRow key={link.collection} link={link} />
            ))}
          </div>
          {linkageTrend.length > 0 && (
            <p className="desc">
              {ko.link_coverage.batches}:{" "}
              {linkageTrend
                .map(
                  (b) =>
                    `${b.filename} ${Math.round(
                      ((b.linkage_connected ?? 0) / Math.max(b.linkage_total ?? 0, 1)) * 100,
                    )}%`,
                )
                .join(" → ")}
            </p>
          )}
        </div>
      )}

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

/** W2: 연결률 행 — 채움 막대 + 70% 기준선 눈금, 펼치면 필드별 건수 칩. */
function LinkCoverageRow({ link }: { link: LinkCoverage }) {
  const pct = Math.round((link.linked / Math.max(link.total, 1)) * 100);
  const summary = `${link.linked}/${link.total} (${pct}%)`;
  return (
    <details className="link-cov-row">
      <summary
        className="source-row"
        title={`${link.collection} — ${ko.link_coverage.fields_hint}`}
      >
        <span className="source-name">{link.collection_ko}</span>
        <span className="source-bar-area">
          <span className="link-track" role="img" aria-label={summary}>
            <span className="link-fill" style={{ width: `${pct}%` }} />
            <span className="link-target-mark" aria-hidden="true" />
          </span>
          <span className="source-count">{summary}</span>
        </span>
      </summary>
      <div className="chip-row link-cov-fields">
        {link.fields.map((field) => (
          <span key={field.field} className="chip" title={field.field}>
            {field.field_ko} {field.linked}
          </span>
        ))}
      </div>
    </details>
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
