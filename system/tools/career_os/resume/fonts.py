from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from career_os.config import ProjectPaths

FontRole = Literal["body-regular", "body-bold", "display-regular", "display-bold"]

_PROFILE_ID = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_SHA256 = r"^[0-9a-f]{64}$"


class FontAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    role: FontRole
    url: HttpUrl
    sha256: str = Field(pattern=_SHA256)
    size: int = Field(gt=0)


class FontPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._-]*$")
    version: str = Field(pattern=r"^[0-9]+(?:\.[0-9]+)*$")
    source: HttpUrl
    license: Literal["OFL-1.1"]
    license_path: str
    assets: list[FontAsset]

    @field_validator("license_path")
    @classmethod
    def validate_license_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if "\\" in value or path.is_absolute() or ".." in path.parts:
            raise ValueError("font license path must be a relative POSIX path")
        return value

    @model_validator(mode="after")
    def validate_assets(self) -> FontPackage:
        names = [asset.name for asset in self.assets]
        if not names or len(names) != len(set(names)):
            raise ValueError("font assets must be present and have unique names")
        return self


class FontManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2]
    bundle: str = Field(pattern=_PROFILE_ID)
    revision: int = Field(ge=1)
    packages: list[FontPackage]

    @model_validator(mode="after")
    def validate_packages(self) -> FontManifest:
        families = [package.family for package in self.packages]
        if not families or len(families) != len(set(families)):
            raise ValueError("font packages must be present and have unique families")
        assets = [asset for package in self.packages for asset in package.assets]
        names = [asset.name for asset in assets]
        roles = [asset.role for asset in assets]
        if len(names) != len(set(names)):
            raise ValueError("font asset names must be unique across packages")
        expected_roles = {
            "body-regular",
            "body-bold",
            "display-regular",
            "display-bold",
        }
        if set(roles) != expected_roles or len(roles) != len(expected_roles):
            raise ValueError("font bundle must define each resume font role exactly once")
        return self

    def iter_assets(self) -> list[tuple[FontPackage, FontAsset]]:
        return [(package, asset) for package in self.packages for asset in package.assets]

    def names_by_role(self) -> dict[FontRole, str]:
        return {asset.role: asset.name for _package, asset in self.iter_assets()}


@dataclass(frozen=True)
class FontStatus:
    family: str
    version: str
    name: str
    status: str
    path: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def font_manifest_json_schema() -> dict[str, object]:
    schema = FontManifest.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://career-os.dev/schemas/font-manifest.schema.json"
    schema["title"] = "Career OS System Font Manifest"
    return schema


def load_font_manifest(project_root: Path) -> FontManifest:
    path = project_root / "system/resume/fonts.json"
    return FontManifest.model_validate_json(path.read_text(encoding="utf-8"))


def font_install_root(paths: ProjectPaths, manifest: FontManifest | None = None) -> Path:
    selected = manifest or load_font_manifest(paths.project_root)
    return paths.local_state_root / "fonts" / f"{selected.bundle}-{selected.revision}"


def font_names_by_role(paths: ProjectPaths) -> dict[FontRole, str]:
    return load_font_manifest(paths.project_root).names_by_role()


def verify_fonts(paths: ProjectPaths) -> list[FontStatus]:
    manifest = load_font_manifest(paths.project_root)
    root = font_install_root(paths, manifest)
    if root.is_symlink():
        return [
            FontStatus(
                manifest.bundle,
                str(manifest.revision),
                "install-root",
                "fail",
                str(root),
                "default font root must not be a symlink",
            )
        ]
    return [
        _verify_font_asset(
            root / asset.name,
            family=package.family,
            version=package.version,
            name=asset.name,
            expected_size=asset.size,
            expected_sha256=asset.sha256,
        )
        for package, asset in manifest.iter_assets()
    ]


def fetch_fonts(paths: ProjectPaths) -> list[FontStatus]:
    manifest = load_font_manifest(paths.project_root)
    root = font_install_root(paths, manifest)
    if root.is_symlink() or root.parent.is_symlink():
        raise ValueError("default font install path must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    for _package, asset in manifest.iter_assets():
        target = root / asset.name
        if target.exists():
            status = next(item for item in verify_fonts(paths) if item.name == asset.name)
            if status.status != "pass":
                raise ValueError(
                    f"refusing to overwrite unverified font file: {target} ({status.detail})"
                )
            continue
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{asset.name}.",
                suffix=".part",
                dir=root,
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                with urllib.request.urlopen(str(asset.url), timeout=60) as response:
                    while chunk := response.read(1024 * 1024):
                        handle.write(chunk)
            size = temporary.stat().st_size
            digest = _sha256_file(temporary)
            if size != asset.size or digest != asset.sha256:
                raise ValueError(
                    f"download verification failed for {asset.name}: size={size}, sha256={digest}"
                )
            created = False
            try:
                with target.open("xb") as destination, temporary.open("rb") as source:
                    created = True
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
            except OSError:
                if created:
                    target.unlink(missing_ok=True)
                raise
            temporary.unlink()
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    statuses = verify_fonts(paths)
    if any(item.status != "pass" for item in statuses):
        raise ValueError("font installation did not pass verification")
    (root / "install.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "bundle": manifest.bundle,
                "revision": manifest.revision,
                "packages": [
                    {
                        "family": package.family,
                        "version": package.version,
                        "source": str(package.source),
                        "license": package.license,
                    }
                    for package in manifest.packages
                ],
                "assets": [item.as_dict() for item in statuses],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return statuses


def _verify_font_asset(
    path: Path,
    *,
    family: str,
    version: str,
    name: str,
    expected_size: int,
    expected_sha256: str,
) -> FontStatus:
    if not path.is_file():
        return FontStatus(family, version, name, "fail", str(path), "missing")
    size = path.stat().st_size
    digest = _sha256_file(path)
    if size != expected_size:
        detail = f"size {size}; expected {expected_size}"
        status = "fail"
    elif digest != expected_sha256:
        detail = f"sha256 {digest}; checksum mismatch"
        status = "fail"
    else:
        detail = digest
        status = "pass"
    return FontStatus(family, version, name, status, str(path), detail)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
