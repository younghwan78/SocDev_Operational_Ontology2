"""openapi.json 드리프트 테스트 — 커밋본과 재생성본이 일치해야 한다."""

from pathlib import Path

from backend.api.openapi_export import render_openapi

ROOT = Path(__file__).resolve().parents[1]


def test_committed_openapi_matches_app() -> None:
    committed = ROOT / "openapi.json"
    assert committed.exists(), "openapi.json 없음 — openapi_export 실행 필요"
    assert committed.read_text(encoding="utf-8") == render_openapi(), (
        "openapi.json 드리프트 — uv run python -m backend.api.openapi_export 재실행 필요"
    )
