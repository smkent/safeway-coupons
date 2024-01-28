import contextlib
from typing import Iterator

import undetected_chromedriver as uc  # type: ignore


@contextlib.contextmanager
def chrome_driver(headless: bool = True) -> Iterator[uc.Chrome]:
    options = uc.ChromeOptions()
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
