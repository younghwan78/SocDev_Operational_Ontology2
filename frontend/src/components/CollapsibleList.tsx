/**
 * 접기 기본 목록 — UI 공통 원칙 "상위 3~5건만 펼치고 나머지 접기".
 */
import { useState, type ReactNode } from "react";
import { ko } from "../i18n/ko";

export function CollapsibleList<T>({
  items,
  limit = 5,
  render,
}: {
  items: T[];
  limit?: number;
  render: (item: T, index: number) => ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? items : items.slice(0, limit);
  return (
    <>
      {visible.map(render)}
      {items.length > limit && (
        <button type="button" className="link-btn" onClick={() => setExpanded(!expanded)}>
          {expanded ? ko.app.show_less : `${ko.app.show_more} (+${items.length - limit})`}
        </button>
      )}
    </>
  );
}
