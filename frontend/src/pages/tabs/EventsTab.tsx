import type { DevelopmentEvent, RoleActivity } from "../../api/client";
import { useLabels } from "../../hooks/useLabels";
import { useValueLabels } from "../../hooks/useValueLabels";
import { ko } from "../../i18n/ko";

const t = ko.scenario_detail;

const SEVERITY_BADGE: Record<string, string> = {
  info: "badge-info",
  low: "badge-ok",
  medium: "badge-warn",
  high: "badge-danger",
  critical: "badge-danger",
};

export function EventsTab({
  events,
  activities,
}: {
  events: DevelopmentEvent[];
  activities: RoleActivity[];
}) {
  const label = useLabels();
  const valueLabel = useValueLabels();
  return (
    <div>
      <div className="card">
        <h2 className="card-title">{t.events_title}</h2>
        {events.length === 0 && <p className="section-note">{ko.app.empty}</p>}
        {events.map((event) => (
          <div key={event.id} className="list-item">
            <div className="head">
              {event.week != null && (
                <span className="badge badge-ok">
                  {t.week_prefix}
                  {event.week}
                </span>
              )}
              <span
                className={`badge ${SEVERITY_BADGE[event.severity] ?? "badge-info"}`}
                title={event.severity}
              >
                {valueLabel("severity", event.severity)}
              </span>
              <span className="title">{event.title}</span>
              <span className="badge badge-info" title={event.status}>
                {valueLabel("event_status", event.status)}
              </span>
            </div>
            <p className="desc">{event.description}</p>
            {(event.roles_involved ?? []).length > 0 && (
              <p className="desc">
                {t.roles}: {(event.roles_involved ?? []).map((roleId) => valueLabel("role", roleId)).join(", ")}
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="card">
        <h2 className="card-title">{t.activities_title}</h2>
        {activities.length === 0 && <p className="section-note">{ko.app.empty}</p>}
        {activities.map((activity) => (
          <div key={activity.id} className="list-item">
            <div className="head">
              <span className="badge badge-warn">
                {t.week_prefix}
                {activity.week}
              </span>
              <span className="badge badge-info" title={activity.role_id}>
                {label(activity.role_id)}
              </span>
              <span className="title">{activity.title}</span>
            </div>
            <p className="desc">{activity.summary}</p>
            {(activity.concerns ?? []).length > 0 && (
              <div>
                {(activity.concerns ?? []).map((concern, index) => (
                  <div key={index} className="grounded">
                    <div>
                      <strong>{t.concerns}</strong> ({t.confidence}: {concern.confidence}):{" "}
                      {concern.description}
                    </div>
                    <div className="derivation">
                      {t.derivation}: {concern.description_derivation}
                    </div>
                    <div className="derivation">
                      {t.supporting_basis}: {concern.supporting_basis.join(", ")}
                    </div>
                  </div>
                ))}
              </div>
            )}
            <p className="desc">
              {t.recommendation}: {activity.recommendation.summary}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
