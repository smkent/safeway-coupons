from __future__ import annotations

import subprocess
import sys
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING

import undetected_chromedriver as uc

if TYPE_CHECKING:
    from collections.abc import Generator

CHROMEDRIVER_PATH = (
    Path.home()
    / ".local"
    / "share"
    / "undetected_chromedriver"
    / "undetected_chromedriver"
)


class ChromeDriverDoesNotExistError(Exception):
    pass


@contextmanager
def chrome_driver(*, headless: bool = True) -> Generator[uc.Chrome]:
    options = uc.ChromeOptions()
    for option in [
        "--incognito",
        "--no-sandbox",
        "--disable-extensions",
        "--disable-application-cache",
        "--disable-gpu",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
    ]:
        options.add_argument(option)
    if headless:
        options.add_argument("--headless=new")
    driver = uc.Chrome(options=options)
    yield driver
    driver.quit()


def chrome_driver_version() -> str:
    if not CHROMEDRIVER_PATH.is_file():
        raise ChromeDriverDoesNotExistError(
            f"Error: {CHROMEDRIVER_PATH} does not exist"
        )
    cmd = [str(CHROMEDRIVER_PATH), "--version"]
    print(f"+ {' '.join(cmd)}", file=sys.stderr)  # noqa: T201
    result = subprocess.run(cmd, capture_output=True, check=True)  # noqa: S603
    return result.stdout.decode()


def init() -> None:
    with suppress(ChromeDriverDoesNotExistError):
        print(chrome_driver_version())  # noqa: T201
        return
    print("Initializing Chrome Driver")  # noqa: T201
    with chrome_driver() as driver:
        print("Connect to example.com")  # noqa: T201
        driver.get("https://example.com")  # ty: ignore[invalid-argument-type, missing-argument]
    print(chrome_driver_version())  # noqa: T201
