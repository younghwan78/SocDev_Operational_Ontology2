"""모델 계약 테스트 — 확신도 정규화, 미지 필드 거부, 근거 문장 필수 필드."""

import pytest
from backend.ontology.common import Confidence, GroundedStatement
from backend.ontology.project import Project
from backend.ontology.scenario import ScenarioRequest
from pydantic import ValidationError


def test_confidence_normalizes_short_forms() -> None:
    """56 fixture의 H/M/L 축약 표기는 low/medium/high로 정규화된다."""
    assert Confidence("H") is Confidence.HIGH
    assert Confidence("M") is Confidence.MEDIUM
    assert Confidence("L") is Confidence.LOW
    assert Confidence("high") is Confidence.HIGH


def test_confidence_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        Confidence("very_high")


def test_extra_fields_rejected() -> None:
    """계약 외 필드는 거부한다 — 스키마 드리프트 차단."""
    with pytest.raises(ValidationError):
        Project.model_validate(
            {"id": "p", "name": "n", "type": "t", "phase": "ph", "unknown_field": 1}
        )


def test_grounded_statement_requires_basis_and_derivation() -> None:
    with pytest.raises(ValidationError):
        GroundedStatement.model_validate({"description": "근거 없는 주장", "confidence": "high"})


def test_scenario_request_confidence_from_fixture_form() -> None:
    minimal = {
        "id": "req_x",
        "title": "t",
        "request_type": "review",
        "status": "open",
        "priority": "P1",
        "confidence": "M",
        "origin_project_id": "project_u",
        "requested_by_role": "pm",
        "requested_week": 1,
        "review_cadence": "weekly",
        "management_interest": "none",
        "system_engineering_tracking_focus": "none",
        "expected_weekly_activity_load": "low",
    }
    request = ScenarioRequest.model_validate(minimal)
    assert request.confidence is Confidence.MEDIUM
