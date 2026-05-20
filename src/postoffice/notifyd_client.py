# notifyd_client.py
# Integration layer for mcfeely event firing and notification routing.
# Fires events to engine.__notify and routes based on postoffice.notification_routing rules.
# Functional design with helper functions.

import json
import os
import hmac
import hashlib
from typing import Optional, List, Dict, Any

from bbsengine6 import database, io

from . import lib

# Optional: bbsengine6 notify integration (for hybrid transport)
try:
    from bbsengine6 import notify as _notify_module
except ImportError:
    _notify_module = None


# --- Configuration ---


def get_obfuscate_secret(args) -> Optional[str]:
    """
    Get obfuscation secret from environment or args.
    Priority:
    1. MCFREELY_OBFUSCATE_SECRET environment variable
    2. args.databasepassword (if available)
    3. None (fall back to plain text)
    """
    secret = os.environ.get("MCFEELY_OBFUSCATE_SECRET")
    if secret:
        return secret
    if hasattr(args, "databasepassword") and args.databasepassword:
        return args.databasepassword
    return None


# --- Cyrus Flag Operations ---


def obfuscate_moniker(moniker: str, secret: Optional[str] = None) -> str:
    """
    Generate obfuscated flag suffix from moniker.
    Uses HMAC-SHA256(moniker, secret), truncated to 8 hex chars.

    Returns: 8-character hex string (or plain moniker if no secret)
    """
    if not secret:
        return moniker

    h = hmac.new(secret.encode("utf-8"), moniker.encode("utf-8"), hashlib.sha256)
    return h.hexdigest()[:8]


def format_claim_flag(moniker: str, secret: Optional[str] = None) -> str:
    """
    Convert moniker to Cyrus custom claim flag name.

    Examples:
        Plain: alice → ClaimedByAlice
        Obfuscated: alice → ClaimedBy_a3f9k2m1
    """
    obfuscated = obfuscate_moniker(moniker, secret)
    if obfuscated == moniker:
        # Plain text case
        return f"ClaimedBy{moniker.capitalize()}"
    else:
        # Obfuscated case
        return f"ClaimedBy_{obfuscated}"


def verify_claim_flag(flag: str, moniker: str, secret: Optional[str] = None) -> bool:
    """
    Verify that a claim flag matches a moniker (for audit/debugging).
    """
    expected = format_claim_flag(moniker, secret)
    return flag == expected


# --- Event Configuration ---


def is_event_enabled(args, mailbox_name: str, event_type: str, **kwargs) -> bool:
    """
    Check if event is enabled for mailbox via postoffice.notification_config.
    Defaults to True if no config exists (no config = all events enabled).

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name
        event_type: Event type
        **kwargs: Optional - conn (database connection), pool (connection pool)
    """
    use_conn, should_close = lib.get_db_connection(args, **kwargs)

    if use_conn is None:
        return True

    try:
        with database.cursor(use_conn) as cur:
            cur.execute(
                """
                SELECT enable_new_message_events, enable_claimed_events,
                       enable_flag_change_events, enable_delete_events
                FROM postoffice.notification_config
                WHERE mailbox_name = %s
                """,
                [mailbox_name],
            )
            row = cur.fetchone()
            if not row:
                return True  # Default to enabled

            enable_new, enable_claimed, enable_flagged, enable_deleted = row

            if event_type == "message-new":
                return enable_new
            elif event_type in ("message-claimed", "message-unclaimed"):
                return enable_claimed
            elif event_type == "message-flagged":
                return enable_flagged
            elif event_type == "message-deleted":
                return enable_deleted
            else:
                return True
    except Exception as e:
        io.echo(f"notifyd_client.is_event_enabled: {e}", level="error")
        return True
    finally:
        if should_close and use_conn:
            try:
                use_conn.close()
            except Exception:
                pass


# --- Event Routing ---


