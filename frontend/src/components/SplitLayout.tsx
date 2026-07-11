/**
 * 스플리터 공용 컴포넌트 — 본문/사이드 패널 폭 조절 (위험 지도·변경 영향 공용).
 * 드래그·좌우 화살표 키(±16px)·더블클릭 초기화, localStorage에 화면별 키로 유지.
 * 레이아웃은 CSS 변수(--side-w)로 전달한다 (.risk-layout-split 참조).
 */
import { useCallback, useState, type PointerEvent as ReactPointerEvent } from "react";

const SIDE_WIDTH_DEFAULT = 400;
const SIDE_WIDTH_MIN = 300;
const SIDE_WIDTH_MAX = 680;
const clampSideWidth = (value: number) =>
  Math.min(SIDE_WIDTH_MAX, Math.max(SIDE_WIDTH_MIN, value));

export function useSidePanelWidth(storageKey: string) {
  const [width, setWidth] = useState(() => {
    const saved = Number(window.localStorage.getItem(storageKey));
    return Number.isFinite(saved) && saved > 0 ? clampSideWidth(saved) : SIDE_WIDTH_DEFAULT;
  });
  const update = useCallback(
    (next: number) => {
      const clamped = clampSideWidth(next);
      setWidth(clamped);
      window.localStorage.setItem(storageKey, String(clamped));
      return clamped;
    },
    [storageKey],
  );
  const reset = useCallback(() => update(SIDE_WIDTH_DEFAULT), [update]);
  return { width, update, reset };
}

export function SplitHandle({
  width,
  onResize,
  onReset,
  label,
}: {
  width: number;
  onResize: (next: number) => void;
  onReset: () => void;
  label: string;
}) {
  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const startWidth = width;
    const target = event.currentTarget;
    const onMove = (move: PointerEvent) => onResize(startWidth + (startX - move.clientX));
    const onUp = () => {
      target.removeEventListener("pointermove", onMove);
      target.removeEventListener("pointerup", onUp);
    };
    target.addEventListener("pointermove", onMove);
    target.addEventListener("pointerup", onUp);
  };
  return (
    <div
      className="split-handle"
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={width}
      aria-valuemin={SIDE_WIDTH_MIN}
      aria-valuemax={SIDE_WIDTH_MAX}
      tabIndex={0}
      title={label}
      onPointerDown={onPointerDown}
      onDoubleClick={onReset}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") onResize(width + 16);
        else if (event.key === "ArrowRight") onResize(width - 16);
        else return;
        event.preventDefault();
      }}
    />
  );
}
