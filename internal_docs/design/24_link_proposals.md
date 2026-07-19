# 설계 24 — 링크 제안 (link-recovery 사외 선행분, 설계 22 후속 ⑥)

> W2 링크 커버리지 지표(설계 22 §3)를 올리는 실행 수단의 결정론 선행분.
> 레퍼런스의 link-recovery 에이전트(LLM 제안 → 대기열 → 사람 승인)에서
> **사외에서 구현 가능한 부분**만 앞당긴다: 결정론 후보 생성 + 근거 동반
> 검토 표면. LLM/임베딩 제안은 Stage 18 결합 시 같은 계약에 플러그인한다.

## 1. 원칙과 범위

- **제안은 파생 뷰다** — 저장하지 않고 읽기 시점 재계산. 자동 반영 없음:
  링크는 항상 원천(JIRA 필드/반입 CSV)에서 고쳐져 ingest로 재진입한다
  (온톨로지 수정 API 금지 원칙 그대로).
- **모든 제안은 basis 동반** — 어떤 토큰이 어디서 일치했는지 명시. 후보
  지위(제안)를 숨기지 않는다.
- **In**: `LinkProposalService`(룰 3종) + `GET /api/v1/link-proposals` +
  출처 지도 "링크 제안" 카드(근거 hover + 반영 경로 안내) + 테스트 + 문서.
- **Out**: 제안 저장·자동 반영, LLM/임베딩 제안(Stage 18 — 같은 계약에
  추가), JIRA writeback(⑤), **수정 CSV 자동 생성** — issues CSV는
  root_causes를 단일 행으로만 표현해 왕복 시 다중 root_cause가 소실되고,
  synthetic 이슈를 CSV 재반입하면 origin이 오염된다. 반영은 원천 수정 경로
  안내로 대신한다 (JIRA 필드 기입 → 재동기화 / 원본 CSV 열 보강 → upsert).

## 2. 결정론 룰 3종 (전부 기존 재료 재사용)

대상: **해당 링크 필드가 비어 있는 이슈만** (W2 커버리지 정의와 동일 방향 —
이미 연결된 이슈에 더 얹는 것은 목표가 아니다).

| 룰 | 제안 대상 | 재료 | 조건 |
|---|---|---|---|
| R1 IP 별칭 토큰 | `affected_scope.ip_blocks` | `IPAliasIndex`(entity resolution과 동일 인덱스) | 제목+증상 토큰이 IP 별칭/이름에 해석됨 (`resolve_all` — 다중 IP 보존) |
| R2 시나리오 토큰 | `affected_scope.scenarios` | Scenario id+name 토큰 역인덱스 | 제목+증상 토큰 일치. 변별력 필터: 토큰 길이 ≥3, 불용어 제외, 4개 이상 시나리오에 걸리는 토큰은 비변별로 제외. `project_relevance`가 있으면 이슈 프로젝트 포함 필수 |
| R3 시나리오 사용 IP 연쇄 | `affected_scope.ip_blocks` | 이슈의 **기존** 연결 시나리오의 `uses_ip_blocks` | 이슈가 시나리오에 연결돼 있고 IP는 비어 있을 때 — 시나리오 정의가 근거 |

토큰 정규화는 `normalize_tokens`(entity_resolution) 재사용 — 휴리스틱을
새로 만들지 않는다. 수치 confidence 없음 — 룰 이름과 basis 문장이 전부다.

## 3. 계약 (파생 뷰)

```python
class LinkProposal(BaseModel):
    field: str            # affected_scope.scenarios | affected_scope.ip_blocks
    field_ko: str
    target_id: str
    rule: str             # ip_alias_token | scenario_token | scenario_uses_ip
    rule_ko: str
    basis_note_ko: str    # "제목 토큰 'uhd60' ↔ 시나리오 이름 'UHD60 녹화'"

class IssueLinkProposals(BaseModel):
    issue_id: str
    issue_title: str
    project_id: str
    proposals: list[LinkProposal]   # field, target_id 순 정렬

class LinkProposalReport(BaseModel):
    issues: list[IssueLinkProposals]  # 제안 있는 이슈만, id 순
    apply_note_ko: str                # 반영 경로 안내 (원천 수정 → 재반입)
```

API: `GET /api/v1/link-proposals?project_id=` (읽기 전용, 결정론).

## 4. UX — 출처 지도 "링크 제안" 카드

연결률 카드 바로 아래 (지표 → 실행 수단의 인접 배치):

```text
┌ 링크 제안 (검토 후 원천에서 반영) ─────────────────────┐
│ 제안은 결정론 토큰 일치 후보입니다 — 반영은 JIRA 필드   │
│ 기입/원본 CSV 보강 후 재반입으로만 이뤄집니다.          │
│ ISP 야간 촬영 프레임 드랍 (project_u)                    │
│   [영향 IP] ISP  · IP 별칭 토큰 ⓘ                       │
│   [영향 시나리오] 저조도 비디오 녹화 · 시나리오 토큰 ⓘ  │
│ MIF 대역폭 마진 부족 (project_v)                         │
│   [영향 IP] MIF · 시나리오 사용 IP ⓘ                    │
└──────────────────────────────────────────────────────────┘
```

- 제안 칩 hover = basis_note_ko + target_id. 대상 라벨은 labels 맵 경유
  (내부 ID 노출 금지).
- 제안 0건이면 카드 미렌더. 이슈당 여러 제안은 필드별로 줄 나눔.
- i18n: `ko.link_proposals.*`.

## 5. 수용 기준

- [ ] R1/R2/R3 각각 단위 테스트 (매치/비매치/이미 연결됨 제외/비변별 토큰
  제외/project_relevance 필터)
- [ ] 제안 있는 이슈만 응답, 결정론 정렬, basis_note_ko 전 건 존재
- [ ] fixture smoke: 제안 생성이 오류 없이 동작 (건수는 고정하지 않음 —
  fixture 이슈는 대부분 연결돼 있어 소수 기대)
- [ ] UI 카드 렌더 + 0건 미렌더 (프론트 테스트)
- [ ] 전체 회귀 + 실서버 smoke, changelog