def get_routing_rules(
    args,
    mailbox_name: str,
    event_type: str,
    actor_moniker: Optional[str] = None,
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    Get matching routing rules for an event using SQL LIKE pattern matching.

    Matches actual mailbox name against patterns in database using SQL LIKE.
    For actor_moniker, supports:
    - Exact match (e.g., 'alice')
    - Pattern match (e.g., 'alice%' matches 'alice', 'alice_bot', etc.)
    - NULL for any actor

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name
        event_type: Event type
        actor_moniker: Optional actor to match against rules
        **kwargs: Optional - conn (database connection), pool (connection pool)

    Returns list of dicts with:
    - recipient_moniker: who gets notified
    - notification_type: template type for engine.__notify
    - urgency: ROUTINE, IMPORTANT, URGENT, CRITICAL
    - delivery_method: 'engine' (engine.__notify) or future: 'email', 'chat'
    """
    use_conn, should_close = lib.get_db_connection(args, **kwargs)

    if use_conn is None:
        return []

    try:
        with database.cursor(use_conn) as cur:
            cur.execute(
                """
                SELECT recipient_moniker, notification_type, urgency, delivery_method
                FROM postoffice.notification_routing
                WHERE %s LIKE mailbox_name
                  AND (event_type = %s OR event_type = '*')
                  AND (%s LIKE actor_moniker OR actor_moniker IS NULL)
                  AND enabled = TRUE
                ORDER BY id ASC
                """,
                [mailbox_name, event_type, actor_moniker],
            )
            rows = cur.fetchall()
            rules = []
            for row in rows:
                rule = {
                    "recipient_moniker": row[0],
                    "notification_type": row[1] or f"mcfeely-{event_type}",
                    "urgency": row[2] or "ROUTINE",
                    "delivery_method": row[3] or "engine",
                }
                rules.append(rule)
            return rules
    except Exception as e:
        io.echo(f"notifyd_client.get_routing_rules: {e}", level="error")
        return []
    finally:
        if should_close and use_conn:
            try:
                use_conn.close()
            except Exception:
                pass


# --- Message Rendering ---

# --- Event Message Templates ---

EVENT_MESSAGE_TEMPLATES = {
    "message-new": "New message from {from}: {subject}",
    "message-claimed": "{actor_moniker} claimed message #{message_uid}",
    "message-unclaimed": "{actor_moniker} unclaimed message #{message_uid}",
    "message-flagged": "{actor_moniker} {action} flag {flag_name}",
    "message-deleted": "Message #{message_uid} deleted",
}


def render_event_message(
    event_type: str, actor_moniker: Optional[str], event_data: Dict[str, Any]
) -> str:
    """
    Render human-readable message for event using template format strings.

    Args:
        event_type: Event type (e.g., 'message-claimed')
        actor_moniker: User who triggered event (optional)
        event_data: Event payload dictionary

    Returns:
        Rendered message string
    """
    # Add actor_moniker to event_data for template formatting
    format_data = dict(event_data)
    if actor_moniker:
        format_data["actor_moniker"] = actor_moniker

    # For message-flagged, compute action field
    if event_type == "message-flagged" and "action" not in format_data:
        added = format_data.get("added", True)
        format_data["action"] = "set" if added else "cleared"

    # Provide defaults for optional fields
    if "subject" not in format_data:
        format_data["subject"] = "(no subject)"
    if "from" not in format_data:
        format_data["from"] = "unknown"
    if "flag_name" not in format_data:
        format_data["flag_name"] = "?"

    # Get template or fall back to generic message
    template = EVENT_MESSAGE_TEMPLATES.get(event_type, f"Event: {event_type}")

    try:
        return template.format(**format_data)
    except KeyError as e:
        # If template formatting fails due to missing keys, return generic message
        return f"Event: {event_type}"


def _fire_event_fallback(
    args,
    mailbox_name: str,
    event_type: str,
    event_data: Dict[str, Any],
    actor_moniker: Optional[str],
    use_conn: Any,
    rendered_message: str,
    rules: List[Dict[str, Any]],
) -> bool:
    """
    Fallback event firing if bbsengine6.notify is not available.

    Direct database insert to engine.__notify (legacy behavior).
    Used only if notify module is not available.
    """
    event_data_json = json.dumps(event_data)
    failcount = 0

    for rule in rules:
        try:
            # Direct insert (legacy behavior)
            with database.cursor(use_conn) as cur:
                cur.execute(
                    """
                    INSERT INTO engine.__notify 
                    (notification_type, sender_moniker, template, rendered_message, 
                     data, urgency, should_persist)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        rule["notification_type"],
                        actor_moniker,
                        rule["notification_type"],
                        rendered_message,
                        event_data_json,
                        rule["urgency"],
                        True,
                    ],
                )

            if getattr(args, "debug", False):
                io.echo(
                    f"notifyd_client: fired {event_type} to {rule['recipient_moniker']} (fallback)",
                    level="debug",
                )

        except Exception as e:
            io.echo(
                f"notifyd_client._fire_event_fallback: {e}",
                level="error",
            )
            failcount += 1

    return failcount == 0


