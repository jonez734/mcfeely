# Mistermcfeely Project Structure & User/Credential Management Analysis

## Executive Summary

**Mistermcfeely** (named after the postman from Mr. Rogers' Neighborhood) is an IMAP postoffice system for managing shared Cyrus mailboxes with real-time NotifyD integration for event-driven workflows. The project integrates with **bbsengine6** core systems and uses PostgreSQL for data persistence.

**Current Status (as of May 20, 2026):**
- 93 tests passing (100% pass rate)
- Fully integrated with bbsengine6 architecture
- Production-ready notification routing and IMAP monitoring

---

## 1. CODEBASE ORGANIZATION & MAIN COMPONENTS

### Directory Structure
```
/home/opencode/data/work/mistermcfeely/
├── src/postoffice/                    # Main source code
│   ├── __init__.py                   # Module entry point
│   ├── __main__.py                   # CLI entry point
│   ├── main.py                       # Main menu loop
│   ├── lib.py                        # Utility functions & db connection pattern
│   ├── startup.py                    # Schema initialization & monitor startup
│   ├── virtual.py                    # Virtual mailbox management UI
│   ├── mailbox.py                    # Mailbox CRUD & password management
│   ├── imap_client.py                # Message claiming/unclaiming + event firing
│   ├── imap_monitor.py               # Background IMAP polling daemon
│   ├── imap_lib.py                   # Cyrus IMAP utility functions
│   ├── message_client.py             # NotifyD integration & event routing
│   └── events.py                     # Event type enumerations
├── sql/                               # Database schema files
│   ├── schema.sql                    # Create postoffice schema
│   ├── mailbox.sql                   # Mailbox & password tables
│   ├── virtual.sql                   # Virtual mailbox rules
│   ├── message.sql                   # Message claim tracking
│   ├── message_routing.sql      # Event routing rules
│   └── message_config.sql       # Per-mailbox event config
├── tests/                             # Test suite
│   ├── test_imap_lib.py              # IMAP utility tests
│   ├── test_imap_monitor.py          # Monitor daemon tests
│   ├── test_message_client.py        # Notification tests
│   └── test_notifyd_integration.py   # Integration tests
├── bin/                               # Executable scripts
│   └── postoffice                    # Main CLI script
└── docs/
    ├── README.md                     # Project overview
    ├── CONN_POOL_PATTERN.md          # Database connection pattern
    ├── IMPLEMENTATION_SUMMARY.md     # Recent enhancements
    └── HYBRID_INTEGRATION_SUMMARY.md # Integration analysis
```

### Core Modules & Responsibilities

| Module | LOC | Purpose |
|--------|-----|---------|
| **imap_lib.py** | 295 | Cyrus IMAP utilities: connect, select, fetch headers/flags, detect changes |
| **imap_monitor.py** | 443 | Background polling daemon: monitors mailboxes for new/deleted/flagged messages |
| **message_client.py** | 443 | NotifyD integration: fires events, routes to recipients, flag obfuscation |
| **imap_client.py** | 291 | Message operations: claim/unclaim messages, fire events |
| **mailbox.py** | 264 | Mailbox CRUD UI: add/edit/delete mailboxes, manage passwords |
| **startup.py** | 186 | Schema initialization & monitor startup on system boot |
| **virtual.py** | 193 | Virtual mailbox pattern management UI |
| **lib.py** | 115 | DB connection pooling pattern, utility helpers |

### Architecture Patterns

**Data Flow:**
```
User claims message in shared mailbox
    ↓
imap_client.claim_message() sets Cyrus custom flag
    ↓
message_client.fire_event() checks message_config
    ↓
SQL pattern matching in message_routing table
    ↓
insert into engine.__notify for each recipient
    ↓
Other bbsengine6 systems consume: email, chat, in-app, webhooks, etc.
```

**Connection Pool Pattern (CONN_POOL_PATTERN):**
- All database functions use `**kwargs` for connection management
- Supports both `conn` (explicit connection) and `pool` (connection pool) parameters
- Helper function: `lib.get_db_connection(args, **kwargs)` - eliminates boilerplate
- Graceful degradation: functions handle None connections safely

**Threading Model:**
- IMAP monitor runs as background daemon thread (started in startup.py)
- Thread-safe state tracking with `threading.Lock()`
- Configurable per-mailbox poll intervals via `message_config` table

---

## 2. USER/ACCOUNT MANAGEMENT

### Account Model

Mistermcfeely uses **bbsengine6's member system** as the user/account model:

**Primary User Reference:**
- `engine.__member` table (from bbsengine6)
- Fields: `id` (int), `moniker` (string), `credits`, etc.

### Account Association Pattern

Users connect to mistermcfeely through **multiple relation types**:

#### A. Mailbox Ownership (`postoffice.mailbox`)
```sql
CREATE TABLE postoffice.mailbox (
    address TEXT PRIMARY KEY,          -- e.g., "shared/support@machine1.example.com"
    maillocation TEXT NOT NULL,        -- e.g., "maildir:~jam"
    enabled BOOLEAN DEFAULT 't'
);
```

**User Link:** Via `postoffice.mailbox_password` table
```sql
CREATE TABLE postoffice.mailbox_password (
    memberid BIGINT NOT NULL           -- FK: engine.__member(id)
        REFERENCES engine.__member(id),
    address TEXT NOT NULL              -- FK: postoffice.mailbox(address)
        REFERENCES postoffice.mailbox(address),
    password TEXT NOT NULL,            -- Encrypted password
    enabled BOOLEAN DEFAULT 't',
    kind TEXT NOT NULL                 -- 'inbound' or 'outbound'
);
```

**Index:** `UNIQUE(memberid, address, kind)` - each member can have different inbound/outbound passwords per mailbox

#### B. Message Claiming (Actor Tracking)
```sql
CREATE TABLE postoffice.__message (
    id TEXT UNIQUE PRIMARY KEY,        -- RFC 822 Message-ID
    claimedbymoniker TEXT,             -- FK: engine.__member(moniker)
        REFERENCES engine.__member(moniker),
    dateclaimed TIMESTAMPTZ
);
```

**How Claiming Works:**
1. User (actor_moniker) claims message via `imap_client.claim_message()`
2. Custom Cyrus flag set: `ClaimedBy_<obfuscated>` (obfuscation optional)
3. Event fired: `fire_event(event_type='message-claimed', actor_moniker=user)`
4. Routing rules checked to determine notification recipients
5. Similar for unclaiming with `message-unclaimed` event

#### C. Virtual Mailbox Management
```sql
CREATE TABLE postoffice.virtual (
    pattern TEXT UNIQUE PRIMARY KEY,   -- e.g., 'shared/support@%'
    result TEXT NOT NULL,              -- Expansion result
    enabled BOOLEAN DEFAULT 'f',
    createdbymoniker TEXT,             -- FK: engine.__member(moniker)
    updatedbymoniker TEXT              -- FK: engine.__member(moniker)
);
```

#### D. Notification Routing (Recipient Tracking)
```sql
CREATE TABLE postoffice.message_routing (
    id BIGSERIAL PRIMARY KEY,
    mailbox_name TEXT NOT NULL,        -- Pattern like 'shared/support@%'
    event_type TEXT NOT NULL,          -- 'message-claimed', '*', etc.
    actor_moniker TEXT,                -- FK: engine.__member(moniker) (optional)
    recipient_moniker TEXT NOT NULL,   -- FK: engine.__member(moniker)
    notification_type TEXT,
    urgency TEXT DEFAULT 'ROUTINE',
    delivery_method TEXT DEFAULT 'engine',
    enabled BOOLEAN DEFAULT TRUE
);
```

**Example Routes:**
- Admin sees all events for all shared mailboxes
- Team member A notified when team member B claims a support ticket
- Support queue manager gets CRITICAL notifications for urgent messages

### User Roles & Permissions

**Built-in Database Roles:**
- `web` - Web interface access
- `term` - Terminal/BBS interface access  
- `sysop` - System operator (full admin)
- `imapd` - Dovecot/Cyrus IMAP daemon (read-only select)

**Grant Structure:**
```sql
GRANT SELECT ON postoffice.message_config TO web, term;
GRANT SELECT, INSERT, UPDATE, DELETE ON postoffice.message_config TO sysop;
GRANT SELECT ON postoffice.mailbox TO imapd;
```

---

## 3. PASSWORD & CREDENTIAL STORAGE

### Password Storage Mechanism

**Storage Location:** `postoffice.mailbox_password` table

**Password Field Details:**
- Column name: `password`
- Data type: `TEXT NOT NULL`
- Storage: **Encrypted using bbsengine6's encryption system**

### Encryption Process

**When Adding/Updating Passwords:**
```python
# From mailbox.py:add() and mailbox.py:_editmailbox()

# User enters password via interactive prompt
passwd = util.inputpassword("{promptcolor}mailbox password: {inputcolor}")
repeatpasswd = util.inputpassword("{promptcolor}repeat password: {inputcolor}")

# Validate match
if passwd == repeatpasswd:
    # Encrypt using bbsengine6's utility
    encryptedpassword = util.getencryptedpassword(args, plaintextpassword)
    
    # Store encrypted value
    _map["password"] = encryptedpassword
    database.insert(args, "postoffice.mailbox_password", _map, ...)
```

**Key Points:**
- Uses `util.getencryptedpassword(args, plaintext)` from bbsengine6
- Encryption implementation is in bbsengine6 (external to this project)
- Passwords are **never stored in plaintext**
- Encrypted value is opaque text in PostgreSQL

### Credential Usage Locations

#### 1. IMAP Connection (for Cyrus server access)
**Source:** Database credentials passed via `args` object from bbsengine6
```python
# From imap_lib.py:connect_cyrus()

host = getattr(args, "imaphost", None)          # IMAP server host
port = getattr(args, "imapport", 993)           # IMAP server port
username = getattr(args, "imapuser", None)      # IMAP login username
password = getattr(args, "imappassword", None)  # IMAP login password

imap = imaplib.IMAP4_SSL(host, port, timeout=timeout)
imap.login(username, password)
```

**Credential Source:** 
- Passed from bbsengine6 session/configuration
- NOT stored in mistermcfeely database
- Used only for daemon IMAP polling thread

#### 2. Mailbox-Specific Passwords (for shared mailbox access)
**Source:** `postoffice.mailbox_password` table
**Usage Pattern:**
- Encrypted passwords retrieved from DB when needed
- Decrypted using bbsengine6's `util.decryptpassword()` (not shown in current code)
- Used to authenticate mailbox access

#### 3. Flag Obfuscation Secret
**Purpose:** Obfuscate claim flag names in Cyrus
**Source Priority:**
1. Environment variable: `MCFEELY_OBFUSCATE_SECRET`
2. Database password: `args.databasepassword` (fallback)
3. Plain text (no obfuscation) - backward compat

**Implementation:**
```python
# From message_client.py:get_obfuscate_secret()

def get_obfuscate_secret(args) -> Optional[str]:
    secret = os.environ.get("MCFEELY_OBFUSCATE_SECRET")
    if secret:
        return secret
    if hasattr(args, "databasepassword") and args.databasepassword:
        return args.databasepassword
    return None

# Usage: HMAC-SHA256(moniker, secret).hexdigest()[:8]
def obfuscate_moniker(moniker: str, secret: Optional[str] = None) -> str:
    if not secret:
        return moniker  # Plain text fallback
    
    h = hmac.new(secret.encode("utf-8"), 
                 moniker.encode("utf-8"), 
                 hashlib.sha256)
    return h.hexdigest()[:8]  # e.g., "a3f9k2m1"

# Example claim flag: "ClaimedBy_a3f9k2m1" (not "ClaimedByAlice")
```

**Benefits:**
- Claim flags don't expose usernames in Cyrus logs
- Reversible (can verify flag matches moniker with secret)
- Optional (backward compatible with plain text)

### Credential Security Summary

| Credential Type | Storage | Protection | Rotation | Access |
|---|---|---|---|---|
| Mailbox passwords | PostgreSQL `postoffice.mailbox_password` | bbsengine6 encryption | Manual via UI | sysop role only |
| IMAP server creds | bbsengine6 session/args | bbsengine6 auth system | N/A | postoffice daemon |
| Obfuscation secret | Environment var or DB password | Env var best practice | Manual | postoffice code |
| Cyrus custom flags | Cyrus custom flag storage | HMAC obfuscation | N/A | Read-only IMAP |

---

## 4. DATABASE SCHEMA & DATA MODELS

### Core Tables

#### `postoffice.mailbox` - Shared Mailbox Definitions
```sql
address TEXT PRIMARY KEY              -- e.g., "shared/support@machine1.example.com"
maillocation TEXT NOT NULL            -- Maildir location, e.g., "maildir:~jam"
enabled BOOLEAN DEFAULT 't'           -- Enable/disable mailbox
```
**Purpose:** Defines shared mailboxes managed by mistermcfeely

#### `postoffice.mailbox_password` - User-Mailbox Credentials
```sql
memberid BIGINT NOT NULL              -- FK to engine.__member(id)
address TEXT NOT NULL                 -- FK to postoffice.mailbox(address)
password TEXT NOT NULL                -- Encrypted password
enabled BOOLEAN DEFAULT 't'           -- Enable/disable this credential
kind TEXT NOT NULL                    -- 'inbound' or 'outbound'
```
**Index:** `UNIQUE(memberid, address, kind)` - one password pair per user per mailbox
**Purpose:** Map users to mailboxes with encrypted access credentials

#### `postoffice.__message` - Message Claim Tracking
```sql
id TEXT UNIQUE PRIMARY KEY            -- RFC 822 Message-ID
claimedbymoniker TEXT                 -- FK to engine.__member(moniker)
dateclaimed TIMESTAMPTZ               -- When claimed
```
**Purpose:** Track which user claimed which message (for audit/UI display)

#### `postoffice.virtual` - Virtual Mailbox Patterns
```sql
pattern TEXT UNIQUE PRIMARY KEY       -- Pattern like 'shared/support@%'
result TEXT NOT NULL                  -- Expansion result
enabled BOOLEAN DEFAULT 'f'           -- Enable/disable pattern
datecreated TIMESTAMPTZ
createdbymoniker TEXT                 -- Who created
dateupdated TIMESTAMPTZ
updatedbymoniker TEXT                 -- Who last edited
```
**Purpose:** Define virtual mailbox expansion rules for Cyrus

#### `postoffice.message_routing` - Event Routing Rules
```sql
id BIGSERIAL PRIMARY KEY
mailbox_name TEXT NOT NULL            -- Pattern match: "shared/%" or "shared/support@%"
event_type TEXT NOT NULL              -- "message-new", "message-claimed", "*" (all)
actor_moniker TEXT                    -- Specific user or NULL (any user)
recipient_moniker TEXT NOT NULL       -- Who gets notification
notification_type TEXT                -- Template type, auto-generated if NULL
urgency TEXT DEFAULT 'ROUTINE'        -- ROUTINE, IMPORTANT, URGENT, CRITICAL
delivery_method TEXT DEFAULT 'engine' -- 'engine' (engine.__notify), future: 'email', 'chat'
enabled BOOLEAN DEFAULT TRUE
```
**Example Rules:**
```sql
-- Admin sees all events in all shared mailboxes
INSERT INTO postoffice.message_routing
VALUES (NULL, 'shared/%', '*', NULL, 'admin', 'mcfeely-all-events', 'ROUTINE', 'engine', TRUE);

-- Alice and Bob notify each other when messages are claimed
INSERT INTO postoffice.message_routing
VALUES (NULL, 'shared/support%', 'message-claimed', 'alice', 'bob', NULL, 'IMPORTANT', 'engine', TRUE);
INSERT INTO postoffice.message_routing
VALUES (NULL, 'shared/support%', 'message-claimed', 'bob', 'alice', NULL, 'IMPORTANT', 'engine', TRUE);
```

#### `postoffice.message_config` - Per-Mailbox Event Settings
```sql
id BIGSERIAL PRIMARY KEY
mailbox_name TEXT NOT NULL UNIQUE     -- Specific mailbox name (no patterns)
enable_new_message_events BOOLEAN DEFAULT TRUE
enable_claimed_events BOOLEAN DEFAULT TRUE
enable_flag_change_events BOOLEAN DEFAULT FALSE
enable_delete_events BOOLEAN DEFAULT FALSE
imap_poll_interval_seconds INTEGER DEFAULT 30
created_at TIMESTAMPTZ DEFAULT NOW()
updated_at TIMESTAMPTZ DEFAULT NOW()
```
**Purpose:** Fine-grained per-mailbox event filtering and polling frequency

### Event Types & Payloads

Events are fired to `engine.__notify` table with JSON data:

#### message-new
```json
{
    "event_type": "message-new",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423,
    "message_id": "<abc123@example.com>",
    "from": "user@example.com",
    "subject": "Help: Password reset",
    "date": "2026-05-18T14:30:00Z"
}
```

#### message-claimed
```json
{
    "event_type": "message-claimed",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423,
    "actor_moniker": "alice"
}
```

#### message-unclaimed
```json
{
    "event_type": "message-unclaimed",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423,
    "actor_moniker": "alice"
}
```

#### message-flagged
```json
{
    "event_type": "message-flagged",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423,
    "flag_name": "\\Seen",
    "added": true
}
```

#### message-deleted
```json
{
    "event_type": "message-deleted",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423
}
```

---

## 5. AUTHENTICATION & AUTHORIZATION PATTERNS

### Authentication Flow

#### A. System-Level Authentication (bbsengine6)
```
User logs into BBS system
    ↓
bbsengine6 authenticates member (engine.__member table)
    ↓
Session created with args object containing:
    - databasename, databasehost, databaseport, databaseuser, databasepassword
    - imaphost, imapport, imapuser, imappassword (if applicable)
    - debug flags
    ↓
postoffice module accessed via bbsengine6 auth
```

#### B. IMAP Server Authentication (Cyrus)
```
imap_monitor daemon polls at startup
    ↓
imap_lib.connect_cyrus(args) uses:
    - args.imaphost (Cyrus server)
    - args.imapport (usually 993 SSL)
    - args.imapuser (service account)
    - args.imappassword (service account password)
    ↓
IMAP4_SSL.login(username, password)
    ↓
Connected to Cyrus, can select/read shared mailboxes
```

#### C. Mailbox Access Authentication
When users access mailboxes:
```
User requests mailbox access
    ↓
Retrieve from postoffice.mailbox_password:
    - Find row where memberid = current_user AND address = mailbox
    ↓
Decrypt password field using bbsengine6 util
    ↓
Authenticate to IMAP using decrypted credential
    ↓
Access granted to shared mailbox
```

### Authorization Model

**Role-Based Access Control (RBAC):**

| Role | postoffice.mailbox | postoffice.message_routing | postoffice.message_config | postoffice.virtual |
|------|---|---|---|---|
| **web** | SELECT | SELECT | SELECT | SELECT |
| **term** | SELECT | SELECT | SELECT | SELECT |
| **sysop** | ALL | ALL | ALL | ALL |
| **imapd** | SELECT | - | - | - |

**Functional Authorization:**

1. **Mailbox Listing**
   - UI shows mailboxes (SELECT on postoffice.mailbox)
   - Restricted to authenticated bbsengine6 users

2. **Notification Routing**
   - Admins configure routing rules (sysop role)
   - System reads rules for event firing (internal code access)

3. **Message Claiming**
   - User moniker captured from bbsengine6 session
   - Only authenticated users can claim (actor_moniker = current_user)
   - Claim flag includes obfuscated moniker (audit trail)

4. **IMAP Monitor (Daemon)**
   - Runs with imapd database role (read-only)
   - Service account credentials used (not member credentials)
   - Polls in background, fires events for all monitored mailboxes

### Access Control Points

**In Code (Authorization Checks):**

```python
# From postoffice modules:

# 1. Init function (gate keeper)
def init(args, **kw):
    return True  # Always allow init

# 2. Access function (per-operation auth)
def access(args, op, **kw):
    return True  # All operations allowed (bbsengine6 handles member auth)

# 3. Functional checks in mailbox.py
memberid = member.getcurrentid(args)  # Current authenticated member
moniker = member.getcurrentmoniker(args)

# 4. Event firing includes actor moniker
imap_client.claim_message(
    args, 
    mailbox_name, 
    message_uid,
    actor_moniker=actor_moniker  # Explicitly track who performed action
)
```

---

## 6. SUMMARY & RECOMMENDATIONS

### Current Architecture Strengths

✅ **Integrated with bbsengine6**
- Uses standard member authentication system
- Respects bbsengine6 encryption for passwords
- Follows connection pool pattern for database access
- Compatible with web and terminal interfaces

✅ **Secure Credential Handling**
- Mailbox passwords encrypted in database
- IMAP server credentials managed by bbsengine6
- Optional obfuscation of claim flags
- Clear separation between application and operational secrets

✅ **Event-Driven Design**
- Pattern-based routing for flexible subscriptions
- Per-mailbox event filtering to reduce noise
- Integration with bbsengine6 notification system
- JSON payloads for machine consumption

✅ **Audit & Tracking**
- Claim flags identify who claimed messages
- Notification routing logs recipients
- Virtual mailbox changes tracked (createdby, updatedby)
- Background daemon logs IMAP changes

### Key User Management Concepts

1. **Users are Members** - `engine.__member` table (bbsengine6)
2. **Mailbox Access** - `postoffice.mailbox_password` (encrypted credentials)
3. **Message Claims** - Actor moniker stored in claim flags and events
4. **Notifications** - Recipient moniker in routing rules
5. **Audit Trail** - Creation/update by moniker in virtual & routing tables

### Credential Handling Best Practices (Currently Implemented)

1. ✅ Passwords encrypted before storage (uses bbsengine6 encryption)
2. ✅ Environment variable support for secrets (MCFEELY_OBFUSCATE_SECRET)
3. ✅ Service account separation (imapd daemon vs. user accounts)
4. ✅ Role-based database access (sysop can modify, web/term can view)
5. ✅ No plaintext secrets in code (uses args object)

### For Future Password Enhancement (if needed)

If you need to implement a password reset/rotation system:
1. Use `postoffice.mailbox_password` table with versioning
2. Call `util.getencryptedpassword()` from bbsengine6 for encryption
3. Add `updated_at` timestamp for audit trail
4. Implement password history (e.g., `postoffice.mailbox_password_history`)
5. Restrict password changes to sysop role via SQL grants

---

**End of Analysis**
