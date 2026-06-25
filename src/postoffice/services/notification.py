# postoffice/services/notification.py
# Build & send postoffice.email notifications via bbsengine6.notify.

import logging
from typing import List

from bbsengine6.notify import send as message_send

from .imap_client import extract_preview

logger = logging.getLogger(__name__)

POSTOFFICE_NOTIFICATION_TYPE = "postoffice.email"
POSTOFFICE_SENDER_MONIKER = "postoffice"


def build_email_payload(envelope_bytes: bytes) -> str:
    """Turn an envelope into the human-readable body of a notification.

    Format:
        From: <sender>
        Subject: <subject>

        <preview text, up to 500 chars>
    """
    parsed = extract_preview(envelope_bytes)
    return (
        f"From: {parsed['sender']}\n"
        f"Subject: {parsed['subject']}\n\n"
        f"{parsed['preview']}"
    )


def notify_new_messages(envelopes: List[bytes], recipients: List[str] = None) -> int:
    """Send one notification per envelope to `recipients` (default @everyone).

    Returns the number of notifications successfully sent.
    """
    if recipients is None:
        recipients = ["@everyone"]

    sent = 0
    for envelope in envelopes:
        try:
            message_send(
                notification_type=POSTOFFICE_NOTIFICATION_TYPE,
                recipients=recipients,
                template=build_email_payload(envelope),
                sender_moniker=POSTOFFICE_SENDER_MONIKER,
            )
            sent += 1
        except Exception as e:
            logger.error(f"notification.notify_new_messages: {e}")
    return sent
