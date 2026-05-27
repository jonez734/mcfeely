# Postoffice Codebase - Complete Exploration Summary

This document provides a comprehensive overview of the postoffice module from the mistermcfeely project.

## Quick Navigation

### For Understanding the System
1. **POSTOFFICE_EXPLORATION_SUMMARY.md** (806 lines)
   - Complete module structure and component relationships
   - Detailed explanation of each submodule
   - Key design patterns and architectural decisions
   - Best for: Understanding the full system architecture

2. **POSTOFFICE_ARCHITECTURE_DIAGRAM.md** (577 lines)
   - Visual system architecture with layer diagrams
   - Data flow examples for common operations
   - Component dependencies
   - Best for: Understanding how pieces fit together

3. **POSTOFFICE_QUICK_REFERENCE.md** (727 lines)
   - Quick lookup for functions and API
   - Copy-paste code examples
   - Common workflows
   - Best for: Quick reference while developing

## What is Postoffice?

**Postoffice** is a comprehensive password management system for email authentication in the mistermcfeely BBS platform.

### Purpose
- Manage IMAP/SMTP passwords for BBS members
- Support both personal accounts and shared mailboxes
- Monitor shared mailboxes for new messages
- Fire events for notification systems
- Provide secure encryption with AES-256-GCM

### Key Statistics
- **Total Lines:** ~3,901 Python code
- **Files:** 21 Python modules
- **Main Components:** 10 major subsystems
- **Database Tables:** 7 core tables

---

## Core Concepts

### 1. Single Encryption Key Pattern

All passwords use **ONE** POSTOFFICE_PASSWORD_KEY:
- 32 bytes, AES-256-GCM encryption
- Stored in env var, file, or memory
- Must be identical across all servers

```
POSTOFFICE_PASSWORD_KEY
         ↓
    (Load from priority sources)
    1. POSTOFFICE_PASSWORD_KEY env var
    2. /etc/postoffice/password.key
    3. ~/.postoffice/password.key
    4. ERROR if not found
         ↓
    (Use for AES-256-GCM encryption)
    ├─ Personal account passwords
    ├─ Shared mailbox passwords
    └─ All stored in database
```

### 2. Two Password Types

**Personal Passwords** (engine.__member)
- For individual member's personal email account
- Stored in engine.__member table
- Fields: inbound_password, outbound_password

**Shared Mailbox Passwords** (postoffice tables)
- For team/group email addresses
- Per-member overrides in postoffice.member_mailbox_password
- Default fallback in postoffice.mailbox_password
- Enables flexible access control

### 3. Credential Fallback Logic

When a member accesses a shared mailbox:

```
get_auth_password(mailbox_id=5, member_moniker="alice")
         ↓
Is there a per-member password?
    YES → return decrypted password
    NO  → Is there a shared default?
            YES → return decrypted password
            NO  → ERROR
```

### 4. IMAP Integration

Connect to Cyrus IMAP with automatic credential resolution:

```
connect_cyrus(args, member_moniker="alice", mailbox_id=5)
         ↓
Get IMAP credentials:
  1. Try direct args (highest priority)
  2. Fallback to password system
         ↓
Open IMAP4_SSL connection to Cyrus
```

### 5. Message Claiming with Obfuscation

Members can claim messages in shared mailboxes with optional obfuscation:

```
claim_message(mailbox="shared/support", uid=42, actor="alice")
         ↓
Get obfuscation secret:
  1. MCFEELY_OBFUSCATE_SECRET env var
  2. args.databasepassword
  3. None (plain text)
         ↓
Format claim flag:
  NO secret    → "ClaimedByAlice"
  With secret  → "ClaimedBy_a3f9k2m1" (HMAC-SHA256)
         ↓
Set Cyrus flag on message
         ↓
Fire message-claimed event
```

### 6. Background Monitoring

Detect changes in shared mailboxes automatically:

```
IMAPMonitor.start()
    ↓ (background thread)
    └─ Every 30 seconds (configurable):
        ├─ Poll each monitored mailbox
        ├─ Detect new messages → fire message-new event
        ├─ Detect flag changes → fire message-flagged event
        └─ Detect deletions → fire message-deleted event
    ↓
Events routed via notification_routing rules
    ↓
Handlers execute (email, webhook, etc.)
```

### 7. Event-Driven Architecture

All changes trigger events:

```
Event Types:
  ├─ message-new       (new message in shared mailbox)
  ├─ message-claimed   (member claimed a message)
  ├─ message-unclaimed (claim removed)
  ├─ message-flagged   (message flags changed)
  └─ message-deleted   (message removed)

Event Flow:
  Change Detected
       ↓
  fire_event()
       ↓
  Write to engine.__notify
       ↓
  Query postoffice.notification_routing
       ↓
  Execute matching actions
```

### 8. TUI Interfaces

Three interactive menus provided:

1. **Main Menu** (main.py)
   - [V] Virtual mailbox management
   - [M] Mailbox CRUD operations
   - [Q] Quit

