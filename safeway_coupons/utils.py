import random
import string
import time
from typing import Generator, Iterable, TypeVar

T = TypeVar("T")


WORD_LIST = [
    "almost",
    "avid",
    "awning",
    "bakery",
    "barmaid",
    "bribe",
    "briskness",
    "canopener",
    "collage",
    "component",
    "computing",
    "corned",
    "cried",
    "crumb",
    "curliness",
    "curvature",
    "cycle",
    "darkening",
    "deflector",
    "desolate",
    "detergent",
    "dipped",
    "disfigure",
    "distinct",
    "duress",
    "ebony",
    "elated",
    "elusive",
    "emcee",
    "emphasize",
    "enjoyable",
    "exact",
    "fall",
    "flatness",
    "footpath",
    "getaway",
    "groom",
    "guts",
    "hangnail",
    "headlamp",
    "headlock",
    "jailbird",
    "kinetic",
    "landfill",
    "linguini",
    "maroon",
    "mouse",
    "nectar",
    "neuron",
    "numerous",
    "nylon",
    "ounce",
    "outburst",
    "overbuilt",
    "pogo",
    "profusely",
    "province",
    "puzzling",
    "quickly",
    "rascal",
    "record",
    "refutable",
    "robotics",
    "rule",
    "sadness",
    "sandlot",
    "schematic",
    "scruffy",
    "secrecy",
    "shaping",
    "skipper",
    "smolder",
    "smooth",
    "snowiness",
    "spirits",
    "spoon",
    "spray",
    "steering",
    "stung",
    "stylized",
    "subarctic",
    "sulfate",
    "throwback",
    "tipper",
    "tweezers",
    "uncoated",
    "unlovely",
    "unmanaged",
    "unmatched",
    "unproven",
    "unrevised",
    "uplifted",
    "viability",
    "vocalist",
    "vocalize",
    "washbasin",
    "washing",
    "womb",
    "xerox",
    "yin",
]


def make_token() -> str:
    return "-".join(random.choices(WORD_LIST, k=4))


def make_nonce() -> str:
    return "".join(
        random.choices(
            string.ascii_lowercase + string.ascii_uppercase + string.digits,
            k=62,
        )
    )


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
