# MCFeely Notification System Plan

## Overview

Create a simple, extensible system for sending notifications from external systems (IMAP, zoidoffice, empyre, murdermotel) to bbsengine6 users, using the bbsengine6.message transport.

## Current State

The current `bbsengine6.message` transport provides:
- `message.send()` - sends notifications with auto-registration of types
- Urgency levels: `ROUTINE`, `IMPORTANT`, `URGENT`, `CRITICAL`
- Rate limiting per sender/type
- Blocking (recipient can block sender)
- Groups (`@everyone` supported)
- Template variables with simple `{variable}` substitution
- `data` JSONB field for arbitrary system-specific data

## Notification Types (dot notation, registered per-game)

| Source | Type Name | Default Urgency |
|--------|-----------|-----------------|
| IMAP | `imap.message` | ROUTINE |
| zoidoffice | `zoidoffice.claim` | IMPORTANT |
| zoidoffice | `zoidoffice.unclaim` | ROUTINE |
| empyre | `empyre.combat` | URGENT |
| empyre | `empyre.turn` | ROUTINE |
| murdermotel | `mm.died` | CRITICAL |
| murdermotel | `mm.target` | IMPORTANT |

## Implementation Steps

### Step 1: Each game registers its notification types in init code

Example in empyre's init:
```python
# empyre/src/empyre/__init__.py or init.py
from bbsengine6.message import register_type, MessageUrgency

register_type("empyre.combat", MessageUrgency.URGENT, max_per_hour=10)
register_type("empyre.turn", MessageUrgency.ROUTINE, max_per_hour=60)
```

### Step 2: Create template files in bbsengine6 skin

Location: `bbsengine6/skin/tmpl/notify/`
- `notify-empyre-combat.tmpl` - Combat notifications
- `notify-empyre-turn.tmpl` - Turn reminders
- `notify-mm-died.tmpl` - Player death
- `notify-mm-target.tmpl` - Target assigned
- `notify-zoidoffice-claim.tmpl` - Project claimed
- `notify-imap-message.tmpl` - New email

### Step 3: Send notifications from each system

```python
from bbsengine6 import message

# In empyre combat
message.send(
    notification_type="empyre.combat",
    recipients=[player.moniker],
    template="empyre-combat",  # references template file
    template_vars={"attacker": "Barbarian", "result": "won"},
    urgency=MessageUrgency.URGENT
)

# In murdermotel when player dies
message.send(
    notification_type="mm.died",
    recipients=[player.moniker],
    template="mm-died",
    template_vars={"killer": "Rabid Wolf", "score": player.score},
    urgency=MessageUrgency.CRITICAL
)
```

### Step 4: Template format (Smarty)

Example `notify-empyre-combat.tmpl`:
```smarty
{block name="message"}
{labelcolor}Combat Report:{/labelcolor} {valuecolor}{vars.result}{/valuecolor}
Attacker: {vars.attacker}
{if vars.lost_soldiers > 0}Lost {vars.lost_soldiers} soldiers{/if}
{/block}
```

## File Structure

```
bbsengine6/skin/tmpl/notify/
    __init__.py          (optional - makes it a package)
    empyre-combat.tmpl
    empyre-turn.tmpl
    mm-died.tmpl
    mm-target.tmpl
    zoidoffice-claim.tmpl
    zoidoffice-unclaim.tmpl
    imap-message.tmpl
    base.tmpl            (common wrapper, extends notify.tmpl)
```

## Template Resolution

The `message.send()` function needs to resolve `template="empyre-combat"` to the file `notify-empyre-combat.tmpl`. This requires either:

1. **Modify `_render_template()`** in bbsengine6.message to check for template file first, then fall back to string substitution
2. **Add template lookup** in the calling code to pass the rendered message directly

---

# IMAP Notification Implementation

## Architecture

Each BBS user has their own IMAP account to poll, plus one or more shared accounts. Design:

1. **Per-user polling** - Each BBS member with IMAP credentials gets their own poller thread
2. **Shared account polling** - Separate thread(s) for shared IMAP accounts, notifying configured users
3. **Single manager** - One `IMAPNotifyManager` coordinates all pollers

## Database Schema (mcfeely schema)

