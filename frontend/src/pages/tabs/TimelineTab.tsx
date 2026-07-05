import type { TimelineItem } from "../../api/client";
import { useLabels } from "../../hooks/useLabels";
import { ko } from "../../i18n/ko";

const TYPE_BADGE: Record<string, string> = {
  event: "badge-info",
  milestone: "badge-ok",
  activity: "badge-warn",
  request: "badge-danger",
};

export function TimelineTab({ items }: { items: TimelineItem[] }) {
  const label = useLabels();
  if (items.length === 0) return <p className="status-msg">{ko.app.empty}</p>;

  const weeks = [...new Set(items.map((item) => item.week))].sort((a, b) => a - b);

  return (
    <div>
      {weeks.map((week) => (
        <div key={week} className="timeline-week card">
          <div className="week-label">
            {ko.scenario_detail.week_prefix}
            {week}
          </div>
          {items
            .filter((item) => item.week === week)
            .map((item, index) => (
              <div key={`${item.ref_id}-${index}`} className="list-item">
                <div className="head">
                  <span className={`badge ${TYPE_BADGE[item.item_type] ?? "badge-info"}`}>
                    {item.item_type_ko}
                  </span>
                  <span className="title">{item.title}</span>
                  {item.status && <span className="badge badge-info">{item.status}</span>}
                </div>
                <p className="desc">
                  {item.project_id ? label(item.project_id) : ""}
                  {item.roles.length > 0 &&
                    ` · ${ko.scenario_detail.roles}: ${item.roles.map((roleId) => label(roleId)).join(", ")}`}
                </p>
              </div>
            ))}
        </div>
      ))}
    </div>
  );
}
