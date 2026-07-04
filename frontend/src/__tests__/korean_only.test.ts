/**
 * UI 문자열 하드코딩 영어 금지 가드.
 * JSX 텍스트 노드에 라틴 문자 단어가 직접 쓰이면 실패한다 —
 * 모든 UI 문자열은 src/i18n/ko.ts를 거쳐야 한다.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..");

function collectTsx(dir: string): string[] {
  const results: string[] = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) {
      if (entry === "__tests__" || entry === "api") continue;
      results.push(...collectTsx(path));
    } else if (entry.endsWith(".tsx")) {
      results.push(path);
    }
  }
  return results;
}

describe("한국어 전용 UI", () => {
  it("JSX 텍스트 노드에 영어 하드코딩이 없어야 한다", () => {
    const offenders: string[] = [];
    // 태그 사이 텍스트 노드에서 4자 이상 라틴 단어 검출 (중괄호 표현식 제외)
    const pattern = />[^<>{}\n]*[A-Za-z]{4,}[^<>{}\n]*</g;
    for (const file of collectTsx(SRC)) {
      const source = readFileSync(file, "utf-8");
      const matches = source.match(pattern);
      if (matches) {
        offenders.push(`${file}: ${matches.join(" | ")}`);
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });
});
