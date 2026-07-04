"""openapi.json export — frontend 타입 생성(openapi-typescript)의 소스.

재생성: uv run python -m backend.api.openapi_export
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.api.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def render_openapi() -> str:
    app = create_app()
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    out = ROOT / "openapi.json"
    out.write_text(render_openapi(), encoding="utf-8", newline="\n")
    print(f"generated {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
