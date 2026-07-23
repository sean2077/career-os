from typing import Annotated

import typer

from career_os import __version__
from career_os.cli.core import check_command, doctor_command, init_command, paths_command
from career_os.cli.downstream import app as downstream_app
from career_os.cli.imports import app as import_app
from career_os.cli.migrate import app as migrate_app
from career_os.cli.release import app as release_app
from career_os.cli.resume import app as resume_app
from career_os.cli.skills import app as skills_app
from career_os.cli.vault import app as vault_app
from career_os.cli.views import app as views_app

app = typer.Typer(
    name="career-os",
    help="Maintain and validate a local Career OS installation.",
    no_args_is_help=True,
)
app.command("init")(init_command)
app.command("paths")(paths_command)
app.command("doctor")(doctor_command)
app.command("check")(check_command)
app.add_typer(downstream_app, name="downstream")
app.add_typer(import_app, name="import")
app.add_typer(migrate_app, name="migrate")
app.add_typer(release_app, name="release", hidden=True)
app.add_typer(resume_app, name="resume")
app.add_typer(skills_app, name="skills")
app.add_typer(views_app, name="views")
app.add_typer(vault_app, name="vault")


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the Career OS version.", is_eager=True),
    ] = False,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()
