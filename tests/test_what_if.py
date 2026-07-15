"""P4 what-if 주입 — 가정 실험의 결정론·불변성·등급 재계산 (설계 16 §5)."""

from __future__ import annotations

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.ontology.event import Issue
from backend.ontology.ip import IPBlock
from backend.ontology.scenario import Scenario, ScenarioGroup
from backend.services.what_if import (
    InvalidAssumptionError,
    UnknownTargetError,
    WhatIfAssumption,
    WhatIfService,
)

_SRC = {"origin": "synthetic", "ref": "test:whatif"}


def _repo(issue_status: str = "open") -> InMemoryRepository:
    """최소 우주 — 시나리오 1 × IP 1 × 그 조합을 겨누는 이슈 1."""
    scenario = Scenario.model_validate(
        {
            "id": "scn_x",
            "source": _SRC,
            "name": "테스트 시나리오",
            "description": "what-if 검증용",
            "domain": "camera",
            "scenario_class": "recording",
            "scenario_group_id": "grp_x",
            "uses_ip_blocks": ["ip_x"],
            "customer_request_relevance": "high",
            "development_relevance": "high",
            "dou_relevance": "low",
            "iq_relevance": "low",
            "sustain_power_relevance": "low",
            "hw_pipeline_change_sensitivity": "low",
            "sw_control_complexity": "low",
        }
    )
    group = ScenarioGroup.model_validate(
        {
            "id": "grp_x",
            "source": _SRC,
            "name": "테스트 그룹",
            "purpose": "테스트",
            "scenarios": ["scn_x"],
        }
    )
    ip = IPBlock.model_validate(
        {
            "id": "ip_x",
            "source": _SRC,
            "name": "ISP-X",
            "category": "functional_mm_ip",
            "domain": "camera",
        }
    )
    issue = Issue.model_validate(
        {
            "id": "iss_x",
            "source": _SRC,
            "project_id": "proj_u",
            "title": "대역폭 초과",
            "issue_type": "bandwidth_overrun",
            "status": issue_status,
            "symptom": "프레임 드랍",
            "confidence": "medium",
            "affected_scope": {"scenarios": ["scn_x"], "ip_blocks": ["ip_x"]},
        }
    )
    return InMemoryRepository(
        {
            "scenarios": [scenario],
            "scenario_groups": [group],
            "ip_blocks": [ip],
            "issues": [issue],
        }
    )


def test_resolving_open_issue_lowers_grade() -> None:
    """수용 기준 1 — open→resolved 가정 시 미해결 이슈 근거가 빠진 등급으로 재계산."""
    repo = _repo("open")
    result = WhatIfService(repo).run(
        [WhatIfAssumption(kind="issue_status", target_id="iss_x", value="resolved")]
    )
    assert len(result.changed_rows) == 1
    row = result.changed_rows[0]
    assert (row.baseline_grade, row.projected_grade) == ("high", "medium")
    cell = row.changed_cells[0]
    assert cell.ip_id == "ip_x"
    assert (cell.baseline_grade, cell.projected_grade) == ("high", "medium")
    # 재계산 근거는 실제 위험 룰의 산출물 — 과거 이슈 패턴으로 바뀐다.
    assert any(b.rule == "past_issue_pattern" for b in cell.projected_basis)
    # 가정 에코 — assumption 지위 + confidence 상한.
    assumption = result.assumptions[0]
    assert assumption.basis_type == "assumption"
    assert assumption.confidence == "medium"
    assert (assumption.from_value, assumption.to_value) == ("open", "resolved")


def test_reopening_closed_issue_raises_grade() -> None:
    """반대 방향 — closed→open 가정 시 등급이 올라간다."""
    repo = _repo("closed")
    result = WhatIfService(repo).run(
        [WhatIfAssumption(kind="issue_status", target_id="iss_x", value="open")]
    )
    row = result.changed_rows[0]
    assert (row.baseline_grade, row.projected_grade) == ("medium", "high")


def test_repository_is_never_mutated() -> None:
    """수용 기준 2 — 어떤 경우에도 저장소 불변 (ephemeral overlay)."""
    repo = _repo("open")
    WhatIfService(repo).run(
        [WhatIfAssumption(kind="issue_status", target_id="iss_x", value="resolved")]
    )
    issue = repo.get("issues", "iss_x")
    assert isinstance(issue, Issue) and issue.status == "open"


def test_unknown_target_and_invalid_value_rejected() -> None:
    repo = _repo("open")
    service = WhatIfService(repo)
    with pytest.raises(UnknownTargetError):
        service.run(
            [WhatIfAssumption(kind="issue_status", target_id="없는_이슈", value="open")]
        )
    with pytest.raises(InvalidAssumptionError):
        service.run(
            [WhatIfAssumption(kind="issue_status", target_id="iss_x", value="이상한값")]
        )
    with pytest.raises(InvalidAssumptionError):
        service.run(
            [WhatIfAssumption(kind="없는_종류", target_id="iss_x", value="open")]
        )
    # 실패한 실행도 저장소를 건드리지 않는다.
    issue = repo.get("issues", "iss_x")
    assert isinstance(issue, Issue) and issue.status == "open"


def test_deterministic_same_input_same_output() -> None:
    """수용 기준 4 — 동일 입력 동일 출력."""
    repo = _repo("open")
    service = WhatIfService(repo)
    assumptions = [
        WhatIfAssumption(kind="issue_status", target_id="iss_x", value="resolved")
    ]
    assert service.run(assumptions).model_dump() == service.run(assumptions).model_dump()


def test_no_change_assumption_reports_unchanged() -> None:
    """변화 없음도 명시적으로 보고된다."""
    repo = _repo("open")
    result = WhatIfService(repo).run(
        [WhatIfAssumption(kind="issue_status", target_id="iss_x", value="open")]
    )
    assert result.changed_rows == []
    assert result.unchanged_scenario_count == 1
