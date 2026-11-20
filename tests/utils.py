from __future__ import annotations

import email
import email.policy
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from safeway_coupons.__main__ import main
from safeway_coupons.models.safeway.offers import Offer, OfferStatus, OfferType

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence
    from email.message import EmailMessage
    from typing import Any, Self


@dataclass
class MainRunner:
    monkeypatch: pytest.MonkeyPatch

    def __call__(self, *cmd: str, match: int = 0) -> None:
        self.monkeypatch.setattr(sys, "argv", ["safeway-coupons", *cmd])
        with pytest.raises(SystemExit, match=str(match)):
            main()


@dataclass
class MockMail(ExitStack):
    messages: list[EmailMessage] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__init__()

    def __enter__(self) -> Self:
        self.enter_context(self.mock_subprocess_sendmail())
        return self

    @contextmanager
    def mock_subprocess_sendmail(self) -> Generator[MagicMock]:
        real_popen = subprocess.Popen

        def _save_message(message: bytes, *_: Any, **__: Any) -> None:
            self.messages.append(
                email.message_from_bytes(message, policy=email.policy.default)
            )

        def _popen(cmd: Sequence[str], *args: Any, **kwargs: Any) -> Any:
            if Path(cmd[0]).name == "sendmail":
                return MagicMock(communicate=_save_message)
            return real_popen(cmd, *args, **kwargs)

        with patch.object(
            subprocess, "Popen", autospec=True, side_effect=_popen
        ) as obj:
            yield obj

    @classmethod
    def attachments(cls, message: EmailMessage) -> dict[str | None, Any]:
        return {
            part.get_filename(): part.get_content()
            for part in message.iter_attachments()
        }

    @classmethod
    def screenshot(cls, message: EmailMessage) -> bytes:
        return cls.attachments(message)["screenshot.png"]


@dataclass
class ClipsTestConfig:
    fail_http_offer_ids: set[str] = field(default_factory=set)
    fail_response_offer_ids: set[str] = field(default_factory=set)
    clipped_offer_ids: list[str] = field(default_factory=list)
    failed_offer_ids: list[str] = field(default_factory=list)


def create_offer(offer_id: str) -> Offer:
    return Offer(
        offer_id=offer_id,
        status=OfferStatus.Unclipped,
        name="Test Food",
        description="Test item for unit testing",
        start_date=datetime.now(tz=UTC) - timedelta(days=1),
        end_date=datetime.now(tz=UTC) + timedelta(days=1),
        offer_price="$99 OFF",
        offer_pgm=OfferType.PersonalizedDeal,
        category_type="Unit Test foods",
        image="https://i.imgur.com/oWSZ8YM.jpg",
    )
