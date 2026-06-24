# postoffice/service.py
# Postoffice service - polls IMAP servers for new email and notifies users
# (Moved from casino/services/postoffice.py)

import asyncio
import imaplib
import logging
from typing import Any, Dict, List, Optional

from .config import get_postoffice_config
from bbsengine6.notify import send as message_send

logger = logging.getLogger(__name__)

POSTOFFICE_CHANNEL = "postoffice:check_mail"


class MailboxConfig:
    """Configuration for a single mailbox to monitor."""
    
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        mailbox: str = "INBOX",
        use_ssl: bool = True,
        port: Optional[int] = None,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self.use_ssl = use_ssl
        self.port = port or (993 if use_ssl else 143)


class PostofficeService:
    """Service that polls IMAP servers for new email and notifies users."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or get_postoffice_config()
        self._enabled = self.config.get("enabled", False)
        self._poll_interval = self.config.get("poll_interval", 30)
        self._mailboxes: List[MailboxConfig] = []
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
        self._load_mailboxes()
    
    def _load_mailboxes(self) -> None:
        """Load mailbox configurations from config."""
        mailboxes = self.config.get("mailboxes", [])
        for mb in mailboxes:
            try:
                self._mailboxes.append(MailboxConfig(
                    host=mb.get("host", ""),
                    username=mb.get("username", ""),
                    password=mb.get("password", ""),
                    mailbox=mb.get("mailbox", "INBOX"),
                    use_ssl=mb.get("use_ssl", True),
                    port=mb.get("port"),
                ))
            except Exception as e:
                logger.error(f"Failed to load mailbox config: {e}")
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    @property
    def poll_interval(self) -> int:
        return self._poll_interval
    
    def start(self) -> None:
        """Start the background polling task."""
        if not self._enabled:
            logger.info("Postoffice service is disabled")
            return
        
        if self._running:
            logger.warning("Postoffice service already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"Postoffice service started (interval: {self._poll_interval}s)")
    
    def stop(self) -> None:
        """Stop the background polling task."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Postoffice service stopped")
    
    async def _poll_loop(self) -> None:
        """Background loop that polls mailboxes at intervals."""
        while self._running:
            try:
                await self._poll_all_mailboxes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")
            
            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
    
    async def _poll_all_mailboxes(self) -> None:
        """Poll all configured mailboxes for new email."""
        for mailbox in self._mailboxes:
            try:
                await self._check_mailbox(mailbox)
            except Exception as e:
                logger.error(f"Error checking mailbox {mailbox.host}: {e}")
    
    async def _check_mailbox(self, mailbox: MailboxConfig) -> None:
        """Check a single mailbox for new messages."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._check_mailbox_sync, mailbox
            )
        except Exception as e:
            logger.error(f"Mailbox check failed: {e}")
    
    def _check_mailbox_sync(self, mailbox: MailboxConfig) -> None:
        """Synchronous IMAP check (runs in executor)."""
        try:
            if mailbox.use_ssl:
                conn = imaplib.IMAP4_SSL(mailbox.host, mailbox.port)
            else:
                conn = imaplib.IMAP4(mailbox.host, mailbox.port)
            
            conn.login(mailbox.username, mailbox.password)
            conn.select(mailbox.mailbox)
            
            typ, data = conn.search(None, "UNSEEN")
            if typ == "OK":
                unseen_count = len(data[0].split())
                if unseen_count > 0:
                    logger.info(f"Found {unseen_count} unread messages in {mailbox.host}")
                    self._notify_new_messages(conn, mailbox, unseen_count)
            
            conn.close()
            conn.logout()
            
        except Exception as e:
            logger.error(f"IMAP error for {mailbox.host}: {e}")
    
    def _notify_new_messages(
        self,
        conn: imaplib.IMAP4,
        mailbox: MailboxConfig,
        count: int,
    ) -> None:
        """Send notifications for new messages."""
        try:
            typ, data = conn.search(None, "UNSEEN")
            if typ != "OK":
                return
            
            message_ids = data[0].split()[:5]
            
            for msg_id in message_ids:
                try:
                    typ, msg_data = conn.fetch(msg_id, "(ENVELOPE)")
                    if typ != "OK":
                        continue
                    
                    envelope = msg_data[0][1]
                    self._process_message_envelope(envelope, mailbox)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        
        except Exception as e:
            logger.error(f"Error notifying new messages: {e}")
    
    def _process_message_envelope(
        self,
        envelope: bytes,
        mailbox: MailboxConfig,
    ) -> None:
        """Process a message envelope and send notification."""
        try:
            from email.parser import BytesParser
            from email.policy import default
            
            parser = BytesParser(policy=default)
            msg = parser.parsebytes(envelope)
            
            sender = msg.get("From", "Unknown")
            subject = msg.get("Subject", "No Subject")
            
            if msg.is_multipart():
                body = ""
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True)
                        if body:
                            body = body.decode("utf-8", errors="ignore")
                            break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")
                else:
                    body = ""
            
            preview = body[:500] if body else ""
            
            notification_content = f"From: {sender}\nSubject: {subject}\n\n{preview}"
            
            message_send(
                notification_type="postoffice.email",
                recipients=["@everyone"],
                template=notification_content,
                sender_moniker="postoffice",
            )
            
        except Exception as e:
            logger.error(f"Error processing envelope: {e}")
    
    async def handle_check_mail(self, moniker: str) -> Dict[str, Any]:
        """Handle manual mail check request (Mode B).
        
        Args:
            moniker: The user requesting the check
            
        Returns:
            Dict with check results
        """
        results = {
            "success": False,
            "mailboxes_checked": 0,
            "total_unread": 0,
            "errors": [],
        }
        
        for mailbox in self._mailboxes:
            results["mailboxes_checked"] += 1
            try:
                unread = await asyncio.get_event_loop().run_in_executor(
                    None, self._check_mailbox_count, mailbox
                )
                results["total_unread"] += unread
            except Exception as e:
                results["errors"].append(f"{mailbox.host}: {str(e)}")
        
        results["success"] = True
        return results
    
    def _check_mailbox_count(self, mailbox: MailboxConfig) -> int:
        """Get unread message count for a mailbox."""
        try:
            if mailbox.use_ssl:
                conn = imaplib.IMAP4_SSL(mailbox.host, mailbox.port)
            else:
                conn = imaplib.IMAP4(mailbox.host, mailbox.port)
            
            conn.login(mailbox.username, mailbox.password)
            conn.select(mailbox.mailbox)
            
            typ, data = conn.search(None, "UNSEEN")
            count = len(data[0].split()) if typ == "OK" else 0
            
            conn.logout()
            return count
            
        except Exception as e:
            logger.error(f"Error counting messages: {e}")
            return 0


_service_instance: Optional[PostofficeService] = None


def get_postoffice_service(config: Optional[Dict[str, Any]] = None) -> PostofficeService:
    """Get the singleton postoffice service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = PostofficeService(config)
    return _service_instance


def start_postoffice_service() -> None:
    """Start the postoffice service."""
    service = get_postoffice_service()
    service.start()


def stop_postoffice_service() -> None:
    """Stop the postoffice service."""
    global _service_instance
    if _service_instance:
        _service_instance.stop()
        _service_instance = None
