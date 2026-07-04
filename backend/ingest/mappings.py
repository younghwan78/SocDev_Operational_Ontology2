"""반입 매핑 정의 — 한국어 열 이름 → 온톨로지 필드.

사내 Excel/CSV의 열을 온톨로지 계약으로 변환하는 명세다.
매핑 추가 시 이 레지스트리에 등록한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IngestMapping:
    """열→필드 매핑 명세."""

    name: str
    label_ko: str
    target_collection: str
    column_map: dict[str, str]  # 열 이름 → 모델 필드
    list_columns: dict[str, str] = field(default_factory=dict)  # 필드 → 구분자
    int_columns: set[str] = field(default_factory=set)
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
}


def convert_row(mapping: IngestMapping, row: dict[str, str]) -> dict[str, object]:
    """열 이름 기반 행을 모델 필드 dict로 변환한다 (값은 문자열 상태 유지, 형 변환만)."""
    record: dict[str, object] = dict(mapping.defaults)
    for column, field_name in mapping.column_map.items():
        raw = row.get(column)
        if raw is None or str(raw).strip() == "":
            continue
        value = str(raw).strip()
        if field_name in mapping.list_columns:
            separator = mapping.list_columns[field_name]
            record[field_name] = [item.strip() for item in value.split(separator) if item.strip()]
        elif field_name in mapping.int_columns:
            record[field_name] = int(float(value))  # Excel 숫자 "12.0" 대비
        else:
            record[field_name] = value
    return record


def missing_required(mapping: IngestMapping, row: dict[str, str]) -> list[str]:
    return [
        column
        for column in sorted(mapping.required_columns)
        if not str(row.get(column, "")).strip()
    ]
