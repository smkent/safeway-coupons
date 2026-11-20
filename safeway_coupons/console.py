from __future__ import annotations

import logging
import re
import sys
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from functools import cached_property, partial
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from rich.console import Console as RichConsole
from rich.console import ConsoleRenderable
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any, TextIO

    from rich.traceback import Traceback

MAIN_LOGGER = "safeway-coupons"


class LogLevel(IntEnum):
    TRACE = 5


for _log_level in LogLevel:
    logging.addLevelName(_log_level, _log_level.name)


class Logger(logging.LoggerAdapter):
    def trace(self, msg: object, *args: object, **kwargs: Any) -> None:
        self.log(LogLevel.TRACE, msg, *args, **kwargs)


class LogHandler(RichHandler):
    LOG_LEVEL_STYLES = MappingProxyType(
        {
            LogLevel.TRACE: Style(dim=True),
            logging.DEBUG: Style(dim=True),
            logging.WARNING: Style(color="yellow", bold=True),
            logging.ERROR: Style(color="red", bold=True),
            logging.CRITICAL: Style(color="red", bold=True, reverse=True),
        }
    )

    def __init__(self, *args: Any, level: int, **kwargs: Any) -> None:
        kwargs.setdefault(
            "log_time_format", lambda dt: dt.strftime("%H:%M:%S.%f")[:-3]
        )
        kwargs.setdefault("omit_repeated_times", False)
        kwargs.setdefault("highlighter", NullHighlighter())
        super().__init__(*args, **kwargs)
        self.setLevel(level)
        self.main_thread_ident = threading.main_thread().ident

    def get_level_text(self, record: logging.LogRecord) -> Text:
        if record.levelno == LogLevel.TRACE:
            return Text.styled("TRACE   ", "dim")
        return super().get_level_text(record)

    def render(
        self,
        *,
        record: logging.LogRecord,
        traceback: Traceback | None,
        message_renderable: ConsoleRenderable,
    ) -> ConsoleRenderable:
        output = super().render(
            record=record,
            traceback=traceback,
            message_renderable=message_renderable,
        )
        if isinstance(output, Table):
            output.expand = False
        return output

    def render_message(
        self, record: logging.LogRecord, message: str
    ) -> ConsoleRenderable:
        msg_text = cast("Text", super().render_message(record, message))
        if record.thread != self.main_thread_ident and (
            thread_name := record.threadName
        ):
            msg_text = Text.assemble(f"[{thread_name}] ", msg_text)

        level_style = self.LOG_LEVEL_STYLES.get(record.levelno)
        if level_style:
            msg_text.stylize_before(level_style)
        return msg_text


@dataclass
class TerminalConsoleOutput:
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
            return RichConsole(
                stderr=True, theme=Theme({"log.time": "medium_purple2"})
            )
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
            show_time=bool(self.level <= logging.DEBUG),
            show_level=bool(self.level <= logging.DEBUG),
            show_path=False if plain else bool(self.level <= LogLevel.TRACE),
        )


@dataclass
class Console:
    verbose: int = 0

    terminal_output: TerminalConsoleOutput | None = field(
        default=None, init=False
    )

    def __post_init__(self) -> None:
        self.reset()

    def logger(self) -> Logger:
        return Logger(logging.getLogger(MAIN_LOGGER))

    def configure(self, *, verbose: int = 0) -> None:
        if verbose != self.verbose:
            self.verbose = verbose
            self.reset()

    def reset(self) -> None:
        log = logging.getLogger()
        if self.terminal_output and self.terminal_output.handler:
            for handler in log.handlers:
                if handler == self.terminal_output.handler:
                    log.removeHandler(handler)

        main_log_level = (
            LogLevel.TRACE
            if self.verbose >= 2
            else logging.DEBUG
            if self.verbose
            else logging.INFO
        )
        self.terminal_output = TerminalConsoleOutput(level=main_log_level)
        log.addHandler(self.terminal_output.handler)
        logging.getLogger().setLevel(
            logging.DEBUG if self.verbose >= 3 else logging.WARNING
        )
        main_log = logging.getLogger(MAIN_LOGGER)
        main_log.setLevel(main_log_level)


def excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
    thread: threading.Thread | None = None,
) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    suffix = f" in thread: {thread.name}" if thread else ""
    log.error(
        f"Uncaught exception{suffix}",
        exc_info=(exc_type, exc_value, exc_traceback),
    )


sys.excepthook = partial(excepthook, thread=None)


console = Console()
log = console.logger()
