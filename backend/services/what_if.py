"""what-if 주입 — 가정 실험, ephemeral overlay (16_digital_twin_followups.md §5).

"이 이슈가 해결되면/안 풀리면 무엇이 달라지나"에 결정론으로 답한다.
저장소에는 어떤 경우에도 쓰지 않는다 — 가정을 적용한 overlay 저장소를 만들어
기존 RiskService 룰로 재계산하고 baseline과의 차이만 돌려준다.
판정 룰을 새로 만들지 않는다: 룰이 하나면 가정 실험과 실제 지도가 절대 어긋나지 않는다.

모든 가정은 assumption으로 명시되고 confidence는 medium을 넘지 않는다.
SimulationRun(56 보존 계약)은 사용하지 않으며 감사 기록도 만들지 않는다 —
결정론 계산이라 동일 입력으로 언제든 재현된다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.loaders.protocols import RepositoryProtocol
from backend.loaders.repository import InMemoryRepository
from backend.ontology import COLLECTIONS, OntologyObject
from backend.ontology.glossary import value_label
from backend.services.common import BasisItem
from backend.services.risk import RiskService

# 가정 종류 → (컬렉션, 대상 필드, 값 도메인, 한국어 라벨)
_ASSUMPTION_KINDS: dict[str, tuple[str, str, str, str]] = {
    "issue_status": ("issues", "status", "issue_status", "이슈 상태 가정"),
    "event_schedule_signal": (
        "development_events",
        "schedule_signal",
        "schedule_signal",
        "이벤트 일정 신호 가정",
    ),
}


class UnknownTargetError(Exception):
    pass


class InvalidAssumptionError(Exception):
    pass


class WhatIfAssumption(BaseModel):
    """가정 1건 — 실재 객체의 단일 필드를 가정 값으로 치환한다."""

    model_config = ConfigDict(extra="forbid")

    kind: str  # issue_status | event_schedule_signal
    target_id: str
    value: str
    note: str | None = None  # 사용자가 붙이는 가정 사유


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumptions: list[WhatIfAssumption] = Field(min_length=1, max_length=10)


class AppliedAssumption(BaseModel):
    """적용된 가정의 에코 — assumption 지위와 confidence 상한을 명시한다."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    kind_ko: str
    target_id: str
    target_title: str
    field: str
    from_value: str | None
    to_value: str
    note: str | None = None
    basis_type: str = "assumption"  # 근거가 아니라 가정이다
    confidence: str = "medium"  # 가정 기반 — high 금지


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


class WhatIfResult(BaseModel):
    """가정 실험 결과 — 변화만 돌려주고, 변화 없음도 명시한다."""

    model_config = ConfigDict(extra="forbid")

    assumptions: list[AppliedAssumption]
    changed_rows: list[WhatIfRowChange]
    unchanged_scenario_count: int
    note_ko: str


class WhatIfService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def run(self, assumptions: list[WhatIfAssumption]) -> WhatIfResult:
        overlay, applied = self._overlay(assumptions)
        baseline = RiskService(self._repo).heatmap()
        projected = RiskService(overlay).heatmap()

        baseline_rows = {row.scenario_id: row for row in baseline.rows}
        projected_rows = {row.scenario_id: row for row in projected.rows}
        changed: list[WhatIfRowChange] = []
        unchanged = 0
        for scenario_id in sorted(set(baseline_rows) | set(projected_rows)):
            before = baseline_rows.get(scenario_id)
            after = projected_rows.get(scenario_id)
            if before is None or after is None:
                # 가정은 시나리오 집합을 바꾸지 않는다 — 방어적으로 건너뜀.
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
        return WhatIfResult(
            assumptions=applied,
            changed_rows=changed,
            unchanged_scenario_count=unchanged,
            note_ko=(
                "가정 기반 재계산 — 실데이터가 아니며 저장되지 않는다. "
                "판정 룰은 위험 지도와 동일하다 (결정론, 동일 입력 동일 출력)."
            ),
        )

    def _overlay(
        self, assumptions: list[WhatIfAssumption]
    ) -> tuple[InMemoryRepository, list[AppliedAssumption]]:
        """가정을 적용한 ephemeral 저장소 — 원 저장소는 불변."""
        collections: dict[str, list[OntologyObject]] = {
            key: list(self._repo.list(key)) for key in COLLECTIONS
        }
        applied: list[AppliedAssumption] = []
        for assumption in assumptions:
            spec = _ASSUMPTION_KINDS.get(assumption.kind)
            if spec is None:
                raise InvalidAssumptionError(
                    f"알 수 없는 가정 종류: {assumption.kind} "
                    f"(가능: {', '.join(sorted(_ASSUMPTION_KINDS))})"
                )
            collection, field, domain, kind_ko = spec
            if value_label(domain, assumption.value) is None:
                raise InvalidAssumptionError(
                    f"'{domain}' 도메인에 등재되지 않은 값: {assumption.value!r}"
                )
            target = next(
                (o for o in collections[collection] if o.id == assumption.target_id),
                None,
            )
            if target is None:
                raise UnknownTargetError(
                    f"{collection}에 없는 대상: {assumption.target_id}"
                )
            updated = target.model_copy(update={field: assumption.value})
            collections[collection] = [
                updated if o.id == assumption.target_id else o
                for o in collections[collection]
            ]
            applied.append(
                AppliedAssumption(
                    kind=assumption.kind,
                    kind_ko=kind_ko,
                    target_id=assumption.target_id,
                    target_title=str(getattr(target, "title", target.id)),
                    field=field,
                    from_value=(
                        str(current) if (current := getattr(target, field, None)) else None
                    ),
                    to_value=assumption.value,
                    note=assumption.note,
                )
            )
        return InMemoryRepository(collections), applied
