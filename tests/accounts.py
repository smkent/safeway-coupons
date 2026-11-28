from safeway_coupons.account import Account, EmailConfig, NotifyConfig
from safeway_coupons.models.fields import Password

ACCOUNTS_TOML = f"""\
[accounts.ness]
username = "ness@onett.example"
password = "{Password.encode("pk_fire")}"

[accounts.paula]
username = "Paula@twoson.example"
password = "{Password.encode("pk_freeze")}"
notify.email.to = "ness@onett.example"
"""


LEGACY_ACCOUNTS_INI = """\
[_global]
email_sender = ness@onett.example

[ness@onett.example]
password = pk_fire

[Paula@twoson.example]
password = pk_freeze
notify = ness@onett.example
"""

LEGACY_ACCOUNTS = {
    "ness@onett.example": Account(
        name="ness@onett.example",
        username="ness@onett.example",
        password=Password.encode("pk_fire"),
        notify=NotifyConfig(email=EmailConfig(mail_from="ness@onett.example")),
    ),
    "paula@twoson.example": Account(
        name="paula@twoson.example",
        username="Paula@twoson.example",
        password=Password.encode("pk_freeze"),
        notify=NotifyConfig(
            email=EmailConfig(
                to="ness@onett.example", mail_from="ness@onett.example"
            )
        ),
    ),
}
