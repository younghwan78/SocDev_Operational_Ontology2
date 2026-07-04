"""CLI — 데이터 검증 및 온톨로지 점검 명령."""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from backend.loaders.repository import InMemoryRepository, check_integrity
from backend.loaders.yaml_loader import FixtureLoadError
from backend.ontology import COLLECTIONS, RUNTIME_CONTRACTS
from backend.ontology.glossary import find_missing_labels, object_label

app = typer.Typer(no_args_is_help=True, help="SoC 운영 온톨로지 CLI")
console = Console()


@app.callback()
def cli() -> None:
    """SoC 운영 온톨로지 CLI."""

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = ROOT / "fixtures"


@app.command("validate-data")
def validate_data(
    fixtures_dir: Path = typer.Option(DEFAULT_FIXTURES, "--fixtures-dir", help="fixture 디렉토리"),
) -> None:
    """fixture 적재 + 모델 검증 + 참조 무결성 + glossary 커버리지를 검사한다."""
    try:
        repo = InMemoryRepository.from_fixtures(fixtures_dir)
    except FixtureLoadError as exc:
        console.print("[red]fixture 적재 실패[/red]")
        console.print(str(exc))
        raise typer.Exit(code=1) from exc

    table = Table(title="적재된 온톨로지 컬렉션")
    table.add_column("컬렉션")
    table.add_column("객체 유형")
    table.add_column("건수", justify="right")
    for key, (_, model) in COLLECTIONS.items():
        table.add_row(key, object_label(model.__name__) or model.__name__, str(len(repo.list(key))))
    console.print(table)

    findings = check_integrity(repo)
    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]

    for finding in errors:
        console.print(f"[red]오류[/red] {finding.message}")
    for finding in warnings:
        console.print(f"[yellow]경고[/yellow] {finding.message}")

    models: list[type[BaseModel]] = [model for _, model in COLLECTIONS.values()]
    models += list(RUNTIME_CONTRACTS.values())
    missing_labels = find_missing_labels(models)
    for item in missing_labels:
        console.print(f"[red]glossary 누락[/red] {item}")

    console.print(
        f"검증 결과: 오류 {len(errors)}건 / 경고 {len(warnings)}건 / glossary 누락 {len(missing_labels)}건"
    )
    if errors or missing_labels:
        raise typer.Exit(code=1)


@app.command("db-init")
def db_init(
    dsn: str | None = typer.Option(None, "--dsn", help="PostgreSQL DSN (기본: SOC_ONTOLOGY_DSN)"),
) -> None:
    """마이그레이션을 적용해 DB 스키마를 초기화한다."""
    from backend.db.connection import get_connection
    from backend.db.migrate import run_migrations

    with get_connection(dsn) as conn:
        applied = run_migrations(conn)
    if applied:
        for name in applied:
            console.print(f"적용: {name}")
    else:
        console.print("적용할 마이그레이션 없음 — 스키마 최신 상태")


@app.command("db-seed")
def db_seed(
    dsn: str | None = typer.Option(None, "--dsn", help="PostgreSQL DSN (기본: SOC_ONTOLOGY_DSN)"),
    fixtures_dir: Path = typer.Option(DEFAULT_FIXTURES, "--fixtures-dir"),
) -> None:
    """fixture 전량을 DB에 반입한다 (멱등)."""
    from backend.db.connection import get_connection
    from backend.ingest.yaml_seed import seed_fixtures

    with get_connection(dsn) as conn:
        counts = seed_fixtures(conn, fixtures_dir)
    total = sum(counts.values())
    console.print(f"반입 완료: {len(counts)}개 컬렉션, {total}건")


@app.command("db-check")
def db_check(
    dsn: str | None = typer.Option(None, "--dsn", help="PostgreSQL DSN (기본: SOC_ONTOLOGY_DSN)"),
) -> None:
    """DB 상태 점검 — 마이그레이션 버전과 컬렉션별 건수."""
    from backend.db.connection import get_connection
    from backend.db.migrate import applied_versions
    from backend.db.repository import PostgresRepository

    with get_connection(dsn) as conn:
        versions = sorted(applied_versions(conn))
        counts = PostgresRepository(conn).counts()

    console.print(f"적용된 마이그레이션: {versions or '없음'}")
    table = Table(title="DB 컬렉션 건수")
    table.add_column("컬렉션")
    table.add_column("건수", justify="right")
    for key in COLLECTIONS:
        table.add_row(key, str(counts.get(key, 0)))
    console.print(table)


@app.command("ingest-file")
def ingest_file(
    file: Path = typer.Option(..., "--file", help="CSV/XLSX 파일 경로"),
    mapping: str = typer.Option(..., "--mapping", help="매핑 이름"),
    dsn: str | None = typer.Option(None, "--dsn", help="PostgreSQL DSN (미지정 시 메모리 — 검증 전용)"),
) -> None:
    """실데이터 파일을 반입한다. DSN 미지정 시 검증만 수행된다(비영속)."""
    from backend.ingest.service import IngestService, MemoryIngestWriter
    from backend.loaders.repository import InMemoryRepository

    if dsn or __import__("os").environ.get("SOC_ONTOLOGY_DSN"):
        from backend.db.connection import get_connection
        from backend.ingest.service import PostgresIngestWriter

        with get_connection(dsn) as conn:
            service = IngestService(PostgresIngestWriter(conn))
            report = service.ingest(file.name, file.read_bytes(), mapping)
    else:
        repo = InMemoryRepository.from_fixtures(DEFAULT_FIXTURES)
        service = IngestService(MemoryIngestWriter(repo))
        report = service.ingest(file.name, file.read_bytes(), mapping)
        console.print("[yellow]DSN 미지정 — 검증만 수행됨 (저장되지 않음)[/yellow]")

    console.print(
        f"배치 {report.batch.id}: 수용 {report.batch.accepted_count}건 / "
        f"거부 {report.batch.rejected_count}건"
    )
    for rejected in report.rejected_rows:
        console.print(f"[red]{rejected.row_number}행[/red] {rejected.reason}")
    if report.rejected_rows:
        raise typer.Exit(code=1)


@app.command("ingest-rollback")
def ingest_rollback(
    batch_id: str = typer.Option(..., "--batch-id", help="롤백할 배치 ID"),
    dsn: str | None = typer.Option(None, "--dsn", help="PostgreSQL DSN"),
) -> None:
    """반입 배치를 롤백한다 — 허용되는 유일한 삭제 경로."""
    from backend.db.connection import get_connection
    from backend.ingest.service import IngestService, PostgresIngestWriter

    with get_connection(dsn) as conn:
        removed = IngestService(PostgresIngestWriter(conn)).rollback(batch_id)
    console.print(f"롤백 완료: {removed}건 제거")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
