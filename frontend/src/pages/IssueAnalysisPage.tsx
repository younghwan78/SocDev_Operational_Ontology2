/**
 * 이슈 분석 화면 — "이 이슈의 원인은? 정말 해결됐나? 재발하나?"
 * 이슈 선택 → 증상→영향→원인→조치→검증 테스트→잔존 리스크→재사용 교훈의 세로 RCA 흐름.
 * 각 노드에 근거 뱃지(초록=있음/빨강=없음/노랑=미검증) — "검증 테스트 없는 close 이슈"가
 * 빨갛게 드러나는 것이 이 화면의 존재 이유다.
 */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchIssueRCA,
  fetchIssues,
  fetchObjectHistory,
  fetchProjects,
  runWhatIf,
  type IssueSummary,
  type RCAChain,
  type RCAItem,
  type RCANode,
  type WhatIfResult,
} from "../api/client";
import { CollapsibleList } from "../components/CollapsibleList";
import { useValueLabels } from "../hooks/useValueLabels";
import { ko } from "../i18n/ko";

const t = ko.issues;

const BADGE_CLASS: Record<string, string> = {
  green: "badge-ok",
  red: "badge-danger",
  yellow: "badge-warn",
};
const BADGE_LABEL: Record<string, string> = {
  green: t.badge_green,
  red: t.badge_red,
  yellow: t.badge_yellow,
};
const VERIFICATION_BADGE: Record<string, string> = {
  verified: "badge-ok",
  unverified: "badge-warn",
  no_tests: "badge-danger",
};
const VERIFICATION_FILTERS: { value: string; label: string }[] = [
  { value: "verified", label: t.verification_verified },
  { value: "unverified", label: t.verification_unverified },
  { value: "no_tests", label: t.verification_no_tests },
];

// 상황판 플래그 필터 — 숫자 카드 클릭이 곧 필터 (URL=상태).
const CLOSED_STATUSES = new Set(["closed", "resolved", "done"]);
const FLAG_FILTERS: Record<string, (issue: IssueSummary) => boolean> = {
  closed_unverified: (issue) => issue.closed_without_verification,
  open: (issue) => !CLOSED_STATUSES.has(issue.status),
  attention: (issue) => Boolean(issue.stale || issue.overdue || issue.reopened),
};

/** 유형별 분포 × 검증 상태 세그먼트 막대 데이터. */
function typeDistribution(issues: IssueSummary[], limit = 6) {
  const byType = new Map<string, IssueSummary[]>();
  for (const issue of issues) {
    const list = byType.get(issue.issue_type) ?? [];
    list.push(issue);
    byType.set(issue.issue_type, list);
  }
  const sorted = [...byType.entries()].sort(
    (a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]),
  );
  const top = sorted.slice(0, limit);
  const rest = sorted.slice(limit).flatMap(([, list]) => list);
  const rows = top.map(([type, list]) => ({ type, issues: list }));
  if (rest.length > 0) rows.push({ type: "__other__", issues: rest });
  return rows;
}

