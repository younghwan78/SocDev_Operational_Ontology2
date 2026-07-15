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

// D1-1 토큰 인증 — 서버가 SOC_API_TOKEN을 켠 경우에만 의미가 있다.
// 토큰은 localStorage에 보관하고, 401을 받으면 토큰 게이트 이벤트를 올린다.
export const API_TOKEN_KEY = "soc-api-token";
export const AUTH_REQUIRED_EVENT = "soc-auth-required";

export function getApiToken(): string | null {
  return typeof window === "undefined" ? null : window.localStorage.getItem(API_TOKEN_KEY);
}

export function setApiToken(token: string): void {
  window.localStorage.setItem(API_TOKEN_KEY, token.trim());
}

function notifyAuthRequired(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT));
}

client.use({
  onRequest({ request }) {
    const token = getApiToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
  onResponse({ response }) {
    if (response.status === 401) notifyAuthRequired();
    return response;
  },
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

export type ReviewPackSummary = components["schemas"]["ReviewPackSummary"];
export type ReviewPackDocument = components["schemas"]["ReviewPackDocument"];
export type ReviewPackRollup = components["schemas"]["ReviewPackRollup"];

export async function fetchReviewPacks(): Promise<ReviewPackSummary[]> {
  const { data, error } = await client.GET("/api/v1/review-packs");
  if (error || !data) throw new Error("review-packs 조회 실패");
  return data;
}

export async function fetchReviewPack(packId: string): Promise<ReviewPackDocument> {
  const { data, error } = await client.GET("/api/v1/review-packs/{pack_id}", {
    params: { path: { pack_id: packId } },
  });
  if (error || !data) throw new Error("review-pack 조회 실패");
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

export type ObjectHistory = components["schemas"]["ObjectHistory"];
export type ObjectVersion = components["schemas"]["ObjectVersion"];
export type StatusTransition = components["schemas"]["StatusTransition"];

export async function fetchObjectHistory(
  collection: string,
  objectId: string,
): Promise<ObjectHistory> {
  const { data, error } = await client.GET("/api/v1/history/{collection}/{object_id}", {
    params: { path: { collection, object_id: objectId } },
  });
  if (error || !data) throw new Error("history 조회 실패");
  return data;
}

export type AskResult = components["schemas"]["AskResult"];
export type AskCard = components["schemas"]["AskCard"];

export async function fetchAskPresets(): Promise<Record<string, string>[]> {
  const { data, error } = await client.GET("/api/v1/ask/presets");
  if (error || !data) throw new Error("ask presets 조회 실패");
  return data;
}

export async function postAsk(question: string): Promise<AskResult> {
  const { data, error } = await client.POST("/api/v1/ask", { body: { question } });
  if (error || !data) throw new Error("ask 질의 실패");
  return data;
}

export type AskPreview = components["schemas"]["AskPreview"];
export type AskLogEntry = components["schemas"]["AskLogEntry"];
export type AskFaqEntry = components["schemas"]["FAQEntry"];

export async function fetchAskPreview(question: string): Promise<AskPreview> {
  const { data, error } = await client.GET("/api/v1/ask/preview", {
    params: { query: { q: question } },
  });
  if (error || !data) throw new Error("ask preview 조회 실패");
  return data;
}

export async function fetchAskHistory(): Promise<AskLogEntry[]> {
  const { data, error } = await client.GET("/api/v1/ask/history");
  if (error || !data) throw new Error("ask history 조회 실패");
  return data;
}

export async function fetchAskFaq(): Promise<AskFaqEntry[]> {
  const { data, error } = await client.GET("/api/v1/ask/faq");
  if (error || !data) throw new Error("ask faq 조회 실패");
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

// P4 what-if 가정 실험 — ephemeral overlay 재계산 (저장 없음, 가정=assumption 지위).
export type WhatIfResult = components["schemas"]["WhatIfResult"];
export type WhatIfAssumptionInput = components["schemas"]["WhatIfAssumption"];
export type WhatIfRowChange = components["schemas"]["WhatIfRowChange"];

export async function runWhatIf(
  assumptions: WhatIfAssumptionInput[],
): Promise<WhatIfResult> {
  const { data, error } = await client.POST("/api/v1/what-if", {
    body: { assumptions },
  });
  if (error || !data) throw new Error("what-if 실행 실패");
  return data;
}

// P3 KPI 시계열 — domain time(week) 축 과제 간 비교 (결정론, 수치 점수 없음).
export type KPISeriesResult = components["schemas"]["KPISeriesResult"];
export type ProjectKPISeries = components["schemas"]["ProjectKPISeries"];
export type KPISeriesPoint = components["schemas"]["KPISeriesPoint"];

export async function fetchKPISeries(
  kpiId: string,
  scenarioId?: string,
): Promise<KPISeriesResult> {
  const { data, error } = await client.GET("/api/v1/kpi/series", {
    params: {
      query: scenarioId
        ? { kpi_id: kpiId, scenario_id: scenarioId }
        : { kpi_id: kpiId },
    },
  });
  if (error || !data) throw new Error("kpi series 조회 실패");
  return data;
}

// P2 T3 as-of 재구성 — transaction time 시점 재생 위험 지도 (meta에 가정/근사 명시).
export type AsOfMeta = components["schemas"]["AsOfMeta"];
export type AsOfRiskHeatmap = components["schemas"]["AsOfRiskHeatmap"];

export async function fetchAsOfRiskHeatmap(
  ts: string,
  projectId?: string,
): Promise<AsOfRiskHeatmap> {
  const { data, error } = await client.GET("/api/v1/as-of/risk/heatmap", {
    params: { query: projectId ? { ts, project_id: projectId } : { ts } },
  });
  if (error || !data) throw new Error("as-of risk heatmap 조회 실패");
  return data;
}

// Q3 as-of 확대 — 포트폴리오 (변경 영향 as-of는 API 표면만, UI 노출 보류 — 설계 17 §4).
export type AsOfPortfolioOverview = components["schemas"]["AsOfPortfolioOverview"];

export async function fetchAsOfPortfolio(ts: string): Promise<AsOfPortfolioOverview> {
  const { data, error } = await client.GET("/api/v1/as-of/portfolio/overview", {
    params: { query: { ts } },
  });
  if (error || !data) throw new Error("as-of portfolio 조회 실패");
  return data;
}

export type SourceCoverage = components["schemas"]["SourceCoverage"];
export type CollectionCoverage = components["schemas"]["CollectionCoverage"];

export async function fetchSourceMap(): Promise<SourceCoverage> {
  const { data, error } = await client.GET("/api/v1/source-map");
  if (error || !data) throw new Error("source-map 조회 실패");
  return data;
}

export type EntityResolutionReport = components["schemas"]["EntityResolutionReport"];
export type AliasEntry = components["schemas"]["AliasEntry"];
export type UnmatchedToken = components["schemas"]["UnmatchedToken"];

export async function fetchEntityResolution(): Promise<EntityResolutionReport> {
  const { data, error } = await client.GET("/api/v1/entity-resolution");
  if (error || !data) throw new Error("entity-resolution 조회 실패");
  return data;
}

export type ActionDraft = components["schemas"]["ActionDraft"];
export type DraftSection = components["schemas"]["DraftSection"];
export type DraftItem = components["schemas"]["DraftItem"];

export async function fetchActionDraft(scenarioId: string): Promise<ActionDraft> {
  const { data, error } = await client.GET("/api/v1/action-draft/scenario/{scenario_id}", {
    params: { path: { scenario_id: scenarioId } },
  });
  if (error || !data) throw new Error("action-draft 조회 실패");
  return data;
}

export async function fetchLabels(): Promise<Record<string, string>> {
  const { data, error } = await client.GET("/api/v1/meta/labels");
  if (error || !data) throw new Error("labels 조회 실패");
  return data;
}

export async function fetchValueLabels(): Promise<Record<string, Record<string, string>>> {
  const { data, error } = await client.GET("/api/v1/meta/glossary");
  if (error || !data) throw new Error("glossary 조회 실패");
  const glossary = data as { value_labels?: Record<string, Record<string, string>> };
  return glossary.value_labels ?? {};
}

export type IngestBatch = components["schemas"]["IngestBatch"];
export type IngestReport = components["schemas"]["IngestReport"];
export type IngestQualityReport = components["schemas"]["QualityReport"];
export type IngestMappingInfo = components["schemas"]["IngestMappingInfo"];
export type QuarantineEntry = components["schemas"]["QuarantineEntry"];

export async function fetchIngestQuarantine(): Promise<QuarantineEntry[]> {
  const { data, error } = await client.GET("/api/v1/ingest/quarantine");
  if (error || !data) throw new Error("보류 행 조회 실패");
  return data;
}
export type Decision = components["schemas"]["Decision"];
export type ActionItem = components["schemas"]["ActionItem"];

export async function fetchActionItems(): Promise<ActionItem[]> {
  const { data, error } = await client.GET("/api/v1/action-items");
  if (error || !data) throw new Error("action items 조회 실패");
  return data;
}

export async function fetchIngestMappings(): Promise<IngestMappingInfo[]> {
  const { data, error } = await client.GET("/api/v1/ingest/mappings");
  if (error || !data) throw new Error("ingest mappings 조회 실패");
  return data;
}

export async function fetchDecisions(params?: {
  projectId?: string;
  eventId?: string;
}): Promise<Decision[]> {
  const { data, error } = await client.GET("/api/v1/decisions", {
    params: {
      query: {
        ...(params?.projectId ? { project_id: params.projectId } : {}),
        ...(params?.eventId ? { event_id: params.eventId } : {}),
      },
    },
  });
  if (error || !data) throw new Error("decisions 조회 실패");
  return data;
}

// multipart 업로드는 openapi-fetch 대신 FormData 직접 — 응답 타입은 생성 스키마 사용.
export async function uploadIngestFile(file: File, mapping: string): Promise<IngestReport> {
  const form = new FormData();
  form.append("file", file);
  const token = getApiToken();
  const response = await globalThis.fetch(
    `${baseUrl}/api/v1/ingest/file?mapping=${encodeURIComponent(mapping)}`,
    {
      method: "POST",
      body: form,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    },
  );
  if (response.status === 401) notifyAuthRequired();
  if (!response.ok) {
    const detail = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(detail?.detail ?? "반입 실패");
  }
  return (await response.json()) as IngestReport;
}

export async function rollbackIngestBatch(batchId: string): Promise<number> {
  const { data, error } = await client.POST("/api/v1/ingest/batches/{batch_id}/rollback", {
    params: { path: { batch_id: batchId } },
  });
  if (error || !data) throw new Error("rollback 실패");
  return (data as { removed: number }).removed;
}

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

export type EvidenceLadder = components["schemas"]["EvidenceLadder"];
export type EvidenceStrengthItem = components["schemas"]["EvidenceStrengthItem"];
export type TierBucket = components["schemas"]["TierBucket"];

export async function fetchEvidenceLadder(filters: {
  projectId?: string;
}): Promise<EvidenceLadder> {
  const { data, error } = await client.GET("/api/v1/evidence/ladder", {
    params: {
      query: {
        ...(filters.projectId ? { project_id: filters.projectId } : {}),
      },
    },
  });
  if (error || !data) throw new Error("evidence-ladder 조회 실패");
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
