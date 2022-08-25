from dataclasses import dataclass, field


@dataclass
class Account:
    username: str
    password: str = field(repr=False)
    mail_to: str
    mail_from: str