export function IssueAnalysisPage() {
  // URL=상태: 필터/검색/선택을 URL에 반영 — 새로고침·공유가 화면을 재현한다.
  const [searchParams, setSearchParams] = useSearchParams();
  const projectFilter = searchParams.get("project") ?? undefined;
  const verificationFilter = searchParams.get("verification") ?? undefined;
  const selectedIssue = searchParams.get("issue");
  const urlQuery = searchParams.get("q") ?? "";
  const [queryDraft, setQueryDraft] = useState(urlQuery);
  const updateParams = (patch: Record<string, string | null>) => {
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        for (const [key, value] of Object.entries(patch)) {
          if (value === null) next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );
  };
  // 300ms debounce로 q를 URL에 반영 (타이핑마다 히스토리 오염 방지).
  useEffect(() => {
    const timer = setTimeout(() => {
      if (queryDraft !== urlQuery) updateParams({ q: queryDraft || null });
    }, 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryDraft]);
  const setProjectFilter = (value: string | undefined) =>
    updateParams({ project: value ?? null });
  const setVerificationFilter = (value: string | undefined) =>
    updateParams({ verification: value ?? null });
  const setSelectedIssue = (value: string | null) => updateParams({ issue: value });

  // 분포 카드 접기 — 선택은 localStorage에 유지 (화면 공간 확보용).
  const [distOpen, setDistOpen] = useState(
    () => window.localStorage.getItem("issues-dist-open") !== "0",
  );
  const toggleDist = () =>
    setDistOpen((previous) => {
      window.localStorage.setItem("issues-dist-open", previous ? "0" : "1");
      return !previous;
    });

  const valueLabel = useValueLabels();
  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  // 서버 필터는 프로젝트만 — 검증/유형/플래그는 클라이언트에서 걸러
  // 상황판·칩 카운트가 항상 전체 분포를 보게 한다 (수백 건 규모까지 문제없음).
  const issues = useQuery({
    queryKey: ["issues", projectFilter],
    queryFn: () => fetchIssues({ projectId: projectFilter }),
  });
  const chain = useQuery({
    queryKey: ["issue-rca", selectedIssue],
    queryFn: () => fetchIssueRCA(selectedIssue!),
    enabled: selectedIssue !== null,
  });

  const flagFilter = searchParams.get("flag");
  const typeFilter = searchParams.get("type");
  const allIssues = issues.data ?? [];
  const query = urlQuery.trim().toLowerCase();
  const visibleIssues = allIssues.filter(
    (issue) =>
      (!verificationFilter || issue.verification === verificationFilter) &&
      (!typeFilter || issue.issue_type === typeFilter) &&
      (!flagFilter || (FLAG_FILTERS[flagFilter]?.(issue) ?? true)) &&
      (!query ||
        issue.title.toLowerCase().includes(query) ||
        issue.issue_type.toLowerCase().includes(query)),
  );

  const boardStats = [
    { key: null, label: t.board_total, count: allIssues.length, danger: false },
    {
      key: "closed_unverified",
      label: t.board_closed_unverified,
      count: allIssues.filter(FLAG_FILTERS.closed_unverified).length,
      danger: true,
    },
    {
      key: "open",
      label: t.board_open,
      count: allIssues.filter(FLAG_FILTERS.open).length,
      danger: false,
    },
    {
      key: "attention",
      label: t.board_attention,
      count: allIssues.filter(FLAG_FILTERS.attention).length,
      danger: false,
    },
  ];
  const verificationCounts = new Map<string, number>();
  for (const issue of allIssues)
    verificationCounts.set(
      issue.verification,
      (verificationCounts.get(issue.verification) ?? 0) + 1,
    );

  if (issues.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (issues.isError) return <p className="status-msg">{ko.app.error}</p>;

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">{t.subtitle}</p>

      {/* I1 이슈 상황판 — 숫자 카드 클릭 = 필터, 분포 막대 클릭 = 유형 필터 */}
      <div className="stat-strip">
        {boardStats.map((stat) => (
          <button
            key={stat.label}
            type="button"
            className={`stat ${stat.danger && stat.count > 0 ? "stat-danger" : ""} ${
              flagFilter === stat.key || (stat.key === null && !flagFilter) ? "stat-active" : ""
            }`}
            onClick={() => updateParams({ flag: stat.key })}
          >
            <b>{stat.count}</b>
            <span>{stat.label}</span>
          </button>
        ))}
      </div>

      <div className="card dist-card">
        <button
          type="button"
          className="head rca-head-btn"
          aria-expanded={distOpen}
          onClick={toggleDist}
        >
          <h2 className="card-title dist-title">{t.board_types}</h2>
          <span className="rca-toggle-hint">
            {distOpen ? t.toggle_hide : t.toggle_show} {distOpen ? "−" : "+"}
          </span>
        </button>
        {distOpen && (
          <TypeDistribution
            issues={allIssues}
            activeType={typeFilter}
            onToggle={(type) => updateParams({ type: typeFilter === type ? null : type })}
            valueLabel={valueLabel}
          />
        )}
      </div>

      <div className="filter-row">
        <span className="filter-label">{ko.scenario_list.filter_label}</span>
        <button
          className={`chip chip-btn ${projectFilter === undefined ? "active" : ""}`}
          onClick={() => setProjectFilter(undefined)}
        >
          {t.filter_all}
        </button>
        {(projects.data ?? []).map((project) => (
          <button
            key={project.id}
            title={project.id}
            className={`chip chip-btn ${projectFilter === project.id ? "active" : ""}`}
            onClick={() => setProjectFilter(project.id)}
          >
            {project.name}
          </button>
        ))}
        <span className="filter-label">{t.filter_verification}</span>
        <button
          className={`chip chip-btn ${verificationFilter === undefined ? "active" : ""}`}
          onClick={() => setVerificationFilter(undefined)}
        >
          {t.filter_all}
        </button>
        {VERIFICATION_FILTERS.map((option) => (
          <button
            key={option.value}
            className={`chip chip-btn ${verificationFilter === option.value ? "active" : ""}`}
            onClick={() => setVerificationFilter(option.value)}
          >
            {option.label} ({verificationCounts.get(option.value) ?? 0})
          </button>
        ))}
        <label className="filter-label" htmlFor="issue-search">
          {t.search_label}
        </label>
        <input
          id="issue-search"
          type="search"
          className="search-input"
          value={queryDraft}
          placeholder={t.search_placeholder}
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => setQueryDraft(event.target.value)}
        />
      </div>

      <div className="rca-layout">
        <div className="card issue-list">
          <h2 className="card-title">
            {t.list_title} ({visibleIssues.length})
          </h2>
          <CollapsibleList
            items={visibleIssues}
            limit={12}
            render={(issue: IssueSummary) => (
              <button
                key={issue.issue_id}
                type="button"
                title={issue.issue_id}
                className={`issue-row ${selectedIssue === issue.issue_id ? "issue-selected" : ""} ${
                  issue.closed_without_verification ? "issue-alert" : ""
                }`}
                onClick={() => setSelectedIssue(issue.issue_id)}
              >
                <span className={`badge ${VERIFICATION_BADGE[issue.verification] ?? "badge-info"}`}>
                  {issue.verification_ko}
                </span>
                {issue.stale && (
                  <span className="badge badge-warn" title={issue.freshness_ko ?? ""}>
                    {t.stale_badge}
                  </span>
                )}
                {issue.overdue && (
                  <span className="badge badge-danger" title={issue.freshness_ko ?? ""}>
                    {t.overdue_badge}
                  </span>
                )}
                {issue.reopened && (
                  <span className="badge badge-warn" title={issue.freshness_ko ?? ""}>
                    {t.reopened_badge}
                  </span>
                )}
                <span className="title">
                  {issue.severity && (
                    <span
                      className={`sev-dot sev-${issue.severity}`}
                      title={`${t.severity_label}: ${valueLabel("severity", issue.severity)}`}
                    />
                  )}
                  {issue.title}
                </span>
                <span className="desc" title={`${issue.issue_type} · ${issue.status}`}>
                  {valueLabel("issue_type", issue.issue_type)} · {t.status_label}:{" "}
                  {valueLabel("issue_status", issue.status)}
                  {(issue.scenario_ids ?? []).length > 0 &&
                    ` · ${t.scenario_count} ${(issue.scenario_ids ?? []).length}`}
                </span>
              </button>
            )}
          />
        </div>

        <div>
          {selectedIssue === null && <p className="status-msg">{t.select_hint}</p>}
          {chain.isFetching && <p className="status-msg">{ko.app.loading}</p>}
          {chain.isError && <p className="status-msg">{ko.app.error}</p>}
          {selectedIssue !== null && chain.data && !chain.isFetching && (
            <RCAFlow chainData={chain.data} />
          )}
        </div>
      </div>
    </div>
  );
}

