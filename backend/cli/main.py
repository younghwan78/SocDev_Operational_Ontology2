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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
