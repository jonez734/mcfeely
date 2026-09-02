# postoffice/services/notification.py
# Build & send postoffice.email notifications via bbsengine6.message.

import logging
import string
from typing import List, Optional

from bbsengine6.message import send as message_send

from .imap_client import extract_preview

logger = logging.getLogger(__name__)

POSTOFFICE_NOTIFICATION_TYPE = "postoffice.email"
POSTOFFICE_SENDER_MONIKER = "postoffice"


# Color-coded notification template.
#
# Labels (lightgray) come from {var:labelcolor}. Values are split:
#   - {var:recipientcolor} (cyan) reads as "an address" -> the email
#     From: line. Matches the convention used for BBS message
#     recipients elsewhere on the BBS terminal.
#   - {var:valuecolor} (green) for the To:, Subject, and body preview
#     lines, matching the label/value pattern used throughout
#     mistermcfeely (mailbox.py, main.py, virtual.py) and the
#     bbsengine6 console.
#
# {var:...} tokens are resolved by the client's ``echo()`` machinery
# when the recipient views their pending message. They pass through
# ``bbsengine6.message.render_template`` untouched (that helper only
# substitutes plain ``{var}`` / ``$var`` forms), so we don't need any
# server-side pre-rendering here.
#
# The {sender}/{to}/{subject}/{preview} placeholders are resolved
# server-side at notification-build time. The template is ``.format``
# -ed via :class:`SafeFormatter`, which treats any field it does not
# recognize (such as ``{var}``) as a literal run-through so the
# color tokens survive the substitution.
NOTIFICATION_TEMPLATE = (
    "{var:labelcolor}From: {var:recipientcolor}{sender}\n"
    "{var:labelcolor}To: {var:valuecolor}{to}\n"
    "{var:labelcolor}Subject: {var:valuecolor}{subject}\n"
    "\n"
    "{var:valuecolor}{preview}"
)


class SafeFormatter(string.Formatter):
    """``str.format`` variant that leaves unknown fields untouched.

    The notification template embeds BBS color tokens like
    ``{var:labelcolor}`` alongside server-substituted fields like
    ``{sender}``. Python's default formatter raises ``KeyError`` for
    any name it doesn't know, which would force us to register every
    ``{var:...}`` token explicitly. This subclass falls back to the
    original ``"{field_name}"`` (or ``"{field_name!conv:spec}"``)
    text for anything missing from the ``kwargs``, so the color tokens
    survive into the rendered string for the recipient's terminal to
    resolve.
    """

    def get_value(self, key, args, kwargs):  # type: ignore[override]
        if isinstance(key, str):
            if key in kwargs:
                return kwargs[key]
            # Reconstruct the literal token: ``{key}`` or
            # ``{key!conv:spec}``. ``string.Formatter.parse`` already
            # stripped those out, so we just return a sentinel that
            # ``format_field`` recognizes and reinflates.
            return _MissingField(key)
        return super().get_value(key, args, kwargs)

    def format_field(self, value, format_spec):  # type: ignore[override]
        if isinstance(value, _MissingField):
            spec = ":" + format_spec if format_spec else ""
            return "{" + value.name + spec + "}"
        return super().format_field(value, format_spec)


class _MissingField:
    """Sentinel returned by :class:`SafeFormatter.get_value` when a
    field isn't in ``kwargs``. :meth:`SafeFormatter.format_field`
    recognizes this and re-emits the literal ``{name}`` text instead
    of raising ``KeyError``.
    """

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name


def _render_template(template: str, **kwargs: str) -> str:
    """Substitute ``kwargs`` into ``template``; leave unknown fields as
    literal ``{field}`` text so BBS color tokens survive.
    """
    return SafeFormatter().format(template, **kwargs)


def build_email_payload(
    envelope_bytes: bytes,
    *,
    to: Optional[str] = None,
) -> str:
    """Turn an envelope into the human-readable body of a notification.

    Uses :data:`NOTIFICATION_TEMPLATE`. :func:`_render_template`
    resolves the ``{sender}`` / ``{subject}`` / ``{preview}`` / ``{to}``
    placeholders before the notification is stored; the
    ``{var:labelcolor}`` / ``{var:valuecolor}`` /
    ``{var:recipientcolor}`` tokens are left intact for the recipient's
    terminal to resolve.

    Args:
        envelope_bytes: Raw RFC822 envelope, as returned by
            :func:`postoffice.services.imap_client.fetch_envelopes`.
        to: Optional label for the ``To:`` line -- typically the IMAP
            account that received the message, e.g.
            ``"user@example.com"`` or ``"shared/support"``. Empty /
            ``None`` renders as a blank after the ``To:`` label.
    """
    parsed = extract_preview(envelope_bytes)
    return _render_template(
        NOTIFICATION_TEMPLATE,
        sender=parsed["sender"],
        to=to or "",
        subject=parsed["subject"],
        preview=parsed["preview"],
    )


def notify_new_messages(
    envelopes: List[bytes],
    recipients: Optional[List[str]] = None,
    *,
    to: Optional[str] = None,
) -> int:
    """Send one notification per envelope to ``recipients``.

    Args:
        envelopes: List of raw RFC822 envelope byte strings, as
            returned by :func:`postoffice.services.imap_client.fetch_envelopes`.
        recipients: BBS monikers and/or ``@<group>`` strings that
            should receive the notification. Defaults to
            ``["@everyone"]`` when ``None``. An empty list short-circuits
            without calling ``bbsengine6.message.send`` at all; this
            lets a configured mailbox opt out of notifying entirely
            (e.g. for analytics-only polling).
        to: Optional label for the ``To:`` line in the notification
            body (e.g. the mailbox account that received the message).

    Returns:
        Number of notifications successfully sent.
    """
    if recipients is None:
        recipients = ["@everyone"]

    # Honor the "don't notify" opt-out up front. bbsengine6.message.send
    # rejects empty recipients with ValueError, so check here rather
    # than relying on the downstream exception.
    if not recipients:
        return 0

    sent = 0
    for envelope in envelopes:
        try:
            message_send(
                notification_type=POSTOFFICE_NOTIFICATION_TYPE,
                recipients=recipients,
                template=build_email_payload(envelope, to=to),
                sender_moniker=POSTOFFICE_SENDER_MONIKER,
            )
            sent += 1
        except Exception as e:
            logger.error(f"notification.notify_new_messages: {e}")
    return sent
