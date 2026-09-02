# Postoffice Codebase Exploration Summary

## Overview

The **postoffice** module is part of the **mistermcfeely** project and provides a comprehensive password management system for email (IMAP/SMTP) authentication across BBS members and shared mailboxes. It's built on top of **bbsengine6** and includes encryption, TUI interfaces, IMAP monitoring, and database integration.

**Location:** `/home/opencode/data/work/mistermcfeely/src/postoffice/`

**Total Size:** ~3,901 lines of Python code across 21 files

---

## 1. Module Structure & Directory Layout

```
postoffice/
├── __init__.py                    # Module exports (bbsengine6 pattern)
├── __main__.py                    # CLI entry point (292 lines)
├── main.py                        # TUI main menu (49 lines)
│
├── startup.py                     # Encryption key initialization (588 lines)
├── password_crypto.py             # DEPRECATED - shim for backward compat (20 lines)
│
├── Password Management (Core)
├── password_auth.py               # Auth fallback logic (149 lines)
├── member_password.py             # Personal account passwords (252 lines)
├── shared_mailbox_password.py     # Per-member shared mailbox passwords (300 lines)
│
├── IMAP Integration
├── imap_client.py                 # Message claiming/unclaiming (291 lines)
├── imap_lib.py                    # Cyrus IMAP utilities (370 lines)
├── imap_monitor.py                # IMAP mailbox monitoring (varies)
│
├── Database & Events
├── mailbox.py                     # Mailbox CRUD operations (264 lines)
├── virtual.py                     # Virtual mailbox patterns
├── events.py                      # Event type definitions
├── audit_log.py                   # Password operation logging
├── message_client.py              # Event firing & notification routing
│
├── Utilities
├── lib.py                         # Shared helpers (115 lines)
│
├── TUI Interface
├── tui/
│   ├── __init__.py
│   └── password_manager.py        # Interactive password management (303 lines)
│
├── password/                      # Package structure
│   └── __init__.py
│
└── Makefile
```

---

## 2. Startup Submodule & KEY Usage

### 2.1 Encryption Key Management

The **startup.py** module handles the cryptographic foundation for the entire system.

#### Key Sources (Priority Order)

```python
1. POSTOFFICE_PASSWORD_KEY        # Environment variable (fastest, development)
2. /etc/postoffice/password.key   # System file (production, recommended)
3. ~/.postoffice/password.key     # User file (personal development)
4. None                           # Error if not found
```

#### Key Properties

- **Size:** Exactly 32 bytes (256 bits) for AES-256-GCM
- **Format:** Base64-encoded when stored/transmitted
- **Access:** Must be identical across all servers and deployments
- **Permissions:** Files must have mode 0600 (read/write for owner only)

#### Key Functions

| Function | Purpose |
|----------|---------|
| `get_encryption_key()` | Retrieve key from priority sources (8-100+ lines) |
| `validate_encryption_key(verbose)` | Verify key exists and is valid format |
| `validate_password_config()` | Check cipher (AES-256-GCM) and storage settings |
| `initialize_password_system(verbose)` | One-time init with idempotent flag |
| `check_key_setup(verbose)` | Diagnose key setup status across all sources |
| `startup(verbose)` | Full system initialization |

### 2.2 CLI Entry Point (__main__.py)

The module supports command-line initialization:

```bash
# Check key setup
python -m postoffice startup-check [--verbose]

# Generate new key (outputs base64)
python -m postoffice startup-generate

# Install key to /etc/postoffice/
python -m postoffice startup-install

# Full initialization
python -m postoffice startup-init [--verbose]
```

### 2.3 Module Integration (bbsengine6 Pattern)

Functions follow bbsengine6 module patterns:

```python
def init_postoffice(args: Any) -> bool:
    """Initialize password system via startup.initialize_password_system()"""

def access_postoffice(args: Any) -> bool:
    """Check if encryption key is available"""

def help_postoffice(args: Any) -> str:
    """Return help text"""

def version_postoffice(args: Any) -> str:
    """Return version string"""
```

---

## 3. IMAP Service & Mailbox Structure

### 3.1 Mailbox Types

The system manages two mailbox categories:

#### Personal Mailboxes
- Individual member accounts
- Passwords stored in `engine.__member` table
- Fields: `inbound_password`, `outbound_password`
- Only accessible by that member (or sysops)

#### Shared Mailboxes
- Team/group email addresses (e.g., support@example.com)
- Member-specific overrides in `postoffice.member_mailbox_password`
- Default password in `postoffice.mailbox_password`
- Fallback logic: per-member → shared default