/** I1 — 유형별 가로 세그먼트 막대: 길이=건수, 색 분해=검증 상태. 클릭=유형 필터 토글. */
function TypeDistribution({
  issues,
  activeType,
  onToggle,
  valueLabel,
}: {
  issues: IssueSummary[];
  activeType: string | null;
  onToggle: (type: string) => void;
  valueLabel: (domain: string, value: string | null | undefined) => string;
}) {
  const rows = typeDistribution(issues);
  if (rows.length === 0) return <p className="desc">{ko.app.empty}</p>;
  const maxCount = Math.max(...rows.map((row) => row.issues.length));
  const segments = (list: IssueSummary[]) =>
    (["no_tests", "unverified", "verified"] as const).map((verification) => ({
      verification,
      count: list.filter((issue) => issue.verification === verification).length,
    }));
  return (
    <div className="dist-rows">
      {rows.map((row) => {
        const isOther = row.type === "__other__";
        const label = isOther ? t.board_other : valueLabel("issue_type", row.type);
        const total = row.issues.length;
        return (
          <button
            key={row.type}
            type="button"
            disabled={isOther}
            title={isOther ? "" : row.type}
            className={`dist-row ${activeType === row.type ? "dist-active" : ""}`}
            onClick={() => !isOther && onToggle(row.type)}
          >
            <span className="dist-label">{label}</span>
            <span className="dist-track" style={{ width: `${(total / maxCount) * 100}%` }}>
              {segments(row.issues).map(
                (segment) =>
                  segment.count > 0 && (
                    <span
                      key={segment.verification}
                      className={`dist-seg dist-${segment.verification}`}
                      style={{ flex: segment.count }}
                    />
                  ),
              )}
            </span>
            <span className="dist-count">{total}</span>
          </button>
        );
      })}
      <div className="origin-legend">
        <span className="origin-key">
          <span className="origin-dot dist-no_tests" /> {t.verification_no_tests}
        </span>
        <span className="origin-key">
          <span className="origin-dot dist-unverified" /> {t.verification_unverified}
        </span>
        <span className="origin-key">
          <span className="origin-dot dist-verified" /> {t.verification_verified}
        </span>
      </div>
    </div>
  );
}

