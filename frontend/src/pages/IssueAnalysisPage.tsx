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
  fetchProjects,
  type IssueSummary,
  type RCAChain,
  type RCAItem,
  type RCANode,
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

  const valueLabel = useValueLabels();
  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const issues = useQuery({
    queryKey: ["issues", projectFilter, verificationFilter],
    queryFn: () => fetchIssues({ projectId: projectFilter, verification: verificationFilter }),
  });
  const chain = useQuery({
    queryKey: ["issue-rca", selectedIssue],
    queryFn: () => fetchIssueRCA(selectedIssue!),
    enabled: selectedIssue !== null,
  });

  const query = urlQuery.trim().toLowerCase();
  const visibleIssues = (issues.data ?? []).filter(
    (issue) =>
      !query ||
      issue.title.toLowerCase().includes(query) ||
      issue.issue_type.toLowerCase().includes(query),
  );

  if (issues.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (issues.isError) return <p className="status-msg">{ko.app.error}</p>;

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">{t.subtitle}</p>

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
            {option.label}
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
                <span className="title">{issue.title}</span>
                <span className="desc" title={`${issue.issue_type} · ${issue.status}`}>
                  {valueLabel("issue_type", issue.issue_type)} · {t.status_label}:{" "}
                  {valueLabel("issue_status", issue.status)}
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

function RCAFlow({ chainData }: { chainData: RCAChain }) {
  const valueLabel = useValueLabels();
  return (
    <div>
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
        {chainData.alert_ko && <p className="rca-alert">⚠ {chainData.alert_ko}</p>}
      </div>

      <div className="rca-flow">
        {chainData.nodes.map((node) => (
          <RCAStep key={node.step} node={node} />
        ))}
      </div>

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

function RCAStep({ node }: { node: RCANode }) {
  return (
    <div className={`card rca-node rca-${node.badge}`}>
      <div className="head">
        <span className="title">{node.step_ko}</span>
        <span className={`badge ${BADGE_CLASS[node.badge]}`}>{BADGE_LABEL[node.badge]}</span>
        <span className="desc">{node.badge_reason_ko}</span>
      </div>
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
    </div>
  );
}
