/**
 * 값 도메인(문자열 코드) → 한국어 라벨 훅 — 한국어 1급(U1).
 * 화면에는 라벨을 쓰고 원문 코드는 hover(title)로만 노출한다.
 * 라벨 사전은 backend glossary VALUE_LABELS가 단일 소스이며,
 * 미등재 값은 원문 폴백(커버리지 테스트가 fixture 누락을 차단).
 */
import { useQuery } from "@tanstack/react-query";
import { fetchValueLabels } from "../api/client";

export function useValueLabels(): (domain: string, value: string | null | undefined) => string {
  const { data } = useQuery({
    queryKey: ["value-labels"],
    queryFn: fetchValueLabels,
    staleTime: Infinity,
  });
  return (domain: string, value: string | null | undefined) => {
    if (!value) return "";
    return data?.[domain]?.[value] ?? value;
  };
}