function RCAFlow({ chainData }: { chainData: RCAChain }) {
  const valueLabel = useValueLabels();
  // 시간 모델 T2: 반입·동기화로 캡처된 버전 이력 — synthetic 이슈는 빈 이력(섹션 숨김).
  const history = useQuery({
    queryKey: ["issue-history", chainData.issue_id],
    queryFn: () => fetchObjectHistory("issues", chainData.issue_id),
  });
  // I2 위계: 문제(빨강/노랑) 스텝은 펼치고, 정상(초록)은 한 줄 요약으로 접는다.
  // 이슈가 바뀌면 override를 render 중 리셋 (effect 아님 — AskPage draft 패턴).
  const [openState, setOpenState] = useState<{
    issueId: string;
    map: Record<string, boolean>;
  }>({ issueId: chainData.issue_id, map: {} });
  if (openState.issueId !== chainData.issue_id) {
    setOpenState({ issueId: chainData.issue_id, map: {} });
  }
  const openMap = openState.map;
  const setOpenMap = (map: Record<string, boolean>) =>
    setOpenState({ issueId: chainData.issue_id, map });
  const setAll = (open: boolean) =>
    setOpenMap(Object.fromEntries(chainData.nodes.map((node) => [node.step, open])));
  const openStep = (step: string) => {
    setOpenMap({ ...openMap, [step]: true });
    document
      .getElementById(`rca-step-${step}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  return (
    <div>
      {/* 경고는 전폭 배너 — 이 화면의 핵심 발견을 최상단에 */}
      {chainData.alert_ko && <p className="rca-alert rca-banner">⚠ {chainData.alert_ko}</p>}
      {/* P1 프로세스 신호: 재개 이력 — 전이 근거(버전·날짜) 동반 사실 서술 */}
      {chainData.reopened && (
        <p className="rca-alert rca-banner">
          ⚠ {t.reopened_alert}
          {chainData.reopen_note_ko ? ` — ${chainData.reopen_note_ko}` : ""}
        </p>
      )}

      <div className="card">
        <div className="head">
          <span className="title" title={chainData.issue_id}>
            {chainData.title}
          </span>
          <span className="badge badge-info" title={chainData.issue_type}>
            {valueLabel("issue_type", chainData.issue_type)}
          </span>
          <span className="badge badge-info" title={chainData.status}>
            {t.status_label}: {valueLabel("issue_status", chainData.status)}
          </span>
          <span className={`badge ${VERIFICATION_BADGE[chainData.verification] ?? "badge-info"}`}>
            {t.verification_label}: {chainData.verification_ko}
          </span>
        </div>
        {/* I2 미니맵 — 체인의 끊긴 고리가 한눈에. 클릭=해당 스텝 펼침+이동 */}
        <div className="rca-stepper-row">
          <div className="rca-stepper">
            {chainData.nodes.map((node) => (
              <button
                key={node.step}
                type="button"
                className={`step-node step-${node.badge}`}
                title={`${node.step_ko} — ${node.badge_reason_ko}`}
                aria-label={`${node.step_ko}: ${node.badge_reason_ko}`}
                onClick={() => openStep(node.step)}
              >
                <span className="step-dot" />
                <span className="step-name">{node.step_ko}</span>
              </button>
            ))}
          </div>
          <span className="rca-stepper-actions">
            <button type="button" className="link-btn" onClick={() => setAll(true)}>
              {t.expand_all}
            </button>
            <button type="button" className="link-btn" onClick={() => setAll(false)}>
              {t.collapse_all}
            </button>
          </span>
        </div>
      </div>

      <div className="rca-flow">
        {chainData.nodes.map((node) => (
          <RCAStep
            key={node.step}
            node={node}
            open={openMap[node.step] ?? node.badge !== "green"}
            onToggle={() =>
              setOpenMap({
                ...openMap,
                [node.step]: !(openMap[node.step] ?? node.badge !== "green"),
              })
            }
          />
        ))}
      </div>

      {/* P4 what-if: 가정 실험 — ephemeral 재계산, 저장 없음 */}
      <WhatIfCard chainData={chainData} />

      {/* 시간 모델 T2: 상태 전이 타임라인 — recorded_at은 twin이 알게 된 시각(transaction time) */}
      {(history.data?.status_transitions ?? []).length > 0 && (
        <div className="card">
          <div className="head">
            <h2 className="card-title">{t.history_title}</h2>
          </div>
          <p className="section-note">{t.history_note}</p>
          {(history.data?.status_transitions ?? []).map((transition) => {
            const version = (history.data?.versions ?? []).find(
              (v) => v.version === transition.version,
            );
            // Q1 프로세스 전이 판정 — version 번호로 매칭 (건너뜀/역행/미등재).
            const finding = (chainData.transition_findings ?? []).find(
              (f) => f.version === transition.version,
            );
            return (
              <div key={transition.version} className="list-item">
                <div className="head">
                  <span className="badge badge-info">
                    {t.history_version_prefix}
                    {transition.version}
                  </span>
                  <span className="title">
                    {transition.from_status
                      ? valueLabel("issue_status", transition.from_status)
                      : t.history_created}{" "}
                    → {valueLabel("issue_status", transition.to_status)}
                  </span>
                  {finding && (
                    <span
                      className={`badge ${
                        finding.kind === "backward" ? "badge-danger" : "badge-warn"
                      }`}
                      title={finding.note_ko}
                    >
                      {finding.kind_ko}
                    </span>
                  )}
                  <span className="desc">
                    {new Date(transition.recorded_at).toLocaleString("ko-KR")}
                  </span>
                </div>
                {finding && <p className="desc">{finding.note_ko}</p>}
                {(version?.changed_fields ?? []).length > 0 && (
                  <p className="desc">
                    {t.history_changed_fields}: {(version?.changed_fields ?? []).join(", ")}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* J4: 관련 문서 후보 — 상세가 Confluence 등 외부 문서에 있는 이슈의 추적 고리 */}
      {((chainData.doc_refs ?? []).length > 0 ||
        (chainData.doc_candidates ?? []).length > 0) && (
        <div className="card">
          <div className="head">
            <h2 className="card-title">{t.doc_candidates_title}</h2>
            <span className="badge badge-warn">{t.doc_not_evidence}</span>
          </div>
          {(chainData.doc_refs ?? []).map((ref) => (
            <p key={ref} className="desc">
              <span className="badge badge-info">{t.doc_ref_label}</span> {ref}
            </p>
          ))}
          {(chainData.doc_candidates ?? []).map((item, index) => (
            <div key={`${item.ref_id}-${index}`} className="list-item">
              <div className="head">
                <span className="title" title={item.ref_id ?? ""}>
                  {item.title}
                </span>
              </div>
              <p className="desc">{item.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const GRADE_BADGE: Record<string, string> = {
  high: "risk-high-badge",
  medium: "risk-medium-badge",
  low: "risk-low-badge",
};

/** P4 what-if — "이 이슈가 해결되면/다시 열리면 위험 지도가 어떻게 변하나" 1클릭 가정 실험. */
function WhatIfCard({ chainData }: { chainData: RCAChain }) {
  const valueLabel = useValueLabels();
  const closed = CLOSED_STATUSES.has(chainData.status);
  const assumedValue = closed ? "open" : "resolved";
  const [state, setState] = useState<{
    issueId: string;
    status: "idle" | "loading" | "error";
    result: WhatIfResult | null;
  }>({ issueId: chainData.issue_id, status: "idle", result: null });
  // 이슈가 바뀌면 결과를 리셋 (render 중 자기 상태 리셋 패턴 — RCAFlow openState와 동일).
  if (state.issueId !== chainData.issue_id) {
    setState({ issueId: chainData.issue_id, status: "idle", result: null });
  }

  const execute = async () => {
    setState({ issueId: chainData.issue_id, status: "loading", result: null });
    try {
      const result = await runWhatIf([
        {
          kind: "issue_status",
          target_id: chainData.issue_id,
          value: assumedValue,
          note: t.whatif_auto_note,
        },
      ]);
      setState({ issueId: chainData.issue_id, status: "idle", result });
    } catch {
      setState({ issueId: chainData.issue_id, status: "error", result: null });
    }
  };

  const result = state.result;
  return (
    <div className="card">
      <div className="head">
        <h2 className="card-title">{t.whatif_title}</h2>
        <span className="badge badge-warn">{t.whatif_assumption_badge}</span>
      </div>
      <p className="section-note">{t.whatif_note}</p>
      <button
        type="button"
        className="run-btn"
        disabled={state.status === "loading"}
        onClick={execute}
      >
        {closed ? t.whatif_button_reopen : t.whatif_button_resolve}
      </button>{" "}
      {/* X1 (설계 19) — 같은 가정을 위험 지도 워크벤치에서 오버레이로 본다 */}
      <Link
        to={`/?project=${chainData.project_id}&whatif=${encodeURIComponent(
          JSON.stringify([
            {
              kind: "issue_status",
              target_id: chainData.issue_id,
              value: assumedValue,
              note: t.whatif_auto_note,
            },
          ]),
        )}`}
        className="chip-link"
      >
        {t.whatif_open_map}
      </Link>
      {state.status === "loading" && <p className="status-msg">{ko.app.loading}</p>}
      {state.status === "error" && <p className="status-msg">{ko.app.error}</p>}
      {result && (
        <div>
          {result.assumptions.map((assumption) => (
            <p key={assumption.target_id} className="desc">
              {assumption.kind_ko}: '
              {assumption.from_value
                ? valueLabel("issue_status", assumption.from_value)
                : "—"}
              ' → '{valueLabel("issue_status", assumption.to_value)}' ·{" "}
              {t.whatif_confidence}: {assumption.confidence}
            </p>
          ))}
          {result.changed_rows.length === 0 && (
            <p className="desc">
              {t.whatif_no_change} ({t.whatif_unchanged}:{" "}
              {result.unchanged_scenario_count})
            </p>
          )}
          {result.changed_rows.map((row) => (
            <div key={row.scenario_id} className="list-item">
              <div className="head">
                <span className="title" title={row.scenario_id}>
                  {row.scenario_name}
                </span>
                <span className={`badge ${GRADE_BADGE[row.baseline_grade] ?? "badge-info"}`}>
                  {row.baseline_grade_ko}
                </span>
                <span>→</span>
                <span className={`badge ${GRADE_BADGE[row.projected_grade] ?? "badge-info"}`}>
                  {row.projected_grade_ko}
                </span>
                <Link
                  to={`/scenarios/${row.scenario_id}/overview`}
                  className="chip-link"
                  title={row.scenario_id}
                >
                  {t.scenario_link}
                </Link>
              </div>
              {(row.changed_cells ?? []).map((cell) => (
                <p key={cell.ip_id} className="desc" title={cell.ip_id}>
                  {cell.ip_id}: {cell.baseline_grade_ko} → {cell.projected_grade_ko}
                  {(cell.projected_basis ?? [])[0] &&
                    ` — ${(cell.projected_basis ?? [])[0].description}`}
                </p>
              ))}
            </div>
          ))}
          {result.changed_rows.length > 0 && (
            <p className="desc">
              {t.whatif_unchanged}: {result.unchanged_scenario_count}
            </p>
          )}
          {/* Q2: 위험 지도에 안 보이는 이슈 신호 변화 (지연/정체/검증/상태) */}
          {(result.changed_issue_signals ?? []).length > 0 && (
            <div>
              <p className="desc">
                <b>{t.whatif_issue_signals}</b>
              </p>
              {(result.changed_issue_signals ?? []).map((signal) => (
                <p key={signal.issue_id} className="desc" title={signal.issue_id}>
                  {signal.title}
                  {signal.appeared
                    ? ` — ${t.whatif_appeared}`
                    : `: ${(signal.changes ?? []).join(" · ")}`}
                  {signal.projected_note_ko ? ` (${signal.projected_note_ko})` : ""}
                </p>
              ))}
            </div>
          )}
          <p className="section-note">{result.note_ko}</p>
        </div>
      )}
    </div>
  );
}

function RCAStep({
  node,
  open,
  onToggle,
}: {
  node: RCANode;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      id={`rca-step-${node.step}`}
      className={`card rca-node rca-${node.badge} ${open ? "" : "rca-collapsed"}`}
    >
      <button
        type="button"
        className="head rca-head-btn"
        aria-expanded={open}
        onClick={onToggle}
      >
        <span className="title">{node.step_ko}</span>
        <span className={`badge ${BADGE_CLASS[node.badge]}`}>{BADGE_LABEL[node.badge]}</span>
        <span className="desc">{node.badge_reason_ko}</span>
        <span className="rca-toggle-hint">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <CollapsibleList
        items={node.items ?? []}
        limit={5}
        render={(item: RCAItem, index: number) => (
          <div key={`${item.ref_id}-${index}`} className="list-item">
            <div className="head">
              {item.badge && (
                <span className={`badge ${BADGE_CLASS[item.badge] ?? "badge-info"}`}>
                  {BADGE_LABEL[item.badge] ?? item.badge}
                </span>
              )}
              <span className="title" title={item.ref_id ?? undefined}>
                {item.title}
              </span>
              {item.ref_collection === "scenarios" && item.ref_id && (
                <Link
                  to={`/scenarios/${item.ref_id}/overview`}
                  className="chip-link"
                  title={item.ref_id}
                >
                  {t.scenario_link}
                </Link>
              )}
            </div>
            {item.description && (
              <p className="desc" title={(item.source_refs ?? []).join(", ")}>
                {item.description}
              </p>
            )}
          </div>
        )}
        />
      )}
    </div>
  );
}
