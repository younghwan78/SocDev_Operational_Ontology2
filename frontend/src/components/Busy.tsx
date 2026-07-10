/**
 * 진행 표시 — 스피너 + 경과 초. LLM 응답(~20초+) 등 긴 대기의 진행감을 준다.
 * 완료 알림은 사용처의 aria-live 영역이 담당한다.
 */
import { useEffect, useState } from "react";
import { ko } from "../i18n/ko";

export function Busy({ message }: { message: string }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((previous) => previous + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <p className="status-msg busy" role="status">
      <span className="spinner" aria-hidden="true" />
      {message} · {seconds}
      {ko.app.busy_seconds}
    </p>
  );
}