Create a `mcfeely` schema for notification configuration:

```sql
-- mcfeely schema for notification configuration

CREATE SCHEMA mcfeely;

-- Per-user IMAP accounts
CREATE TABLE mcfeely.imap_account (
    id bigserial PRIMARY KEY,
    moniker text NOT NULL REFERENCES engine.member(moniker) ON DELETE CASCADE,
    host text NOT NULL,
    port int DEFAULT 993,
    username text NOT NULL,
    password text NOT NULL,  -- encrypted
    mailbox text DEFAULT 'INBOX',
    enabled boolean DEFAULT true,
    last_checked timestamptz,
    created_at timestamptz DEFAULT now(),
    UNIQUE(moniker)
);

-- Track last seen UID per account (to avoid re-notifying)
CREATE TABLE mcfeely.imap_last_uid (
    account_id bigint REFERENCES mcfeely.imap_account(id) ON DELETE CASCADE,
    mailbox text NOT NULL,
    last_uid text,
    PRIMARY KEY (account_id, mailbox)
);

-- Indexes
CREATE INDEX idx_imap_account_moniker ON mcfeely.imap_account(moniker);
CREATE INDEX idx_imap_account_enabled ON mcfeely.imap_account(enabled);
```

**Shared accounts** stored in config file (no DB needed).

```python
BBS_NOTIFY = {
    "imap": {
        "check_interval": 60,  # seconds between polls
        "shared_accounts": [
            {
                "name": "shared-inbox",
                "host": "imap.example.com",
                "port": 993,
                "username": "shared@example.com",
                "password": "secret",
                "mailbox": "INBOX",
                "notify_monikers": ["user1", "user2", "@everyone"],  # BBS monikers to notify
            },
        ],
    },
}
```

## Implementation

`bbsengine6/py/src/bbsengine6/imapnotify.py`:

