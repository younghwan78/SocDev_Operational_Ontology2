// U1 값 도메인 한국어화 — 라벨 조회와 원문 폴백 (backend VALUE_LABELS가 단일 소스).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { useValueLabels } from "../hooks/useValueLabels";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useValueLabels", () => {
  it("glossary value_labels로 라벨을 해석하고 미등재 값은 원문 폴백한다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            objects: {},
            fields: {},
            enums: {},
            value_labels: { availability: { available: "확보" } },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const { result } = renderHook(() => useValueLabels(), { wrapper });
    await waitFor(() => {
      expect(result.current("availability", "available")).toBe("확보");
    });
    expect(result.current("availability", "값_없는_코드")).toBe("값_없는_코드");
    expect(result.current("없는_도메인", "x")).toBe("x");
    expect(result.current("availability", null)).toBe("");
    vi.unstubAllGlobals();
  });
});
