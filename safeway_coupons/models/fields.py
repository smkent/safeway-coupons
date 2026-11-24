from __future__ import annotations

import base64
import binascii
import re
from typing import Annotated

from pydantic import (
    AfterValidator,
    BeforeValidator,
    PlainSerializer,
    SecretStr,
)


class Password:
    PREFIX = "base64:"

    @classmethod
    def decode_field(cls, value: object) -> SecretStr:
        if isinstance(value, SecretStr):  # Set in code, already plaintext
            return value
        if not isinstance(value, str) or not value.startswith(cls.PREFIX):
            raise ValueError(f"password must start with {cls.PREFIX!r}")
        try:
            plain_value = base64.b64decode(
                value.removeprefix(cls.PREFIX), validate=True
            ).decode()
            return SecretStr(plain_value)
        except (binascii.Error, UnicodeDecodeError) as e:
            raise ValueError("password is not valid base64") from e

    @classmethod
    def encode(cls, value: str) -> str:
        return cls.PREFIX + base64.b64encode(value.encode()).decode()

    @classmethod
    def encode_field(cls, value: SecretStr) -> str:
        return cls.encode(value.get_secret_value())


PasswordT = Annotated[
    SecretStr,
    BeforeValidator(Password.decode_field),
    PlainSerializer(Password.encode_field),
]


class ItemName:
    INVALID_CHARS = re.compile(r"[\s/\\]")

    @classmethod
    def validate(cls, value: str) -> str:
        """Return the name in lowercase, if it's valid."""
        value = value.lower()
        if not (
            value[:1].isalnum()
            and value.isprintable()
            and not cls.INVALID_CHARS.search(value)
        ):
            raise ValueError(
                "must start with a letter or number,"
                " and can't contain spaces or slashes"
            )
        return value


ItemNameT = Annotated[str, AfterValidator(ItemName.validate)]
