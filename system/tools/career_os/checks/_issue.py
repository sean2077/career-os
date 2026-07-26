from __future__ import annotations

from dataclasses import asdict, dataclass

from pydantic import ValidationError


@dataclass(frozen=True)
class CheckIssue:
    id: str
    status: str
    path: str | None
    detail: str

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


def _issue_detail(error: Exception) -> str:
    """Render one exception as a compact check detail.

    A record envelope is a tagged union over every kind, so Pydantic titles its
    error with all member models and buries the real message under thousands of
    characters. Keep only each error's location and message.
    """
    if not isinstance(error, ValidationError):
        return str(error)
    details = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        message = item["msg"].removeprefix("Value error, ")
        details.append(f"{location}: {message}" if location else message)
    return "; ".join(details) or str(error)
