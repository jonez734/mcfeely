# postoffice/services/config.py
# Mailbox configuration: dataclass + loader.

from typing import Any, Dict, List, Optional


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
        recipients: Optional[List[str]] = None,
        accept_self_signed: bool = True,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self.use_ssl = use_ssl
        self.port = port or (993 if use_ssl else 143)
        self.accept_self_signed = accept_self_signed
        # BBS monikers and/or "@<group>" strings that should receive a
        # notification when new mail arrives in this mailbox. None
        # means fall back to the default ("@everyone"); an empty list
        # means "don't notify anyone" (the poller still runs but
        # produces no notifications).
        self.recipients = recipients


def load_mailboxes(config: Optional[Dict[str, Any]] = None) -> List[MailboxConfig]:
    """Build MailboxConfig objects from a config dict.

    Args:
        config: Dict with a "mailboxes" key holding a list of dicts
            (each: host, username, password, mailbox?, use_ssl?,
            port?, recipients?, accept_self_signed?). ``recipients`` is
            optional; when absent the MailboxConfig defaults to ``None``
            (which signals the notifier to use the @everyone fallback).
            ``accept_self_signed`` defaults to ``True`` so self-signed
            local Cyrus certs work out of the box; set it to ``False``
            in production when you want strict CA verification. If
            None, returns an empty list.
    """
    if not config:
        return []
    mailboxes: List[MailboxConfig] = []
    for mb in config.get("mailboxes", []):
        recipients = mb.get("recipients")
        if recipients is not None and not isinstance(recipients, list):
            raise ValueError(
                f"mailbox {mb.get('username', '?')!r}: "
                "'recipients' must be a list of monikers/groups"
            )
        mailboxes.append(
            MailboxConfig(
                host=mb.get("host", ""),
                username=mb.get("username", ""),
                password=mb.get("password", ""),
                mailbox=mb.get("mailbox", "INBOX"),
                use_ssl=mb.get("use_ssl", True),
                port=mb.get("port"),
                recipients=recipients,
                accept_self_signed=mb.get("accept_self_signed", True),
            )
        )
    return mailboxes
