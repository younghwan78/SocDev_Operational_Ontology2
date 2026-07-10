"""반입 매핑 정의 — 한국어 열 이름 → 온톨로지 필드.

사내 Excel/CSV의 열을 온톨로지 계약으로 변환하는 명세다.
매핑 추가 시 이 레지스트리에 등록한다.

중첩 필드는 점 표기로 지원한다 (예: "영향 시나리오" → "affected_scope.scenarios").
단일 하위 객체 리스트(예: root_causes 1건)는 `single_item_lists`로 감싼다 —
반입 CSV는 행당 근본원인 1건까지만 담는다 (다중 원인은 fixture/커넥터 경로).
"""

from __future__ import annotations

from dataclasses import dataclass, field

_TRUE_TOKENS = {"예", "true", "yes", "y", "1"}
_FALSE_TOKENS = {"아니오", "false", "no", "n", "0"}


@dataclass(frozen=True)
class IngestMapping:
    """열→필드 매핑 명세. 필드 경로는 점 표기로 중첩을 표현한다."""

    name: str
    label_ko: str
    target_collection: str
    column_map: dict[str, str]  # 열 이름 → 모델 필드 경로
    list_columns: dict[str, str] = field(default_factory=dict)  # 필드 경로 → 구분자
    int_columns: set[str] = field(default_factory=set)
    bool_columns: set[str] = field(default_factory=set)  # "예/아니오", "true/false"
    single_item_lists: set[str] = field(default_factory=set)  # 조립 후 [obj]로 감쌀 필드
    defaults: dict[str, object] = field(default_factory=dict)
    required_columns: set[str] = field(default_factory=set)


MAPPINGS: dict[str, IngestMapping] = {
    "project_milestones": IngestMapping(
        name="project_milestones",
        label_ko="프로젝트 마일스톤",
        target_collection="project_milestones",
        column_map={
            "마일스톤 ID": "id",
            "프로젝트 ID": "project_id",
            "제목": "title",
            "설명": "description",
            "유형": "milestone_type",
            "개발 단계": "lifecycle_stage",
            "결정 구간": "decision_window",
            "주차": "week",
            "분기": "quarter",
            "관련 역할": "relevant_roles",
        },
        list_columns={"relevant_roles": ";"},
        int_columns={"week"},
        required_columns={"마일스톤 ID", "프로젝트 ID", "제목"},
    ),
    "measurement_evidence": IngestMapping(
        name="measurement_evidence",
        label_ko="측정 근거",
        target_collection="measurement_evidence",
        column_map={
            "측정 ID": "id",
            "프로젝트 ID": "project_id",
            "시나리오 ID": "scenario_id",
            "이벤트 ID": "event_id",
            "근거 ID": "evidence_id",
            "제목": "title",
            "근거 유형": "evidence_type",
            "측정 유형": "measurement_type",
            "관측값": "observed_value",
            "단위": "unit",
            "값 상태": "value_status",
            "정성 결과": "qualitative_result",
            "확신도": "confidence",
            "출처 종류": "source_kind",
            "출처 참조": "source_ref",
            "한계": "limitations",
            "관련 KPI": "related_kpi_ids",
            "관련 IP": "related_ip_ids",
        },
        list_columns={"limitations": ";", "related_kpi_ids": ";", "related_ip_ids": ";"},
        required_columns={"측정 ID", "프로젝트 ID", "시나리오 ID", "제목"},
    ),
    "issues": IngestMapping(
        name="issues",
        label_ko="개발 이슈",
        target_collection="issues",
        column_map={
            "이슈 ID": "id",
            "프로젝트 ID": "project_id",
            "제목": "title",
            "유형": "issue_type",
            "상태": "status",
            "심각도": "severity",
            "증상": "symptom",
            "확신도": "confidence",
            "근거 참조": "evidence_refs",
            "영향 시나리오": "affected_scope.scenarios",
            "영향 IP": "affected_scope.ip_blocks",
            "영향 시스템 블록": "affected_scope.system_blocks",
            "영향 KPI": "affected_scope.kpis",
            "원인 유형": "root_causes.cause_type",
            "원인 설명": "root_causes.description",
            "원인 확신도": "root_causes.confidence",
            "원인 근거": "root_causes.evidence_refs",
            "조치 유형": "fix_type",
            "조치 설명": "fix_description",
            "우회책": "workaround",
            "검증 테스트 ID": "verifying_test_ids",
            "잔존 리스크": "residual_risk",
            "교훈": "reusable_lesson",
            "해결 주차": "resolved_week",
        },
        list_columns={
            "evidence_refs": ";",
            "affected_scope.scenarios": ";",
            "affected_scope.ip_blocks": ";",
            "affected_scope.system_blocks": ";",
            "affected_scope.kpis": ";",
            "root_causes.evidence_refs": ";",
            "verifying_test_ids": ";",
        },
        int_columns={"resolved_week"},
        single_item_lists={"root_causes"},
        required_columns={"이슈 ID", "프로젝트 ID", "제목", "유형", "상태", "증상", "확신도"},
    ),
    "tests": IngestMapping(
        name="tests",
        label_ko="검증 테스트",
        target_collection="tests",
        column_map={
            "테스트 ID": "id",
            "프로젝트 ID": "project_id",
            "제목": "title",
            "유형": "test_type",
            "결과": "result",
            "요약": "summary",
            "관련 시나리오": "linked_scenario_ids",
            "검증 이슈 ID": "verifies_issue_ids",
            "관련 근거": "linked_evidence_ids",
            "실행 주차": "executed_week",
        },
        list_columns={
            "linked_scenario_ids": ";",
            "verifies_issue_ids": ";",
            "linked_evidence_ids": ";",
        },
        int_columns={"executed_week"},
        required_columns={"테스트 ID", "프로젝트 ID", "제목", "유형", "결과", "요약"},
    ),
    "development_events": IngestMapping(
        name="development_events",
        label_ko="개발 이벤트",
        target_collection="development_events",
        column_map={
            "이벤트 ID": "id",
            "프로젝트 ID": "project_id",
            "제목": "title",
            "설명": "description",
            "유형": "event_type",
            "분류": "event_category",
            "개발 단계": "lifecycle_stage",
            "심각도": "severity",
            "상태": "status",
            "일정 신호": "schedule_signal",
            "주차": "week",
            "분기": "quarter",
            "관련 역할": "roles_involved",
            "영향 도메인": "affected_domains",
            "관련 IP": "related_ip_ids",
            "관련 시나리오": "linked_scenario_ids",
            "관련 근거": "linked_evidence_ids",
        },
        list_columns={
            "roles_involved": ";",
            "affected_domains": ";",
            "related_ip_ids": ";",
            "linked_scenario_ids": ";",
            "linked_evidence_ids": ";",
        },
        int_columns={"week"},
        required_columns={"이벤트 ID", "프로젝트 ID", "제목", "설명", "유형", "분류"},
    ),
    "evidence_catalog": IngestMapping(
        name="evidence_catalog",
        label_ko="근거 카탈로그",
        target_collection="evidence_catalog",
        column_map={
            "근거 ID": "id",
            "프로젝트 ID": "project_id",
            "시나리오 ID": "scenario_id",
            "제목": "title",
            "근거 유형": "evidence_type",
            "가용성": "availability",
            "확신도 기여": "confidence_contribution",
            "실측 여부": "is_measurement",
            "예측 여부": "is_prediction",
            "알려진 한계": "known_limitation",
            "측정 단계": "measurement_stage",
            "시나리오 정합": "scenario_match",
            "출처 시스템": "source_system",
            "출처 참조": "source_ref",
            "주차": "week",
            "관련 마일스톤": "related_milestone_ids",
            "관련 요청": "related_request_ids",
        },
        list_columns={"related_milestone_ids": ";", "related_request_ids": ";"},
        int_columns={"week"},
        bool_columns={"is_measurement", "is_prediction"},
        required_columns={"근거 ID", "프로젝트 ID", "시나리오 ID", "제목"},
    ),
}


