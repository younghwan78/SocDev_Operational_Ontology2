"""위험 지도 비교 — 두 heatmap의 행/셀 등급 변화 (설계 20 §3에서 추출).

what-if(가정 전/후)와 as-of diff(시점 A/B)가 같은 비교 로직을 공유한다 —
룰이 하나면 "가정 비교"와 "시점 비교"가 같은 언어로 읽힌다.
모델 이름(WhatIf*)은 openapi 스키마 안정성을 위해 유지한다 (what_if가 re-export).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.services.common import BasisItem
from backend.services.risk import RiskHeatmap


class WhatIfCellChange(BaseModel):
    """시나리오×IP 셀의 등급 변화 — 재계산 근거 동반."""

    model_config = ConfigDict(extra="forbid")

    ip_id: str
    baseline_grade: str
    baseline_grade_ko: str
    projected_grade: str
    projected_grade_ko: str
    projected_basis: list[BasisItem]


class WhatIfRowChange(BaseModel):
    """시나리오 행의 변화 — 종합 등급과 달라진 셀."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    scenario_name: str
    baseline_grade: str
    baseline_grade_ko: str
    projected_grade: str
    projected_grade_ko: str
    changed_cells: list[WhatIfCellChange] = Field(default_factory=list)


def diff_heatmaps(
    baseline: RiskHeatmap, projected: RiskHeatmap
) -> tuple[list[WhatIfRowChange], int]:
    """두 지도의 (변경 행 목록, 변화 없는 시나리오 수) — 동일 입력 동일 출력.

    양쪽에 모두 있는 시나리오만 비교한다 (가정/시점 재생은 시나리오 집합을
    바꾸지 않는 것이 정상 — 한쪽에만 있으면 방어적으로 건너뜀).
    """
    baseline_rows = {row.scenario_id: row for row in baseline.rows}
    projected_rows = {row.scenario_id: row for row in projected.rows}
    changed: list[WhatIfRowChange] = []
    unchanged = 0
    for scenario_id in sorted(set(baseline_rows) | set(projected_rows)):
        before = baseline_rows.get(scenario_id)
        after = projected_rows.get(scenario_id)
        if before is None or after is None:
            continue
        before_cells = {c.ip_id: c for c in before.cells}
        after_cells = {c.ip_id: c for c in after.cells}
        cell_changes = [
            WhatIfCellChange(
                ip_id=ip_id,
                baseline_grade=before_cells[ip_id].grade,
                baseline_grade_ko=before_cells[ip_id].grade_ko,
                projected_grade=after_cells[ip_id].grade,
                projected_grade_ko=after_cells[ip_id].grade_ko,
                projected_basis=after_cells[ip_id].basis,
            )
            for ip_id in sorted(set(before_cells) & set(after_cells))
            if before_cells[ip_id].grade != after_cells[ip_id].grade
        ]
        if before.overall_grade == after.overall_grade and not cell_changes:
            unchanged += 1
            continue
        changed.append(
            WhatIfRowChange(
                scenario_id=scenario_id,
                scenario_name=before.scenario_name,
                baseline_grade=before.overall_grade,
                baseline_grade_ko=before.overall_grade_ko,
                projected_grade=after.overall_grade,
                projected_grade_ko=after.overall_grade_ko,
                changed_cells=cell_changes,
            )
        )
    return changed, unchanged
