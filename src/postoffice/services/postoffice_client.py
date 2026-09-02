# postoffice/services/postoffice_client.py
# Service-shaped IMAP operations: connect, count UNSEEN, fetch envelopes,
# extract previews, message claim/unclaim, and event firing. Thin wrappers
# over the stdlib imaplib so the rest of the services package doesn't deal
# with imaplib specifics directly.

import imaplib
from email.parser import BytesParser
from email.policy import default
from typing import Any, Dict, List, Optional, Tuple

from bbsengine6 import io

from .. import message_client
from .config import MailboxConfig


def connect(mailbox: MailboxConfig, timeout: Optional[int] = None) -> imaplib.IMAP4:
    """Open an IMAP connection and log in. Caller is responsible for close/logout."""
    if mailbox.use_ssl:
        conn = imaplib.IMAP4_SSL(mailbox.host, mailbox.port)
    else:
        conn = imaplib.IMAP4(mailbox.host, mailbox.port)
    conn.login(mailbox.username, mailbox.password)
    conn.select(mailbox.mailbox)
    return conn


def count_unseen(mailbox: MailboxConfig) -> int:
    """Return the number of UNSEEN messages in mailbox, or 0 on error."""
    conn = None
    try:
        conn = connect(mailbox)
        typ, data = conn.search(None, "UNSEEN")
        if typ != "OK" or not data or not data[0]:
            return 0
        return len(data[0].split())
    except Exception:
        return 0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            try:
                conn.logout()
            except Exception:
                pass


def fetch_envelopes(
    conn: imaplib.IMAP4, limit: int = 5
) -> Tuple[List[bytes], List[Any]]:
    """Fetch up to ``limit`` envelope payloads from the currently selected mailbox.

    Returns a ``(envelopes, message_ids)`` tuple. ``message_ids`` lists
    the IMAP identifiers that correspond to each envelope (in the same
    order, by position) so the caller can mark them ``\\Seen`` after a
    successful notification. ``message_ids[i]`` corresponds to
    ``envelopes[i]``; either list is empty if the mailbox had no UNSEEN
    messages (or the SEARCH returned an empty set).

    The IMAP ``message_id`` is typed as ``Any`` because imaplib emits
    bytes on a SEARCH split, but downstream ``conn.store`` also accepts
    string IDs; coercing happens at the call site.
    """
    typ, data = conn.search(None, "UNSEEN")
    if typ != "OK" or not data or not data[0]:
        return [], []
    message_ids = data[0].split()[:limit]
    envelopes: List[bytes] = []
    fetched_ids: List[Any] = []
    for msg_id in message_ids:
        # imaplib's stubs type SEARCH split results as ``int | bytes``,
        # but at runtime ``data[0].split()`` always yields ``bytes`` (or
        # ``str`` if ``unicode=True`` was passed to IMAP4). Coerce to
        # bytes here so the downstream ``conn.fetch`` / ``conn.store``
        # calls don't trip strict type-checkers.
        if isinstance(msg_id, int):
            msg_id = str(msg_id).encode("ascii")
        elif isinstance(msg_id, str):
            msg_id = msg_id.encode("ascii")
        try:
            typ, msg_data = conn.fetch(msg_id, "(ENVELOPE)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            envelope = msg_data[0][1] if len(msg_data[0]) > 1 else b""
            if envelope:
                envelopes.append(envelope)
                fetched_ids.append(msg_id)
        except Exception:
            continue
    return envelopes, fetched_ids


def extract_preview(envelope_bytes: bytes, body_limit: int = 500) -> Dict[str, str]:
    """Parse an envelope and return {"sender", "subject", "preview"}.

    `body_limit` truncates the text body preview to that many characters.
    """
    parser = BytesParser(policy=default)
    try:
        msg = parser.parsebytes(envelope_bytes)
    except Exception:
        return {"sender": "Unknown", "subject": "No Subject", "preview": ""}

    sender = msg.get("From", "Unknown") or "Unknown"
    subject = msg.get("Subject", "No Subject") or "No Subject"

    body = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode("utf-8", errors="ignore")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="ignore")
    except Exception:
        body = ""

    preview = body[:body_limit] if body else ""
    return {"sender": sender, "subject": subject, "preview": preview}


