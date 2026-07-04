"""fixture YAML 로더 — fixtures/*.yaml을 온톨로지 모델로 검증 적재한다."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from backend.ontology import COLLECTIONS, OntologyObject


class FixtureLoadError(Exception):
    """fixture 적재 실패 — 파일/컬렉션/레코드 위치를 포함한 메시지."""


def fixture_files() -> dict[str, list[str]]:
    """모듈 파일명 → 그 파일이 담는 컬렉션 키 목록."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for collection_key, (module_name, _) in COLLECTIONS.items():
        grouped[module_name].append(collection_key)
    return dict(grouped)


def load_fixtures(fixtures_dir: Path) -> dict[str, list[OntologyObject]]:
    """fixtures 디렉토리 전체를 적재해 컬렉션 키 → 모델 리스트로 반환한다."""
    loaded: dict[str, list[OntologyObject]] = {}
    errors: list[str] = []

    for module_name, collection_keys in fixture_files().items():
        path = fixtures_dir / f"{module_name}.yaml"
        if not path.exists():
            errors.append(f"{path.name}: 파일 없음")
            continue
        try:
            data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            errors.append(f"{path.name}: YAML 파싱 실패 — {exc}")
            continue

        unknown = set(data.keys()) - set(collection_keys)
        if unknown:
            errors.append(f"{path.name}: 알 수 없는 컬렉션 {sorted(unknown)}")

        for key in collection_keys:
            model = COLLECTIONS[key][1]
            records = data.get(key, [])
            items: list[OntologyObject] = []
            for index, record in enumerate(records):
                try:
                    items.append(model.model_validate(record))
                except ValidationError as exc:
                    record_id = record.get("id", f"index={index}") if isinstance(record, dict) else f"index={index}"
                    errors.append(f"{path.name}::{key}[{record_id}]: {exc}")
            loaded[key] = items

    if errors:
        raise FixtureLoadError("\n".join(errors))
    return loaded
