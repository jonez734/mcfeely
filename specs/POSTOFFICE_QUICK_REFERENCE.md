# Postoffice Module Quick Reference

## File Locations

```
/home/opencode/data/work/mistermcfeely/src/postoffice/
├── startup.py (588 lines)              - Encryption key initialization
├── password_auth.py (149 lines)        - Auth fallback logic  
├── member_password.py (252 lines)      - Personal passwords
├── shared_mailbox_password.py (300)    - Shared mailbox passwords
├── imap_lib.py (370 lines)             - IMAP connection
├── imap_client.py (291 lines)          - Message operations
├── imap_monitor.py                     - Background monitoring
├── message_client.py                   - Event firing
├── mailbox.py (264 lines)              - Mailbox CRUD
├── virtual.py                          - Virtual patterns
├── main.py (49 lines)                  - Main menu
├── __main__.py (292 lines)             - CLI entry
├── __init__.py                         - Module exports
├── lib.py (115 lines)                  - Utilities
├── events.py                           - Event types
├── audit_log.py                        - Logging
├── password_crypto.py (20 lines)       - DEPRECATED shim
├── tui/
│   ├── __init__.py
│   └── password_manager.py (303 lines) - Password UI
└── password/
    └── __init__.py
```

---

## Key Concepts at a Glance

### Encryption Key (startup.py)

**The ONE Key:**
- **Size:** 32 bytes (256-bit for AES-256-GCM)
- **Format:** Base64-encoded
- **Must be identical** across all servers

**Sources (in priority order):**
```python
1. os.environ["POSTOFFICE_PASSWORD_KEY"]      # fastest
2. "/etc/postoffice/password.key"             # production
3. "~/.postoffice/password.key"               # dev
4. None                                        # error
```

**Getting the key:**
```python
from postoffice.startup import get_encryption_key
key = get_encryption_key()  # Returns bytes or None
```

**Generate new key:**
```bash
python -m postoffice startup-generate
```

---

### Password Types

#### 1. Personal Passwords (engine.__member table)

For a single member's personal email account.

```python
# Set
member_password.set_personal_password(
    args,
    member_moniker="alice",
    password_type="inbound",  # or "outbound"
    password="<plaintext>",
    set_by_moniker="alice"  # who's setting it
) -> bool

# Get
member_password.get_personal_password(
    args,
    member_moniker="alice",
    password_type="inbound",
    requester_moniker="alice"  # permission check
) -> Optional[str]
```

#### 2. Shared Mailbox Passwords (postoffice.member_mailbox_password table)

For a member accessing a shared mailbox (e.g., support@example.com).

```python
# Set per-member override
shared_mailbox_password.set_shared_mailbox_password(
    args,
    mailbox_id=5,
    member_moniker="alice",
    password_type="inbound",
    password="<plaintext>",
    set_by_moniker="alice"
) -> bool

# Get per-member password (with fallback to default)
shared_mailbox_password.get_shared_mailbox_password(
    args,
    mailbox_id=5,
    member_moniker="alice",
    password_type="inbound",
    requester_moniker="alice"
) -> Optional[str]
```

#### 3. Getting Any Password (password_auth.py)

Unified interface with automatic fallback:

```python
password_auth.get_auth_password(
    args,
    mailbox_id=None,         # None for personal
    member_moniker="alice",
    password_type="inbound",
    requester_moniker="alice"
) -> Optional[str]

# For personal accounts:
#   mailbox_id=None
#   → tries engine.__member
#
# For shared mailboxes:
#   mailbox_id=5
#   → tries per-member (postoffice.member_mailbox_password)
#   → falls back to default (postoffice.mailbox_password)
```

---

## Permission Model

### Members (Regular Users)

- Can only manage **their own** passwords
- Can set personal passwords (inbound/outbound)
- Can set passwords for shared mailboxes they access

### Sysops (Administrators)

- Can manage **any member's** passwords
- Can set personal passwords for any member
- Can set shared mailbox passwords for any member

