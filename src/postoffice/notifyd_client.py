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


def is_event_enabled(args, mailbox_name: str, event_type: str, conn=None) -> bool:
    """
    Check if event is enabled for mailbox via postoffice.notification_config.
    Defaults to True if no config exists (no config = all events enabled).
    """
    if conn is None:
        return True

    try:
        with database.cursor(conn) as cur:
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


# --- Event Routing ---


def get_routing_rules(
    args,
    mailbox_name: str,
    event_type: str,
    actor_moniker: Optional[str] = None,
    conn=None,
) -> List[Dict[str, Any]]:
    """
    Get matching routing rules for an event using SQL LIKE pattern matching.

    Matches actual mailbox name against patterns in database using SQL LIKE.
    For actor_moniker, supports:
    - Exact match (e.g., 'alice')
    - Pattern match (e.g., 'alice%' matches 'alice', 'alice_bot', etc.)
    - NULL for any actor

    Returns list of dicts with:
    - recipient_moniker: who gets notified
    - notification_type: template type for engine.__notify
    - urgency: ROUTINE, IMPORTANT, URGENT, CRITICAL
    - delivery_method: 'engine' (engine.__notify) or future: 'email', 'chat'
    """
    if conn is None:
        return []

    try:
        with database.cursor(conn) as cur:
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


# --- Message Rendering ---


def render_event_message(
    event_type: str, actor_moniker: Optional[str], event_data: Dict[str, Any]
) -> str:
    """Render human-readable message for event."""
    if event_type == "message-claimed":
        uid = event_data.get("message_uid", "?")
        return f"{actor_moniker} claimed message #{uid}"
    elif event_type == "message-unclaimed":
        uid = event_data.get("message_uid", "?")
        return f"{actor_moniker} unclaimed message #{uid}"
    elif event_type == "message-new":
        from_addr = event_data.get("from", "unknown")
        subject = event_data.get("subject", "(no subject)")
        return f"New message from {from_addr}: {subject}"
    elif event_type == "message-flagged":
        flag = event_data.get("flag_name", "?")
        added = event_data.get("added", True)
        action = "set" if added else "cleared"
        return f"{actor_moniker} {action} flag {flag}"
    elif event_type == "message-deleted":
        uid = event_data.get("message_uid", "?")
        return f"Message #{uid} deleted"
    else:
        return f"Event: {event_type}"


# --- Event Firing ---


def fire_event(
    args,
    mailbox_name: str,
    event_type: str,
    event_data: Dict[str, Any],
    actor_moniker: Optional[str] = None,
    conn=None,
    close_conn=False,
) -> bool:
    """
    Fire an event and route to recipients via engine.__notify.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name (e.g., 'shared/support@machine1.example.com')
        event_type: Event type (message-new, message-claimed, etc.)
        event_data: Event payload (dict, will be JSON-serialized)
        actor_moniker: User who triggered event (optional)
        conn: Database connection (optional, will create if not provided)
        close_conn: Close connection after use (if we created it)

    Returns: True on success, False on error
    """
    should_close = close_conn

    # Create connection if not provided
    if conn is None:
        try:
            conn = database.connect(args, dbname=args.databasename)
            should_close = True
        except Exception as e:
            io.echo(f"notifyd_client.fire_event.120: {e}", level="error")
            return False

    try:
        # Check if event is enabled for this mailbox
        if not is_event_enabled(args, mailbox_name, event_type, conn=conn):
            if getattr(args, "debug", False):
                io.echo(
                    f"notifyd_client.fire_event: event disabled: {mailbox_name} / {event_type}",
                    level="debug",
                )
            return True  # Not an error, just disabled

        # Get routing rules
        rules = get_routing_rules(
            args, mailbox_name, event_type, actor_moniker, conn=conn
        )

        if not rules:
            if getattr(args, "debug", False):
                io.echo(
                    f"notifyd_client.fire_event: no routing rules: {mailbox_name} / {event_type}",
                    level="debug",
                )
            return True  # No routes = success (nothing to deliver)

        # Fire event for each recipient
        event_data_json = json.dumps(event_data)
        rendered_message = render_event_message(event_type, actor_moniker, event_data)
        failcount = 0

        for rule in rules:
            try:
                # Insert into engine.__notify
                with database.cursor(conn) as cur:
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
                        f"notifyd_client: fired {event_type} to {rule['recipient_moniker']}",
                        level="debug",
                    )

            except Exception as e:
                io.echo(
                    f"notifyd_client.fire_event.200: failed to fire event: {e}",
                    level="error",
                )
                failcount += 1

        conn.commit()
        return failcount == 0

    finally:
        if should_close and conn:
            try:
                conn.close()
            except Exception:
                pass
