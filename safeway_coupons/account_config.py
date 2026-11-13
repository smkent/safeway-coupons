from __future__ import annotations

import base64
import binascii
import tempfile
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import tomlkit
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    SecretStr,
)

PASSWORD_PREFIX = "base64:"  # noqa: S105


def password_decode(value: object) -> SecretStr:
    if isinstance(value, SecretStr):  # Set in code, already plaintext
        return value
    if not isinstance(value, str) or not value.startswith(PASSWORD_PREFIX):
        raise ValueError(f"password must start with {PASSWORD_PREFIX!r}")
    try:
        raw = base64.b64decode(
            value.removeprefix(PASSWORD_PREFIX), validate=True
        )
        return SecretStr(raw.decode())
    except (binascii.Error, UnicodeDecodeError) as e:
        raise ValueError("password is not valid base64") from e


def password_encode(value: SecretStr) -> str:
    encoded = base64.b64encode(value.get_secret_value().encode()).decode()
    return PASSWORD_PREFIX + encoded


Password = Annotated[
    SecretStr,
    BeforeValidator(password_decode),
    PlainSerializer(password_encode),
]


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @classmethod
    def _update(cls, table: Any, data: dict[str, Any]) -> None:
        """Merge data into a tomlkit table in place, keeping comments."""
        for key in [k for k in table if k not in data]:
            del table[key]
        for key, value in data.items():
            if isinstance(value, dict) and isinstance(table.get(key), dict):
                cls._update(table[key], value)
            else:
                table[key] = value


class EmailConfig(ConfigModel):
    to: str | None = None
    mail_from: str | None = Field(default=None, alias="from")


class AccountConfig(ConfigModel):
    config_version: Literal[1]
    username: str
    password: Password
    email: EmailConfig | None = None

    @classmethod
    def load(cls, path: Path) -> Self:
        with path.open("r") as f:
            return cls.model_validate(tomlkit.load(f).unwrap())

    def save(self, path: Path) -> None:
        data = (
            tomlkit.parse(path.read_text())
            if path.is_file()
            else tomlkit.document()
        )
        self._update(
            data,
            self.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=path.parent, suffix=".tmp") as td:
            temp_path = Path(td) / f".{path.name}.tmp"
            with temp_path.open("w") as file:
                temp_path.chmod(0o600)
                tomlkit.dump(data, file)
            temp_path.replace(path)
