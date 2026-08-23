import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return REPOSITORY_ROOT.joinpath(relative_path).read_text(encoding="utf-8")


def test_installation_contract_uses_machine_owned_version_authorities() -> None:
    installation = _read("docs/installation.md")
    project_config = tomllib.loads(_read("career-os.toml"))
    pyproject = tomllib.loads(_read("pyproject.toml"))

    required_contracts = (
        "Python 3.12",
        "uv sync --locked",
        "career-os.toml",
        "pyproject.toml",
        "latexmk",
        "xelatex",
        "system/resume/fonts.json",
        "fresh offline clone",
        "career-os resume doctor",
    )

    assert all(contract in installation for contract in required_contracts)
    assert project_config["system_version"] == pyproject["project"]["version"]
    assert project_config["obsidian"]["minimum_version"] not in installation
    assert project_config["obsidian"]["quickadd_version"] not in installation


def test_readme_routes_setup_without_repeating_volatile_procedures() -> None:
    readme = _read("README.md")
    version = tomllib.loads(_read("pyproject.toml"))["project"]["version"]

    required_routes = (
        "docs/installation.md",
        "docs/private-downstream.md",
        "docs/embedded-vault.md",
        "docs/releases/README.md",
        "CONTRIBUTING.md",
    )

    assert all(route in readme for route in required_routes)
    assert f"v{version}" not in readme
    assert "git clone " not in readme
    assert "uv run " not in readme
    assert "git remote set-url --push upstream DISABLED" not in readme
    assert "career-os resume fonts fetch" not in readme


def test_current_docs_keep_downstream_vault_and_release_authorities_separate() -> None:
    downstream = _read("docs/private-downstream.md")
    embedded = _read("docs/embedded-vault.md")
    release_index = _read("docs/releases/README.md")

    assert "ln -s ../../career-home" not in downstream
    assert "vault plan --action attach" not in downstream
    assert "ln -s ../../career-home" in embedded
    assert "vault plan --action attach" in embedded
    assert "uv run career-os" not in release_index
    assert "git clone " not in release_index


def test_record_relation_names_match_current_contract() -> None:
    resume = _read("docs/resume.md")
    communication_seed = _read("system/seeds/authorities/70-career-communication.md")

    assert all(name in resume for name in ("uses_claim", "target_jd", "identity_profile"))
    assert all(name not in resume for name in ("uses-claim", "targets-jd", "uses-identity"))
    assert "uses_claim" in communication_seed
    assert "uses-claim" not in communication_seed


def test_maintainer_commands_have_one_documentation_authority() -> None:
    tooling = _read("docs/tooling.md")
    entry_points = "\n".join((_read("README.md"), _read("CONTRIBUTING.md"), _read("AGENTS.md")))

    assert "uv run career-os check --fast" in tooling
    assert "uv run pytest" in tooling
    assert "uv run career-os check --fast" not in entry_points
    assert "uv run pytest" not in entry_points
    assert entry_points.count("docs/tooling.md") >= 2
