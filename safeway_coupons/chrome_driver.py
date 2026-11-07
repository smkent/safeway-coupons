import contextlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from collections.abc import Iterator

import undetected_chromedriver as uc  # type: ignore

CHROMEDRIVER_PATH = (
    Path.home()
    / ".local"
    / "share"
    / "undetected_chromedriver"
    / "undetected_chromedriver"
)

CHROME_BINARY_NAMES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
)


class ChromeDriverDoesNotExist(Exception):
    pass


def chrome_binary() -> str:
    """Return the path to the Chrome binary or raise a clear error."""
    configured = os.environ.get("CHROME_BINARY")
    if configured:
        if Path(configured).is_file():
            return configured
        raise ChromeDriverDoesNotExist(
            f"Error: CHROME_BINARY={configured} does not exist"
        )
    for name in CHROME_BINARY_NAMES:
        path = shutil.which(name)
        if path:
            return path
    raise ChromeDriverDoesNotExist(
        "Error: no Google Chrome/Chromium binary found. Install Chrome or "
        "set CHROME_BINARY to its path."
    )


@contextlib.contextmanager
def chrome_driver(headless: bool = True) -> Iterator[uc.Chrome]:
    options = uc.ChromeOptions()
    options.binary_location = chrome_binary()
    options.headless = headless
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
        raise ChromeDriverDoesNotExist(
            f"Error: {CHROMEDRIVER_PATH} does not exist"
        )
    cmd = [str(CHROMEDRIVER_PATH), "--version"]
    print(f"+ {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True)
    return result.stdout.decode()


def init() -> None:
    with contextlib.suppress(ChromeDriverDoesNotExist):
        print(chrome_driver_version())
        return
    print("Initializing Chrome Driver")
    with chrome_driver() as driver:
        print("Connect to example.com")
        driver.get("https://example.com")
    print(chrome_driver_version())