**Check:**
```python
is_sysop = getattr(args, "issuperuser", False)
```

---

## IMAP Operations

### Getting IMAP Credentials

```python
from postoffice.imap_lib import get_imap_credentials

creds = get_imap_credentials(
    args,
    member_moniker="alice",
    mailbox_id=5  # optional, for shared mailbox
)

# Returns:
# {
#     "host": "imap.example.com",
#     "port": 993,
#     "username": "alice@example.com",
#     "password": "<decrypted>"
# }
```

**Credential Priority:**
1. Direct args: `args.imaphost`, `args.imapuser`, `args.imappassword`
2. Password system: calls `password_auth.get_auth_password()`

### Connecting to IMAP

```python
from postoffice.imap_lib import connect_cyrus

conn = connect_cyrus(
    args,
    readonly=True,           # read-only mode
    timeout=10,              # seconds
    member_moniker="alice",  # optional
    mailbox_id=5             # optional
)

if conn:
    # Use the connection
    conn.select("INBOX")
    # ...
    conn.close()
else:
    # Error connecting
    pass
```

### Message Operations

```python
from postoffice.imap_client import claim_message, unclaim_message

# Claim a message
claim_message(
    args,
    mailbox_name="shared/support@example.com",
    message_uid=42,
    actor_moniker="alice",
    message_id="<msg@example.com>",      # optional
    message_from="user@example.com",     # optional
    message_subject="Help needed",       # optional
    imap_conn=imap_connection            # optional
) -> bool

# Unclaim a message
unclaim_message(
    args,
    mailbox_name="shared/support@example.com",
    message_uid=42,
    actor_moniker="alice",
    imap_conn=imap_connection  # optional
) -> bool
```

Both fire events automatically.

---

## Events

### Event Types

```python
from postoffice.events import EventType

EventType.MESSAGE_NEW = "message-new"
EventType.MESSAGE_CLAIMED = "message-claimed"
EventType.MESSAGE_UNCLAIMED = "message-unclaimed"
EventType.MESSAGE_FLAGGED = "message-flagged"
EventType.MESSAGE_DELETED = "message-deleted"
```

### Firing Events

```python
from postoffice.message_client import fire_event

fire_event(
    args,
    mailbox_name="shared/support@example.com",
    event_type="message-claimed",
    event_data={
        "message_uid": 42,
        "actor_moniker": "alice",
        "message_id": "<msg@example.com>",
        "from": "user@example.com",
        "subject": "Help needed"
    },
    actor_moniker="alice",  # optional
    conn=db_connection,     # optional
    pool=connection_pool    # optional
) -> bool
```

Events are routed via `postoffice.message_routing` rules.

---

## Background Monitoring

### Starting IMAP Monitor

```python
from postoffice.imap_monitor import IMAPMonitor

monitor = IMAPMonitor(
    args,
    poll_interval_seconds=30,  # default
    pool=connection_pool       # optional
)

# Start monitoring
monitor.start()

# Monitor runs in background thread
# Detects: new, changed, deleted messages
# Fires events automatically

# Stop monitoring
monitor.stop()
```

### What It Detects

1. **New Messages** → fires `message-new` event
2. **Flag Changes** → fires `message-flagged` event  
3. **Deleted Messages** → fires `message-deleted` event

---

## TUI Components

### Password Manager

```python
from postoffice.tui.password_manager import PasswordManager

pm = PasswordManager(args)
exit_code = pm.run()  # Interactive menu
```

**Member Menu:**
- 1a: Set personal inbound password
- 1b: Set personal outbound password
- 1c: View personal password status
- 1d: Delete personal inbound password
- 1e: Delete personal outbound password
- 2a: Set shared mailbox password
- 2b: View shared mailbox passwords
- 2c: Delete shared mailbox password

**Sysop Menu:**
- Same as member, but can manage any member

### Mailbox CRUD

