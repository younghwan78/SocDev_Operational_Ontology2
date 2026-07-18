/** 시간 표기 공통 포맷터 (R8, 설계 21) — slice/L10n 혼재를 하나로. */

/** ISO 문자열 → "2026. 7. 18. 오전 9:30" (ko-KR 로컬 시각). 파싱 실패 시 원문. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("ko-KR", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** ms → "3.2초" (사람이 읽는 소요 시간). */
export function formatDuration(ms: number | null | undefined): string {
  if (!ms || ms <= 0) return "0초";
  return `${(ms / 1000).toFixed(1)}초`;
}

/** Date → datetime-local 입력값 (로컬 타임존, 분 단위). */
export function toDateTimeLocal(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}
