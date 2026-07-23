from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import typer
from career_os.checks import CheckIssue
from career_os.cli import app
from career_os.cli.core import (
    _obsidian_doctor_checks,
    _parse_version,
    _version_at_least,
    init_command,
)
from career_os.config import load_project_config, normalize_vault_mount
from pydantic import ValidationError
from typer.testing import CliRunner


def _write_config(root: Path) -> None:
    root.joinpath("career-os.toml").write_text(
        """schema_version = 1
system_version = "0.1.0-rc.1"
data_root = "career"
runtime_root = "runtime"
build_root = "build"
preferred_language = "en"

[obsidian]
minimum_version = "1.12.7"
quickadd_version = "2.12.3"

[resume]
engine = "xelatex"
""",
        encoding="utf-8",
    )
    source_seeds = Path(__file__).resolve().parents[1] / "seeds"
    shutil.copytree(source_seeds, root / "system/seeds")
    source_bases = Path(__file__).resolve().parents[1] / "obsidian/bases"
    shutil.copytree(source_bases, root / "system/obsidian/bases")


def test_init_is_idempotent_and_multilingual(tmp_path: Path) -> None:
    _write_config(tmp_path)
    repository_root = Path(__file__).resolve().parents[2]
    framework_homes = [tmp_path / "Home.md", tmp_path / "主页.md"]
    for framework_home in framework_homes:
        shutil.copy2(repository_root / framework_home.name, framework_home)
    framework_homes_before = {
        path.name: path.read_bytes() for path in framework_homes
    }
    base_root = tmp_path / "system/obsidian/bases"
    bases_before = {
        path.relative_to(base_root): path.read_bytes()
        for path in sorted(base_root.rglob("*.base"))
    }
    runner = CliRunner()

    first = runner.invoke(
        app,
        ["init", "--mode", "standalone", "--root", str(tmp_path), "--languages", "en,zh-CN"],
    )
    home = tmp_path / "career/README.md"
    assert home.is_file()
    assert home.read_text(encoding="utf-8") == tmp_path.joinpath(
        "system/seeds/data-root-readme.md"
    ).read_text(encoding="utf-8")
    home.write_text("# My Career Home\n", encoding="utf-8")
    second = runner.invoke(
        app,
        ["init", "--mode", "standalone", "--root", str(tmp_path), "--languages", "en,zh-CN"],
    )

    assert first.exit_code == 0, first.stdout
    assert second.exit_code == 0, second.stdout
    payload = json.loads(second.stdout)
    assert payload["created"] == []
    assert home.read_text(encoding="utf-8") == "# My Career Home\n"
    assert {path.name: path.read_bytes() for path in framework_homes} == (
        framework_homes_before
    )
    assert {
        path.relative_to(base_root): path.read_bytes()
        for path in sorted(base_root.rglob("*.base"))
    } == bases_before
    assert (tmp_path / "career/10-career-evidence/README.md").is_file()
    assert not any(tmp_path.joinpath("career").rglob("*.base"))


def test_removed_resume_template_selector_is_rejected(tmp_path: Path) -> None:
    _write_config(tmp_path)
    config = tmp_path / "career-os.toml"
    config.write_text(
        config.read_text(encoding="utf-8") + 'template = "single-column"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="template"):
        load_project_config(tmp_path)


def test_init_does_not_materialize_the_system_owned_root_homepage(tmp_path: Path) -> None:
    _write_config(tmp_path)
    result = CliRunner().invoke(
        app,
        ["init", "--mode", "standalone", "--root", str(tmp_path), "--languages", "en"],
    )

    assert result.exit_code == 0, result.stdout
    assert not (tmp_path / "Home.md").exists()
    assert not (tmp_path / "主页.md").exists()


def test_init_supports_external_project_through_relative_vault_mount(
    tmp_path: Path,
) -> None:
    project = tmp_path / "career-home"
    vault = tmp_path / "vault"
    project.mkdir()
    vault.mkdir()
    _write_config(project)
    homepage = project / "Home.md"
    shutil.copy2(Path(__file__).resolve().parents[2] / "Home.md", homepage)
    homepage_before = homepage.read_bytes()
    mount = vault / "career-home"
    try:
        mount.symlink_to("../career-home", target_is_directory=True)
    except OSError as error:
        pytest.skip(f"local platform does not permit directory symlinks: {error}")

    arguments = [
        "init",
        "--mode",
        "embedded",
        "--root",
        str(project),
        "--vault-root",
        str(vault),
        "--vault-mount",
        "career-home",
        "--languages",
        "en,zh-CN",
    ]
    result = CliRunner().invoke(
        app,
        arguments,
    )
    repeated = CliRunner().invoke(app, arguments)

    assert result.exit_code == 0, result.stdout
    assert repeated.exit_code == 0, repeated.stdout
    payload = json.loads(result.stdout)
    assert payload["vault_mount"] == "career-home"
    assert json.loads(repeated.stdout)["created"] == []
    assert homepage.read_bytes() == homepage_before
    paths = CliRunner().invoke(app, ["paths", "--json", "--root", str(project)])
    assert paths.exit_code == 0, paths.stdout
    assert Path(json.loads(paths.stdout)["vault_mount_root"]) == mount
    assert not any(project.joinpath("career").rglob("*.base"))


def test_init_preserves_homepage_with_custom_external_data_root(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    project = vault / "career-home"
    data_root = vault / "private-career"
    project.mkdir(parents=True)
    _write_config(project)
    homepage = project / "Home.md"
    shutil.copy2(Path(__file__).resolve().parents[2] / "Home.md", homepage)
    homepage_before = homepage.read_bytes()
    arguments = [
        "init",
        "--mode",
        "embedded",
        "--root",
        str(project),
        "--vault-root",
        str(vault),
        "--data-root",
        str(data_root),
        "--languages",
        "en,zh-CN",
    ]

    first = CliRunner().invoke(app, arguments)
    second = CliRunner().invoke(app, arguments)

    assert first.exit_code == 0, first.stdout
    assert second.exit_code == 0, second.stdout
    assert json.loads(second.stdout)["created"] == []
    assert homepage.read_bytes() == homepage_before
    assert (data_root / "README.md").is_file()
    assert not any(data_root.rglob("*.base"))


def test_init_rejects_external_project_without_vault_mount(tmp_path: Path) -> None:
    project = tmp_path / "career-home"
    vault = tmp_path / "vault"
    project.mkdir()
    vault.mkdir()
    _write_config(project)

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--mode",
            "embedded",
            "--root",
            str(project),
            "--vault-root",
            str(vault),
        ],
    )

    assert result.exit_code == 2
    with pytest.raises(typer.BadParameter, match="requires --vault-mount"):
        init_command(mode="embedded", root=project, vault_root=vault)


