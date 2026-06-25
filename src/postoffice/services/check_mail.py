# postoffice/services/check_mail.py
# On-demand mail check: count UNSEEN across all configured mailboxes.

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .config import MailboxConfig, load_mailboxes
from . import imap_client as svc_imap

logger = logging.getLogger(__name__)


async def check_mail(
    config: Optional[Dict[str, Any]] = None, moniker: str = ""
) -> Dict[str, Any]:
    """On-demand mail check.

    Iterates configured mailboxes and returns a result dict:
        {
            "success": bool,
            "mailboxes_checked": int,
            "total_unread": int,
            "errors": [str, ...],
        }
    """
    mailboxes: List[MailboxConfig] = load_mailboxes(config)
    result: Dict[str, Any] = {
        "success": False,
        "mailboxes_checked": 0,
        "total_unread": 0,
        "errors": [],
    }
    for mb in mailboxes:
        result["mailboxes_checked"] += 1
        try:
            count = await asyncio.get_event_loop().run_in_executor(
                None, svc_imap.count_unseen, mb
            )
            result["total_unread"] += count
        except Exception as e:
            result["errors"].append(f"{mb.host}: {e}")
            logger.error(f"check_mail[{mb.host}]: {e}")
    result["success"] = True
    return result