```python
from postoffice import mailbox

mailbox.summary(args)        # List all mailboxes
mailbox.edit(args)           # Interactive editor
```

### Main Menu

```python
# Invoked via bbsengine6
# Shows: [V] Virtual, [M] Mailbox, [Q] Quit
```

---

## Database Tables

### engine.__member

Personal account passwords

```sql
SELECT * FROM engine.__member WHERE moniker='alice';
-- Columns: ..., inbound_password, outbound_password, ...
```

### postoffice.mailbox

Mailbox metadata

```sql
SELECT * FROM postoffice.mailbox;
-- id, address, enabled, maillocation, memberid
```

### postoffice.mailbox_password

Default shared mailbox password (legacy)

```sql
SELECT * FROM postoffice.mailbox_password;
-- address, kind, password
```

### postoffice.member_mailbox_password

Per-member shared mailbox password overrides

```sql
SELECT * FROM postoffice.member_mailbox_password;
-- mailbox_id, member_moniker, password_type, encrypted_password, 
-- set_by_moniker, created_at, updated_at
```

### postoffice.virtual

Virtual mailbox patterns

```sql
SELECT * FROM postoffice.virtual;
-- pattern, result, enabled
```

### postoffice.message_routing

Event routing rules

```sql
SELECT * FROM postoffice.message_routing;
-- event_type, condition, action
```

### engine.__notify

Event log

```sql
SELECT * FROM engine.__notify;
-- event_type, mailbox_name, event_data, created_at
```

---

## Logging

### Password Operation Logging

```python
from postoffice.audit_log import log_password_operation

log_password_operation(
    action="set",           # "set", "delete", "access"
    target_type="personal", # "personal", "shared_mailbox"
    target_moniker="alice",
    password_type="inbound",
    performed_by="sysop",
    mailbox_id=None,        # only for shared mailbox
    reason=None,
    log_entry_fn=bbsengine6_logentry_function
) -> bool
```

### Authentication Failure Logging

```python
from postoffice.audit_log import log_auth_failure

log_auth_failure(
    member_moniker="alice",
    password_type="inbound",
    reason="password not found",
    mailbox_id=None,
    log_entry_fn=bbsengine6_logentry_function
) -> bool
```

---

## Claim Flag Obfuscation

### Setting a Claim Flag

```python
from postoffice.message_client import format_claim_flag, obfuscate_moniker

# Without obfuscation
flag = format_claim_flag("alice", secret=None)
# Result: "ClaimedByAlice"

# With obfuscation
secret = "my_database_password"
flag = format_claim_flag("alice", secret=secret)
# Result: "ClaimedBy_a3f9k2m1"  (HMAC-SHA256 first 8 chars)
```

### Getting Obfuscation Secret

```python
from postoffice.message_client import get_obfuscate_secret

secret = get_obfuscate_secret(args)
# Checks:
# 1. MCFEELY_OBFUSCATE_SECRET env var
# 2. args.databasepassword
# 3. None (no obfuscation)
```

### Verifying Claim Flag

```python
from postoffice.message_client import verify_claim_flag

is_valid = verify_claim_flag(
    flag="ClaimedBy_a3f9k2m1",
    moniker="alice",
    secret="my_database_password"
)
```

---

## Module Integration (bbsengine6 Pattern)

The postoffice module follows bbsengine6 conventions:

```python
# __init__.py exports these functions:

def init(args, **kw) -> bool:
    """Initialize module"""

def access(args, op, **kw) -> bool:
    """Check if accessible"""

def buildargs(args, **kw) -> bool:
    """Build command-line arguments"""

def main(args, **kw):
    """Main entry point - shows TUI menu"""
```

---

## CLI Commands

### Check Key Setup

```bash
python -m postoffice startup-check [--verbose]
```

Checks all key sources and reports status.

### Generate New Key

```bash
python -m postoffice startup-generate
```

Outputs base64-encoded 32-byte key.