def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _TRUE_TOKENS:
        return True
    if lowered in _FALSE_TOKENS:
        return False
    raise ValueError(f"불리언 값이 아님: {value!r} (예/아니오 또는 true/false)")


def _assign(record: dict[str, object], field_path: str, value: object) -> None:
    """점 표기 경로를 중첩 dict로 조립해 값을 넣는다."""
    parts = field_path.split(".")
    target = record
    for part in parts[:-1]:
        node = target.setdefault(part, {})
        if not isinstance(node, dict):
            raise ValueError(f"중첩 경로 충돌: {field_path}")
        target = node
    target[parts[-1]] = value


def convert_row(mapping: IngestMapping, row: dict[str, str]) -> dict[str, object]:
    """열 이름 기반 행을 모델 필드 dict로 변환한다 (값은 문자열 상태 유지, 형 변환만)."""
    record: dict[str, object] = dict(mapping.defaults)
    for column, field_path in mapping.column_map.items():
        raw = row.get(column)
        if raw is None or str(raw).strip() == "":
            continue
        value = str(raw).strip()
        parsed: object
        if field_path in mapping.list_columns:
            separator = mapping.list_columns[field_path]
            parsed = [item.strip() for item in value.split(separator) if item.strip()]
        elif field_path in mapping.int_columns:
            parsed = int(float(value))  # Excel 숫자 "12.0" 대비
        elif field_path in mapping.bool_columns:
            parsed = _parse_bool(value)
        else:
            parsed = value
        _assign(record, field_path, parsed)
    for field_name in sorted(mapping.single_item_lists):
        if field_name in record:
            record[field_name] = [record[field_name]]
    return record


def missing_required(mapping: IngestMapping, row: dict[str, str]) -> list[str]:
    return [
        column
        for column in sorted(mapping.required_columns)
        if not str(row.get(column, "")).strip()
    ]
