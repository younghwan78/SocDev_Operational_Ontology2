import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAdvisoryRuns, runAdvisory, type RoleAdvisory } from "../../api/client";
import { useLabels } from "../../hooks/useLabels";
import { Busy } from "../../components/Busy";
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

  const runs = useQuery({
    queryKey: ["advisory", scenarioId],
    queryFn: () => fetchAdvisoryRuns(scenarioId),
  });

  const execute = useMutation({
    mutationFn: () => runAdvisory(scenarioId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["advisory", scenarioId] }),
  });

  const latest = runs.data?.[0];

  return (
    <div>
      <div className="filter-row">
        <button
          className="chip chip-btn active"
          onClick={() => execute.mutate()}
          disabled={execute.isPending}
        >
          {t.run_button}
        </button>
        {execute.isPending && <Busy message={t.running} />}
        {execute.isError && <span className="badge badge-danger">{t.run_failed}</span>}
      </div>

      {runs.isPending && <p className="status-msg">{ko.app.loading}</p>}
      {runs.isSuccess && !latest && <p className="status-msg">{t.empty}</p>}

      {latest && (
        <div>
          <p className="section-note">
            {t.not_final} · {t.created_at}: {latest.created_at} · {t.duration}:{" "}
            {latest.duration_ms ?? 0}ms
          </p>
          {(latest.advisories ?? []).map((advisory) => (
            <AdvisoryCard key={advisory.role_id} advisory={advisory} />
          ))}
          {(latest.validation_notes ?? []).length > 0 && (
            <div className="card">
              <h2 className="card-title">{t.validation_notes}</h2>
              {(latest.validation_notes ?? []).map((note, index) => (
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

function AdvisoryCard({ advisory }: { advisory: RoleAdvisory }) {
  const label = useLabels();
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
