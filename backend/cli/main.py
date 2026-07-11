"""CLI — 데이터 검증 및 온톨로지 점검 명령."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from backend.loaders.repository import InMemoryRepository, check_integrity

if TYPE_CHECKING:
    from backend.connectors.jira import JiraFieldMap
    from backend.ingest.service import IngestReport, IngestService
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

    _print_ingest_report(report, origin_note="origin=imported")
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


@app.command("sync-jira")
def sync_jira(
    payload: Path | None = typer.Option(
        None, "--payload", help="JIRA 응답 fixture JSON — 사외/dry-run 검증 경로"
    ),
    jql: str | None = typer.Option(
        None, "--jql", help="실 JIRA JQL (JIRA_BASE_URL/JIRA_API_TOKEN 환경변수 필요)"
    ),
    mapping_file: Path | None = typer.Option(
        None, "--mapping-file", help="필드 매핑 YAML (기본: backend/connectors/jira_field_map.yaml)"
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        help="증분 동기화 — ISO 시각 또는 'auto'(같은 소스의 마지막 완료 배치 시각). --jql와 결합",
    ),
    env_prefix: str = typer.Option(
        "", "--env-prefix", help="그룹별 JIRA 인스턴스 env 접두 (예: CAMERA_ → CAMERA_JIRA_BASE_URL)"
    ),
    execute: bool = typer.Option(
        False, "--execute", help="Postgres(DSN)로 실제 반입 — 기본은 dry-run(비영속 검증)"
    ),
    dsn: str | None = typer.Option(None, "--dsn", help="PostgreSQL DSN (--execute 시 필요)"),
) -> None:
    """JIRA 이슈를 ingest 배치로 동기화한다 — 커넥터는 저장하지 않고 ingest 경유만.

    upsert 의미론: 같은 JIRA 키 재동기화 시 내용이 다르면 교체, 같으면 건너뜀
    (14_ingest_reality_gaps.md §2 J2). 주기 실행은 --since auto 권장.
    """
    from backend.connectors.jira import ConnectorError, JiraFieldMap
    from backend.ingest.service import IngestService, MemoryIngestWriter

    try:
        field_map = JiraFieldMap.load(mapping_file)

        if execute:
            import os

            if not (dsn or os.environ.get("SOC_ONTOLOGY_DSN")):
                console.print("[red]--execute는 PostgreSQL DSN이 필요합니다 (in-memory 반입은 비영속)[/red]")
                raise typer.Exit(code=1)
            from backend.db.connection import get_connection
            from backend.ingest.service import PostgresIngestWriter

            with get_connection(dsn) as conn:
                service = IngestService(PostgresIngestWriter(conn))
                report = _run_jira_sync(
                    service, field_map, payload, jql, since, env_prefix
                )
        else:
            repo = InMemoryRepository.from_fixtures(DEFAULT_FIXTURES)
            service = IngestService(MemoryIngestWriter(repo))
            report = _run_jira_sync(service, field_map, payload, jql, since, env_prefix)
            console.print("[yellow]dry-run — 정규화·검증만 수행됨 (저장되지 않음)[/yellow]")
    except ConnectorError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _print_ingest_report(report, origin_note="origin=integrated")
    if report.rejected_rows:
        raise typer.Exit(code=1)


def _run_jira_sync(
    service: IngestService,
    field_map: JiraFieldMap,
    payload: Path | None,
    jql: str | None,
    since: str | None,
    env_prefix: str,
) -> IngestReport:
    from backend.connectors.jira import (
        ConnectorError,
        FakeJiraClient,
        JiraConnector,
        JiraHttpClient,
        incremental_jql,
    )

    since_iso: str | None = None
    if since == "auto":
        # 같은 소스의 마지막 완료 배치 시각 — 별도 상태 저장 없이 배치 이력에서 유도.
        for batch in service.list_batches():
            if (
                batch.filename == "jira-sync"
                and batch.mapping_name == field_map.issue_mapping
                and batch.status == "completed"
            ):
                since_iso = batch.created_at
                break
        if since_iso is None:
            console.print("[yellow]--since auto: 이전 동기화 이력 없음 — 전량 동기화[/yellow]")
    elif since:
        since_iso = since

    if payload is not None:
        if since_iso:
            console.print(
                "[yellow]--since는 fetch 측(JQL) 필터 — payload 경로에서는 upsert의 "
                "변동 없음 건너뛰기가 대신 동작합니다[/yellow]"
            )
        client: object = FakeJiraClient(payload)
    elif jql is not None:
        effective = incremental_jql(jql, since_iso)
        if effective != jql:
            console.print(f"증분 JQL: {effective}")
        client = JiraHttpClient(effective, env_prefix=env_prefix)
    else:
        raise ConnectorError("--payload 또는 --jql 중 하나가 필요합니다")
    return JiraConnector(client, field_map).sync(service)  # type: ignore[arg-type]


def _print_ingest_report(report: IngestReport, *, origin_note: str) -> None:
    batch = report.batch
    console.print(
        f"배치 {batch.id} (매핑 {batch.mapping_name}, {origin_note}): "
        f"신규 {batch.accepted_count}건 / 갱신 {batch.updated_count}건 / "
        f"변동 없음 {batch.unchanged_count}건 / 거부 {batch.rejected_count}건"
    )
    if report.quality is not None:
        quality = report.quality
        if quality.linkage_total:
            console.print(
                f"온톨로지 연결률: {quality.linkage_connected}/{quality.linkage_total}"
            )
        for line in quality.unlabeled_values:
            console.print(f"[yellow]라벨 미등재[/yellow] {line}")
        for line in quality.missing_ref_warnings:
            console.print(f"[yellow]참조 없음[/yellow] {line}")
    for rejected in report.rejected_rows:
        console.print(f"[red]{rejected.row_number}행[/red] {rejected.reason}")


@app.command("sync-confluence")
def sync_confluence(
    payload: Path = typer.Option(..., "--payload", help="Confluence 페이지 fixture JSON"),
    execute: bool = typer.Option(
        False, "--execute", help="Postgres(DSN)로 실제 반입 — 기본은 dry-run(비영속 검증)"
    ),
    dsn: str | None = typer.Option(None, "--dsn", help="PostgreSQL DSN (--execute 시 필요)"),
) -> None:
    """Confluence 페이지를 SemanticChunk 검색 후보로 동기화한다 (증거 아님 — §3)."""
    from backend.connectors.confluence import (
        ConfluenceConnector,
        ConfluenceError,
        FakeConfluenceClient,
    )
    from backend.ingest.service import IngestService, MemoryIngestWriter

    try:
        connector = ConfluenceConnector(FakeConfluenceClient(payload))
        if execute:
            import os

            if not (dsn or os.environ.get("SOC_ONTOLOGY_DSN")):
                console.print("[red]--execute는 PostgreSQL DSN이 필요합니다[/red]")
                raise typer.Exit(code=1)
            from backend.db.connection import get_connection
            from backend.ingest.service import PostgresIngestWriter

            with get_connection(dsn) as conn:
                report = connector.sync(IngestService(PostgresIngestWriter(conn)))
        else:
            repo = InMemoryRepository.from_fixtures(DEFAULT_FIXTURES)
            report = connector.sync(IngestService(MemoryIngestWriter(repo)))
            console.print("[yellow]dry-run — 정규화·검증만 수행됨 (저장되지 않음)[/yellow]")
    except ConfluenceError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"배치 {report.batch.id} (semantic_chunks, origin=integrated): "
        f"신규 {report.batch.accepted_count}건 / 갱신 {report.batch.updated_count}건 / "
        f"변동 없음 {report.batch.unchanged_count}건 / 거부 {report.batch.rejected_count}건"
    )
    for rejected in report.rejected_rows:
        console.print(f"[red]{rejected.row_number}행[/red] {rejected.reason}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
