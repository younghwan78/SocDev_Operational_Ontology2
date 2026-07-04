import { ko } from "../i18n/ko";

/** 데이터 출처 뱃지 — 가상(synthetic)/반입(imported)/연동(integrated). */
export function SourceBadge({ origin }: { origin?: string | null }) {
  if (!origin) return null;
  const label = ko.origin[origin as keyof typeof ko.origin] ?? origin;
  const style =
    origin === "synthetic" ? "badge-info" : origin === "imported" ? "badge-warn" : "badge-ok";
  return <span className={`badge ${style}`}>{label}</span>;
}
