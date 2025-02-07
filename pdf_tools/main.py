from pdf_tools.cli import AsyncTyper
from pdf_tools.convert.cli import cli as convert_cli
from pdf_tools.merge.cli import cli as merge_cli

app = AsyncTyper(no_args_is_help=True)

app.add_typer(convert_cli, name="convert", no_args_is_help=True)
app.add_typer(merge_cli, name="merge", no_args_is_help=True)

if __name__ == "__main__":
    app()
