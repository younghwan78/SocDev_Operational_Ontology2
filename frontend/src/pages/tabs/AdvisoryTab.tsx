import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  fetchAdvisoryRuns,
  fetchValueLabels,
  runAdvisory,
  type RoleAdvisory,
} from "../../api/client";
import { Busy } from "../../components/Busy";
import { ErrorState } from "../../components/ErrorState";
import { useLabels } from "../../hooks/useLabels";
import { formatDateTime, formatDuration } from "../../lib/format";
import { ko } from "../../i18n/ko";

const t = ko.advisory;

const PROVIDER_LABELS: Record<string, string> = {
  claude_cli: t.provider_claude,
  openai_compat: t.provider_onprem,
  deterministic: t.provider_deterministic,
};

const CONFIDENCE_BADGE: Record<string, string> = {
  low: "badge-danger",
  medium: "badge-warn",
  high: "badge-ok",
};

export function AdvisoryTab({ scenarioId }: { scenarioId: string }) {
  const queryClient = useQueryClient();
  const label = useLabels();

  const runs = useQuery({
    queryKey: ["advisory", scenarioId],
    queryFn: () => fetchAdvisoryRuns(scenarioId),
  });
  // R7: 역할 선택 실행 — API는 원래 roles를 받는다. 역할 목록은 glossary role 도메인.
  const valueLabels = useQuery({
    queryKey: ["value-labels"],
    queryFn: fetchValueLabels,
    staleTime: Infinity,
  });
  const roleIds = Object.keys(valueLabels.data?.role ?? {});
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const toggleRole = (roleId: string) =>
    setSelectedRoles((previous) =>
      previous.includes(roleId)
        ? previous.filter((id) => id !== roleId)
        : [...previous, roleId],
    );

  const execute = useMutation({
    mutationFn: () =>
      runAdvisory(scenarioId, selectedRoles.length > 0 ? selectedRoles : undefined),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["advisory", scenarioId] }),
  });

  // 실행 이력 선택 — 기본은 최신 실행.
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const shown =
    runs.data?.find((run) => run.id === selectedRunId) ?? runs.data?.[0];

  return (
    <div>
      <div className="filter-row">
        <span className="filter-label">{t.roles_label}</span>
        <button
          type="button"
          className={`chip chip-btn ${selectedRoles.length === 0 ? "active" : ""}`}
          onClick={() => setSelectedRoles([])}
        >
          {t.roles_all}
        </button>
        {roleIds.map((roleId) => (
          <button
            key={roleId}
            type="button"
            title={roleId}
            className={`chip chip-btn ${selectedRoles.includes(roleId) ? "active" : ""}`}
            onClick={() => toggleRole(roleId)}
          >
            {valueLabels.data?.role?.[roleId] ?? roleId}
          </button>
        ))}
      </div>
      <p className="section-note">{t.roles_hint}</p>
      <div className="filter-row">
        <button
          className="chip chip-btn active"
          onClick={() => execute.mutate()}
          disabled={execute.isPending}
        >
          {t.run_button}
          {selectedRoles.length > 0 ? ` (${selectedRoles.length})` : ""}
        </button>
        {execute.isPending && <Busy message={t.running} />}
        {execute.isError && <span className="badge badge-danger">{t.run_failed}</span>}
        {(runs.data ?? []).length > 1 && (
          <>
            <label className="filter-label" htmlFor="advisory-run-select">
              {t.history_label}
            </label>
            <select
              id="advisory-run-select"
              value={shown?.id ?? ""}
              onChange={(event) => setSelectedRunId(event.target.value || null)}
            >
              {(runs.data ?? []).map((run, index) => (
                <option key={run.id} value={run.id}>
                  {index === 0 ? `${t.history_latest} · ` : ""}
                  {formatDateTime(run.created_at)}
                </option>
              ))}
            </select>
          </>
        )}
      </div>

      {runs.isPending && <p className="status-msg">{ko.app.loading}</p>}
      {runs.isError && (
        <ErrorState error={runs.error} onRetry={() => void runs.refetch()} />
      )}
      {runs.isSuccess && !shown && <p className="status-msg">{t.empty}</p>}

      {shown && (
        <div>
          <p className="section-note">
            {t.not_final} · {t.created_at}: {formatDateTime(shown.created_at)} ·{" "}
            {t.duration}: {formatDuration(shown.duration_ms)}
          </p>
          {(shown.advisories ?? []).map((advisory) => (
            <AdvisoryCard key={advisory.role_id} advisory={advisory} label={label} />
          ))}
          {(shown.validation_notes ?? []).length > 0 && (
            <div className="card">
              <h2 className="card-title">{t.validation_notes}</h2>
              {(shown.validation_notes ?? []).map((note, index) => (
                <p key={index} className="section-note">
                  {note}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AdvisoryCard({
  advisory,
  label,
}: {
  advisory: RoleAdvisory;
  label: (id: string) => string;
}) {
  return (
    <div className="card">
      <div className="list-item" style={{ borderBottom: "none", padding: 0 }}>
        <div className="head">
          <span className="badge badge-info" title={advisory.role_id}>
            {label(advisory.role_id)}
          </span>
          <span className="badge badge-ok">
            {t.provider}: {PROVIDER_LABELS[advisory.provider] ?? advisory.provider}
          </span>
          <span className={`badge ${CONFIDENCE_BADGE[advisory.confidence] ?? "badge-info"}`}>
            {t.confidence}: {advisory.confidence}
          </span>
        </div>
        <p className="desc">{advisory.summary}</p>

        {(advisory.concerns ?? []).map((concern, index) => (
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

        {/* B3: §2.2 피드백 루프 가시화 — HW/SW → SE/Arch 차기 개선 전달 */}
        {(advisory.feedback_items ?? []).map((feedback, index) => (
          <div key={`fb-${index}`} className="grounded feedback-item">
            <div>
              <strong>{t.feedback}</strong> → {label(feedback.target_role)} ({t.confidence}:{" "}
              {feedback.confidence}): {feedback.description}
            </div>
            <div className="derivation">
              {t.derivation}: {feedback.description_derivation}
            </div>
            <div className="derivation">
              {t.supporting_basis}: {(feedback.supporting_basis ?? []).join(", ")}
            </div>
          </div>
        ))}

        {(advisory.required_evidence ?? []).length > 0 && (
          <p className="desc">
            {t.required_evidence}: {(advisory.required_evidence ?? []).join(" · ")}
          </p>
        )}
        {(advisory.missing_information ?? []).length > 0 && (
          <p className="desc">
            {t.missing_information}: {(advisory.missing_information ?? []).join(" · ")}
          </p>
        )}
        <p className="desc">
          <strong>{t.recommendation}</strong>: {advisory.recommendation}
        </p>
      </div>
    </div>
  );
}