```python
"""IMAP notification poller - polls multiple IMAP accounts and creates bbsengine6 notifications."""

import threading
import time
import imaplib
import email
from dataclasses import dataclass
from typing import Optional
import logging

from . import message

logger = logging.getLogger("bbsengine6.imapnotify")


@dataclass
class IMAPAccount:
    """Single IMAP account configuration."""
    moniker: str  # BBS moniker (empty for shared accounts)
    host: str
    port: int = 993
    username: str
    password: str
    mailbox: str = "INBOX"
    notify_monikers: list[str] = None  # For shared accounts: who to notify


class IMAPPoller(threading.Thread):
    """Thread that polls a single IMAP account."""

    def __init__(self, account: IMAPAccount, check_interval: int = 60):
        super().__init__(daemon=True, name=f"IMAPPoller-{account.moniker or account.username}")
        self.account = account
        self.check_interval = check_interval
        self._running = False
        self._last_seen_uid: Optional[str] = None

    def run(self):
        self._running = True
        while self._running:
            try:
                self._check_imap()
            except Exception as e:
                logger.error(f"IMAP poll error for {self.account.username}: {e}")

            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

    def stop(self):
        self._running = False

    def _check_imap(self):
        """Check IMAP account for new messages."""
        try:
            mail = imaplib.IMAP4_SSL(self.account.host, self.account.port)
            mail.login(self.account.username, self.account.password)
            mail.select(self.account.mailbox)

            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                return

            for uid in messages[0].split():
                if self._last_seen_uid and uid <= self._last_seen_uid:
                    continue

                status, msg_data = mail.fetch(uid, "(RFC822)")
                if status != "OK":
                    continue

                msg = email.message_from_bytes(msg_data[0][1])
                from_addr = email.utils.parseaddr(msg.get("From", ""))[1]
                subject = msg.get("Subject", "(no subject)")
                date = msg.get("Date", "")

                # Determine recipients
                if self.account.moniker:
                    # Per-user account: notify the owner
                    recipients = [self.account.moniker]
                else:
                    # Shared account: notify configured monikers
                    recipients = self.account.notify_monikers or []

                for moniker in recipients:
                    message.send(
                        notification_type="imap.message",
                        recipients=[moniker],
                        template="imap-message",
                        template_vars={"from": from_addr, "subject": subject, "date": date},
                    )

                self._last_seen_uid = uid

            mail.logout()
        except Exception as e:
            logger.error(f"IMAP check failed: {e}")


class IMAPNotifyManager:
    """Manages IMAP polling threads for all accounts."""

    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self._pollers: list[IMAPPoller] = []
        self._running = False

    def add_user_account(self, moniker: str, host: str, port: int, username: str, password: str, mailbox: str = "INBOX"):
        """Add a per-user IMAP account."""
        account = IMAPAccount(moniker=moniker, host=host, port=port, username=username, password=password, mailbox=mailbox)
        poller = IMAPPoller(account, self.check_interval)
        self._pollers.append(poller)

    def add_shared_account(self, name: str, host: str, port: int, username: str, password: str, mailbox: str, notify_monikers: list[str]):
        """Add a shared IMAP account."""
        account = IMAPAccount(moniker="", host=host, port=port, username=username, password=password, mailbox=mailbox, notify_monikers=notify_monikers)
        poller = IMAPPoller(account, self.check_interval)
        self._pollers.append(poller)

    def start(self):
        """Start all poller threads."""
        self._running = True
        for poller in self._pollers:
            poller.start()
        logger.info(f"Started {len(self._pollers)} IMAP poller threads")

    def stop(self):
        """Stop all poller threads."""
        self._running = False
        for poller in self._pollers:
            poller.stop()
        for poller in self._pollers:
            poller.join(timeout=5)


# Global manager instance
_manager: Optional[IMAPNotifyManager] = None


def init_from_config(config: dict, member_accounts: list[dict]) -> None:
    """Initialize IMAP notifier from config.
    
    Args:
        config: BBS_NOTIFY.imap config dict with check_interval and shared_accounts
        member_accounts: List of dicts with imap credentials from mcfeely.imap_account
    """
    global _manager
    
    check_interval = config.get("check_interval", 60)
    _manager = IMAPNotifyManager(check_interval)

    # Add per-user accounts
    for member in member_accounts:
        if member.get("enabled"):
            _manager.add_user_account(
                moniker=member["moniker"],
                host=member["host"],
                port=member.get("port", 993),
                username=member["username"],
                password=member["password"],
                mailbox=member.get("mailbox", "INBOX"),
            )

    # Add shared accounts
    for shared in config.get("shared_accounts", []):
        _manager.add_shared_account(
            name=shared["name"],
            host=shared["host"],
            port=shared.get("port", 993),
            username=shared["username"],
            password=shared["password"],
            mailbox=shared.get("mailbox", "INBOX"),
            notify_monikers=shared["notify_monikers"],
        )

    _manager.start()


def stop():
    """Stop all IMAP pollers."""
    global _manager
    if _manager:
        _manager.stop()
```

## Startup Integration

In BBS startup (e.g., `bbsengine6/console/__main__.py`):

```python
from bbsengine6 import imapnotify

def main():
    # ... existing code ...
    
    # Start IMAP notification polling
    config = get_site_config()  # your site's config function
    imap_config = config.get("BBS_NOTIFY", {}).get("imap", {})
    
    # Get member IMAP accounts from mcfeely schema
    member_accounts = db.query("""
        SELECT moniker, host, port, username, password, mailbox, enabled
        FROM mcfeely.imap_account WHERE enabled = true
    """)
    
    imapnotify.init_from_config(imap_config, member_accounts)
    
    # ... rest of BBS ...
```

## No changes to getch()

The existing notification system in `getch()` already:
- Checks `notify.count(moniker)` on each keypress
- Emits bell when notifications exist
- Shows pending notifications on F2

The IMAP poller simply adds more notifications to the same queue via `message.send()`.

---

## Questions/Notes

1. **Template location**: Templates live in `bbsengine6/skin/tmpl/notify/`

2. **Missing templates**: If a type is sent but no template file exists, fall back to simple string substitution

3. **Template storage**: Template names stored in DB (`bbsengine6.message` payload field), template files on disk

4. **Existing types**: Do not migrate existing notification types (like `link-approved`) to new dot notation

5. **IMAP credentials**: Stored in mcfeely.imap_account table, password encrypted

6. **User mapping**: 
   - Per-user accounts: notify the BBS moniker that owns the IMAP account
   - Shared accounts: notify configured monikers or @everyone group