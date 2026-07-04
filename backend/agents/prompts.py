"""Advisory 프롬프트 빌더 — 역할 정의 + 시나리오 분석 컨텍스트 + 출력 계약."""

from __future__ import annotations

import json
from typing import Any

from backend.ontology.role import RoleAgent
from backend.services.scenario_analysis import ScenarioAnalysis


def build_context(analysis: ScenarioAnalysis) -> dict[str, Any]:
    """LLM에 전달할 압축 컨텍스트 — 근거 ID를 보존해 supporting_basis로 쓰게 한다."""
    return {
        "scenario": {
            "id": analysis.scenario.id,
            "name": analysis.scenario.name,
            "description": analysis.scenario.description,
            "domain": analysis.scenario.domain,
            "primary_kpis": analysis.scenario.primary_kpis,
            "uses_ip_blocks": analysis.scenario.uses_ip_blocks,
            "depends_on_system_blocks": analysis.scenario.depends_on_system_blocks,
            "projects": analysis.scenario.project_relevance,
        },
        "requests": [
            {
                "id": r.id,
                "title": r.title,
                "priority": r.priority,
                "status": r.status,
                "requested_week": r.requested_week,
                "missing_evidence": r.missing_evidence,
                "management_interest": r.management_interest,
            }
            for r in analysis.requests
        ],
        "events": [
            {
                "id": e.id,
                "title": e.title,
                "week": e.week,
                "severity": e.severity,
                "status": e.status,
                "schedule_signal": e.schedule_signal,
                "required_evidence": [
                    {
                        "id": n.evidence_need_id,
                        "reason": n.reason,
                        "availability": n.availability,
                        "blocks_confidence_above": n.blocks_confidence_above,
                    }
                    for n in e.required_evidence
                ],
            }
            for e in analysis.events
        ],
        "evidence_gaps": [
            {
                "kind": g.kind,
                "ref_id": g.ref_id,
                "description": g.description,
                "source_refs": g.source_refs,
            }
            for g in analysis.evidence_gaps
        ],
        "evidence_catalog": [
            {
                "id": c.id,
                "title": c.title,
                "availability": c.availability,
                "known_limitation": c.known_limitation,
            }
            for c in analysis.evidence_catalog
        ],
        "issues": [
            {"id": i.id, "title": i.title, "symptom": i.symptom, "status": i.status}
            for i in analysis.issues
        ],
        "measurement_requirements": [
            {"id": m.id, "title": m.title, "description": m.description}
            for m in analysis.measurement_requirements
        ],
    }


OUTPUT_SCHEMA_EXAMPLE = {
    "summary": "역할 관점의 한 문단 요약 (한국어)",
    "concerns": [
        {
            "description": "구체적 우려 — 어떤 근거에서 무엇이 문제인지",
            "description_derivation": "이 서술이 어떤 컨텍스트 항목에서 도출됐는지",
            "supporting_basis": ["컨텍스트에_있는_ID"],
            "confidence": "low | medium | high",
        }
    ],
    "required_evidence": ["다음에 확보할 근거"],
    "recommendation": "검토 권고 (최종 결정 아님)",
    "confidence": "low | medium | high",
    "missing_information": ["부족한 정보"],
    "derivation_summary": "전체 도출 과정 요약",
}


def build_prompt(role: RoleAgent, context: dict[str, Any]) -> str:
    """역할별 advisory 프롬프트 (한국어 출력 강제)."""
    return f"""당신은 Multimedia SoC 개발 조직의 '{role.name}' 역할 에이전트입니다.

## 역할 정의
- 목표: {"; ".join(role.goals)}
- 책임: {"; ".join(role.responsibilities)}
- 주요 관심사: {"; ".join(role.primary_concerns)}
- 가드레일: {"; ".join(role.guardrails)}

## 시나리오 분석 컨텍스트 (이 데이터만 근거로 사용)
```json
{json.dumps(context, ensure_ascii=False, indent=1)}
```

## 지시
위 컨텍스트를 근거로 실무 리더에게 줄 검토 조언을 작성하십시오.

규칙 (위반 시 출력이 거부됨):
1. 모든 우려(concern)는 supporting_basis에 컨텍스트에 존재하는 ID를 1개 이상 인용해야 한다.
2. evidence_gaps가 1건 이상 존재하거나 missing_information이 비어 있지 않으면,
   전체 confidence와 개별 concern의 confidence는 절대 high가 될 수 없다 (low/medium만 허용).
3. "추가 분석이 필요하다" 같은 일반론 금지 — 어떤 데이터가 왜 문제인지 구체적으로.
4. 당신의 역할 책임 경계를 벗어난 결정을 내리지 않는다. 최종 결정이 아니라 검토 조언이다.
5. 모든 텍스트는 한국어로 작성한다.

아래 JSON 스키마로만 응답하십시오 (설명 문장, 코드펜스 밖 텍스트 금지):
```json
{json.dumps(OUTPUT_SCHEMA_EXAMPLE, ensure_ascii=False, indent=1)}
```"""
