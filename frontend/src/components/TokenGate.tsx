/**
 * 토큰 게이트 (D1-1) — 서버가 401을 돌려주면 뜨는 접속 토큰 입력 오버레이.
 * 서버가 SOC_API_TOKEN을 켜지 않은 개발 모드에서는 절대 나타나지 않는다.
 */
import { useEffect, useState } from "react";
import { AUTH_REQUIRED_EVENT, getApiToken, setApiToken } from "../api/client";
import { ko } from "../i18n/ko";

const t = ko.auth;

export function TokenGate() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    const onAuthRequired = () => {
      setDraft(getApiToken() ?? "");
      setOpen(true);
    };
    window.addEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
    return () => window.removeEventListener(AUTH_REQUIRED_EVENT, onAuthRequired);
  }, []);

  if (!open) return null;
  return (
    <div className="token-gate" role="dialog" aria-modal="true" aria-label={t.title}>
      <div className="card token-card">
        <h2 className="card-title">{t.title}</h2>
        <p className="desc">{t.hint}</p>
        <form
          className="ask-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!draft.trim()) return;
            setApiToken(draft);
            window.location.reload();
          }}
        >
          <input
            type="password"
            className="ask-input"
            autoFocus
            aria-label={t.title}
            autoComplete="off"
            value={draft}
            placeholder={t.placeholder}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button type="submit" className="run-btn" disabled={!draft.trim()}>
            {t.save}
          </button>
        </form>
      </div>
    </div>
  );
}
