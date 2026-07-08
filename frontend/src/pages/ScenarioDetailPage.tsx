import { useQuery } from "@tanstack/react-query";
import { NavLink, useParams } from "react-router-dom";
import { fetchScenarioAnalysis } from "../api/client";
import { TraceabilityPanel } from "../components/TraceabilityPanel";
import { ko } from "../i18n/ko";
import { ActionDraftTab } from "./tabs/ActionDraftTab";
import { AdvisoryTab } from "./tabs/AdvisoryTab";
import { EventsTab } from "./tabs/EventsTab";
import { OverviewTab } from "./tabs/OverviewTab";
import { TimelineTab } from "./tabs/TimelineTab";

const TABS = [
  { key: "overview", label: ko.scenario_detail.tab_overview },
  { key: "timeline", label: ko.scenario_detail.tab_timeline },
  { key: "events", label: ko.scenario_detail.tab_events },
  { key: "advisory", label: ko.advisory.tab },
  { key: "action-draft", label: ko.action_draft.tab },
  { key: "trace", label: ko.scenario_detail.tab_trace },
] as const;

export function ScenarioDetailPage() {
  const { scenarioId, tab } = useParams<{ scenarioId: string; tab: string }>();

  const analysis = useQuery({
    queryKey: ["analysis", scenarioId],
    queryFn: () => fetchScenarioAnalysis(scenarioId!),
    enabled: Boolean(scenarioId),
  });

  if (!scenarioId) return <p className="status-msg">{ko.scenario_detail.not_found}</p>;
  if (analysis.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (analysis.isError) return <p className="status-msg">{ko.scenario_detail.not_found}</p>;

  const data = analysis.data;

  return (
    <div>
      <h1>{data.scenario.name}</h1>
      <nav className="tabs">
        {TABS.map(({ key, label }) => (
          <NavLink
            key={key}
            to={`/scenarios/${scenarioId}/${key}`}
            className={({ isActive }) => `tab ${isActive ? "active" : ""}`}
          >
            {label}
          </NavLink>
        ))}
      </nav>
      {tab === "overview" && <OverviewTab analysis={data} />}
      {tab === "timeline" && <TimelineTab items={data.timeline} />}
      {tab === "events" && <EventsTab events={data.events} activities={data.activities} />}
      {tab === "advisory" && <AdvisoryTab scenarioId={scenarioId} />}
      {tab === "action-draft" && <ActionDraftTab scenarioId={scenarioId} />}
      {tab === "trace" && <TraceabilityPanel rootId={scenarioId} />}
    </div>
  );
}
