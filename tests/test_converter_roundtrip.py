"""변환 회귀 테스트 — 56 원본이 있으면 재변환 결과가 배포 fixture와 일치해야 한다."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_56 = Path(r"E:\56_Codex_SoC_Operational_Ontology\synthetic_data")

sys.path.insert(0, str(ROOT))


@pytest.mark.skipif(not SOURCE_56.exists(), reason="56 참조 디렉토리 없음")
def test_conversion_matches_shipped_fixtures(tmp_path: Path) -> None:
    from tools.convert_56_fixtures import convert

    assert convert(SOURCE_56, tmp_path) == 0
    shipped_dir = ROOT / "fixtures"
    generated = sorted(p.name for p in tmp_path.glob("*.yaml"))
    shipped = sorted(p.name for p in shipped_dir.glob("*.yaml"))
    assert generated == shipped
    for name in generated:
        assert (tmp_path / name).read_text(encoding="utf-8") == (
            shipped_dir / name
        ).read_text(encoding="utf-8"), f"{name} 불일치 — 변환 스크립트 재실행 필요"
