# postoffice/services/mailbox_poller.py
# Background poller: runs an asyncio task that periodically checks each
# configured mailbox for new mail and fires notifications.

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .config import MailboxConfig, load_mailboxes
from . import imap_client as svc_imap
from . import notification

logger = logging.getLogger(__name__)


class MailboxPoller:
    """Async background poller for one or more mailboxes."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._enabled: bool = self.config.get("enabled", False)
        self._poll_interval: int = self.config.get("poll_interval", 30)
        self._mailboxes: List[MailboxConfig] = load_mailboxes(self.config)
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def mailboxes(self) -> List[MailboxConfig]:
        return list(self._mailboxes)

    def start(self) -> None:
        """Start the background polling task."""
        if not self._enabled:
            logger.info("MailboxPoller: disabled, not starting")
            return
        if self._running:
            logger.warning("MailboxPoller: already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            f"MailboxPoller: started (interval={self._poll_interval}s, "
            f"mailboxes={len(self._mailboxes)})"
        )

    def stop(self) -> None:
        """Stop the background polling task."""
        if not self._running:
            return
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("MailboxPoller: stopped")

    async def _poll_loop(self) -> None:
        """Main loop: poll all mailboxes, then sleep."""
        while self._running:
            try:
                await self._poll_all_mailboxes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MailboxPoller._poll_loop: {e}")
            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break

    async def _poll_all_mailboxes(self) -> None:
        """Poll each configured mailbox once."""
        for mb in self._mailboxes:
            try:
                await self._check_mailbox(mb)
            except Exception as e:
                logger.error(f"MailboxPoller._poll_all_mailboxes[{mb.host}]: {e}")

    async def _check_mailbox(self, mb: MailboxConfig) -> None:
        """Check a single mailbox: connect, fetch envelopes, notify."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._check_mailbox_sync, mb
            )
        except Exception as e:
            logger.error(f"MailboxPoller._check_mailbox[{mb.host}]: {e}")

    def _check_mailbox_sync(self, mb: MailboxConfig) -> None:
        """Synchronous IMAP check (runs in executor)."""
        conn = None
        try:
            conn = svc_imap.connect(mb)
            envelopes = svc_imap.fetch_envelopes(conn, limit=5)
            if envelopes:
                notification.notify_new_messages(envelopes)
        except Exception as e:
            logger.error(f"MailboxPoller._check_mailbox_sync[{mb.host}]: {e}")
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
