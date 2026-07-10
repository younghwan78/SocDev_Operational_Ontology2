/**
 * 근거 태세 칩 — 위험 등급(●◐○ 빨/노/초)과 다른 시각 언어(중립 아웃라인)로
 * "위험함"과 "근거 강도"의 축을 분리한다. 실측 0건일 때만 텍스트 강조.
 * 건수 표시일 뿐 수치 점수가 아니다.
 */
import { ko } from "../i18n/ko";

export function PostureChip({
  measured,
  predicted,
  absent,
  note,
}: {
  measured: number;
  predicted: number;
  absent: number;
  note?: string | null;
}) {
  return (
    <span
      className={`posture-chip${measured === 0 ? " posture-weak" : ""}`}
      title={note ?? ko.posture.label}
    >
      {ko.posture.measured}
      {measured}·{ko.posture.predicted}
      {predicted}·{ko.posture.absent}
      {absent}
    </span>
  );
}
