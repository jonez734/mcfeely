# imap_monitor.py
# IMAP mailbox monitoring with embedded polling thread.
# Detects new messages, flag changes, and deletions in shared mailboxes.
# Fires corresponding events via notifyd integration.

import threading
import time
import imaplib
from typing import Optional, Dict, Set, List, Any
from dataclasses import dataclass, field

from bbsengine6 import database, io

from . import imap_client, notifyd_client


@dataclass
class MessageState:
    """Track state of a single message."""
    uid: int
    flags: Set[str] = field(default_factory=set)
    message_id: Optional[str] = None
    from_addr: Optional[str] = None
    subject: Optional[str] = None


@dataclass
class MailboxState:
    """Track state of a mailbox."""
    mailbox_name: str
    messages: Dict[int, MessageState] = field(default_factory=dict)
    uidvalidity: Optional[int] = None
    last_poll_time: Optional[float] = None


class IMAPMonitor:
    """
    Monitor shared mailboxes for changes via IMAP IDLE or polling.
    
    Functional approach: uses internal state tracking to detect:
    - New messages (fire message-new event)
    - Flag changes (fire message-flagged event)
    - Message deletions (fire message-deleted event)
    
    Design:
    - Run as background thread or periodic task
    - Poll at intervals defined in postoffice.notification_config
    - Track UIDs and flags per mailbox
    - Handle UID validity changes (mailbox reset)
    - Graceful error handling (continue on connection errors)
    """
    
    def __init__(self, args, poll_interval_seconds: int = 30):
        """
        Initialize monitor.
        
        Args:
            args: bbsengine6 args object
            poll_interval_seconds: Default polling interval (can be overridden per mailbox)
        """
        self.args = args
        self.default_poll_interval = poll_interval_seconds
        self.mailbox_states: Dict[str, MailboxState] = {}
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
    
    def start(self) -> None:
        """Start the monitoring thread."""
        if self.running:
            io.echo("imap_monitor: Already running", level="warn")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        io.echo("imap_monitor: Started background polling thread", level="info")
    
    def stop(self, timeout_seconds: int = 5) -> None:
        """Stop the monitoring thread gracefully."""
        if not self.running:
            return
        
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout_seconds)
            if self.thread.is_alive():
                io.echo("imap_monitor: Thread did not stop within timeout", level="warn")
        
        io.echo("imap_monitor: Stopped", level="info")
    
    def add_mailbox(self, mailbox_name: str) -> None:
        """Register a mailbox for monitoring."""
        with self.lock:
            if mailbox_name not in self.mailbox_states:
                self.mailbox_states[mailbox_name] = MailboxState(mailbox_name=mailbox_name)
                if getattr(self.args, "debug", False):
                    io.echo(f"imap_monitor: Added mailbox {mailbox_name}", level="debug")
    
    def remove_mailbox(self, mailbox_name: str) -> None:
        """Unregister a mailbox from monitoring."""
        with self.lock:
            if mailbox_name in self.mailbox_states:
                del self.mailbox_states[mailbox_name]
                if getattr(self.args, "debug", False):
                    io.echo(f"imap_monitor: Removed mailbox {mailbox_name}", level="debug")
    
    def _run_loop(self) -> None:
        """Main polling loop (runs in background thread)."""
        io.echo("imap_monitor: Polling loop started", level="debug")
        
        while self.running:
            try:
                self._poll_all_mailboxes()
            except Exception as e:
                io.echo(f"imap_monitor._run_loop: {e}", level="error")
            
            # Sleep before next poll
            time.sleep(self.default_poll_interval)
    
    def _poll_all_mailboxes(self) -> None:
        """Poll all registered mailboxes for changes."""
        with self.lock:
            mailboxes = list(self.mailbox_states.keys())
        
        for mailbox_name in mailboxes:
            if not self.running:
                break
            
            try:
                self._poll_mailbox(mailbox_name)
            except Exception as e:
                io.echo(
                    f"imap_monitor._poll_all_mailboxes[{mailbox_name}]: {e}",
                    level="error"
                )
    
    def _poll_mailbox(self, mailbox_name: str) -> None:
        """Poll a single mailbox for changes."""
        # Get poll interval from config
        poll_interval = self._get_poll_interval(mailbox_name)
        
        with self.lock:
            state = self.mailbox_states[mailbox_name]
            last_poll = state.last_poll_time
        
        # Skip if polled recently
        if last_poll and (time.time() - last_poll) < poll_interval:
            return
        
        # Connect to IMAP and check mailbox
        try:
            imap_conn = self._connect_imap()
            if not imap_conn:
                return
            
            try:
                self._check_mailbox(imap_conn, mailbox_name)
            finally:
                try:
                    imap_conn.close()
                except Exception:
                    pass
        
        except Exception as e:
            io.echo(f"imap_monitor._poll_mailbox[{mailbox_name}]: {e}", level="error")
        
        # Update last poll time
        with self.lock:
            state.last_poll_time = time.time()
    
    def _connect_imap(self) -> Optional[imaplib.IMAP4_SSL]:
        """Connect to IMAP server (stub - would use bbsengine6 IMAP config)."""
        # TODO: Implement IMAP connection using bbsengine6 Cyrus configuration
        # For now, return None (graceful degradation)
        return None
    
    def _check_mailbox(self, imap_conn: imaplib.IMAP4_SSL, mailbox_name: str) -> None:
        """Check mailbox for new messages, flag changes, deletions."""
        try:
            # Select mailbox
            status, response = imap_conn.select(mailbox_name, readonly=True)
            if status != "OK":
                io.echo(
                    f"imap_monitor: Failed to select {mailbox_name}: {response}",
                    level="error"
                )
                return
            
            # Get current UIDs
            status, uid_list = imap_conn.uid("SEARCH", "ALL")
            if status != "OK":
                current_uids = set()
            else:
                try:
                    uids_str = uid_list[0].decode("utf-8")
                    current_uids = set(int(uid) for uid in uids_str.split() if uid)
                except (ValueError, AttributeError):
                    current_uids = set()
            
            with self.lock:
                state = self.mailbox_states[mailbox_name]
                old_uids = set(state.messages.keys())
            
            # Detect new messages
            new_uids = current_uids - old_uids
            for uid in new_uids:
                self._handle_new_message(imap_conn, mailbox_name, uid)
            
            # Detect flag changes and deletions
            for uid in (old_uids & current_uids):
                self._handle_flag_changes(imap_conn, mailbox_name, uid)
            
            # Detect deletions
            deleted_uids = old_uids - current_uids
            for uid in deleted_uids:
                self._handle_message_deleted(mailbox_name, uid)
        
        except Exception as e:
            io.echo(f"imap_monitor._check_mailbox[{mailbox_name}]: {e}", level="error")
    
    def _handle_new_message(
        self,
        imap_conn: imaplib.IMAP4_SSL,
        mailbox_name: str,
        uid: int
    ) -> None:
        """Handle newly detected message."""
        try:
            # Fetch message headers
            status, msg_parts = imap_conn.uid("FETCH", str(uid), "(RFC822.HEADER FLAGS)")
            if status != "OK":
                return
            
            message_id = ""
            from_addr = ""
            subject = ""
            flags = set()
            
            # TODO: Parse headers and extract message-id, from, subject
            # TODO: Store message state
            # TODO: Fire message-new event
            
            if getattr(self.args, "debug", False):
                io.echo(
                    f"imap_monitor: New message in {mailbox_name}: #{uid}",
                    level="debug"
                )
        
        except Exception as e:
            io.echo(f"imap_monitor._handle_new_message: {e}", level="error")
    
    def _handle_flag_changes(
        self,
        imap_conn: imaplib.IMAP4_SSL,
        mailbox_name: str,
        uid: int
    ) -> None:
        """Detect and handle flag changes on existing message."""
        try:
            # Fetch current flags
            status, flags_response = imap_conn.uid("FETCH", str(uid), "FLAGS")
            if status != "OK":
                return
            
            # TODO: Parse flags, compare with stored state
            # TODO: Fire message-flagged events for each change
            
        except Exception as e:
            io.echo(f"imap_monitor._handle_flag_changes: {e}", level="error")
    
    def _handle_message_deleted(self, mailbox_name: str, uid: int) -> None:
        """Handle message deletion."""
        try:
            # Fire message-deleted event
            db_conn = database.connect(self.args, dbname=self.args.databasename)
            try:
                imap_client.fire_message_deleted_event(
                    self.args,
                    mailbox_name,
                    uid,
                    db_conn=db_conn
                )
            finally:
                db_conn.close()
            
            # Remove from state
            with self.lock:
                state = self.mailbox_states[mailbox_name]
                if uid in state.messages:
                    del state.messages[uid]
            
            if getattr(self.args, "debug", False):
                io.echo(
                    f"imap_monitor: Message deleted in {mailbox_name}: #{uid}",
                    level="debug"
                )
        
        except Exception as e:
            io.echo(f"imap_monitor._handle_message_deleted: {e}", level="error")
    
    def _get_poll_interval(self, mailbox_name: str) -> int:
        """Get poll interval for mailbox from config."""
        try:
            conn = database.connect(self.args, dbname=self.args.databasename)
            try:
                with database.cursor(conn) as cur:
                    cur.execute(
                        """
                        SELECT imap_poll_interval_seconds
                        FROM postoffice.notification_config
                        WHERE mailbox_name = %s
                        """,
                        [mailbox_name]
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        return row[0]
            finally:
                conn.close()
        except Exception as e:
            io.echo(f"imap_monitor._get_poll_interval: {e}", level="error")
        
        return self.default_poll_interval


# Global monitor instance
_monitor: Optional[IMAPMonitor] = None


def initialize_monitor(args, poll_interval_seconds: int = 30) -> IMAPMonitor:
    """Initialize global IMAP monitor."""
    global _monitor
    _monitor = IMAPMonitor(args, poll_interval_seconds)
    return _monitor


def get_monitor() -> Optional[IMAPMonitor]:
    """Get global IMAP monitor instance."""
    return _monitor


def start_monitor() -> None:
    """Start global IMAP monitor background thread."""
    if _monitor:
        _monitor.start()


def stop_monitor(timeout_seconds: int = 5) -> None:
    """Stop global IMAP monitor background thread."""
    if _monitor:
        _monitor.stop(timeout_seconds)
