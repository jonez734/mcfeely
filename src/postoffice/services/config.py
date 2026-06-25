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
    ):
        self.host = host
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self.use_ssl = use_ssl
        self.port = port or (993 if use_ssl else 143)


def load_mailboxes(config: Optional[Dict[str, Any]] = None) -> List[MailboxConfig]:
    """Build MailboxConfig objects from a config dict.

    Args:
        config: Dict with a "mailboxes" key holding a list of dicts
            (each: host, username, password, mailbox?, use_ssl?, port?).
            If None, returns an empty list.
    """
    if not config:
        return []
    mailboxes: List[MailboxConfig] = []
    for mb in config.get("mailboxes", []):
        mailboxes.append(
            MailboxConfig(
                host=mb.get("host", ""),
                username=mb.get("username", ""),
                password=mb.get("password", ""),
                mailbox=mb.get("mailbox", "INBOX"),
                use_ssl=mb.get("use_ssl", True),
                port=mb.get("port"),
            )
        )
    return mailboxes
