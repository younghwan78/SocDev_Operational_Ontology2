"""56 synthetic_data 전량을 58 온톨로지 v1.0 계약으로 변환한다.

- 56 원본은 절대 수정하지 않는다 (read-only).
- id 별칭 필드(event_id 등)는 본 id와 동일함을 확인 후 제거한다.
- 구 events.yaml 레코드는 DevelopmentEvent 통합 계약으로 승격한다.
- 모든 객체에 source(origin=synthetic, ref=원본 위치)를 부여한다.

실행: uv run python tools/convert_56_fixtures.py [--source-dir DIR] [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ontology import COLLECTIONS  # noqa: E402

DEFAULT_SOURCE = Path(r"E:\56_Codex_SoC_Operational_Ontology\synthetic_data")
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "fixtures"

# 56 파일::컬렉션 → 58 컬렉션 키
COLLECTION_MAP: dict[tuple[str, str], str] = {
    ("projects.yaml", "projects"): "projects",
    ("project_milestones.yaml", "project_milestones"): "project_milestones",
    ("customer_requests.yaml", "customer_requests"): "customer_requests",
    ("project_links.yaml", "project_links"): "project_links",
    ("project_scenario_focuses.yaml", "project_scenario_focuses"): "project_scenario_focuses",
    ("kpi_definitions.yaml", "kpis"): "kpi_definitions",
    ("scenario_groups.yaml", "scenario_groups"): "scenario_groups",
    ("scenarios.yaml", "scenarios"): "scenarios",
    ("variants.yaml", "variants"): "variants",
    ("scenario_ip_requirements.yaml", "scenario_ip_requirements"): "scenario_ip_requirements",
    ("scenario_requests.yaml", "scenario_requests"): "scenario_requests",
    ("ips.yaml", "ip_blocks"): "ip_blocks",
    ("ip_base_specs.yaml", "ip_base_specs"): "ip_base_specs",
    ("ip_base_specs.yaml", "ip_capabilities"): "ip_capabilities",
    ("ip_knobs.yaml", "ip_knobs"): "ip_knobs",
    ("ip_dependency_rules.yaml", "ip_dependency_rules"): "ip_dependency_rules",
    ("development_events.yaml", "development_events"): "development_events",
    ("events.yaml", "events"): "development_events",
    ("issues.yaml", "issues"): "issues",
    ("evidence.yaml", "evidence"): "evidence",
    ("evidence_catalog.yaml", "evidence_catalog"): "evidence_catalog",
    ("measurement_evidence.yaml", "measurement_evidence"): "measurement_evidence",
    ("measurement_requirements.yaml", "measurement_requirements"): "measurement_requirements",
    ("semantic_chunks.yaml", "semantic_chunks"): "semantic_chunks",
    ("semantic_vectors.yaml", "semantic_vectors"): "semantic_vectors",
    ("roles.yaml", "roles"): "roles",
    ("role_agent_activities.yaml", "role_agent_activities"): "role_activities",
    ("decisions.yaml", "decisions"): "decisions",
    ("decisions.yaml", "action_items"): "action_items",
    ("review_packs.yaml", "review_packs"): "review_packs",
    ("relations.yaml", "relations"): "relations",
    ("simulation_runs.yaml", "simulation_runs"): "simulation_runs",
}

# 설계 23: 58 전용 보강 — 마일스톤 exit 기준 (56 원본에 없는 계약 필드).
# 게이트 판정 데모/테스트 재료: spec freeze(근거+이슈 상한)·아키 리뷰(검증된
# 종결)·ES 릴리스(이슈 상한). 실데이터에서는 반입 경로가 채운다.
GATE_CRITERIA_58: dict[str, list[dict[str, Any]]] = {
    "project_w_spec_freeze_q2": [
        {
            "criterion_id": "gate_w_specfreeze_evidence",
            "kind": "required_evidence",
            "description": "스펙 확정 전 대표 시나리오의 현세대 실측 근거가 확보되어야 한다",
            "evidence_types": ["current_project_measurement"],
            "scenario_ids": ["uhd60_recording_eis_on"],
        },
        {
            "criterion_id": "gate_w_specfreeze_blockers",
            "kind": "max_open_issues",
            "description": "높음 이상 심각도의 미해결 이슈가 없어야 한다",
            "max_open_issues": 0,
            "min_severity": "high",
        },
    ],
    "project_w_architecture_review_q2_q3": [
        {
            "criterion_id": "gate_w_archreview_verified_closure",
            "kind": "verified_closure",
            "description": "종결된 이슈는 통과한 검증 테스트가 연결되어 있어야 한다",
        }
    ],
    "project_u_es_release_w12": [
        {
            "criterion_id": "gate_u_es_blockers",
            "kind": "max_open_issues",
            "description": "ES 릴리스 전 높음 이상 심각도의 미해결 이슈가 없어야 한다",
            "max_open_issues": 0,
            "min_severity": "high",
        }
    ],
}

# 컬렉션별 id 별칭 필드 — 본 id와 동일해야 하며 제거된다.
ID_ALIASES: dict[str, str] = {
    "development_events": "event_id",
    "project_milestones": "milestone_id",
    "project_scenario_focuses": "focus_id",
    "scenario_requests": "request_id",
    "measurement_requirements": "requirement_id",
    "evidence_catalog": "evidence_id",
    "role_activities": "activity_id",
    "review_packs": "pack_id",
}


def strip_none(value: Any) -> Any:
    """None 값 키를 제거한다 — 모델 기본값(Optional/빈 리스트)으로 대체된다."""
    if isinstance(value, dict):
        return {k: strip_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [strip_none(v) for v in value]
    return value


def convert_legacy_event(record: dict[str, Any]) -> dict[str, Any]:
    """구 events.yaml 레코드를 DevelopmentEvent 통합 계약으로 승격한다."""
    return {
        "id": record["id"],
        "project_id": record["project_id"],
        "title": record["title"],
        "description": record["description"],
        "event_type": record["type"],
        "event_category": "legacy_event",
        "linked_scenario_ids": record.get("affected_scenarios", []),
        "requested_by": record.get("requested_by"),
    }


def transform(key_56: tuple[str, str], record: dict[str, Any], problems: list[str]) -> dict[str, Any]:
    """56 레코드 하나를 58 계약 dict로 변환한다."""
    filename, _ = key_56
    collection_58 = COLLECTION_MAP[key_56]

    if key_56 == ("events.yaml", "events"):
        record = convert_legacy_event(record)
    record = strip_none(dict(record))

    alias = ID_ALIASES.get(collection_58)
    if alias and alias in record:
        if record[alias] != record.get("id"):
            problems.append(
                f"{filename}::{collection_58}[{record.get('id')}]: "
                f"id 별칭 불일치 {alias}={record[alias]}"
            )
        record.pop(alias)

    record["source"] = {
        "origin": "synthetic",
        "ref": f"56:synthetic_data/{filename}#{record.get('id', '?')}",
    }
    if collection_58 == "project_milestones":
        criteria = GATE_CRITERIA_58.get(str(record.get("id", "")))
        if criteria:
            record["exit_criteria"] = criteria
    return record


def convert(source_dir: Path, out_dir: Path) -> int:
    problems: list[str] = []
    converted: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for (filename, collection_56), collection_58 in COLLECTION_MAP.items():
        path = source_dir / filename
        if not path.exists():
            problems.append(f"{filename}: 원본 파일 없음")
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for record in data.get(collection_56, []):
            converted[collection_58].append(transform((filename, collection_56), record, problems))

    # 모델 검증 — 계약과 데이터가 어긋나면 여기서 실패한다.
    validated: dict[str, list[dict[str, Any]]] = {}
    for collection_58, records in converted.items():
        model = COLLECTIONS[collection_58][1]
        rows: list[dict[str, Any]] = []
        for record in records:
            try:
                obj = model.model_validate(record)
            except Exception as exc:
                problems.append(f"{collection_58}[{record.get('id')}]: 검증 실패\n{exc}")
                continue
            rows.append(obj.model_dump(mode="json", exclude_none=True))
        validated[collection_58] = rows

    if problems:
        print("변환 실패:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    # 모듈 파일별로 기록
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)
    for collection_58, rows in validated.items():
        module_name = COLLECTIONS[collection_58][0]
        grouped[module_name][collection_58] = rows

    out_dir.mkdir(parents=True, exist_ok=True)
    for module_name, collections in sorted(grouped.items()):
        out_path = out_dir / f"{module_name}.yaml"
        ordered = {key: collections[key] for key in COLLECTIONS if key in collections}
        header = (
            "# GENERATED — tools/convert_56_fixtures.py가 56 synthetic_data에서 변환함.\n"
            "# 직접 편집 금지. 재생성: uv run python tools/convert_56_fixtures.py\n"
        )
        body = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False, width=100)
        out_path.write_text(header + body, encoding="utf-8", newline="\n")
        total = sum(len(v) for v in collections.values())
        print(f"기록: {out_path.name} ({total}건)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    raise SystemExit(convert(args.source_dir, args.out_dir))


if __name__ == "__main__":
    main()