### 3.2 IMAP Client Operations

**imap_client.py** provides functional message operations:

```python
claim_message(
    args,
    mailbox_name,       # "shared/support@example.com"
    message_uid,        # IMAP UID
    actor_moniker,      # Who is claiming
    message_id=None,    # Optional: RFC 822 Message-ID
    message_from=None,  # Optional: From header
    message_subject=None, # Optional: Subject
    **kwargs            # imap_conn, conn, pool
) -> bool
```

- Sets custom Cyrus flag: `ClaimedBy<moniker>` (optionally obfuscated)
- Fires `message-claimed` event via message_client
- Supports optional obfuscation (HMAC-SHA256)

```python
unclaim_message(
    args,
    mailbox_name,
    message_uid,
    actor_moniker,
    **kwargs
) -> bool
```

- Removes claim flag
- Fires `message-unclaimed` event

### 3.3 IMAP Library (imap_lib.py)

**imap_lib.py** provides Cyrus IMAP utilities:

```python
get_imap_credentials(args, member_moniker, mailbox_id) -> Dict
```

**Credential Resolution:**
1. Direct args (highest priority): `args.imaphost`, `args.imapuser`, `args.imappassword`
2. Password system (fallback): calls `password_auth.get_auth_password()`
3. Error if no credentials found

```python
connect_cyrus(args, readonly=True, timeout=10, member_moniker=None, mailbox_id=None) -> IMAP4_SSL
```

- Opens IMAP4_SSL connection
- Uses `get_imap_credentials()` for auth
- Optional read-only mode
- Returns None on error

### 3.4 IMAP Monitor (imap_monitor.py)

**IMAPMonitor** class provides background mailbox monitoring:

```python
class IMAPMonitor:
    def __init__(self, args, poll_interval_seconds=30, pool=None)
    def start() -> None                    # Start monitoring thread
    def stop() -> None                     # Stop monitoring
    def _run_loop()                        # Main polling loop
    def _check_mailbox(mailbox_name)       # Poll single mailbox
```

**Detects:**
- New messages → fires `message-new` event
- Flag changes → fires `message-flagged` event
- Message deletions → fires `message-deleted` event

**State Tracking:**

```python
@dataclass
class MessageState:
    uid: int
    flags: Set[str]
    message_id: Optional[str]
    from_addr: Optional[str]
    subject: Optional[str]

@dataclass
class MailboxState:
    mailbox_name: str
    messages: Dict[int, MessageState]
    uidvalidity: Optional[int]
    last_poll_time: Optional[float]
```

---

## 4. Existing TUI & UI Components

### 4.1 Main Menu (main.py)

Simple interactive menu using **bbsengine6.io**:

```
[V] Virtual      - Virtual mailbox management
[M] Mailbox      - Mailbox CRUD operations
[Q] Quit         - Exit
```

Uses `io.inputchar()` for terminal input and `io.echo()` for output.

### 4.2 Password Manager TUI (tui/password_manager.py)

**PasswordManager** class (303 lines) provides interactive password management:

```python
class PasswordManager:
    def __init__(self, args: Any)
    def run(self) -> int                  # Main TUI loop
    
    # Member menu (regular users)
    def _show_member_menu()
    def _set_personal_password(password_type)
    def _view_personal_passwords()
    def _delete_personal_password(password_type)
    def _set_shared_mailbox_password()
    def _view_shared_mailbox_passwords()
    def _delete_shared_mailbox_password()
    
    # Sysop menu (administrators)
    def _show_sysop_menu()
    def _handle_choice(choice)
```

**Member Capabilities:**
- Set/view/delete own passwords (inbound/outbound)
- Set/view/delete passwords for shared mailboxes they access

**Sysop Capabilities:**
- Set/view/delete passwords for ANY member
- Set/view/delete passwords for ANY member on ANY mailbox

Uses `bbsengine6.console.inputpassword.inputpassword()` for secure input.

### 4.3 Mailbox CRUD (mailbox.py)

TUI-driven mailbox editing:

```python
def summary(args)        # List all mailboxes
def edit(args)           # Interactive edit menu
def _editmailbox(mailbox, mode="NEEDINFO")  # Field-by-field editing
```

Interactive menu for setting:
- Address (`[A]`)
- Enabled status (`[E]`)
- Mail location (`[M]`)
- Member ID (`[I]`)
- Password (`[P]`)

Uses bbsengine6 input functions for each field.

### 4.4 Virtual Mailbox CRUD (virtual.py)

Similar pattern for virtual mailbox patterns:

