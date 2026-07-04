"""버전드 SQL 마이그레이션 경량 러너."""

from __future__ import annotations

from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def migration_files(migrations_dir: Path = MIGRATIONS_DIR) -> list[Path]:
    """버전 순 정렬된 마이그레이션 파일 목록 (NNNN_name.sql)."""
    files = sorted(migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    versions = [int(f.name[:4]) for f in files]
    if len(versions) != len(set(versions)):
        raise ValueError("마이그레이션 버전 번호가 중복됩니다.")
    return files


def applied_versions(conn: psycopg.Connection) -> set[int]:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    integer     NOT NULL PRIMARY KEY,
            name       text        NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row[0] for row in rows}


def run_migrations(conn: psycopg.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """미적용 마이그레이션을 순서대로 적용하고 적용 파일명 목록을 반환한다."""
    done = applied_versions(conn)
    applied: list[str] = []
    for path in migration_files(migrations_dir):
        version = int(path.name[:4])
        if version in done:
            continue
        conn.execute(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
            (version, path.name),
        )
        applied.append(path.name)
    return applied