# ---------------------------------------------------------------------------
# Message claim / unclaim + event firing
# ---------------------------------------------------------------------------
# These functions used to live in the top-level postoffice.imap_client module.
# They were merged here when that module was retired in favor of a single
# services.postoffice_client entry point.


def claim_message(
    args,
    mailbox_name: str,
    message_uid: int,
    actor_moniker: str,
    message_id: str = "",
    message_from: str = "",
    message_subject: str = "",
    **kwargs,
) -> bool:
    """
    Claim a message in a shared mailbox.

    Updates Cyrus with claim flag and fires notification event.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name (e.g., 'shared/support@example.com')
        message_uid: IMAP UID of message
        actor_moniker: Moniker of user claiming message
        message_id: RFC 822 Message-ID (optional, for event data)
        message_from: Message From header (optional, for event data)
        message_subject: Message Subject header (optional, for event data)
        **kwargs: Optional - imap_conn (IMAP connection), conn (DB connection), pool (connection pool)

    Returns: True on success, False on error
    """
    imap_conn = kwargs.get("imap_conn")
    db_conn = kwargs.get("conn")
    try:
        # Format the claim flag with obfuscation
        secret = message_client.get_obfuscate_secret(args)
        claim_flag = message_client.format_claim_flag(actor_moniker, secret)

        if getattr(args, "debug", False):
            io.echo(
                f"postoffice_client.claim_message: {mailbox_name} / {message_uid} / {claim_flag}",
                level="debug",
            )

        # If IMAP connection provided, set the flag
        if imap_conn:
            try:
                imap_conn.select(mailbox_name)
                imap_conn.store(str(message_uid), "+FLAGS", f"({claim_flag})")
            except Exception as e:
                io.echo(
                    f"postoffice_client.claim_message.100: IMAP error: {e}",
                    level="error",
                )
                return False

        # Build event data
        event_data: Dict[str, Any] = {
            "event_type": "message-claimed",
            "mailbox_name": mailbox_name,
            "message_uid": message_uid,
            "actor_moniker": actor_moniker,
        }

        if message_id:
            event_data["message_id"] = message_id
        if message_from:
            event_data["from"] = message_from
        if message_subject:
            event_data["subject"] = message_subject

        # Fire notification event
        return message_client.fire_event(
            args,
            mailbox_name,
            "message-claimed",
            event_data,
            actor_moniker=actor_moniker,
            conn=db_conn,
            pool=kwargs.get("pool"),
        )

    except Exception as e:
        io.echo(f"postoffice_client.claim_message.200: {e}", level="error")
        return False


def unclaim_message(
    args,
    mailbox_name: str,
    message_uid: int,
    actor_moniker: str,
    **kwargs,
) -> bool:
    """
    Unclaim a message in a shared mailbox (remove claim flag).

    Updates Cyrus and fires notification event.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name
        message_uid: IMAP UID of message
        actor_moniker: Moniker of user unclaiming message
        **kwargs: Optional - imap_conn (IMAP connection), conn (DB connection), pool (connection pool)

    Returns: True on success, False on error
    """
    imap_conn = kwargs.get("imap_conn")
    db_conn = kwargs.get("conn")
    try:
        # Format the claim flag with obfuscation
        secret = message_client.get_obfuscate_secret(args)
        claim_flag = message_client.format_claim_flag(actor_moniker, secret)

        if getattr(args, "debug", False):
            io.echo(
                f"postoffice_client.unclaim_message: {mailbox_name} / {message_uid} / {claim_flag}",
                level="debug",
            )

        # If IMAP connection provided, remove the flag
        if imap_conn:
            try:
                imap_conn.select(mailbox_name)
                imap_conn.store(str(message_uid), "-FLAGS", f"({claim_flag})")
            except Exception as e:
                io.echo(
                    f"postoffice_client.unclaim_message.100: IMAP error: {e}",
                    level="error",
                )
                return False

        # Build event data
        event_data: Dict[str, Any] = {
            "event_type": "message-unclaimed",
            "mailbox_name": mailbox_name,
            "message_uid": message_uid,
            "actor_moniker": actor_moniker,
        }

        # Fire notification event
        return message_client.fire_event(
            args,
            mailbox_name,
            "message-unclaimed",
            event_data,
            actor_moniker=actor_moniker,
            conn=db_conn,
            pool=kwargs.get("pool"),
        )

    except Exception as e:
        io.echo(f"postoffice_client.unclaim_message.200: {e}", level="error")
        return False


