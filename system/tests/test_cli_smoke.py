from career_os.cli import app
from typer.testing import CliRunner


def test_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_root_help() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Maintain and validate a local Career OS installation" in result.stdout
    assert "import" in result.stdout


def test_import_help() -> None:
    result = CliRunner().invoke(app, ["import", "--help"])

    assert result.exit_code == 0
    assert "hash-bound legacy imports" in result.stdout
    assert all(command in result.stdout for command in ("plan", "apply", "verify", "rollback"))
    assert "verify-review" not in result.stdout
    assert "inventory" not in result.stdout


def test_migrate_help() -> None:
    result = CliRunner().invoke(app, ["migrate", "--help"])

    assert result.exit_code == 0
    assert all(command in result.stdout for command in ("plan", "apply", "verify", "rollback"))


def test_reviewer_validator_help_is_available() -> None:
    result = CliRunner().invoke(app, ["skills", "validate-reviewer", "--help"])

    assert result.exit_code == 0
    assert "CONTRACT" in result.stdout
    assert "PATH" in result.stdout


def test_downstream_sync_commands_are_discoverable() -> None:
    result = CliRunner().invoke(app, ["downstream", "--help"])

    assert result.exit_code == 0
    assert "plan" in result.stdout
    assert "apply" in result.stdout
    assert "rollback" in result.stdout
    assert "validate" in result.stdout


def test_resume_font_commands_are_discoverable() -> None:
    result = CliRunner().invoke(app, ["resume", "fonts", "--help"])

    assert result.exit_code == 0
    assert "fetch" in result.stdout
    assert "verify" in result.stdout
    assert CliRunner().invoke(app, ["resume", "fonts", "import", "--help"]).exit_code != 0
    assert CliRunner().invoke(app, ["resume", "fonts", "verify", "--help"]).exit_code == 0


def test_resume_doctor_needs_no_manifest_selection() -> None:
    result = CliRunner().invoke(
        app,
        ["resume", "doctor", "--help"],
        env={"NO_COLOR": "1", "FORCE_COLOR": None},
    )

    assert result.exit_code == 0
    assert "--manifest" not in result.stdout