# --- Event Firing ---


def fire_event(
    args,
    mailbox_name: str,
    event_type: str,
    event_data: Dict[str, Any],
    actor_moniker: Optional[str] = None,
    **kwargs,
) -> bool:
    """
    Fire an event and route to recipients via engine.__notify.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name (e.g., 'shared/support@machine1.example.com')
        event_type: Event type (message-new, message-claimed, etc.)
        event_data: Event payload (dict, will be JSON-serialized)
        actor_moniker: User who triggered event (optional)
        **kwargs: Optional - conn (database connection), pool (connection pool)

    Returns: True on success, False on error
    """
    use_conn, should_close = lib.get_db_connection(args, **kwargs)

    if use_conn is None:
        io.echo(
            "notifyd_client.fire_event: no connection or pool provided", level="error"
        )
        return False

    try:
        # Check if event is enabled for this mailbox
        if not is_event_enabled(args, mailbox_name, event_type, conn=use_conn):
            if getattr(args, "debug", False):
                io.echo(
                    f"notifyd_client.fire_event: event disabled: {mailbox_name} / {event_type}",
                    level="debug",
                )
            return True  # Not an error, just disabled

        # Get routing rules
        rules = get_routing_rules(
            args, mailbox_name, event_type, actor_moniker, conn=use_conn
        )

        if not rules:
            if getattr(args, "debug", False):
                io.echo(
                    f"notifyd_client.fire_event: no routing rules: {mailbox_name} / {event_type}",
                    level="debug",
                )
            return True  # No routes = success (nothing to deliver)

        # Render message for notifications
        rendered_message = render_event_message(event_type, actor_moniker, event_data)

        # Fire event for each recipient via bbsengine6.notify.send()
        notify = _notify_module
        if notify is None:
            # Fallback: direct database insert if notify not available
            io.echo(
                "notifyd_client.fire_event: bbsengine6.notify not available, "
                "falling back to direct database insert",
                level="warn",
            )
            return _fire_event_fallback(
                args,
                mailbox_name,
                event_type,
                event_data,
                actor_moniker,
                use_conn,
                rendered_message,
                rules,
            )

        failcount = 0

        for rule in rules:
            try:
                # Use bbsengine6.notify as transport layer
                # This provides rate limiting, recipient expansion, and standardized handling
                notify.send(
                    notification_type=rule["notification_type"],
                    recipients=[rule["recipient_moniker"]],
                    template=rule["notification_type"],
                    template_vars={},  # We render message inline, template vars not used
                    sender_moniker=actor_moniker,
                    data=event_data,
                    urgency=rule["urgency"],
                    should_persist=True,
                    conn=use_conn,
                )

                if getattr(args, "debug", False):
                    io.echo(
                        f"notifyd_client: fired {event_type} to {rule['recipient_moniker']}",
                        level="debug",
                    )

            except Exception as e:
                io.echo(
                    f"notifyd_client.fire_event.200: failed to fire event: {e}",
                    level="error",
                )
                failcount += 1

        use_conn.commit()
        return failcount == 0

    finally:
        if should_close and use_conn:
            try:
                use_conn.close()
            except Exception:
                pass