@pytest.mark.parametrize("value", ["", "../career-home", "/career-home", "C:/career-home", "a\\b"])
def test_vault_mount_rejects_nonportable_paths(value: str) -> None:
    with pytest.raises(ValueError, match="vault_mount"):
        normalize_vault_mount(value)


def test_paths_reports_resolved_roots(tmp_path: Path) -> None:
    _write_config(tmp_path)
    result = CliRunner().invoke(app, ["paths", "--root", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert Path(payload["data_root"]) == tmp_path / "career"


def test_paths_accepts_explicit_json_interface(tmp_path: Path) -> None:
    _write_config(tmp_path)
    result = CliRunner().invoke(app, ["paths", "--json", "--root", str(tmp_path)])

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["ok"] is True


@pytest.mark.parametrize("json_output", [False, True])
def test_check_reports_nonfatal_attention_without_claiming_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, json_output: bool
) -> None:
    monkeypatch.setattr("career_os.cli.core.resolve_paths", lambda _root: object())
    monkeypatch.setattr(
        "career_os.cli.core.run_checks",
        lambda _paths, *, fast, host: [
            CheckIssue(
                "records.semantic",
                "attention",
                "career/example.md",
                "source-migrated record requires a human semantic review",
            )
        ],
    )
    args = ["check", "--root", str(tmp_path)]
    if json_output:
        args.append("--json")

    result = CliRunner().invoke(app, args)

    assert result.exit_code == 0, result.stdout
    if json_output:
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["status"] == "attention"
    else:
        assert result.stdout.endswith("Career OS check: ATTENTION\n")


def test_obsidian_version_parsing_and_minimum() -> None:
    assert _parse_version("Obsidian 1.12.7") == "1.12.7"
    assert _parse_version("no version") is None
    assert _version_at_least("1.12.7", "1.12.7")
    assert _version_at_least("1.13.0", "1.12.7")
    assert not _version_at_least("1.12.6", "1.12.7")


def test_obsidian_doctor_does_not_launch_a_stopped_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path)
    monkeypatch.setattr("career_os.cli.core.shutil.which", lambda _name: "obsidian")
    monkeypatch.setattr("career_os.cli.core._obsidian_process_running", lambda: False)

    def unexpected_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("doctor must not invoke the CLI when Obsidian is stopped")

    monkeypatch.setattr("career_os.cli.core.subprocess.run", unexpected_run)

    checks = _obsidian_doctor_checks(tmp_path)

    assert {item["id"] for item in checks} == {
        "obsidian.cli-registration",
        "obsidian.app-running",
        "obsidian.version",
    }
    assert all(item["status"] in {"pass", "attention"} for item in checks)


def test_obsidian_doctor_checks_enabled_cli_and_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path)
    monkeypatch.setattr("career_os.cli.core.shutil.which", lambda _name: "obsidian")
    monkeypatch.setattr("career_os.cli.core._obsidian_process_running", lambda: True)
    monkeypatch.setattr(
        "career_os.cli.core.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["obsidian", "version"], 0, stdout="Obsidian 1.12.7\n", stderr=""
        ),
    )

    checks = _obsidian_doctor_checks(tmp_path)

    assert next(item for item in checks if item["id"] == "obsidian.cli-enabled")[
        "status"
    ] == "pass"
    assert next(item for item in checks if item["id"] == "obsidian.version")["status"] == "pass"
