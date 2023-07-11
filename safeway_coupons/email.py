import collections
import mimetypes
import os
import subprocess
from email.message import EmailMessage
from pathlib import Path
from typing import List, Optional

from .accounts import Account
from .errors import ClipError, Error, TooManyClipErrors
from .models import Offer


def _send_email(
    sendmail: List[str],
    account: Account,
    subject: str,
    mail_message: List[str],
    debug_level: int,
    send_email: bool,
    attachments: Optional[List[Path]] = None,
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
    msg = EmailMessage()
    msg["To"] = account.mail_to
    msg["From"] = account.mail_from
    if subject:
        msg["Subject"] = subject
    msg.set_content(mail_message_str)
    for attachment in attachments or []:
        mt = mimetypes.guess_type(attachment.name)[0]
        main, sub = mt.split("/", 1) if mt else ("application", "octet-stream")
        msg.add_attachment(
            attachment.read_bytes(),
            filename=attachment.name,
            maintype=main,
            subtype=sub,
        )
    p = subprocess.Popen(
        sendmail + ["-f", account.mail_to, "-t"], stdin=subprocess.PIPE
    )
    p.communicate(bytes(msg.as_string(), "UTF-8"))


def email_clip_results(
    sendmail: List[str],
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
    _send_email(
        sendmail, account, mail_subject, mail_message, debug_level, send_email
    )


def email_error(
    sendmail: List[str],
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
    _send_email(
        sendmail,
        account,
        mail_subject,
        mail_message,
        debug_level,
        send_email,
        attachments=getattr(error, "attachments", None),
    )
