from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

OperationRoot = Literal["project", "vault", "data", "runtime", "host_repo"]
SourceRoot = Literal["project", "vault", "data", "runtime", "host_repo", "source"]


class FileOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["mkdir", "write_text", "copy_file", "delete"]
    root: OperationRoot
    path: str
    expected_sha256: str | None = None
    result_sha256: str | None = None
    content: str | None = None
    source_root: SourceRoot | None = None
    source_path: str | None = None
    source_sha256: str | None = None

    @model_validator(mode="after")
    def validate_operation_contract(self) -> FileOperation:
        source_fields = (self.source_root, self.source_path, self.source_sha256)
        if self.op == "copy_file":
            if any(value is None for value in source_fields):
                raise ValueError("copy_file requires source_root, source_path, and source_sha256")
            if self.content is not None:
                raise ValueError("copy_file cannot contain inline text")
            if self.result_sha256 != self.source_sha256:
                raise ValueError("copy_file result_sha256 must match source_sha256")
        elif any(value is not None for value in source_fields):
            raise ValueError(f"{self.op} cannot define copy source fields")
        if self.op == "write_text":
            if self.content is None or self.result_sha256 is None:
                raise ValueError("write_text requires content and result_sha256")
        elif self.content is not None:
            raise ValueError(f"{self.op} cannot contain inline text")
        return self


class OperationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    id: UUID
    action: str
    created_at: datetime
    source_version: str
    target_version: str
    roots: dict[str, str]
    metadata: dict[str, str] = Field(default_factory=dict)
    operations: list[FileOperation] = Field(default_factory=list)
    plan_sha256: str
    applied_at: datetime | None = None
    rolled_back_at: datetime | None = None