def fire_new_message_event(
    args,
    mailbox_name: str,
    message_uid: int,
    message_id: str,
    message_from: str,
    message_subject: str,
    **kwargs,
) -> bool:
    """
    Fire notification for newly arrived message.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name
        message_uid: IMAP UID
        message_id: RFC 822 Message-ID
        message_from: From header
        message_subject: Subject header
        **kwargs: Optional - conn (DB connection), pool (connection pool)

    Returns: True on success, False on error
    """
    try:
        event_data: Dict[str, Any] = {
            "event_type": "message-new",
            "mailbox_name": mailbox_name,
            "message_uid": message_uid,
            "message_id": message_id,
            "from": message_from,
            "subject": message_subject,
        }

        return message_client.fire_event(
            args,
            mailbox_name,
            "message-new",
            event_data,
            actor_moniker=None,
            conn=kwargs.get("conn"),
            pool=kwargs.get("pool"),
        )

    except Exception as e:
        io.echo(f"postoffice_client.fire_new_message_event: {e}", level="error")
        return False


def fire_flag_changed_event(
    args,
    mailbox_name: str,
    message_uid: int,
    flag_name: str,
    added: bool,
    actor_moniker: Optional[str] = None,
    **kwargs,
) -> bool:
    """
    Fire notification for flag change on message.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name
        message_uid: IMAP UID
        flag_name: Flag name (e.g., '\\Seen')
        added: True if flag was added, False if removed
        actor_moniker: User who triggered flag change (optional)
        **kwargs: Optional - conn (DB connection), pool (connection pool)

    Returns: True on success, False on error
    """
    try:
        event_data: Dict[str, Any] = {
            "event_type": "message-flagged",
            "mailbox_name": mailbox_name,
            "message_uid": message_uid,
            "flag_name": flag_name,
            "added": added,
        }

        return message_client.fire_event(
            args,
            mailbox_name,
            "message-flagged",
            event_data,
            actor_moniker=actor_moniker,
            conn=kwargs.get("conn"),
            pool=kwargs.get("pool"),
        )

    except Exception as e:
        io.echo(f"postoffice_client.fire_flag_changed_event: {e}", level="error")
        return False


def fire_message_deleted_event(
    args, mailbox_name: str, message_uid: int, **kwargs
) -> bool:
    """
    Fire notification for message deletion/expunge.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name
        message_uid: IMAP UID
        **kwargs: Optional - conn (DB connection), pool (connection pool)

    Returns: True on success, False on error
    """
    try:
        event_data: Dict[str, Any] = {
            "event_type": "message-deleted",
            "mailbox_name": mailbox_name,
            "message_uid": message_uid,
        }

        return message_client.fire_event(
            args,
            mailbox_name,
            "message-deleted",
            event_data,
            actor_moniker=None,
            conn=kwargs.get("conn"),
            pool=kwargs.get("pool"),
        )

    except Exception as e:
        io.echo(f"postoffice_client.fire_message_deleted_event: {e}", level="error")
        return False
