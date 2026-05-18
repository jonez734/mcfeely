# notifyd_client.py
# Integration layer for mcfeely event firing and notification routing.
# Fires events to engine.__notify and routes based on postoffice.notification_routing rules.

import json
import os
import hmac
import hashlib
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from bbsengine6 import database, io


# --- Configuration ---

def _get_obfuscate_secret(args) -> Optional[str]:
    """
    Get obfuscation secret from environment or args.
    Priority:
    1. MCFEELY_OBFUSCATE_SECRET environment variable
    2. args.databasepassword (if available)
    3. None (fall back to plain text)
    """
    secret = os.environ.get("MCFEELY_OBFUSCATE_SECRET")
    if secret:
        return secret
    if hasattr(args, "databasepassword") and args.databasepassword:
        return args.databasepassword
    return None


# --- Cyrus Flag Manager ---

class CyrusFlagManager:
    """Utility for managing Cyrus custom claim flags with obfuscation."""

    @staticmethod
    def obfuscate_moniker(moniker: str, secret: Optional[str] = None) -> str:
        """
        Generate obfuscated flag suffix from moniker.
        Uses HMAC-SHA256(moniker, secret), truncated to 8 hex chars.
        
        Returns: 8-character hex string
        """
        if not secret:
            # Fall back to plain text (backward compat)
            return moniker
        
        h = hmac.new(
            secret.encode("utf-8"),
            moniker.encode("utf-8"),
            hashlib.sha256
        )
        return h.hexdigest()[:8]

    @staticmethod
    def format_flag(moniker: str, secret: Optional[str] = None) -> str:
        """
        Convert moniker to Cyrus custom flag name.
        
        Examples:
            Plain: alice → ClaimedByAlice
            Obfuscated: alice → ClaimedBy_a3f9k2m1
        """
        obfuscated = CyrusFlagManager.obfuscate_moniker(moniker, secret)
        if obfuscated == moniker:
            # Plain text case
            return f"ClaimedBy{moniker.capitalize()}"
        else:
            # Obfuscated case
            return f"ClaimedBy_{obfuscated}"

    @staticmethod
    def verify_flag(flag: str, moniker: str, secret: Optional[str] = None) -> bool:
        """
        Verify that a claim flag matches a moniker (for audit/debugging).
        """
        expected = CyrusFlagManager.format_flag(moniker, secret)
        return flag == expected


# --- Notification Configuration ---

@dataclass
class NotificationConfig:
    """Per-mailbox notification event configuration."""
    mailbox_name: str
    enable_new_message_events: bool = True
    enable_claimed_events: bool = True
    enable_flag_change_events: bool = False
    enable_delete_events: bool = False
    imap_poll_interval_seconds: int = 30


class NotificationConfigCache:
    """Load and cache per-mailbox event configuration."""

    def __init__(self):
        self._cache = {}
        self._ttl_seconds = 300  # 5 minute cache

    def is_enabled(
        self, args, mailbox_name: str, event_type: str, **kwargs
    ) -> bool:
        """Check if event is enabled for mailbox."""
        config = self._get_config(args, mailbox_name, **kwargs)
        if not config:
            # Default to enabled if no config
            return True

        if event_type == "message-new":
            return config.enable_new_message_events
        elif event_type == "message-claimed":
            return config.enable_claimed_events
        elif event_type == "message-unclaimed":
            return config.enable_claimed_events
        elif event_type == "message-flagged":
            return config.enable_flag_change_events
        elif event_type == "message-deleted":
            return config.enable_delete_events
        else:
            return True

    def _get_config(
        self, args, mailbox_name: str, **kwargs
    ) -> Optional[NotificationConfig]:
        """Query or retrieve cached config."""
        if mailbox_name in self._cache:
            return self._cache[mailbox_name]

        # Query database
        conn = kwargs.get("conn")
        if conn is None:
            return None

        try:
            with database.cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT enable_new_message_events, enable_claimed_events,
                           enable_flag_change_events, enable_delete_events,
                           imap_poll_interval_seconds
                    FROM postoffice.notification_config
                    WHERE mailbox_name = %s
                    """,
                    [mailbox_name]
                )
                row = cur.fetchone()
                if row:
                    config = NotificationConfig(
                        mailbox_name=mailbox_name,
                        enable_new_message_events=row[0],
                        enable_claimed_events=row[1],
                        enable_flag_change_events=row[2],
                        enable_delete_events=row[3],
                        imap_poll_interval_seconds=row[4]
                    )
                    self._cache[mailbox_name] = config
                    return config
        except Exception as e:
            io.echo(f"notifyd_client.NotificationConfigCache.100: {e}", level="error")
        
        return None


# --- Routing ---

@dataclass
class RoutingRule:
    """Notification routing rule result."""
    id: int
    recipient_moniker: str
    notification_type: str
    urgency: str
    delivery_method: str


class NotificationRouter:
    """Query postoffice.notification_routing rules with pattern matching."""

    @staticmethod
    def get_routes(
        args,
        mailbox_name: str,
        event_type: str,
        actor_moniker: Optional[str] = None,
        **kwargs
    ) -> List[RoutingRule]:
        """
        Get matching routing rules for an event.
        
        Pattern matching:
        - mailbox_name uses SQL LIKE (% and _)
        - event_type can be '*' for all events
        - actor_moniker can be NULL for any actor
        """
        conn = kwargs.get("conn")
        if conn is None:
            return []

        try:
            with database.cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT id, recipient_moniker, notification_type, urgency, delivery_method
                    FROM postoffice.notification_routing
                    WHERE %s LIKE mailbox_name
                      AND (event_type = %s OR event_type = '*')
                      AND (actor_moniker = %s OR actor_moniker IS NULL)
                      AND enabled = TRUE
                    ORDER BY id ASC
                    """,
                    [mailbox_name, event_type, actor_moniker]
                )
                rows = cur.fetchall()
                rules = []
                for row in rows:
                    rule = RoutingRule(
                        id=row[0],
                        recipient_moniker=row[1],
                        notification_type=row[2] or f"mcfeely-{event_type}",
                        urgency=row[3] or "ROUTINE",
                        delivery_method=row[4] or "engine"
                    )
                    rules.append(rule)
                return rules
        except Exception as e:
            io.echo(f"notifyd_client.NotificationRouter.100: {e}", level="error")
        
        return []


