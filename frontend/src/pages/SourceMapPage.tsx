import { useQuery } from "@tanstack/react-query";
import { fetchSourceMap, type CollectionCoverage } from "../api/client";
import { ko } from "../i18n/ko";

const t = ko.source_map;

export function SourceMapPage() {
  const query = useQuery({ queryKey: ["source-map"], queryFn: fetchSourceMap });

  if (query.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (query.isError) return <p className="status-msg">{ko.app.error}</p>;

  const { collections, totals } = query.data;
  const realTotal = totals.imported + totals.integrated;

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">{t.subtitle}</p>

      <div className="card">
        <h2 className="card-title">{t.total_summary}</h2>
        <dl className="kv">
          <dt>{t.total}</dt>
          <dd>{totals.total}</dd>
          <dt>{t.real_data}</dt>
          <dd>{totals.real_data_note}</dd>
        </dl>
        <OriginBar
          synthetic={totals.synthetic}
          imported={totals.imported}
          integrated={totals.integrated}
          total={totals.total}
        />
        {realTotal === 0 && <p className="desc">{t.note_synthetic_ok}</p>}
      </div>

      <div className="card">
        <h2 className="card-title">{t.by_collection}</h2>
        <div className="source-collection-list">
          {collections.map((c) => (
            <CollectionRow key={c.collection} coverage={c} />
          ))}
        </div>
      </div>
    </div>
  );
}

function CollectionRow({ coverage }: { coverage: CollectionCoverage }) {
  return (
    <div className="list-item" title={coverage.collection}>
      <div className="head">
        <span className="title">{coverage.collection_ko}</span>
        <span className="chip">
          {t.col_total} {coverage.total}
        </span>
        {coverage.without_ref > 0 && (
          <span
            className="badge badge-warn"
            title={t.without_ref_hint}
          >
            {t.without_ref} {coverage.without_ref}
          </span>
        )}
      </div>
      <OriginBar
        synthetic={coverage.synthetic}
        imported={coverage.imported}
        integrated={coverage.integrated}
        total={coverage.total}
      />
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
  return (
    <div className="origin-bar" role="img" aria-label={`${t.origin_synthetic} ${synthetic}, ${t.origin_imported} ${imported}, ${t.origin_integrated} ${integrated}`}>
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
