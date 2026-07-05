/**
 * 내부 ID → 표시명 해석 훅 — UI 공통 원칙 "내부 ID 숨김" 지원.
 * 화면에는 표시명을 쓰고, ID는 hover(title)/상세 패널에서만 노출한다.
 */
import { useQuery } from "@tanstack/react-query";
import { fetchLabels } from "../api/client";

export function useLabels(): (id: string) => string {
  const { data } = useQuery({
    queryKey: ["labels"],
    queryFn: fetchLabels,
    staleTime: Infinity,
  });
  return (id: string) => data?.[id] ?? id;
}
