from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_installation_contract_separates_core_obsidian_and_resume_readiness() -> None:
    text = REPOSITORY_ROOT.joinpath("docs/installation.md").read_text(encoding="utf-8")

    required_contracts = (
        "Python 3.12",
        "uv sync --locked",
        "Obsidian 1.12.7",
        "latexmk",
        "xelatex",
        "Source Han Serif SC",
        "Noto Sans CJK SC",
        "career-os-resume-fonts-1",
        ".career-os/fonts/",
        "fresh offline clone",
        "career-os resume doctor",
    )
    assert all(contract in text for contract in required_contracts)


def test_recommended_installation_links_requirements_and_resume_bootstrap() -> None:
    readme = REPOSITORY_ROOT.joinpath("README.md").read_text(encoding="utf-8")

    assert "docs/installation.md" in readme
    assert "career-os resume fonts fetch" in readme
    assert "career-os resume doctor --json" in readme


def test_opencli_installation_is_optional_local_and_read_only() -> None:
    text = " ".join(
        REPOSITORY_ROOT.joinpath("docs/installation.md")
        .read_text(encoding="utf-8")
        .split()
    )

    required_contracts = (
        "OpenCLI is an optional acquisition transport",
        "npm install -g @jackwener/opencli@latest",
        "career-research",
        "access: read",
        "loopback-only",
        "never starts the daemon",
    )
    assert all(contract in text for contract in required_contracts)
