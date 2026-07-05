/**
 * 타입 안전 API 클라이언트 — openapi-typescript 생성 스키마 기반.
 * 수동 타입 작성 금지. 재생성: npm run gen:api
 */
import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

// 상대 URL은 테스트(Node fetch)에서 불가하므로 origin을 절대 기본값으로 쓴다.
// 개발 시에는 vite proxy(/api → 127.0.0.1:8000)가 전달한다.
const baseUrl =
  import.meta.env.VITE_API_BASE ||
  (typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:8000");

export const client = createClient<paths>({
  baseUrl,
  // fetch를 늦은 바인딩으로 위임 — 테스트의 fetch stub이 적용되게 한다.
  fetch: (request) => globalThis.fetch(request),
});

export type Scenario = components["schemas"]["Scenario"];
export type ScenarioAnalysis = components["schemas"]["ScenarioAnalysis"];
export type DevelopmentEvent = components["schemas"]["DevelopmentEvent"];
export type RoleActivity = components["schemas"]["RoleActivity"];
export type ScenarioRequest = components["schemas"]["ScenarioRequest"];
export type EvidenceGapItem = components["schemas"]["EvidenceGapItem"];
export type TimelineItem = components["schemas"]["TimelineItem"];
export type TraceabilityResult = components["schemas"]["TraceabilityResult"];
export type TraceLink = components["schemas"]["TraceLink"];
export type Project = components["schemas"]["Project"];

export async function fetchScenarios(projectId?: string): Promise<Scenario[]> {
  const { data, error } = await client.GET("/api/v1/scenarios", {
    params: { query: projectId ? { project_id: projectId } : {} },
  });
  if (error || !data) throw new Error("scenarios 조회 실패");
  return data;
}

export async function fetchProjects(): Promise<Project[]> {
  const { data, error } = await client.GET("/api/v1/projects");
  if (error || !data) throw new Error("projects 조회 실패");
  return data;
}

export async function fetchScenarioAnalysis(scenarioId: string): Promise<ScenarioAnalysis> {
  const { data, error } = await client.GET("/api/v1/scenarios/{scenario_id}/analysis", {
    params: { path: { scenario_id: scenarioId } },
  });
  if (error || !data) throw new Error("analysis 조회 실패");
  return data;
}

export async function fetchTraceability(objectId: string): Promise<TraceabilityResult> {
  const { data, error } = await client.GET("/api/v1/traceability/{object_id}", {
    params: { path: { object_id: objectId } },
  });
  if (error || !data) throw new Error("traceability 조회 실패");
  return data;
}

export type AgentRun = components["schemas"]["AgentRun"];
export type RoleAdvisory = components["schemas"]["RoleAdvisory"];
export type PortfolioOverview = components["schemas"]["PortfolioOverview"];
export type AttentionItem = components["schemas"]["AttentionItem"];
export type ScenarioCell = components["schemas"]["ScenarioCell"];
export type WeeklyIndex = components["schemas"]["WeeklyIndex"];
export type WeeklySnapshot = components["schemas"]["WeeklySnapshot"];
export type EvidenceCatalogEntry = components["schemas"]["EvidenceCatalogEntry"];

export async function fetchPortfolio(): Promise<PortfolioOverview> {
  const { data, error } = await client.GET("/api/v1/portfolio/overview");
  if (error || !data) throw new Error("portfolio 조회 실패");
  return data;
}

export async function fetchWeeklyIndex(): Promise<WeeklyIndex> {
  const { data, error } = await client.GET("/api/v1/review/weekly");
  if (error || !data) throw new Error("weekly index 조회 실패");
  return data;
}

export async function fetchWeeklySnapshot(week: number): Promise<WeeklySnapshot> {
  const { data, error } = await client.GET("/api/v1/review/weekly/{week}", {
    params: { path: { week } },
  });
  if (error || !data) throw new Error("weekly snapshot 조회 실패");
  return data;
}

export type RiskHeatmap = components["schemas"]["RiskHeatmap"];
export type ScenarioRiskRow = components["schemas"]["ScenarioRiskRow"];
export type RiskCell = components["schemas"]["RiskCell"];
export type BasisItem = components["schemas"]["BasisItem"];
export type HeatmapColumn = components["schemas"]["HeatmapColumn"];
export type WeeklyFocusItem = components["schemas"]["WeeklyFocusItem"];
export type ChangeImpactResult = components["schemas"]["ChangeImpactResult"];
export type ChangeImpactOptions = components["schemas"]["ChangeImpactOptions"];
export type IPOption = components["schemas"]["IPOption"];
export type ImpactedScenario = components["schemas"]["ImpactedScenario"];
export type ImpactedKPI = components["schemas"]["ImpactedKPI"];
export type ChainedIP = components["schemas"]["ChainedIP"];
export type ChecklistItem = components["schemas"]["ChecklistItem"];
export type SimilarCase = components["schemas"]["SimilarCase"];

export type IssueSummary = components["schemas"]["IssueSummary"];
export type RCAChain = components["schemas"]["RCAChain"];
export type RCANode = components["schemas"]["RCANode"];
export type RCAItem = components["schemas"]["RCAItem"];

export async function fetchIssues(filters: {
  projectId?: string;
  verification?: string;
}): Promise<IssueSummary[]> {
  const { data, error } = await client.GET("/api/v1/issues", {
    params: {
      query: {
        ...(filters.projectId ? { project_id: filters.projectId } : {}),
        ...(filters.verification ? { verification: filters.verification } : {}),
      },
    },
  });
  if (error || !data) throw new Error("issues 조회 실패");
  return data;
}

export async function fetchIssueRCA(issueId: string): Promise<RCAChain> {
  const { data, error } = await client.GET("/api/v1/issues/{issue_id}/rca", {
    params: { path: { issue_id: issueId } },
  });
  if (error || !data) throw new Error("rca 조회 실패");
  return data;
}

export interface ChangeImpactParams {
  ipId: string;
  knobId?: string;
  capabilityId?: string;
  mode?: string;
}

export async function fetchChangeImpactOptions(): Promise<ChangeImpactOptions> {
  const { data, error } = await client.GET("/api/v1/change-impact/options");
  if (error || !data) throw new Error("change-impact options 조회 실패");
  return data;
}

export async function fetchChangeImpact(params: ChangeImpactParams): Promise<ChangeImpactResult> {
  const { data, error } = await client.GET("/api/v1/change-impact", {
    params: {
      query: {
        ip_id: params.ipId,
        ...(params.knobId ? { knob_id: params.knobId } : {}),
        ...(params.capabilityId ? { capability_id: params.capabilityId } : {}),
        ...(params.mode ? { mode: params.mode } : {}),
      },
    },
  });
  if (error || !data) throw new Error("change-impact 분석 실패");
  return data;
}

export async function fetchRiskHeatmap(projectId?: string): Promise<RiskHeatmap> {
  const { data, error } = await client.GET("/api/v1/risk/heatmap", {
    params: { query: projectId ? { project_id: projectId } : {} },
  });
  if (error || !data) throw new Error("risk heatmap 조회 실패");
  return data;
}

export async function fetchLabels(): Promise<Record<string, string>> {
  const { data, error } = await client.GET("/api/v1/meta/labels");
  if (error || !data) throw new Error("labels 조회 실패");
  return data;
}

export type IngestBatch = components["schemas"]["IngestBatch"];

export async function fetchIngestBatches(): Promise<IngestBatch[]> {
  const { data, error } = await client.GET("/api/v1/ingest/batches");
  if (error || !data) throw new Error("ingest batches 조회 실패");
  return data;
}

export async function fetchEvidence(filters: {
  projectId?: string;
  availability?: string;
}): Promise<EvidenceCatalogEntry[]> {
  const { data, error } = await client.GET("/api/v1/evidence", {
    params: {
      query: {
        ...(filters.projectId ? { project_id: filters.projectId } : {}),
        ...(filters.availability ? { availability: filters.availability } : {}),
      },
    },
  });
  if (error || !data) throw new Error("evidence 조회 실패");
  return data;
}

export async function fetchAdvisoryRuns(scenarioId: string): Promise<AgentRun[]> {
  const { data, error } = await client.GET("/api/v1/scenarios/{scenario_id}/advisory", {
    params: { path: { scenario_id: scenarioId } },
  });
  if (error || !data) throw new Error("advisory 조회 실패");
  return data;
}

export async function runAdvisory(scenarioId: string, roles?: string[]): Promise<AgentRun> {
  const { data, error } = await client.POST("/api/v1/scenarios/{scenario_id}/advisory", {
    params: { path: { scenario_id: scenarioId } },
    body: { roles: roles ?? null },
  });
  if (error || !data) throw new Error("advisory 실행 실패");
  return data;
}