```python
def summary(args)              # List patterns
def edit(args)                 # Interactive pattern editor
def inputvirtualpattern()      # Pattern input with autocomplete
```

Uses custom `completeVirtualPattern` class for bash-like completion.

---

## 5. Module Invocation

### 5.1 bbsengine6 Module Pattern

**postoffice** follows bbsengine6 module conventions via `__init__.py`:

```python
def init(args, **kw) -> bool
def access(args, op, **kw) -> bool
def buildargs(args, **kw) -> bool
def main(args, **kw)
```

Invoked from bbsengine6 menu system with standard args object.

### 5.2 Module Runners

```python
# postoffice/lib.py
def runmodule(args, modulename, **kw):
    """Run submodule like 'postoffice.virtual' or 'postoffice.mailbox'"""
    x = f"postoffice.{modulename}"
    return module.runmodule(args, x, **kw)
```

**Main menu (main.py) uses:**
```python
lib.runmodule(args, "virtual")    # Run postoffice.virtual
lib.runmodule(args, "mailbox")    # Run postoffice.mailbox
```

### 5.3 CLI Entry Points

```bash
# Explicit startup command
python -m postoffice.startup --check
python -m postoffice.startup --generate
python -m postoffice.startup --install
python -m postoffice.startup --init

# New CLI pattern (__main__.py)
python -m postoffice startup-check
python -m postoffice startup-generate
python -m postoffice startup-install
python -m postoffice startup-init
```

---

## 6. Password Management Architecture

### 6.1 Personal Account Passwords

**Storage:** `engine.__member` table

```sql
UPDATE engine.__member 
SET inbound_password = <encrypted>, 
    outbound_password = <encrypted> 
WHERE moniker = ?
```

**Functions:**

```python
member_password.set_personal_password(
    args,
    member_moniker,
    password_type,    # "inbound" or "outbound"
    password,
    set_by_moniker
) -> bool

member_password.get_personal_password(
    args,
    member_moniker,
    password_type,
    requester_moniker  # Permission check
) -> Optional[str]

member_password.list_personal_passwords(
    args,
    member_moniker,
    requester_moniker
) -> Dict[str, bool]  # Which types are set
```

### 6.2 Shared Mailbox Passwords

**Storage:** `postoffice.member_mailbox_password` table

```sql
INSERT INTO postoffice.member_mailbox_password (
    mailbox_id,
    member_moniker,
    password_type,
    encrypted_password,
    set_by_moniker,
    created_at,
    updated_at
) VALUES (?, ?, ?, ?, ?, NOW(), NOW())
ON CONFLICT (mailbox_id, member_moniker, password_type)
DO UPDATE SET encrypted_password = ?, set_by_moniker = ?, updated_at = NOW()
```

**Functions:**

```python
shared_mailbox_password.set_shared_mailbox_password(
    args,
    mailbox_id,
    member_moniker,
    password_type,
    password,
    set_by_moniker
) -> bool

shared_mailbox_password.get_shared_mailbox_password(
    args,
    mailbox_id,
    member_moniker,
    password_type,
    requester_moniker
) -> Optional[str]

shared_mailbox_password.list_shared_mailbox_passwords(
    args,
    mailbox_id,
    requester_moniker
) -> Dict[str, Dict]
```

### 6.3 Authentication with Fallback

**password_auth.py** implements priority-based credential resolution:

```python
get_auth_password(
    args,
    mailbox_id,          # None for personal
    member_moniker,
    password_type,
    requester_moniker,
    log_entry_fn=None
) -> Optional[str]
```

**For Shared Mailboxes (mailbox_id set):**
1. Try per-member password → `shared_mailbox_password.get_shared_mailbox_password()`
2. Fall back to mailbox default → `postoffice.mailbox_password` table
3. Return decrypted password or None

**For Personal Accounts (mailbox_id None):**
1. Get from `engine.__member` table
2. Return decrypted password or None

### 6.4 Encryption (Moved to bbsengine6)

**password_crypto.py** is a **deprecated shim** for backward compatibility.

```python
# DEPRECATED - DO NOT USE
from postoffice.password_crypto import encrypt_password

# CORRECT - Use bbsengine6 directly
from bbsengine6.util import encrypt_password, decrypt_password
```

**Actual implementations:**
- `bbsengine6.util.get_encryption_key()`
- `bbsengine6.util.encrypt_password(plaintext) -> bytes`
- `bbsengine6.util.decrypt_password(ciphertext) -> str`
- Cipher: **AES-256-GCM** (authenticated encryption)

