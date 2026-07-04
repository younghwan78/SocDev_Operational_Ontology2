"""JSON Schema 드리프트 테스트 — 커밋된 스키마와 모델 재생성 결과가 일치해야 한다."""

from pathlib import Path

from backend.ontology.schema_export import export_targets, render_schema

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def test_committed_schemas_match_models() -> None:
    """schemas/*.schema.json은 모델에서 재생성해도 diff가 없어야 한다."""
    drifted: list[str] = []
    for name, model in export_targets().items():
        path = SCHEMAS / f"{name}.schema.json"
        if not path.exists():
            drifted.append(f"{path.name}: 파일 없음 — schema_export 실행 필요")
            continue
        if path.read_text(encoding="utf-8") != render_schema(model):
            drifted.append(f"{path.name}: 모델과 불일치 — schema_export 재실행 필요")
    assert drifted == [], "\n".join(drifted)


def test_no_orphan_schema_files() -> None:
    """모델 없는 고아 스키마 파일이 없어야 한다."""
    expected = {f"{name}.schema.json" for name in export_targets()}
    actual = {p.name for p in SCHEMAS.glob("*.schema.json")}
    assert actual == expected
