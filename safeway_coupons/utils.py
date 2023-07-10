import random
import time
from typing import Generator, Iterable, TypeVar

T = TypeVar("T")


def yield_delay(
    iterable: Iterable[T], sleep_level: int, debug_level: int
) -> Generator[T, None, None]:
    for count, item in enumerate(iterable):
        delay_time = 0.0
        if sleep_level < 2:
            if sleep_level < 1 and count and count % 12 == 0:
                if count % 48 == 0:
                    delay_time = random.uniform(15.0, 25.0)
                else:
                    delay_time = random.uniform(4.0, 8.0)
                delay_time = round(delay_time, 2)
            else:
                delay_time = random.uniform(0.3, 0.8)
        if delay_time:
            if debug_level >= 1 and delay_time >= 1:
                print(f"Waiting {delay_time} seconds")
            time.sleep(delay_time)
        yield item
