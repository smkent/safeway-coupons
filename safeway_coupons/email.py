import collections
import os
import subprocess
from email.mime.text import MIMEText
from typing import List

from .accounts import Account
from .models import Offer


def email_clip_results(
    account: Account, offers: List[Offer], debug: bool, send_email: bool
) -> None:
    offers_by_type = collections.defaultdict(list)
    for offer in offers:
        offers_by_type[offer.offer_pgm].append(offer)
    mail_subject = f"Safeway coupons: {len(offers)} clipped"
    mail_message: List[str] = [
        f"Safeway account: {account.username}",
        f"Clipped {len(offers)} total:",
    ]
    for offer_type, offers_this_type in offers_by_type.items():
        mail_message.append(
            f"    {offer_type.name}: {len(offers_this_type)} coupons"
        )

    mail_message_str = os.linesep.join(mail_message)
    if debug:
        print("Sending email to {}".format(account.mail_to))
        print(">>>>>>")
        print(mail_message_str)
        print("<<<<<<")
    if not send_email:
        return
    email_data = MIMEText(mail_message_str)
    email_data["To"] = account.mail_to
    email_data["From"] = account.mail_from
    if mail_subject:
        email_data["Subject"] = mail_subject
    p = subprocess.Popen(
        ["/usr/sbin/sendmail", "-f", account.mail_to, "-t"],
        stdin=subprocess.PIPE,
    )
    p.communicate(bytes(email_data.as_string(), "UTF-8"))
