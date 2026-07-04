"""결정론 어드바이저 — 체인의 최종 fallback. LLM 없이 항상 가용하다.

시나리오 분석의 근거 공백/이벤트/요청에서 역할 관점 조언을 규칙으로 생성한다.
"""

from __future__ import annotations

from backend.agents.validators import AdvisoryDraft
from backend.ontology.common import Confidence, GroundedStatement
from backend.ontology.role import RoleAgent
from backend.services.scenario_analysis import ScenarioAnalysis

# 역할별 관점 서술 — 역할 책임 경계(CLAUDE.md §2.2)를 반영한다.
ROLE_PERSPECTIVES: dict[str, str] = {
    "product_planning": "고객 요구와 상품성 관점에서",
    "soc_architecture": "아키텍처 트레이드오프 관점에서",
    "system_engineering": "추적성과 시스템 최적화 관점에서",
    "hw_development": "HW 구현·검증 가능성 관점에서",
    "sw_development": "SW 구현·검증 가능성 관점에서",
    "pm": "일정과 리스크 관리 관점에서",
    "management": "사업 영향과 최종 트레이드오프 관점에서",
}

MAX_CONCERNS = 5


def generate_deterministic_draft(role: RoleAgent, analysis: ScenarioAnalysis) -> AdvisoryDraft:
    perspective = ROLE_PERSPECTIVES.get(role.id, f"{role.name} 관점에서")
    scenario = analysis.scenario

    concerns: list[GroundedStatement] = []
    for gap in analysis.evidence_gaps[:MAX_CONCERNS]:
        confidence = (
            Confidence.LOW
            if gap.kind in ("missing_evidence", "confidence_blocked")
            else Confidence.MEDIUM
        )
        concerns.append(
            GroundedStatement(
                description=f"{perspective} 확인 필요: {gap.description}",
                description_derivation=(
                    f"시나리오 '{scenario.id}' 분석의 근거 공백 항목({gap.kind_ko})에서 도출"
                ),
                supporting_basis=[gap.ref_id, *gap.source_refs][:4],
                confidence=confidence,
            )
        )

    # 일정 신호가 정상이 아닌 이벤트 — PM/경영 관점에 특히 중요
    for event in analysis.events:
        if len(concerns) >= MAX_CONCERNS:
            break
        if event.schedule_signal and event.schedule_signal not in ("on_track", "none"):
            concerns.append(
                GroundedStatement(
                    description=(
                        f"{perspective} 주시 필요: 이벤트 '{event.title}'의 일정 신호가 "
                        f"'{event.schedule_signal}' 상태다 (W{event.week}, 심각도 {event.severity})"
                    ),
                    description_derivation="개발 이벤트의 schedule_signal 필드에서 도출",
                    supporting_basis=[event.id],
                    confidence=Confidence.MEDIUM,
                )
            )

    if not concerns:
        concerns.append(
            GroundedStatement(
                description=(
                    f"{perspective} 볼 때 시나리오 '{scenario.name}'에 현재 미해결 근거 공백은 "
                    f"없으나, 연결 이벤트 {len(analysis.events)}건의 주간 변화를 계속 관찰해야 한다"
                ),
                description_derivation="근거 공백 0건 + 연결 이벤트 수에서 도출",
                supporting_basis=[scenario.id],
                confidence=Confidence.MEDIUM,
            )
        )

    missing = sorted(
        {m for request in analysis.requests for m in request.missing_evidence}
    )
    required = [req.title for req in analysis.measurement_requirements] + missing

    gap_count = len(analysis.evidence_gaps)
    if gap_count > 0:
        recommendation = (
            f"근거 공백 {gap_count}건을 먼저 해소한 뒤 재검토를 권고한다. "
            f"우선 확보 대상: {', '.join(missing[:3]) if missing else '카탈로그 미가용 근거'}."
        )
        confidence = Confidence.LOW if gap_count > 2 else Confidence.MEDIUM
    else:
        recommendation = "현재 근거 기준으로 진행 가능하며, 주간 리뷰에서 변화를 추적할 것을 권고한다."
        confidence = Confidence.MEDIUM

    return AdvisoryDraft(
        summary=(
            f"{scenario.name}: {perspective} 근거 공백 {gap_count}건, "
            f"연결 이벤트 {len(analysis.events)}건, 요청 {len(analysis.requests)}건을 검토했다."
        ),
        concerns=concerns,
        required_evidence=required[:6],
        recommendation=recommendation,
        confidence=confidence,
        missing_information=missing,
        derivation_summary=(
            "결정론 규칙 기반 생성 — 시나리오 분석의 근거 공백, 이벤트 일정 신호, "
            "측정 요구에서 도출했다. LLM을 사용하지 않았다."
        ),
    )
