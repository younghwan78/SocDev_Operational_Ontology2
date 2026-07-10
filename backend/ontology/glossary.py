"""한국어 도메인 용어집 — 온톨로지의 label_ko 단일 소스.

UI 번역 파일이 아니라 온톨로지 메타데이터 계약이다. 용어 변경은 changelog 필수.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel

# ---------------------------------------------------------------- 객체 라벨

OBJECT_LABELS: dict[str, str] = {
    # project
    "Project": "프로젝트",
    "ProjectMilestone": "프로젝트 마일스톤",
    "CustomerRequest": "고객 요구",
    "ProjectLink": "프로젝트 연결",
    "ProjectScenarioFocus": "프로젝트 시나리오 포커스",
    "WeekWindow": "주차 구간",
    "StageWindow": "개발 단계 구간",
    # scenario
    "KPIDefinition": "KPI 정의",
    "ScenarioGroup": "시나리오 그룹",
    "Scenario": "시나리오",
    "Variant": "시나리오 변형",
    "VariantStream": "변형 스트림",
    "ScenarioIPRequirement": "시나리오 IP 요구",
    "ScenarioRequest": "시나리오 요청",
    "ProjectSpan": "프로젝트 구간",
    "Propagation": "전파",
    # ip
    "IPBlock": "IP 블록",
    "IPBaseSpec": "IP 기본 스펙",
    "IPCapability": "IP 캐퍼빌리티",
    "IPKnob": "IP 제어 노브",
    "IPDependencyRule": "IP 의존 규칙",
    # event
    "DevelopmentEvent": "개발 이벤트",
    "Issue": "이슈",
    "ConfidenceSignal": "확신도 신호",
    "CandidateOption": "후보 옵션",
    "DecisionQuestion": "결정 질문",
    "EventRelations": "이벤트 관계",
    "ExpectedReviewOutput": "기대 검토 산출",
    "RequiredEvidenceNeed": "요구 근거",
    "AffectedScope": "영향 범위",
    "RootCause": "근본 원인",
    "Test": "검증 테스트",
    # evidence
    "Evidence": "근거",
    "EvidenceCatalogEntry": "근거 카탈로그 항목",
    "MeasurementEvidence": "측정 근거",
    "MeasurementRequirement": "측정 요구",
    "SemanticChunk": "시맨틱 청크",
    "SemanticVector": "시맨틱 벡터",
    "ChunkMetadata": "청크 메타데이터",
    "VectorMetadata": "벡터 메타데이터",
    # role
    "RoleAgent": "역할 에이전트",
    "RoleActivity": "역할 활동",
    "RoleOutput": "역할 출력",
    "UIIdentity": "UI 정체성",
    "ActivityInputContext": "활동 입력 컨텍스트",
    "EvidenceAssessment": "근거 평가",
    "OptionAssessment": "옵션 평가",
    "ConfidencePosture": "확신도 자세",
    "ActivityRecommendation": "활동 권고",
    "SafetyFlags": "안전 플래그",
    "ActivityTraceability": "활동 추적성",
    "FeedbackItem": "피드백 항목",
    # decision
    "Decision": "결정",
    "DecisionOption": "결정 옵션",
    "DecisionBasis": "결정 근거",
    "ActionItem": "액션 아이템",
    "ReviewPack": "리뷰 팩",
    "DocRef": "문서 참조",
    # relation
    "Relation": "관계",
    "SimulationRun": "시뮬레이션 실행",
    "AgentRun": "조언 실행 기록",
    "RoleAdvisory": "역할 조언",
    # common
    "GroundedStatement": "근거 문장",
    "SourceMeta": "출처 메타데이터",
}

# ------------------------------------------------------------ 공통 필드 라벨

COMMON_FIELD_LABELS: dict[str, str] = {
    "id": "ID",
    "source": "출처",
    "project_id": "프로젝트 ID",
    "scenario_id": "시나리오 ID",
    "ip_id": "IP ID",
    "event_id": "이벤트 ID",
    "variant_id": "변형 ID",
    "role_id": "역할 ID",
    "chunk_id": "청크 ID",
    "title": "제목",
    "name": "이름",
    "description": "설명",
    "summary": "요약",
    "notes": "비고",
    "note": "메모",
    "aliases": "별칭",
    "category": "분류",
    "domain": "도메인",
    "domains": "도메인 목록",
    "status": "상태",
    "priority": "우선순위",
    "confidence": "확신도",
    "confidence_level": "확신 수준",
    "week": "주차",
    "quarter": "분기",
    "unit": "단위",
    "condition": "조건",
    "direction": "방향",
    "reason": "이유",
    "basis": "근거",
    "rationale": "근거 논리",
    "statement": "진술",
    "purpose": "목적",
    "availability": "가용성",
    "resolution": "해상도",
    "fps": "FPS",
    "metadata": "메타데이터",
    "source_ref": "출처 참조",
    "source_refs": "출처 참조 목록",
    "source_basis": "출처 근거",
    "source_type": "출처 유형",
    "source_id": "출처 객체 ID",
    "supporting_basis": "뒷받침 근거",
    "description_derivation": "서술 도출 과정",
    "lifecycle_stage": "개발 단계",
    "evidence_type": "근거 유형",
    "evidence_level": "근거 수준",
    "request_type": "요청 유형",
    "start_week": "시작 주차",
    "end_week": "종료 주차",
    "required_by_week": "요구 기한 주차",
    "not_final_decision": "최종 결정 아님",
    "not_causal_proof": "인과 증명 아님",
    "read_only": "읽기 전용",
    "relevant_roles": "관련 역할",
    "related_scenario_groups": "관련 시나리오 그룹",
    "scenario_ids": "시나리오 ID 목록",
    "scenario_group_ids": "시나리오 그룹 ID 목록",
    "scenario_group_id": "시나리오 그룹 ID",
    "primary_kpis": "주요 KPI",
    "variants": "변형 목록",
    "scenarios": "시나리오 목록",
    "linked_scenario_ids": "연결 시나리오 ID",
    "linked_evidence_ids": "연결 근거 ID",
    "linked_milestone_ids": "연결 마일스톤 ID",
    "linked_request_ids": "연결 요청 ID",
    "linked_propagation_ids": "연결 전파 ID",
    "missing_data": "누락 데이터",
    "missing_information": "누락 정보",
    "related_ip_ids": "관련 IP ID",
    "related_scenario_ids": "관련 시나리오 ID",
    "related_kpi_ids": "관련 KPI ID",
    "related_knob_ids": "관련 노브 ID",
    "required_evidence": "요구 근거",
    "required_evidence_need_ids": "요구 근거 ID 목록",
    "concerns": "우려",
    "recommendation": "권고",
    "cost_impact": "비용 영향",
    "risks": "리스크",
    "toggles": "토글",
    "mode": "모드",
}

# --------------------------------------------------------- 모델별 필드 라벨

MODEL_FIELD_LABELS: dict[str, dict[str, str]] = {
    "SourceMeta": {
        "origin": "출처 구분",
        "ref": "원본 참조",
        "ingested_at": "반입 시각",
    },
    "Project": {
        "type": "프로젝트 유형",
        "phase": "프로젝트 단계",
        "key_themes": "핵심 테마",
        "silicon_status": "실리콘 상태",
        "customer_stage": "고객 단계",
        "hw_status": "HW 상태",
        "sw_status": "SW 상태",
        "spec_status": "스펙 상태",
        "target_product_generation": "목표 제품 세대",
    },
    "ProjectMilestone": {
        "milestone_type": "마일스톤 유형",
        "decision_window": "결정 시점 구간",
        "historical_relation": "과거 이력 관계",
        "timeline_scope": "타임라인 범위",
    },
    "CustomerRequest": {
        "target_improvement": "목표 개선",
        "target_kpis": "목표 KPI",
    },
    "ProjectLink": {
        "from_project": "출발 프로젝트",
        "to_project": "도착 프로젝트",
        "link_type": "연결 유형",
    },
    "StageWindow": {
        "stage": "개발 단계",
        "focus_types": "포커스 유형",
        "measurement_policy": "측정 정책",
    },
    "ProjectScenarioFocus": {
        "objectives": "목표",
        "annual_horizon": "연간 구간",
        "development_stage_windows": "개발 단계 구간",
    },
    "KPIDefinition": {
        "group": "KPI 그룹",
    },
    "ScenarioGroup": {
        "feature_toggles": "기능 토글",
    },
    "Scenario": {
        "scenario_class": "시나리오 분류",
        "project_relevance": "프로젝트 연관성",
        "uses_ip_blocks": "사용 IP 블록",
        "depends_on_system_blocks": "의존 시스템 블록",
        "generation_path": "생성 경로",
        "base_from_previous_project": "이전 프로젝트 기반 여부",
        "derived_from_scenario_id": "파생 원본 시나리오 ID",
        "customer_request_relevance": "고객 요구 연관성",
        "development_relevance": "개발 연관성",
        "dou_relevance": "DoU 연관성",
        "iq_relevance": "화질 연관성",
        "sustain_power_relevance": "지속 전력 연관성",
        "hw_pipeline_change_sensitivity": "HW 파이프라인 변경 민감도",
        "sw_control_complexity": "SW 제어 복잡도",
        "catalog_status": "카탈로그 상태",
        "legacy_aliases": "구 별칭",
    },
    "Variant": {
        "streams": "스트림 목록",
        "operation": "동작",
        "operations": "동작 목록",
        "ai_solution": "AI 솔루션",
        "capture_mode": "촬영 모드",
        "dpu_clock_policy": "DPU 클럭 정책",
        "panel_mode": "패널 모드",
    },
    "ScenarioIPRequirement": {
        "required_capability": "요구 캐퍼빌리티",
        "required_mode": "요구 모드",
        "requirement_level": "요구 수준",
    },
    "ProjectSpan": {
        "impact_direction": "영향 방향",
        "posture": "검토 자세",
        "evidence_status": "근거 상태",
    },
    "Propagation": {
        "propagation_id": "전파 ID",
        "from_project_id": "출발 프로젝트 ID",
        "to_project_id": "도착 프로젝트 ID",
        "at_week": "발생 주차",
        "propagation_type": "전파 유형",
        "trigger_role": "트리거 역할",
        "relation_summary": "관계 요약",
    },
    "ScenarioRequest": {
        "origin_project_id": "발원 프로젝트 ID",
        "request_scope": "요청 범위",
        "requested_by_role": "요청 역할",
        "requested_week": "요청 주차",
        "review_cadence": "검토 주기",
        "role_relevance": "역할 연관성",
        "trigger_roles": "트리거 역할 목록",
        "management_interest": "경영 관심사",
        "system_engineering_tracking_focus": "시스템 엔지니어링 추적 포커스",
        "expected_weekly_activity_load": "예상 주간 활동 부하",
        "evidence_basis": "근거 기반",
        "missing_evidence": "누락 근거",
        "milestone_refs": "마일스톤 참조",
        "linked_focus_ids": "연결 포커스 ID",
        "linked_review_pack_ids": "연결 리뷰팩 ID",
        "linked_review_report_scenario_id": "연결 리뷰 리포트 시나리오 ID",
        "project_spans": "프로젝트 구간",
        "propagation": "전파 목록",
    },
    "IPBlock": {
        "rt_relevant": "실시간(RT) 관련 여부",
    },
    "IPBaseSpec": {
        "spec_id": "원본 스펙 ID",
        "display_name": "표시 이름",
        "driver_name": "드라이버 이름",
        "driver_path": "드라이버 경로",
        "internal_blocks": "내부 블록",
        "supported_modes": "지원 모드",
        "dvfs_or_control_domains": "DVFS/제어 도메인",
        "capabilities": "캐퍼빌리티 목록",
        "knobs": "제어 노브 목록",
    },
    "IPCapability": {
        "support_status": "지원 상태",
        "value": "값",
        "values": "값 목록",
    },
    "IPKnob": {
        "control_domain": "제어 도메인",
        "power_direction": "전력 방향",
        "latency_direction": "지연 방향",
        "bandwidth_direction": "대역폭 방향",
        "risk_direction": "리스크 방향",
        "affected_kpis": "영향 KPI",
        "related_scenarios": "관련 시나리오",
    },
    "IPDependencyRule": {
        "depends_on_ip_id": "의존 대상 IP ID",
        "relationship": "의존 관계",
    },
    "ConfidenceSignal": {},
    "CandidateOption": {
        "option_id": "옵션 ID",
        "option_type": "옵션 유형",
        "current_posture": "현재 자세",
        "feasibility": "실현 가능성",
        "known_risks": "알려진 리스크",
        "qualitative_impact": "정성 영향",
        "target_project_id": "대상 프로젝트 ID",
    },
    "DecisionQuestion": {
        "question_id": "질문 ID",
        "question": "질문",
        "scopes": "질문 범위",
    },
    "EventRelations": {
        "predecessor_event_ids": "선행 이벤트 ID",
        "derived_from_event_ids": "유래 이벤트 ID",
        "propagation_event_ids": "전파 이벤트 ID",
        "supersedes_event_ids": "대체 이벤트 ID",
        "validation_event_ids": "검증 이벤트 ID",
    },
    "ExpectedReviewOutput": {
        "output_type": "산출 유형",
    },
    "RequiredEvidenceNeed": {
        "evidence_need_id": "근거 요구 ID",
        "blocks_confidence_above": "확신도 상한",
        "related_option_ids": "관련 옵션 ID",
        "review_impact": "검토 영향",
    },
    "DevelopmentEvent": {
        "event_type": "이벤트 유형",
        "event_category": "이벤트 분류",
        "severity": "심각도",
        "schedule_signal": "일정 신호",
        "roles_involved": "참여 역할",
        "affected_domains": "영향 도메인",
        "resource_signal": "리소스 신호",
        "confidence_signal": "확신도 신호",
        "requested_by": "요청자",
        "candidate_options": "후보 옵션",
        "decision_question": "결정 질문",
        "event_relations": "이벤트 관계",
        "expected_review_output": "기대 검토 산출",
        "review_posture": "검토 자세",
    },
    "AffectedScope": {
        "ip_blocks": "IP 블록",
        "system_blocks": "시스템 블록",
        "kpis": "KPI 목록",
    },
    "Issue": {
        "issue_type": "이슈 유형",
        "severity": "심각도",
        "symptom": "증상",
        "evidence_refs": "근거 참조",
        "root_cause_candidates": "근본원인 후보",
        "affected_scope": "영향 범위",
        "root_causes": "근본 원인 목록",
        "fix_type": "조치 유형",
        "fix_description": "조치 내용",
        "workaround": "임시 우회",
        "verifying_test_ids": "검증 테스트 ID",
        "residual_risk": "잔존 리스크",
        "reusable_lesson": "재사용 교훈",
        "resolved_week": "종결 주차",
    },
    "RootCause": {
        "cause_type": "원인 유형",
        "evidence_refs": "근거 참조",
    },
    "Test": {
        "test_type": "테스트 유형",
        "result": "결과",
        "verifies_issue_ids": "검증 대상 이슈 ID",
        "executed_week": "실행 주차",
    },
    "EvidenceCatalogEntry": {
        "confidence_contribution": "확신도 기여",
        "is_measurement": "측정 여부",
        "is_prediction": "예측 여부",
        "known_limitation": "알려진 한계",
        "measurement_stage": "측정 단계",
        "scenario_match": "시나리오 일치도",
        "source_system": "출처 시스템",
        "related_milestone_ids": "관련 마일스톤 ID",
        "related_request_ids": "관련 요청 ID",
    },
    "MeasurementEvidence": {
        "measurement_type": "측정 유형",
        "evidence_id": "근거 ID",
        "observed_value": "관측값",
        "value_status": "값 상태",
        "qualitative_result": "정성 결과",
        "source_kind": "출처 종류",
        "limitations": "한계",
        "related_measurement_requirement_ids": "관련 측정 요구 ID",
        "related_resource_profile_ids": "관련 리소스 프로파일 ID",
        "related_risk_basis_ids": "관련 리스크 근거 ID",
    },
    "MeasurementRequirement": {
        "measurement_type": "측정 유형",
        "required_for": "필요 목적",
        "related_evidence_gap_ids": "관련 근거 공백 ID",
        "related_resource_profile_ids": "관련 리소스 프로파일 ID",
        "related_risk_basis_ids": "관련 리스크 근거 ID",
    },
    "ChunkMetadata": {
        "decision_stage": "결정 단계",
        "retrieval_use": "검색 용도",
        "source_confidence": "출처 확신도",
    },
    "SemanticChunk": {
        "chunk_text": "청크 텍스트",
        "embedding_status": "임베딩 상태",
        "evidence_confidence": "근거 확신도",
        "ip_ids": "IP ID 목록",
        "kpi_ids": "KPI ID 목록",
        "system_block_ids": "시스템 블록 ID 목록",
    },
    "VectorMetadata": {
        "confidence_upgrade_allowed": "확신도 상향 허용",
        "not_evidence_proof": "증거 아님",
        "retrieval_role": "검색 역할",
    },
    "SemanticVector": {
        "embedding": "임베딩 벡터",
        "vector_model": "벡터 모델",
        "vector_dimension": "벡터 차원",
    },
    "UIIdentity": {
        "visual_concept": "시각 컨셉",
        "icon_keywords": "아이콘 키워드",
    },
    "RoleAgent": {
        "role_type": "역할 유형",
        "includes_verification": "검증 포함 여부",
        "goals": "목표",
        "responsibilities": "책임",
        "primary_concerns": "주요 관심사",
        "guardrails": "가드레일",
        "feedback_targets": "피드백 대상",
        "ui_identity": "UI 정체성",
    },
    "ActivityInputContext": {
        "evidence_ids": "근거 ID 목록",
        "milestone_ids": "마일스톤 ID 목록",
        "propagation_ids": "전파 ID 목록",
        "candidate_option_ids": "후보 옵션 ID 목록",
        "decision_question_ref": "결정 질문 참조 여부",
    },
    "EvidenceAssessment": {
        "evidence_id": "근거 ID",
        "assessment": "평가",
        "limitation": "한계",
        "missing_information_ref": "누락 정보 참조",
        "role_interpretation": "역할 해석",
    },
    "OptionAssessment": {
        "option_id": "옵션 ID",
        "role_posture": "역할 자세",
        "blockers": "차단 요인",
        "expected_impact": "기대 영향",
    },
    "ConfidencePosture": {
        "level": "확신 수준",
        "blocked_by": "차단 요인",
    },
    "ActivityRecommendation": {
        "recommendation_type": "권고 유형",
        "target_roles": "대상 역할",
    },
    "SafetyFlags": {
        "fixture_derived": "fixture 유래",
        "not_agent_execution": "에이전트 실행 아님",
    },
    "ActivityTraceability": {},
    "RoleActivity": {
        "activity_type": "활동 유형",
        "expected_output": "기대 산출",
        "linked_event_id": "연결 이벤트 ID",
        "input_context": "입력 컨텍스트",
        "observations": "관찰",
        "concerns": "우려",
        "evidence_assessment": "근거 평가",
        "option_assessments": "옵션 평가",
        "confidence_posture": "확신도 자세",
        "recommendation": "권고",
        "follow_up_actions": "후속 조치",
        "handoff_to_roles": "인계 역할",
        "safety": "안전 플래그",
        "traceability": "추적성",
    },
    "FeedbackItem": {
        "target_role": "대상 역할",
    },
    "RoleOutput": {
        "run_id": "실행 ID",
        "risk_assessment": "리스크 평가",
        "feedback_items": "피드백 항목",
        "derivation_summary": "도출 요약",
    },
    "RoleAdvisory": {
        "run_id": "실행 ID",
        "provider": "생성 엔진",
        "model_name": "모델",
        "derivation_summary": "도출 요약",
    },
    "AgentRun": {
        "input_hash": "입력 해시",
        "requested_roles": "요청 역할",
        "advisories": "조언 목록",
        "validation_notes": "검증 기록",
        "duration_ms": "소요 시간(ms)",
        "created_at": "생성 시각",
    },
    "DecisionOption": {
        "label": "표시명",
        "benefits": "이득",
    },
    "DecisionBasis": {
        "basis_type": "근거 유형",
        "ref_id": "참조 ID",
    },
    "Decision": {
        "decision_type": "결정 유형",
        "options": "결정 옵션",
        "selected_option": "선택 옵션",
        "tradeoff_summary": "트레이드오프 요약",
        "unresolved_risks": "미해결 리스크",
        "action_items": "액션 아이템",
    },
    "ActionItem": {
        "source_decision_id": "원천 결정 ID",
        "owner_role": "담당 역할",
        "due_phase": "기한 단계",
    },
    "DocRef": {
        "document": "문서",
        "section": "섹션",
    },
    "ReviewPack": {
        "project_ids": "프로젝트 ID 목록",
    },
    "Relation": {
        "relation_type": "관계 유형",
        "target_id": "대상 객체 ID",
        "target_type": "대상 객체 유형",
    },
    "SimulationRun": {
        "expected_outputs": "기대 산출",
    },
    "GroundedStatement": {},
}

# ---------------------------------------------------------------- enum 라벨

ENUM_LABELS: dict[str, dict[str, str]] = {
    "SourceOrigin": {
        "synthetic": "가상",
        "imported": "반입",
        "integrated": "연동",
    },
    "Confidence": {
        "low": "낮음",
        "medium": "중간",
        "high": "높음",
    },
    "RootCauseType": {
        "architecture_miss": "아키텍처 누락",
        "spec_ambiguity": "스펙 모호성",
        "verification_gap": "검증 공백",
        "power_model_error": "전력 모델 오류",
        "sw_workaround_dependency": "SW 우회 의존",
        "customer_scenario_mismatch": "고객 시나리오 불일치",
    },
}

# ---------------------------------------------------------------- 값 도메인 라벨 (U1)
# 문자열 코드 값 도메인의 한국어 라벨 사전 — 화면 표시는 한국어, 원문 코드는 hover만.
# fixture 전 값 커버리지는 tests/test_glossary.py가 강제한다: 반입(CSV/JIRA)으로
# 새 값이 들어오면 여기 누락이 테스트로 드러난다 (06_stage16_ui_overhaul.md U1).

VALUE_LABELS: dict[str, dict[str, str]] = {
    "issue_status": {
        "open": "미해결",
        "synthetic_open": "미해결(합성)",
        "under_analysis": "분석 중",
        "workaround_applied": "우회 적용",
        "resolved": "해결됨",
        "closed": "종결",
        "done": "완료",
    },
    "issue_type": {
        "architecture_tradeoff": "아키텍처 트레이드오프",
        "audio_latency": "오디오 지연",
        "av_sync": "A/V 동기",
        "bandwidth_overrun": "대역폭 초과",
        "defect": "결함",
        "image_quality_regression": "화질 회귀",
        "latency_regression": "지연 회귀",
        "performance_competitiveness": "성능 경쟁력",
        "power_budget_overrun": "전력 예산 초과",
        "power_gap": "전력 격차",
        "power_regression": "전력 회귀",
        "qos_config": "QoS 설정",
        "real_time_stability": "실시간 안정성",
        "resume_latency": "재개 지연",
        "stability": "안정성",
        "thermal_throttling": "발열 스로틀링",
        "underrun": "언더런",
    },
    "fix_type": {
        "hw_fix": "HW 수정",
        "sw_fix": "SW 수정",
        "tuning": "튜닝",
        "spec_change": "스펙 변경",
        "process_change": "프로세스 변경",
        "none": "조치 없음",
    },
    "severity": {
        "critical": "치명",
        "high": "높음",
        "medium": "중간",
        "low": "낮음",
        "info": "정보",
    },
    "test_type": {
        "regression": "회귀",
        "scenario": "시나리오",
        "cts_vts": "CTS/VTS",
        "power": "전력",
    },
    "test_result": {
        "passed": "통과",
        "failed": "실패",
        "blocked": "차단됨",
        "planned": "계획됨",
    },
    "event_status": {
        "recorded": "기록됨",
        "open": "미해결",
        "in_review": "검토 중",
        "mitigated": "완화됨",
        "deferred": "유보됨",
        "available": "확보됨",
    },
    "schedule_signal": {
        "on_track": "정상 진행",
        "watch": "관찰",
        "at_risk": "위험",
        "window_closing": "결정 시한 임박",
        "deferred": "유보",
        "not_applicable": "해당 없음",
    },
    "availability": {
        "available": "확보",
        "partial": "부분 확보",
        "missing": "부재",
        "planned": "계획됨",
    },
    "confidence_contribution": {
        "high": "높음",
        "medium": "중간",
        "low": "낮음",
        "none": "없음",
    },
    "measurement_stage": {
        "current_silicon": "현 실리콘",
        "field": "필드",
        "previous_project": "이전 프로젝트",
        "customer_project": "고객 프로젝트",
        "emulator": "에뮬레이터",
        "architecture": "아키텍처",
        "planned": "계획됨",
    },
    "scenario_match": {
        "strong": "정합",
        "partial": "부분 정합",
        "none": "무정합",
    },
    "request_status": {
        "architecture_document_input": "아키텍처 문서 입력",
        "architecture_review": "아키텍처 검토",
        "customer_spec_intake": "고객 스펙 접수",
        "design_support_review": "설계 지원 검토",
        "drop_or_defer_review": "철회·유보 검토",
        "evidence_open": "근거 미확보",
        "evt0_regression_scope_open": "EVT0 회귀 범위 미정",
        "evt1_review": "EVT1 검토",
        "feasibility_review": "실현성 검토",
        "function_done_power_open": "기능 완료·전력 미해결",
        "hw_window_closed": "HW 변경 시한 종료",
        "optimization_review": "최적화 검토",
        "pre_es_measurement_planning": "ES 전 측정 계획",
        "pre_spec_freeze_review": "스펙 확정 전 검토",
        "predevelopment_review": "선행 개발 검토",
        "regression_open": "회귀 미해결",
        "reproduced": "재현됨",
        "spec_discussion": "스펙 논의",
        "spec_freeze_review": "스펙 확정 검토",
        "under_review": "검토 중",
    },
    "request_priority": {
        "P0": "P0(최우선)",
        "P1": "P1(우선)",
        "P2": "P2(일반)",
    },
    "requirement_level": {
        "required": "필수",
        "candidate": "후보",
    },
    "direction": {
        "increase": "증가",
        "decrease": "감소",
        "mixed": "혼합",
        "unknown": "미상",
    },
    "support_status": {
        "supported": "지원",
        "conditional": "조건부 지원",
        "unsupported": "미지원",
        "unknown": "미상",
    },
}

# ---------------------------------------------------------------- 조회 API


def object_label(model_name: str) -> str | None:
    """모델(객체 타입)의 한국어 라벨."""
    return OBJECT_LABELS.get(model_name)


def field_label(model_name: str, field_name: str) -> str | None:
    """필드의 한국어 라벨 — 모델별 정의가 공통 정의보다 우선."""
    specific = MODEL_FIELD_LABELS.get(model_name, {})
    return specific.get(field_name) or COMMON_FIELD_LABELS.get(field_name)


def enum_label(enum_name: str, value: str) -> str | None:
    """enum 값의 한국어 라벨."""
    return ENUM_LABELS.get(enum_name, {}).get(value)


def value_label(domain: str, value: str) -> str | None:
    """값 도메인(문자열 코드)의 한국어 라벨 — 없으면 None (화면은 원문 폴백)."""
    return VALUE_LABELS.get(domain, {}).get(value)


def collect_models(root_models: list[type[BaseModel]]) -> list[type[BaseModel]]:
    """루트 모델에서 중첩 서브모델까지 재귀 수집한다."""
    seen: dict[str, type[BaseModel]] = {}

    def walk(model: type[BaseModel]) -> None:
        if model.__name__ in seen:
            return
        seen[model.__name__] = model
        for field in model.model_fields.values():
            for candidate in _nested_models(field.annotation):
                walk(candidate)

    for m in root_models:
        walk(m)
    return list(seen.values())


def _nested_models(annotation: Any) -> list[type[BaseModel]]:
    """타입 어노테이션에서 BaseModel 서브클래스를 추출한다."""
    import typing

    found: list[type[BaseModel]] = []
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        found.append(annotation)
    for arg in typing.get_args(annotation):
        found.extend(_nested_models(arg))
    return found


def find_missing_labels(root_models: list[type[BaseModel]]) -> list[str]:
    """라벨 누락 항목을 찾는다 — 커버리지 테스트/validate CLI에서 사용."""
    missing: list[str] = []
    for model in collect_models(root_models):
        if object_label(model.__name__) is None:
            missing.append(f"object:{model.__name__}")
        for field_name, field in model.model_fields.items():
            if field_label(model.__name__, field_name) is None:
                missing.append(f"field:{model.__name__}.{field_name}")
            for enum_type in _nested_enums(field.annotation):
                for member in enum_type:
                    if enum_label(enum_type.__name__, member.value) is None:
                        missing.append(f"enum:{enum_type.__name__}.{member.value}")
    return missing


def _nested_enums(annotation: Any) -> list[type[Enum]]:
    import typing

    found: list[type[Enum]] = []
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        found.append(annotation)
    for arg in typing.get_args(annotation):
        found.extend(_nested_enums(arg))
    return found


def export_glossary(root_models: list[type[BaseModel]]) -> dict[str, Any]:
    """glossary를 직렬화 가능한 dict로 export한다 (frontend 소비용)."""
    objects: dict[str, str] = {}
    fields: dict[str, dict[str, str]] = {}
    for model in collect_models(root_models):
        label = object_label(model.__name__)
        if label:
            objects[model.__name__] = label
        model_fields: dict[str, str] = {}
        for field_name in model.model_fields:
            f_label = field_label(model.__name__, field_name)
            if f_label:
                model_fields[field_name] = f_label
        fields[model.__name__] = model_fields
    return {
        "objects": objects,
        "fields": fields,
        "enums": ENUM_LABELS,
        "value_labels": VALUE_LABELS,
    }