2. **Password Manager** (tui/password_manager.py)
   - Member mode: manage own passwords
   - Sysop mode: manage any member's passwords
   - Set/view/delete personal and shared passwords

3. **Mailbox CRUD** (mailbox.py)
   - List all mailboxes
   - Edit mailbox properties (address, location, etc.)

---

## Architecture Layers

```
┌─────────────────────────────────────────┐
│ USER INTERFACES (TUI/CLI)               │
│ main.py, password_manager.py, __main__.py
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ INITIALIZATION (Encryption Keys)        │
│ startup.py                              │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ PASSWORD MANAGEMENT                     │
│ member_password.py                      │
│ shared_mailbox_password.py              │
│ password_auth.py (fallback logic)       │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ IMAP INTEGRATION                        │
│ imap_lib.py (connect)                   │
│ imap_client.py (operations)             │
│ imap_monitor.py (monitoring)            │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ EVENT SYSTEM                            │
│ notifyd_client.py (firing)              │
│ events.py (types)                       │
│ audit_log.py (logging)                  │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ DATABASE                                │
│ engine.__member (personal passwords)    │
│ postoffice.* (mailboxes, events, etc)   │
└─────────────────────────────────────────┘
```

---

## Key Files Summary

| File | Lines | Purpose |
|------|-------|---------|
| startup.py | 588 | Encryption key management & CLI |
| imap_lib.py | 370 | Cyrus IMAP connection utilities |
| shared_mailbox_password.py | 300 | Shared mailbox password CRUD |
| tui/password_manager.py | 303 | Interactive password management |
| __main__.py | 292 | CLI entry point |
| imap_client.py | 291 | Message claiming operations |
| mailbox.py | 264 | Mailbox CRUD interface |
| member_password.py | 252 | Personal password CRUD |
| password_auth.py | 149 | Auth fallback logic |
| lib.py | 115 | Shared utilities |
| **TOTAL** | **3,901** | **Complete system** |

---

## Database Schema Overview

### engine.__member
Personal account passwords
```sql
inbound_password VARCHAR(ENCRYPTED)
outbound_password VARCHAR(ENCRYPTED)
```

### postoffice.mailbox
Mailbox metadata
```sql
id INT PRIMARY KEY
address VARCHAR (email)
enabled BOOLEAN
maillocation VARCHAR (Cyrus path)
memberid INT
```

### postoffice.member_mailbox_password
Per-member shared mailbox password overrides
```sql
mailbox_id INT FK
member_moniker VARCHAR
password_type ENUM ('inbound', 'outbound')
encrypted_password VARCHAR (AES-256-GCM)
set_by_moniker VARCHAR
created_at TIMESTAMP
updated_at TIMESTAMP
```

### postoffice.mailbox_password
Default shared mailbox password (legacy)
```sql
address VARCHAR FK
kind VARCHAR ('inbound outbound')
password VARCHAR (legacy encrypted format)
```

### postoffice.virtual
Virtual mailbox patterns
```sql
pattern VARCHAR
result VARCHAR (delivery target)
enabled BOOLEAN
```

### postoffice.notification_routing
Event routing rules
```sql
event_type VARCHAR
condition VARCHAR
action VARCHAR
```

### engine.__notify
Event log
```sql
event_type VARCHAR
mailbox_name VARCHAR
event_data JSON
created_at TIMESTAMP
```

---

## Common Operations

### Set a Password
```python
from postoffice import shared_mailbox_password

shared_mailbox_password.set_shared_mailbox_password(
    args,
    mailbox_id=5,
    member_moniker="alice",
    password_type="inbound",
    password="new_password",
    set_by_moniker="sysop"
)
```

### Get a Password (with fallback)
```python
from postoffice.password_auth import get_auth_password

password = get_auth_password(
    args,
    mailbox_id=5,
    member_moniker="alice",
    password_type="inbound",
    requester_moniker="alice"
)
```

### Connect to IMAP
```python
from postoffice.imap_lib import connect_cyrus

conn = connect_cyrus(
    args,
    member_moniker="alice",
    mailbox_id=5
)
```

### Claim a Message
```python
from postoffice.imap_client import claim_message

claim_message(
    args,
    mailbox_name="shared/support@example.com",
    message_uid=42,
    actor_moniker="alice"
)
```

### Start IMAP Monitoring
```python
from postoffice.imap_monitor import IMAPMonitor

monitor = IMAPMonitor(args, poll_interval_seconds=30)
monitor.start()
```

---

## Startup/Initialization

### Generate a New Key
```bash
python -m postoffice startup-generate
```

### Install Key to System
```bash
python -m postoffice startup-install
```

### Check Key Setup
```bash
python -m postoffice startup-check --verbose
```

### Full Initialization
```bash
python -m postoffice startup-init --verbose
```

---

## Integration with bbsengine6

The postoffice module follows bbsengine6 conventions:

```python
# Standard module functions
def init(args, **kw) -> bool
def access(args, op, **kw) -> bool
def buildargs(args, **kw) -> bool
def main(args, **kw)

# invoked from bbsengine6 menu system
# args object provides database connection, current user, etc.
```

---

## Design Patterns Used

