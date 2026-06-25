# postoffice/services/imap_client.py
# Service-shaped IMAP operations: connect, count UNSEEN, fetch envelopes,
# extract previews. Thin wrappers over the stdlib imaplib so the rest of
# the services package doesn't deal with imaplib specifics directly.

import imaplib
from email.parser import BytesParser
from email.policy import default
from typing import Dict, List, Optional

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


def fetch_envelopes(conn: imaplib.IMAP4, limit: int = 5) -> List[bytes]:
    """Fetch up to `limit` envelope payloads from the currently selected mailbox."""
    typ, data = conn.search(None, "UNSEEN")
    if typ != "OK" or not data or not data[0]:
        return []
    message_ids = data[0].split()[:limit]
    envelopes: List[bytes] = []
    for msg_id in message_ids:
        try:
            typ, msg_data = conn.fetch(msg_id, "(ENVELOPE)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                continue
            envelope = msg_data[0][1] if len(msg_data[0]) > 1 else b""
            if envelope:
                envelopes.append(envelope)
        except Exception:
            continue
    return envelopes


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
