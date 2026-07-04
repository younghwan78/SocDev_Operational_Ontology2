import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchTraceability, type TraceLink } from "../api/client";
import { ko } from "../i18n/ko";

/**
 * 공통 traceability drill-down 패널.
 * 어떤 객체 ID든 받아 양방향 연결을 보여주고, 링크를 누르면 그 객체로 파고든다.
 * 이후 모든 화면이 이 패턴 하나를 재사용한다.
 */
export function TraceabilityPanel({ rootId }: { rootId: string }) {
  const [stack, setStack] = useState<string[]>([rootId]);
  const currentId = stack[stack.length - 1];

  const trace = useQuery({
    queryKey: ["traceability", currentId],
    queryFn: () => fetchTraceability(currentId),
  });

  const drill = (objectId: string) => {
    if (objectId !== currentId) setStack((prev) => [...prev, objectId]);
  };
  const jumpTo = (index: number) => setStack((prev) => prev.slice(0, index + 1));

  if (trace.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (trace.isError) return <p className="status-msg">{ko.app.error}</p>;

  const outgoing = trace.data.links.filter((link) => link.direction === "outgoing");
  const incoming = trace.data.links.filter((link) => link.direction === "incoming");

  return (
    <div>
      <p className="trace-note">{ko.trace.note}</p>
      <div className="breadcrumb">
        {stack.map((objectId, index) => (
          <span key={`${objectId}-${index}`}>
            {index > 0 && <span className="sep"> › </span>}
            <button onClick={() => jumpTo(index)}>
              {index === 0 ? `${ko.trace.breadcrumb_root} (${objectId})` : objectId}
            </button>
          </span>
        ))}
      </div>
      {trace.data.links.length === 0 && <p className="status-msg">{ko.trace.no_links}</p>}
      {outgoing.length > 0 && (
        <div className="card">
          <h2 className="card-title">{ko.trace.outgoing}</h2>
          <LinkList links={outgoing} onDrill={drill} />
        </div>
      )}
      {incoming.length > 0 && (
        <div className="card">
          <h2 className="card-title">{ko.trace.incoming}</h2>
          <LinkList links={incoming} onDrill={drill} />
        </div>
      )}
    </div>
  );
}

function LinkList({ links, onDrill }: { links: TraceLink[]; onDrill: (id: string) => void }) {
  return (
    <div className="trace-links">
      {links.map((link, index) => (
        <button
          key={`${link.other_id}-${link.link_type}-${index}`}
          className="trace-link"
          onClick={() => onDrill(link.other_id)}
        >
          <span className="rel">{link.link_type.replaceAll("_", " ")}</span>
          <span className="obj">
            {link.other_label_ko ?? "?"}
            {link.other_title ? ` — ${link.other_title}` : ""}
          </span>
          <span className="id">{link.other_id}</span>
          {!link.resolved && <span className="badge badge-warn">{ko.trace.unresolved}</span>}
        </button>
      ))}
    </div>
  );
}
