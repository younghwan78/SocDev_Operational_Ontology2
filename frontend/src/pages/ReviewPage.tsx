import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { fetchWeeklyIndex, fetchWeeklySnapshot } from "../api/client";
import { ko } from "../i18n/ko";

const t = ko.review;

export function ReviewPage() {
  const { week } = useParams<{ week: string }>();
  const navigate = useNavigate();

  const index = useQuery({ queryKey: ["weekly-index"], queryFn: fetchWeeklyIndex });
  const selectedWeek = week ? Number(week) : undefined;
  const snapshot = useQuery({
    queryKey: ["weekly-snapshot", selectedWeek],
    queryFn: () => fetchWeeklySnapshot(selectedWeek!),
    enabled: selectedWeek !== undefined,
  });

  if (index.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (index.isError) return <p className="status-msg">{ko.app.error}</p>;

  const weeks = index.data.weeks;
  const active = selectedWeek ?? weeks[0];

  return (
    <div>
      <h1>{t.title}</h1>
      <div className="filter-row">
        <span className="filter-label">{t.week_select}</span>
        {weeks.map((w) => (
          <button
            key={w}
            className={`chip chip-btn ${w === active ? "active" : ""}`}
            onClick={() => navigate(`/review/${w}`)}
          >
            {ko.scenario_detail.week_prefix}
            {w}
          </button>
        ))}
      </div>

      {selectedWeek === undefined && weeks.length > 0 && (
        <p className="section-note">
          {t.counts
            .replace("{e}", String(index.data.event_counts[String(active)] ?? 0))
            .replace("{a}", String(index.data.activity_counts[String(active)] ?? 0))
            .replace("{r}", String(index.data.request_counts[String(active)] ?? 0))}
        </p>
      )}

      {snapshot.isPending && selectedWeek !== undefined && (
        <p className="status-msg">{ko.app.loading}</p>
      )}
      {snapshot.data && (
        <div>
          <div className="card">
            <h2 className="card-title">{t.events_section}</h2>
            {snapshot.data.events.length === 0 && <p className="section-note">{ko.app.empty}</p>}
            {snapshot.data.events.map((event) => (
              <div key={event.id} className="list-item">
                <div className="head">
                  <span className="badge badge-info">{event.severity}</span>
                  <span className="title">{event.title}</span>
                  <span className="badge badge-ok">{event.status}</span>
                </div>
                <p className="desc">{event.description}</p>
              </div>
            ))}
          </div>
          <div className="card">
            <h2 className="card-title">{t.activities_section}</h2>
            {snapshot.data.activities.length === 0 && (
              <p className="section-note">{ko.app.empty}</p>
            )}
            {snapshot.data.activities.map((activity) => (
              <div key={activity.id} className="list-item">
                <div className="head">
                  <span className="badge badge-warn">{activity.role_id}</span>
                  <span className="title">{activity.title}</span>
                </div>
                <p className="desc">{activity.summary}</p>
              </div>
            ))}
          </div>
          <div className="card">
            <h2 className="card-title">{t.requests_section}</h2>
            {snapshot.data.requests.length === 0 && <p className="section-note">{ko.app.empty}</p>}
            {snapshot.data.requests.map((request) => (
              <div key={request.id} className="list-item">
                <div className="head">
                  <span className="badge badge-danger">{request.priority}</span>
                  <span className="title">{request.title}</span>
                  <span className="badge badge-info">{request.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
