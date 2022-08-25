from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Account:
    username: str
    password: str = field(repr=False)
    mail_to: Optional[str]
