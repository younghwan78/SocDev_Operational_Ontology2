"""JSON Schema 자동 export — Pydantic 모델(단일 소스)에서 생성한다.

schemas/*.schema.json은 생성물이므로 손으로 편집하지 않는다.
드리프트는 테스트(test_schema_export)로 차단한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from backend.ontology import COLLECTIONS, RUNTIME_CONTRACTS

GENERATED_NOTE = (
    "GENERATED FILE — backend/ontology 모델에서 자동 생성됨. 직접 편집 금지. "
    "재생성: uv run python -m backend.ontology.schema_export"
)


def export_targets() -> dict[str, type[BaseModel]]:
    """export할 스키마 이름 → 모델 매핑."""
    targets: dict[str, type[BaseModel]] = {}
    for collection_key, (_, model) in COLLECTIONS.items():
        targets[collection_key] = model
    targets.update(RUNTIME_CONTRACTS)
    return targets


def render_schema(model: type[BaseModel]) -> str:
    """모델 하나의 JSON Schema를 결정론적 문자열로 렌더링한다."""
    schema = model.model_json_schema()
    schema["$comment"] = GENERATED_NOTE
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def export_schemas(out_dir: Path) -> list[Path]:
    """모든 스키마를 out_dir에 기록하고 생성 파일 목록을 반환한다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in export_targets().items():
        path = out_dir / f"{name}.schema.json"
        path.write_text(render_schema(model), encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    written = export_schemas(root / "schemas")
    for path in written:
        print(f"generated {path.relative_to(root)}")


if __name__ == "__main__":
    main()