---

## 7. Events & Notifications

### 7.1 Event Types (events.py)

```python
class EventType(str, Enum):
    MESSAGE_NEW = "message-new"
    MESSAGE_CLAIMED = "message-claimed"
    MESSAGE_UNCLAIMED = "message-unclaimed"
    MESSAGE_FLAGGED = "message-flagged"
    MESSAGE_DELETED = "message-deleted"
```

### 7.2 Event Firing (message_client.py)

```python
def fire_event(
    args,
    mailbox_name,
    event_type,
    event_data,     # Dict with event details
    actor_moniker=None,
    conn=None,
    pool=None
) -> bool
```

**Event Data Example:**

```python
{
    "event_type": "message-claimed",
    "mailbox_name": "shared/support@example.com",
    "message_uid": 42,
    "actor_moniker": "alice",
    "message_id": "<msg@example.com>",
    "from": "user@example.com",
    "subject": "Help needed"
}
```

### 7.3 Claim Flag Obfuscation

```python
def obfuscate_moniker(moniker: str, secret: Optional[str]) -> str
    """Generate HMAC-SHA256(moniker, secret), truncated to 8 chars"""

def format_claim_flag(moniker: str, secret: Optional[str]) -> str
    """Convert to Cyrus flag name:
    - Plain: alice → ClaimedByAlice
    - Obfuscated: alice → ClaimedBy_a3f9k2m1
    """

def verify_claim_flag(flag: str, moniker: str, secret: Optional[str]) -> bool
    """Verify flag matches moniker"""
```

**Obfuscation Secret Source:**
1. `MCFEELY_OBFUSCATE_SECRET` environment variable
2. `args.databasepassword`
3. None (fall back to plain text)

---

## 8. Audit & Logging

### 8.1 Audit Log Functions (audit_log.py)

```python
log_password_operation(
    action,              # "set", "delete", "access", etc.
    target_type,        # "personal" or "shared_mailbox"
    target_moniker,
    password_type,      # "inbound" or "outbound"
    performed_by,
    mailbox_id=None,
    reason=None,
    log_entry_fn=None   # bbsengine6.logentry()
) -> bool

log_auth_failure(
    member_moniker,
    password_type,
    reason,
    mailbox_id=None,
    log_entry_fn=None
) -> bool
```

**Log Format:**
```
[PASSWORD] SET | type=personal | member=alice | pwd_type=inbound | by=sysop
[PASSWORD] AUTH_FAIL | type=shared_mailbox | member=bob | pwd_type=outbound | by=system | mailbox_id=5 | reason=not_found
```

---

## 9. Connection Pool Pattern (lib.py)

The module implements **CONN_POOL_PATTERN** for flexible database access:

```python
def get_db_connection(args, **kwargs):
    """Extract or create connection from kwargs.
    
    Args:
        args: bbsengine6 args
        **kwargs: May contain:
            - conn: Existing database connection
            - pool: Connection pool
    
    Returns:
        Tuple of (use_conn, should_close)
        - use_conn: Connection to use (or None)
        - should_close: Boolean - caller should close if True
    """
```

**Pattern in Functions:**

```python
def some_function(args, **kwargs):
    conn, should_close = lib.get_db_connection(args, **kwargs)
    try:
        # Use conn for database operations
        cursor = conn.cursor()
        ...
    finally:
        if should_close and conn:
            conn.close()
```

---

## 10. Key Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                      POSTOFFICE MODULE                      │
└─────────────────────────────────────────────────────────────┘

startup.py (INIT LAYER)
    ├─ get_encryption_key()
    │   └─ → POSTOFFICE_PASSWORD_KEY (env/file)
    │
    ├─ initialize_password_system()
    │   ├─ → validate_encryption_key()
    │   └─ → validate_password_config()
    │
    └─ check_key_setup()
        └─ Diagnoses all key sources

                        ↓

password_auth.py (AUTH LAYER)
    ├─ get_auth_password()
    │   ├─ For shared mailbox (mailbox_id set):
    │   │   ├─ → shared_mailbox_password.get()
    │   │   │   └─ From postoffice.member_mailbox_password
    │   │   └─ → _get_shared_mailbox_default_password()
    │   │       └─ From postoffice.mailbox_password
    │   │
    │   └─ For personal account (mailbox_id None):
    │       └─ → member_password.get_personal_password()
    │           └─ From engine.__member
    │
    └─ validate_password()

                        ↓

