import collections
import os
import subprocess
from email.mime.text import MIMEText
from typing import List, Optional

from .accounts import Account
from .errors import ClipError, Error, TooManyClipErrors
from .models import Offer


def _send_email(
    account: Account,
    subject: str,
    mail_message: List[str],
    debug_level: int,
    send_email: bool,
) -> None:
    mail_message_str = os.linesep.join(mail_message)
    if debug_level >= 1:
        if send_email:
            print(f"Sending email to {account.mail_to}")
        else:
            print(f"Would send email to {account.mail_to}")
        print(">>>>>>")
        print(mail_message_str)
        print("<<<<<<")
    if not send_email:
        return
    email_data = MIMEText(mail_message_str)
    email_data["To"] = account.mail_to
    email_data["From"] = account.mail_from
    if subject:
        email_data["Subject"] = subject
    p = subprocess.Popen(
        ["/usr/sbin/sendmail", "-f", account.mail_to, "-t"],
        stdin=subprocess.PIPE,
    )
    p.communicate(bytes(email_data.as_string(), "UTF-8"))


def email_clip_results(
    account: Account,
    offers: List[Offer],
    error: Optional[Error],
    clip_errors: Optional[List[ClipError]],
    debug_level: int,
    send_email: bool,
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
    _send_email(account, mail_subject, mail_message, debug_level, send_email)


def email_error(
    account: Account,
    error: Error,
    debug_level: int,
    send_email: bool,
) -> None:
    mail_subject = f"Safeway coupons: {error.__class__.__name__} error"
    mail_message: List[str] = [
        f"Safeway account: {account.username}",
        f"Error: {error}",
    ]
    if isinstance(error, TooManyClipErrors) and error.clipped_offers:
        mail_message += ["Clipped coupons:", ""]
        for offer in error.clipped_offers:
            mail_message += str(offer)
    _send_email(account, mail_subject, mail_message, debug_level, send_email)
