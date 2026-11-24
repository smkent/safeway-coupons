from safeway_coupons.models.fields import Password

ACCOUNTS_TOML = f"""\
[accounts.ness]
username = "ness@onett.example"
password = "{Password.encode("pk_fire")}"

[accounts.paula]
username = "Paula@twoson.example"
password = "{Password.encode("pk_freeze")}"

[accounts.paula.notify.email]
to = "ness@onett.example"
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
