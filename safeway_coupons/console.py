from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass, field
from enum import IntEnum
from functools import cached_property
from typing import TYPE_CHECKING, ClassVar, cast

from rich.console import Console as RichConsole
from rich.console import ConsoleRenderable
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler
from rich.theme import Theme

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any, TextIO

    from rich.text import Text


MAIN_LOGGER = "safeway-coupons"


class LogLevel(IntEnum):
    TRACE = 5


for _log_level in LogLevel:
    logging.addLevelName(_log_level, _log_level.name)


class Logger(logging.LoggerAdapter):
    def trace(self, msg: object, *args: object, **kwargs: Any) -> None:
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        self.log(LogLevel.TRACE, msg, *args, **kwargs)


class LogHandler(RichHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(
            "log_time_format", lambda dt: dt.strftime("%H:%M:%S.%f")[:-3]
        )
        kwargs.setdefault("omit_repeated_times", False)
        kwargs.setdefault("highlighter", NullHighlighter())
        super().__init__(*args, **kwargs)

    def render_message(
        self, record: logging.LogRecord, message: str
    ) -> ConsoleRenderable:
        msg_text = cast("Text", super().render_message(record, message))
        msg_text.stylize_before(f"log.message.{record.levelname.lower()}")
        return msg_text


@dataclass
class ConsoleOutput:
    THEME: ClassVar[Theme] = Theme(
        {
            "log.time": "medium_purple2",
            "logging.level.trace": "dim",
            "log.message.trace": "dim",
            "log.message.debug": "dim",
            "log.message.warning": "bold yellow",
            "log.message.error": "bold red",
            "log.message.critical": "bold red reverse",
        }
    )

    level: int = field(default=logging.CRITICAL, kw_only=True)

    class PlainStderr:
        def __getattr__(self, key: str) -> Any:
            return getattr(sys.stderr, key)

        def write(self, text: str) -> int:
            return sys.stderr.write(
                re.sub(r" +$", "", text, flags=re.MULTILINE)
            )

    @cached_property
    def console(self) -> RichConsole:
        if sys.stderr.isatty():
            return RichConsole(stderr=True, theme=self.THEME)
        return RichConsole(
            file=cast("TextIO", self.PlainStderr()),
            width=100_000,
            no_color=True,
        )

    @cached_property
    def handler(self) -> RichHandler:
        plain = not self.console.is_terminal
        return LogHandler(
            level=self.level,
            console=self.console,
            rich_tracebacks=not plain,
            show_time=self.level <= logging.DEBUG,
            show_level=self.level <= logging.DEBUG,
            show_path=False if plain else (self.level <= LogLevel.TRACE),
        )


@dataclass
class Console:
    handler: logging.Handler | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.configure()

    def logger(self) -> Logger:
        return Logger(logging.getLogger(MAIN_LOGGER))

    def configure(self, *, verbose: int = 0) -> None:
        level = (
            LogLevel.TRACE
            if verbose >= 2
            else logging.DEBUG
            if verbose
            else logging.INFO
        )
        root_logger = logging.getLogger()
        if self.handler:
            root_logger.removeHandler(self.handler)
        self.handler = ConsoleOutput(level=level).handler
        root_logger.addHandler(self.handler)
        logging.getLogger(MAIN_LOGGER).setLevel(level)
        root_logger.setLevel(
            logging.DEBUG if verbose >= 3 else logging.WARNING
        )


def excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    log.error(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
    )


sys.excepthook = excepthook


console = Console()
log = console.logger()