# --- Event Firer ---

class EventFirer:
    """Fire notification events to engine.__notify."""

    def __init__(self, args):
        self.args = args
        self.obfuscate_secret = _get_obfuscate_secret(args)
        self.config_cache = NotificationConfigCache()

    def fire_event(
        self,
        mailbox_name: str,
        event_type: str,
        event_data: Dict[str, Any],
        actor_moniker: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Fire an event and route to recipients via engine.__notify.
        
        Args:
            mailbox_name: Mailbox name (e.g., 'shared/support@machine1.example.com')
            event_type: Event type (message-new, message-claimed, etc.)
            event_data: Event payload (dict, will be JSON-serialized)
            actor_moniker: User who triggered event (optional)
            **kwargs: conn=database_connection (optional, will create if not provided)
        """
        conn = kwargs.get("conn")
        should_close = False

        # Create connection if not provided
        if conn is None:
            try:
                pool = kwargs.get("pool")
                if pool is None:
                    pool = database.getpool(self.args, dbname=self.args.databasename)
                conn = database.connect(self.args, pool=pool)
                should_close = True
            except Exception as e:
                io.echo(f"notifyd_client.EventFirer.120: {e}", level="error")
                return False

        try:
            # Check if event is enabled for this mailbox
            if not self.config_cache.is_enabled(self.args, mailbox_name, event_type, conn=conn):
                if self.args.debug:
                    io.echo(
                        f"notifyd_client.EventFirer: event disabled: {mailbox_name} / {event_type}",
                        level="debug"
                    )
                return True  # Not an error, just disabled

            # Get routing rules
            rules = NotificationRouter.get_routes(
                self.args,
                mailbox_name,
                event_type,
                actor_moniker,
                conn=conn
            )

            if not rules:
                if self.args.debug:
                    io.echo(
                        f"notifyd_client.EventFirer: no routing rules: {mailbox_name} / {event_type}",
                        level="debug"
                    )
                return True  # No routes = success (nothing to deliver)

            # Fire event for each recipient
            event_data_json = json.dumps(event_data)
            failcount = 0

            for rule in rules:
                try:
                    # Render message
                    rendered_message = self._render_message(event_type, actor_moniker, event_data)

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
                                rule.notification_type,
                                actor_moniker,
                                rule.notification_type,
                                rendered_message,
                                event_data_json,
                                rule.urgency,
                                True
                            ]
                        )

                    if self.args.debug:
                        io.echo(
                            f"notifyd_client: fired {event_type} to {rule.recipient_moniker}",
                            level="debug"
                        )

                except Exception as e:
                    io.echo(
                        f"notifyd_client.EventFirer.200: failed to fire event: {e}",
                        level="error"
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

    def _render_message(
        self,
        event_type: str,
        actor_moniker: Optional[str],
        event_data: Dict[str, Any]
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
