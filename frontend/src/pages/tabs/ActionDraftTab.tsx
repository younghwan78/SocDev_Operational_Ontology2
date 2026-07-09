import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  fetchActionDraft,
  type ActionDraft,
  type BasisItem,
  type DraftSection,
} from "../../api/client";
import { CollapsibleList } from "../../components/CollapsibleList";
import { ko } from "../../i18n/ko";

const t = ko.action_draft;

function toMarkdown(draft: ActionDraft): string {
  const lines: string[] = [`# ${t.title} — ${draft.scenario_name}`, "", `> ${draft.provenance_note}`, ""];
  lines.push(`_${draft.generated_context}_`, "");
  if (draft.evidence_posture) {
    const p = draft.evidence_posture;
    lines.push(
      `**${t.posture}**: ${t.posture_measured} ${p.measured} · ${t.posture_predicted} ${p.predicted} · ${t.posture_absent} ${p.absent} — ${p.note_ko}`,
      "",
    );
  }
  for (const section of draft.sections) {
    lines.push(`## ${section.kind_ko} — ${section.title}`, "");
    section.items.forEach((item, i) => {
      const strength = item.strength_ko ? ` [${t.strength}: ${item.strength_ko}]` : "";
      lines.push(`${i + 1}. ${item.statement}${strength}`);
      for (const b of item.basis) {
        lines.push(`   - (${b.rule_ko}) ${b.ref_id}`);
      }
    });
    lines.push("");
  }
  return lines.join("\n");
}

const POSTURE_BADGE = (measured: number, predicted: number, absent: number): string => {
  if (measured === 0) return "badge-danger";
  if (predicted > measured || absent > measured) return "badge-warn";
  return "badge-ok";
};

export function ActionDraftTab({ scenarioId }: { scenarioId: string }) {
  const draft = useQuery({
    queryKey: ["action-draft", scenarioId],
    queryFn: () => fetchActionDraft(scenarioId),
  });
  const [copied, setCopied] = useState<string | null>(null);

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(t.copied);
    } catch {
      setCopied(t.copy_failed);
    }
  };

  if (draft.isPending) return <p className="status-msg">{t.generating}</p>;
  if (draft.isError) return <p className="status-msg">{ko.app.error}</p>;

  const data = draft.data;

  return (
    <div>
      <p className="section-note">{t.subtitle}</p>
      <div className="card">
        <div className="head">
          <span className="badge badge-warn">{data.provenance_note}</span>
        </div>
        <p className="desc">
          {t.context}: {data.generated_context}
        </p>
        {data.evidence_posture && (
          <p className="desc">
            <span
              className={`badge ${POSTURE_BADGE(
                data.evidence_posture.measured,
                data.evidence_posture.predicted,
                data.evidence_posture.absent,
              )}`}
            >
              {t.posture}: {t.posture_measured} {data.evidence_posture.measured} ·{" "}
              {t.posture_predicted} {data.evidence_posture.predicted} · {t.posture_absent}{" "}
              {data.evidence_posture.absent}
            </span>{" "}
            {data.evidence_posture.note_ko}
          </p>
        )}
        <div className="chip-row">
          <button type="button" className="link-btn" onClick={() => copy(JSON.stringify(data, null, 2))}>
            {t.copy_json}
          </button>
          <button type="button" className="link-btn" onClick={() => copy(toMarkdown(data))}>
            {t.copy_markdown}
          </button>
          {copied && <span className="badge badge-ok">{copied}</span>}
        </div>
      </div>

      {data.sections.length === 0 && <p className="status-msg">{t.empty}</p>}
      {data.sections.map((section) => (
        <DraftSectionCard key={section.kind} section={section} />
      ))}
    </div>
  );
}

function DraftSectionCard({ section }: { section: DraftSection }) {
  return (
    <div className="card">
      <h2 className="card-title">
        {section.kind_ko} — {section.title} ({section.items.length})
      </h2>
      {section.items.map((item, index) => (
        <div key={`${section.kind}-${index}`} className="list-item">
          <p className="title">
            {item.strength_ko && (
              <span className="chip">
                {t.strength}: {item.strength_ko}
              </span>
            )}{" "}
            {item.statement}
          </p>
          <CollapsibleList
            items={item.basis}
            limit={3}
            render={(basis: BasisItem, i: number) => (
              <p key={`${basis.ref_id}-${i}`} className="desc" title={basis.ref_id}>
                <span className="chip">{basis.rule_ko}</span> {basis.description}
              </p>
            )}
          />
        </div>
      ))}
    </div>
  );
}