imap_lib.py (IMAP CONNECTION LAYER)
    ├─ get_imap_credentials()
    │   ├─ 1. args.imaphost/imapuser/imappassword (direct)
    │   └─ 2. password_auth.get_auth_password() (fallback)
    │
    └─ connect_cyrus()
        ├─ get_imap_credentials()
        └─ → imaplib.IMAP4_SSL

                        ↓

imap_client.py (MESSAGE OPERATIONS)
    ├─ claim_message()
    │   ├─ imap_conn.store() → Cyrus flag
    │   └─ → message_client.fire_event("message-claimed")
    │
    └─ unclaim_message()
        ├─ imap_conn.store() → remove flag
        └─ → message_client.fire_event("message-unclaimed")

                        ↓

imap_monitor.py (BACKGROUND MONITORING)
    ├─ IMAPMonitor.start()
    ├─ _run_loop() → polling thread
    │   └─ For each mailbox:
    │       ├─ Detect new messages
    │       ├─ Detect flag changes
    │       ├─ Detect deletions
    │       └─ → fire_event() for each change
    │
    └─ State tracking (MailboxState, MessageState)

                        ↓

message_client.py (EVENT SYSTEM)
    ├─ fire_event()
    │   ├─ Write to engine.__notify
    │   └─ Route via postoffice.message_routing rules
    │
    ├─ obfuscate_moniker() → HMAC-SHA256
    ├─ format_claim_flag()
    └─ verify_claim_flag()

TUI Layer
├─ main.py
│   └─ Main menu → [V] Virtual, [M] Mailbox
│
├─ tui/password_manager.py
│   ├─ Member mode
│   │   ├─ Set personal passwords
│   │   └─ Set shared mailbox passwords
│   └─ Sysop mode (all members)
│
├─ mailbox.py
│   ├─ summary()
│   ├─ edit()
│   └─ _editmailbox()
│
└─ virtual.py
    ├─ summary()
    ├─ edit()
    └─ inputvirtualpattern()

Database
├─ engine.__member
│   └─ inbound_password, outbound_password
├─ postoffice.mailbox_password
│   └─ Default passwords for shared mailboxes
├─ postoffice.member_mailbox_password
│   └─ Per-member overrides
├─ postoffice.mailbox
│   └─ Mailbox metadata
├─ postoffice.virtual
│   └─ Virtual mailbox patterns
└─ engine.__notify
    └─ Event log
```

---

## 11. Deployment Considerations

### KEY Distribution

The POSTOFFICE_PASSWORD_KEY **must be identical** across:
- All IMAP servers
- All web admin servers
- All scheduled/daemon processes
- All backups

### Database Schema

Requires postoffice tables:
- `postoffice.mailbox`
- `postoffice.mailbox_password`
- `postoffice.member_mailbox_password`
- `postoffice.virtual`
- `postoffice.message_routing`
- `postoffice.message_config` (for monitoring intervals)

### Permissions

- Key files: mode 0600
- Directory: `/etc/postoffice/` owned by root or service user
- Database user: SELECT, INSERT, UPDATE, DELETE on postoffice tables

---

## 12. Summary Table

| Component | Lines | Purpose |
|-----------|-------|---------|
| startup.py | 588 | Encryption key init, validation, CLI |
| imap_lib.py | 370 | Cyrus IMAP connection utilities |
| shared_mailbox_password.py | 300 | Per-member shared mailbox password CRUD |
| tui/password_manager.py | 303 | Interactive password management UI |
| __main__.py | 292 | CLI entry point with startup commands |
| imap_client.py | 291 | Message claiming/unclaiming operations |
| mailbox.py | 264 | Mailbox CRUD with TUI |
| member_password.py | 252 | Personal account password CRUD |
| password_auth.py | 149 | Auth fallback logic |
| lib.py | 115 | Shared utilities, module runners |
| **Total** | **3,901** | **Complete system** |

---

## 13. Key Takeaways

1. **Single Encryption Key:** One KEY for all member passwords across all systems
2. **Two Password Types:** Personal (engine.__member) and Shared Mailbox (postoffice tables)
3. **Credential Fallback:** Shared mailboxes try per-member, then default password
4. **IMAP Integration:** Full support for claiming messages with obfuscated flags
5. **Background Monitoring:** IMAPMonitor detects changes and fires events
6. **TUI Interface:** Both member and sysop modes for password management
7. **Event System:** Integrates with bbsengine6 notify for event routing
8. **Connection Pooling:** Flexible database access via CONN_POOL_PATTERN
9. **Audit Logging:** All password operations logged via bbsengine6.logentry()
10. **bbsengine6 Integration:** Follows module patterns and uses standard utilities