### 1. Single Responsibility
Each module handles one concern:
- startup.py → encryption keys only
- member_password.py → personal passwords only
- imap_lib.py → IMAP connections only

### 2. Fallback Pattern
Shared mailbox access tries multiple sources:
- Per-member password first
- Shared default fallback
- Clear error if all sources exhausted

### 3. Event-Driven
Changes trigger events that route to handlers:
- Decouples detection from reaction
- Enables extensibility
- Centralizes logging/auditing

### 4. Connection Pooling
Functions accept optional connections:
- Caller can provide pre-opened connection
- Or connection pool for batching
- Or function creates new connection (slower)

### 5. Obfuscation for Privacy
Claim flags can hide identities:
- Optional HMAC-SHA256 obfuscation
- Deterministic (same member = same hash)
- Verifiable by authorized parties

---

## Security Considerations

1. **Single Key Philosophy**
   - One key for all passwords
   - Simplifies rotation
   - Centralizes key management

2. **File Permissions**
   - Key files must be 0600 (rw-------)
   - Only owner can read
   - System prevents accidental disclosure

3. **AES-256-GCM**
   - Authenticated encryption
   - Detects tampering
   - Industry standard

4. **Permission Checks**
   - Members can only access own passwords
   - Sysops can access any member's
   - Explicit permission checks throughout

5. **Audit Logging**
   - All password operations logged
   - Integrates with bbsengine6 logentry
   - Enables compliance audits

---

## Deployment Checklist

### Before Production
- [ ] Generate POSTOFFICE_PASSWORD_KEY using startup-generate
- [ ] Distribute identical key to all servers
- [ ] Install key to /etc/postoffice/password.key with 0600 permissions
- [ ] Initialize database schema (postoffice tables)
- [ ] Run startup-check --verbose to validate setup
- [ ] Configure notification routing rules
- [ ] Test password encryption/decryption

### During Deployment
- [ ] Start IMAP monitor on dedicated server
- [ ] Verify claim flags working in Cyrus
- [ ] Test message events firing
- [ ] Verify notification routing

### Post-Deployment
- [ ] Monitor audit logs for errors
- [ ] Verify all members can access their passwords
- [ ] Test shared mailbox access
- [ ] Verify event notifications working

---

## Performance Notes

### Encryption
- AES-256-GCM: ~1ms per password encrypt/decrypt
- Consider caching decrypted credentials short-term

### IMAP Monitoring
- Poll interval configurable per mailbox
- Default 30 seconds balances responsiveness and load
- Adjust based on message volume

### Database Queries
- Use connection pooling for batch operations
- Consider indexing on (mailbox_id, member_moniker, password_type)

---

## Related Documentation

In the mistermcfeely project directory:

- **ENCRYPTION_KEY_MANAGEMENT.md** - Key distribution strategies
- **PASSWORD_SYSTEMS_EXPLAINED.md** - Detailed password architecture
- **PASSWORD_SYSTEMS_SUMMARY.md** - Quick password system overview
- **CONN_POOL_PATTERN.md** - Connection pooling details
- **IMAP_DAEMON_INTEGRATION.md** - IMAP service integration

---

## File Locations

All postoffice source code:
```
/home/opencode/data/work/mistermcfeely/src/postoffice/
```

Documentation:
```
/home/opencode/data/work/POSTOFFICE_*.md
```

---

## Questions & Troubleshooting

### "Encryption key not found"
1. Check environment variable: `echo $POSTOFFICE_PASSWORD_KEY`
2. Check system file: `ls -la /etc/postoffice/password.key`
3. Check user file: `ls -la ~/.postoffice/password.key`
4. Run: `python -m postoffice startup-check`

### "Permission denied" on key file
- Fix: `sudo chmod 600 /etc/postoffice/password.key`

### "Password not found for member"
- Check if password is set: `SELECT * FROM postoffice.member_mailbox_password WHERE member_moniker='alice'`
- Set password using password_manager TUI

### IMAP connection failing
- Verify credentials: `python -c "from postoffice.imap_lib import get_imap_credentials; print(get_imap_credentials(args))"`
- Check Cyrus is running and accessible

### Events not firing
- Verify IMAPMonitor is running
- Check postoffice.notification_routing rules
- Review engine.__notify table for events

---

## Version Information

- **Project:** mistermcfeely
- **Module:** postoffice
- **Total Lines:** ~3,901
- **Python Version:** 3.9-3.12 (via bbsengine6)
- **Dependencies:** bbsengine6, imaplib (stdlib)
- **Cipher:** AES-256-GCM (via bbsengine6.util)

---

## Further Reading

Start with:
1. **POSTOFFICE_QUICK_REFERENCE.md** for copy-paste code
2. **POSTOFFICE_EXPLORATION_SUMMARY.md** for detailed understanding
3. **POSTOFFICE_ARCHITECTURE_DIAGRAM.md** for system diagrams

Then dive into the source code:
- startup.py - for encryption key logic
- password_auth.py - for credential fallback
- imap_monitor.py - for background monitoring
- notifyd_client.py - for event firing