### Install Key

```bash
python -m postoffice startup-install
```

Generates and installs to `/etc/postoffice/password.key` with 0600 permissions.

### Full Initialization

```bash
python -m postoffice startup-init [--verbose]
```

Validates key and password configuration.

---

## Connection Pool Pattern

Many postoffice functions support optional connection pooling:

```python
# Option 1: Pass existing connection
my_function(
    args,
    conn=existing_connection,
    other_arg=value
)

# Option 2: Pass connection pool
my_function(
    args,
    pool=connection_pool,
    other_arg=value
)

# Option 3: Function creates connection (slower)
my_function(
    args,
    other_arg=value
)
```

**Implementing the pattern:**

```python
def my_function(args, **kwargs):
    conn, should_close = lib.get_db_connection(args, **kwargs)
    try:
        cursor = conn.cursor()
        # Use cursor
    finally:
        if should_close and conn:
            conn.close()
```

---

## Common Workflows

### Sysop Sets Member's Shared Mailbox Password

```python
from postoffice.shared_mailbox_password import set_shared_mailbox_password

success = set_shared_mailbox_password(
    args=args,
    mailbox_id=5,                    # support@example.com
    member_moniker="alice",
    password_type="inbound",
    password="new_password_123",
    set_by_moniker="sysop"
)

if success:
    print("✓ Password set for alice on mailbox 5")
```

### Member Accesses Shared Mailbox via IMAP

```python
from postoffice.imap_lib import connect_cyrus

conn = connect_cyrus(
    args,
    member_moniker="alice",
    mailbox_id=5
)

if conn:
    conn.select("shared/support@example.com")
    # Alice can now read/send messages as support@example.com
    conn.close()
```

### Monitor Shared Mailbox and React to New Messages

```python
from postoffice.imap_monitor import IMAPMonitor

monitor = IMAPMonitor(args, poll_interval_seconds=30)
monitor.start()

# Background thread now:
# 1. Polls shared/support@example.com every 30 seconds
# 2. Detects new messages
# 3. Fires message-new events
# 4. Events route to handlers via message_routing rules
```

### List All Member Passwords

```python
from postoffice.member_password import list_personal_passwords

passwords = list_personal_passwords(
    args,
    member_moniker="alice",
    requester_moniker="alice"  # or sysop
)

# Returns: {"inbound": True, "outbound": False}
# (True = password is set, False = not set)
```

---

## Encryption Details

**Cipher:** AES-256-GCM (authenticated encryption)

**Key Source:**
```python
from bbsengine6.util import get_encryption_key
key = get_encryption_key()  # 32 bytes
```

**Encrypt/Decrypt:**
```python
from bbsengine6.util import encrypt_password, decrypt_password

ciphertext = encrypt_password("plaintext_password")
plaintext = decrypt_password(ciphertext)
```

Note: postoffice.password_crypto is deprecated - use bbsengine6.util directly.

---

## Debugging

### Enable Verbose Output

```bash
python -m postoffice startup-check --verbose
python -m postoffice startup-init --verbose
```

### Check Encryption Key

```bash
python -m postoffice startup-check
# Checks:
# - POSTOFFICE_PASSWORD_KEY env var
# - /etc/postoffice/password.key file
# - ~/.postoffice/password.key file
# - File permissions
# - Key validity
```

### Debug Flag in Args

```python
if getattr(args, "debug", False):
    from bbsengine6.io import echo
    echo("Debug message", level="debug")
```

---

## Related Documentation

- **POSTOFFICE_EXPLORATION_SUMMARY.md** - Full codebase structure and details
- **POSTOFFICE_ARCHITECTURE_DIAGRAM.md** - System architecture and data flows
- **ENCRYPTION_KEY_MANAGEMENT.md** - Key distribution and setup
- **PASSWORD_SYSTEMS_EXPLAINED.md** - Password storage architecture
- **CONN_POOL_PATTERN.md** - Database connection pooling

