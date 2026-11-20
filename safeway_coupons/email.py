from __future__ import annotations

import collections
import mimetypes
import os
import subprocess
from email.message import EmailMessage
from typing import TYPE_CHECKING

from .console import log
from .errors import Error, TooManyClipErrors
from .models.safeway.offers import OfferType

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from .account import Account
    from .models.safeway.offers import Offer


def _send_email(
    sendmail: Sequence[str],
    account: Account,
    subject: str,
    mail_message: list[str],
    attachments: Sequence[Path] | None = None,
    *,
    send_email: bool,
) -> None:
    mail_message_str = os.linesep.join(mail_message)
    if send_email:
        log.debug("Sending email to %s", account.mail_to)
    else:
        log.debug("Would send email to %s", account.mail_to)
    log.debug(">>>>>>")
    log.debug(mail_message_str)
    log.debug("<<<<<<")
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
    p = subprocess.Popen(  # noqa: S603
        [*sendmail, "-f", account.mail_from, "-t"],
        stdin=subprocess.PIPE,
    )
    p.communicate(bytes(msg.as_string(), "UTF-8"))


def email_clip_results(
    sendmail: Sequence[str],
    account: Account,
    offers: list[Offer],
    *,
    send_email: bool,
) -> None:
    offers_by_type = collections.defaultdict(list)
    for offer in offers:
        offers_by_type[
            offer.offer_pgm.name
            if isinstance(offer.offer_pgm, OfferType)
            else offer.offer_pgm
        ].append(offer)
    mail_subject = f"Safeway coupons: {len(offers)} clipped"
    mail_message: list[str] = [
        f"Safeway account: {account.username}",
        f"Clipped {len(offers)} total:",
    ]
    for offer_type, offers_this_type in offers_by_type.items():
        mail_message.append(
            f"    {offer_type}: {len(offers_this_type)} coupons"
        )
    _send_email(
        sendmail,
        account,
        mail_subject,
        mail_message,
        send_email=send_email,
    )


def email_error(
    sendmail: Sequence[str],
    account: Account,
    error: Error,
    *,
    send_email: bool,
) -> None:
    mail_subject = f"Safeway coupons: {error.__class__.__name__} error"
    mail_message: list[str] = [
        f"Safeway account: {account.username}",
        f"Error: {error}",
    ]
    if isinstance(error, TooManyClipErrors) and error.clipped_offers:
        mail_message += ["Clipped coupons:", ""]
        for offer in error.clipped_offers:
            mail_message.append(str(offer))
    _send_email(
        sendmail,
        account,
        mail_subject,
        mail_message,
        send_email=send_email,
        attachments=error.attachments,
    )
