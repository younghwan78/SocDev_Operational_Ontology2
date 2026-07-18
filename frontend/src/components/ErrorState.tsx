/**
 * 오류 상태 (R6, 설계 21) — 서버가 만든 한국어 detail을 표시하고 재시도를 제공한다.
 * 일반 오류 한 줄("데이터를 불러오지 못했습니다")로 뭉개지 않는다.
 */
import { ko } from "../i18n/ko";

export function ErrorState({
  error,
  onRetry,
}: {
  error?: unknown;
  onRetry?: () => void;
}) {
  const detail = error instanceof Error && error.message ? error.message : null;
  return (
    <p className="status-msg" role="alert">
      {ko.app.error}
      {detail && detail !== ko.app.error ? ` — ${detail}` : ""}
      {onRetry && (
        <>
          {" "}
          <button type="button" className="link-btn" onClick={onRetry}>
            {ko.app.retry}
          </button>
        </>
      )}
    </p>
  );
}
