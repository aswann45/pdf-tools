"""Entrypoint for CLI application."""

from pdf_tools.cli import AsyncTyper
from pdf_tools.convert.cli import cli as convert_cli
from pdf_tools.merge.cli import cli as merge_cli
from pdf_tools.process.cli import cli as process_cli
from pdf_tools.watermark.cli import cli as watermark_cli

app = AsyncTyper(no_args_is_help=True)

app.add_typer(convert_cli, name="convert", no_args_is_help=True)
app.add_typer(merge_cli, name="merge", no_args_is_help=True)
app.add_typer(process_cli, name="process", no_args_is_help=True)
app.add_typer(watermark_cli, name="watermark", no_args_is_help=True)

if __name__ == "__main__":
    app()
