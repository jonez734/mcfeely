# imap_lib.py
# Cyrus IMAP utilities for mcfeely message monitoring.
# Provides functional helpers for IMAP operations specific to Cyrus.

import email
import imaplib
import ssl
from typing import Optional, Dict, Set, Tuple, Any

from bbsengine6 import io

from . import password_auth

_insecure_warned = False


def _warn_insecure_once(host: str) -> None:
    """Emit the DEV-only warning the first time we build an unverified context."""
    global _insecure_warned
    if _insecure_warned:
        return
    _insecure_warned = True
    io.echo(
        f"WARNING: TLS certificate verification is disabled for IMAP "
        f"connections to {host} (accept_self_signed=true). This is "
        f"vulnerable to MITM attacks and should be turned off in production.",
        level="warning",
    )


def _resolve_accept_self_signed(args_or_creds, explicit: Optional[bool]) -> bool:
    """Resolve the accept_self_signed flag.

    Precedence: explicit kwarg > args.accept_self_signed > True (default).
    Accepts both args objects and dicts (callers may pass either).
    """
    if explicit is not None:
        return explicit
    if isinstance(args_or_creds, dict):
        return args_or_creds.get("accept_self_signed", True)
    return getattr(args_or_creds, "accept_self_signed", True)


def _build_insecure_ssl_context() -> ssl.SSLContext:
    """Build a client SSLContext that does not verify peer certificates."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def get_imap_credentials(
    args: Any,
    member_moniker: Optional[str] = None,
    mailbox_id: Optional[int] = None,
) -> Optional[Dict[str, str]]:
    """
    Get IMAP credentials with fallback to password management system.

    Priority order:
    1. args.imaphost/imapuser/imappassword (direct config, highest priority)
    2. Password management system (member_moniker required)
    3. None (no credentials available)

    Args:
        args: bbsengine6 args object with IMAP configuration
        member_moniker: Member's moniker for per-member password lookup
        mailbox_id: Mailbox ID for shared mailbox password lookup

    Returns:
        Dict with 'host', 'port', 'username', 'password' keys, or None
    """
    host = getattr(args, "imaphost", None)
    port = getattr(args, "imapport", None) or 993
    username = getattr(args, "imapuser", None)
    password = getattr(args, "imappassword", None)

    # Direct args credentials take priority
    if host and username and password:
        return {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
        }

    # Fall back to password management system if member specified
    if member_moniker and host and username:
        try:
            system_password = password_auth.get_auth_password(
                args,
                mailbox_id=mailbox_id,
                member_moniker=member_moniker,
                password_type="inbound",
                requester_moniker=member_moniker,
            )

            if system_password:
                return {
                    "host": host,
                    "port": port,
                    "username": username,
                    "password": system_password,
                }
        except Exception as e:
            if getattr(args, "debug", False):
                io.echo(
                    f"imap_lib.get_imap_credentials: password lookup failed: {e}",
                    level="debug",
                )

    return None


def connect_cyrus(
    args_or_creds,
    readonly: bool = True,
    timeout: int = 10,
    member_moniker: Optional[str] = None,
    mailbox_id: Optional[int] = None,
    accept_self_signed: Optional[bool] = None,
) -> Optional[imaplib.IMAP4_SSL]:
    """
    Connect to Cyrus IMAP server.

    Credentials loaded with fallback:
    1. Direct dict with 'host'/'port'/'username'/'password' keys
    2. Direct args (args.imaphost/imapuser/imappassword) - highest priority
    3. Password management system (requires member_moniker)
    4. Error if no credentials found

    Args:
        args_or_creds: Either args object or pre-fetched creds dict
        readonly: If True, open mailboxes read-only
        timeout: Connection timeout in seconds
        member_moniker: Member moniker for password system lookup (optional)
        mailbox_id: Mailbox ID for shared mailbox lookup (optional)
        accept_self_signed: If True, build an unverified SSL context so
            self-signed Cyrus certs work. If None, falls back to
            ``args.accept_self_signed`` (and ``True`` when absent). If
            False, use Python's default-verifying context.

    Returns:
        Connected imaplib.IMAP4_SSL object, or None on error
    """
    try:
        if isinstance(args_or_creds, dict):
            creds = args_or_creds
            args = None
        else:
            args = args_or_creds
            creds = get_imap_credentials(
                args,
                member_moniker=member_moniker,
                mailbox_id=mailbox_id,
            )

        if not creds:
            io.echo(
                "imap_lib.connect_cyrus: Missing IMAP credentials (host/user/pass)",
                level="error",
            )
            return None

        host = creds["host"]
        port = int(creds["port"])
        username = creds["username"]
        password = creds["password"]

        insecure = _resolve_accept_self_signed(args_or_creds, accept_self_signed)
        if insecure:
            _warn_insecure_once(host)
            ctx = _build_insecure_ssl_context()
            imap = imaplib.IMAP4_SSL(host, port, ssl_context=ctx, timeout=timeout)
        else:
            imap = imaplib.IMAP4_SSL(host, port, timeout=timeout)
        imap.login(username, password)

        debug = (
            getattr(args_or_creds, "debug", False)
            if not isinstance(args_or_creds, dict)
            else False
        )
        if debug:
            io.echo(
                f"imap_lib.connect_cyrus: Connected to {host}:{port}",
                level="debug",
            )

        return imap

    except imaplib.IMAP4.error as e:
        io.echo(f"imap_lib.connect_cyrus: IMAP login failed: {e}", level="error")
        return None
    except Exception as e:
        io.echo(
            f"imap_lib.connect_cyrus: Connection failed: {e}",
            level="error",
        )
        return None


def select_mailbox(
    imap: imaplib.IMAP4_SSL,
    mailbox_name: str,
    readonly: bool = True,
) -> bool:
    """
    Select a mailbox on the IMAP server.

    Args:
        imap: Connected IMAP4_SSL object
        mailbox_name: Mailbox name (e.g., 'shared/support@example.com')
        readonly: If True, open read-only

    Returns:
        True on success, False on error
    """
    try:
        status, response = imap.select(mailbox_name, readonly=readonly)
        if status != "OK":
            io.echo(
                f"imap_lib.select_mailbox: Failed to select {mailbox_name}: {response}",
                level="error",
            )
            return False
        return True
    except Exception as e:
        io.echo(
            f"imap_lib.select_mailbox[{mailbox_name}]: {e}",
            level="error",
        )
        return False


def get_all_uids(imap: imaplib.IMAP4_SSL) -> Set[int]:
    """
    Get all message UIDs in currently selected mailbox.

    Args:
        imap: Connected IMAP4_SSL object (mailbox must be selected)

    Returns:
        Set of UIDs, empty set on error
    """
    try:
        status, data = imap.uid("SEARCH", None, "ALL")
        if status != "OK":
            return set()

        if not data or not data[0]:
            return set()

        uids = set()
        for uid_str in data[0].split():
            try:
                uids.add(int(uid_str))
            except ValueError:
                pass

        return uids

    except Exception as e:
        io.echo(f"imap_lib.get_all_uids: {e}", level="error")
        return set()


def get_message_flags(imap: imaplib.IMAP4_SSL, uid: int) -> Set[str]:
    """
    Get flags for a message by UID.

    Args:
        imap: Connected IMAP4_SSL object
        uid: Message UID

    Returns:
        Set of flag strings (e.g., {'\\Seen', '\\Flagged', 'ClaimedBy_a3f9k2m1'})
    """
    try:
        status, data = imap.uid("FETCH", str(uid), "FLAGS")
        if status != "OK" or not data:
            return set()

        # Parse FLAGS response: b'123 (FLAGS (\\Seen \\Flagged ClaimedBy_a3f9k2m1))'
        flags_str = data[0].decode("utf-8") if isinstance(data[0], bytes) else data[0]

        # Extract the FLAGS section: find the inner parentheses containing actual flags
        # Response format: "uid (FLAGS (flag1 flag2 flag3))"
        # We need to find the innermost parentheses

        if "FLAGS" not in flags_str:
            return set()

        # Find first ( after FLAGS
        flags_idx = flags_str.find("FLAGS")
        if flags_idx == -1:
            return set()

        # Find the opening paren after FLAGS
        paren_start = flags_str.find("(", flags_idx)
        if paren_start == -1:
            return set()

        # Find matching closing paren
        paren_count = 0
        paren_end = -1
        for i in range(paren_start, len(flags_str)):
            if flags_str[i] == "(":
                paren_count += 1
            elif flags_str[i] == ")":
                paren_count -= 1
                if paren_count == 0:
                    paren_end = i
                    break

        if paren_end == -1:
            return set()

        flags_content = flags_str[paren_start + 1 : paren_end].strip()
        if not flags_content:
            return set()

        return set(flags_content.split())

    except Exception as e:
        io.echo(f"imap_lib.get_message_flags[{uid}]: {e}", level="error")
        return set()


def get_message_headers(
    imap: imaplib.IMAP4_SSL,
    uid: int,
) -> Dict[str, Any]:
    """
    Fetch and parse message headers for a message by UID.

    Returns dict with keys: message_id, from_addr, subject, date

    Args:
        imap: Connected IMAP4_SSL object
        uid: Message UID

    Returns:
        Dict with parsed headers, empty dict on error
    """
    try:
        status, data = imap.uid("FETCH", str(uid), "RFC822.HEADER")
        if status != "OK" or not data:
            return {}

        # Parse email header
        raw_headers = data[0][1] if isinstance(data[0], tuple) else data[0]
        msg = email.message_from_bytes(raw_headers)

        return {
            "message_id": msg.get("Message-ID", ""),
            "from_addr": msg.get("From", ""),
            "subject": msg.get("Subject", ""),
            "date": msg.get("Date", ""),
        }

    except Exception as e:
        io.echo(f"imap_lib.get_message_headers[{uid}]: {e}", level="error")
        return {}


def detect_new_messages(
    current_uids: Set[int],
    stored_uids: Set[int],
) -> Set[int]:
    """
    Detect messages that are new (in current but not stored).

    Args:
        current_uids: UIDs from current mailbox state
        stored_uids: UIDs from last known state

    Returns:
        Set of new UIDs
    """
    return current_uids - stored_uids


def detect_deleted_messages(
    current_uids: Set[int],
    stored_uids: Set[int],
) -> Set[int]:
    """
    Detect messages that were deleted (in stored but not current).

    Args:
        current_uids: UIDs from current mailbox state
        stored_uids: UIDs from last known state

    Returns:
        Set of deleted UIDs
    """
    return stored_uids - current_uids


def detect_flag_changes(
    current_flags: Set[str],
    stored_flags: Set[str],
) -> Tuple[Set[str], Set[str]]:
    """
    Detect flag changes between two flag sets.

    Args:
        current_flags: Current flags on message
        stored_flags: Previously stored flags

    Returns:
        Tuple of (added_flags, removed_flags)
    """
    added = current_flags - stored_flags
    removed = stored_flags - current_flags
    return added, removed


__all__ = [
    "connect_cyrus",
    "select_mailbox",
    "get_all_uids",
    "get_message_flags",
    "get_message_headers",
    "detect_new_messages",
    "detect_deleted_messages",
    "detect_flag_changes",
]
