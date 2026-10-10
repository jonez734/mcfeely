# Mistermcfeely Quick Reference Guide

## Project at a Glance

**What:** IMAP Postoffice system for shared Cyrus mailboxes with real-time notifications  
**Where:** `/home/opencode/data/work/mistermcfeely/`  
**Status:** Production-ready (93/93 tests passing)  
**Integration:** bbsengine6 core system  
**Database:** PostgreSQL (`postoffice` schema)

---

## Key Files & What They Do

### Source Code (`src/postoffice/`)

| File | Purpose | Key Functions |
|------|---------|---|
| `imap_lib.py` | Cyrus IMAP connection & operations | `connect_cyrus()`, `get_message_headers()`, `detect_flag_changes()` |
| `imap_monitor.py` | Background polling daemon | `IMAPMonitor` class, `start_monitor()`, `stop_monitor()` |
| `message_client.py` | Event firing & routing | `fire_event()`, `get_routing_rules()`, `obfuscate_moniker()` |
| `imap_client.py` | Message operations | `claim_message()`, `unclaim_message()`, `fire_new_message_event()` |
| `mailbox.py` | Mailbox UI & password mgmt | `add()`, `edit()`, `summary()` |
| `startup.py` | Schema init & startup | `init()` - called on system boot |
| `virtual.py` | Virtual mailbox UI | `add()`, `edit()`, `summary()` |
| `lib.py` | Utilities & DB helpers | `get_db_connection()`, `runmodule()` |

### Database Schema (`sql/`)

| File | Table(s) | Purpose |
|------|----------|---------|
| `mailbox.sql` | `postoffice.__address`, `postoffice.mailbox_password` | Define mailboxes & user access |
| `message.sql` | `postoffice.__message` | Track claimed messages |
| `virtual.sql` | `postoffice.virtual` | Virtual mailbox expansion rules |
| `message_routing.sql` | `postoffice.message_routing` | Who gets notified for what events |
| `mailbox_view.sql` | `postoffice.mailbox` (view) / `postoffice.__mailbox` (table) | Per-mailbox event settings |
| `mailbox_member.sql` | `postoffice.mailbox_member` (view) / `postoffice.__mailbox_member` (table) | Per-member overrides |

---

## Password & Credential Handling

### Where Passwords Are Stored

```
postoffice.mailbox_password table:
├── memberid (user ID from bbsengine6)
├── address (mailbox name)
├── password (ENCRYPTED using bbsengine6 util)
├── enabled (bool)
└── kind ('inbound' or 'outbound')
```

### How Passwords Are Protected

1. **Encryption:** `util.getencryptedpassword(args, plaintext)` from bbsengine6
2. **Storage:** Encrypted value in PostgreSQL TEXT field
3. **Access:** Only `sysop` database role can modify
4. **Input:** Interactive prompt with validation in `mailbox.py:_editmailbox()`

### How Passwords Are Used

```python
# When setting password in mailbox UI:
plaintext = util.inputpassword("Enter password: ")
encrypted = util.getencryptedpassword(args, plaintext)
database.insert(..., password=encrypted)  # Store encrypted

# When using for IMAP:
credential = database.select(...)[0]['password']
decrypted = util.decryptpassword(args, encrypted)  # Not shown in code
imap.login(username, decrypted)  # Use decrypted
```

### Other Credentials

| Credential | Source | Protection | Usage |
|---|---|---|---|
| IMAP server auth | bbsengine6 args | bbsengine6 auth system | `imap_lib.connect_cyrus()` |
| Obfuscation secret | Env var or DB password | Environment variable (best) | Claim flag HMAC-SHA256 |
| Member passwords | bbsengine6 | bbsengine6 auth system | BBS login |

---

## User Account Model

### Users are "Members"

```
engine.__member (from bbsengine6)
├── id (bigint PK)
├── moniker (string - user's login name)
├── credits (int)
└── ... other fields
```

### How Users Connect to Mistermcfeely

1. **Mailbox Access:** `postoffice.mailbox_password` records link users to mailboxes
2. **Message Claiming:** `actor_moniker` in events identifies who claimed
3. **Notifications:** `recipient_moniker` in routing rules identifies who gets notified
4. **Audit Trail:** `createdbymoniker`, `updatedbymoniker` track changes

### Example User Interactions

```python
# User alice claims message 42 in shared/support
imap_client.claim_message(
    args,
    mailbox_name="shared/support",
    message_uid=42,
    actor_moniker="alice"  # Who is claiming
)

# This fires an event routed by message_routing rules:
# IF mailbox LIKE 'shared/support%'
#   AND event_type = 'message-claimed'
#   AND actor_moniker = 'alice'
# THEN notify recipient_moniker (e.g., 'bob', 'admin', etc.)
```

---

## Database Tables Summary

### `postoffice.__address` - Per-User Mailboxes
```sql
address TEXT PRIMARY KEY          -- "shared/support@machine1.example.com"
maillocation TEXT                 -- Maildir location
enabled BOOLEAN
```

### `postoffice.mailbox_password` - User-Mailbox Credentials
```sql
memberid BIGINT                   -- Who (bbsengine6 member)
address TEXT                      -- Which mailbox
password TEXT                     -- ENCRYPTED password
enabled BOOLEAN
kind TEXT                         -- 'inbound' or 'outbound'
UNIQUE(memberid, address, kind)   -- One password pair per user per mailbox
```

### `postoffice.message_routing` - Event Routing
```sql
mailbox_name TEXT                 -- Pattern: "shared/%" or "shared/support@%"
event_type TEXT                   -- "message-claimed", "message-new", "*" (all)
actor_moniker TEXT                -- Who triggered (alice, bob, NULL=any)
recipient_moniker TEXT            -- Who gets notified (admin, alice, bob, etc.)
urgency TEXT                      -- ROUTINE, IMPORTANT, URGENT, CRITICAL
enabled BOOLEAN
```

**Example:** "When alice claims in shared/support%, notify bob as IMPORTANT"

### `postoffice.mailbox` - Per-Mailbox Settings (view)
Backing table: `postoffice.__mailbox`.
```sql
mailbox_name TEXT UNIQUE          -- Specific mailbox (no patterns)
enable_new_message_events BOOLEAN -- Fire on new arrivals?
enable_claimed_events BOOLEAN     -- Fire on claim/unclaim?
enable_flag_change_events BOOLEAN -- Fire on flag changes?
enable_delete_events BOOLEAN      -- Fire on deletion?
imap_poll_interval_seconds INT    -- How often to check (default 30)
```

### `postoffice.mailbox_member` - Per-Member Overrides (view)
Backing table: `postoffice.__mailbox_member`. Coalesced against the parent
mailbox defaults; members with no row here inherit the per-mailbox toggles.
```sql
mailbox_name TEXT                 -- FK -> __mailbox(mailbox_name)
member_moniker CITEXT             -- FK -> engine.__member(moniker)
enable_new_message_events BOOLEAN -- Override per-member
enable_claimed_events BOOLEAN
enable_flag_change_events BOOLEAN
enable_delete_events BOOLEAN
```

---

## Event Types & Flows

### Five Event Types

1. **message-new** - New message arrived
2. **message-claimed** - User claimed message
3. **message-unclaimed** - User released claim
4. **message-flagged** - Flag added/removed
5. **message-deleted** - Message expunged

### Event Flow Example

```
New email arrives in shared/support
    ↓
imap_monitor._handle_new_message() detects UID
    ↓
imap_client.fire_new_message_event(
    mailbox="shared/support",
    uid=42,
    from="customer@example.com",
    subject="Help!"
)
    ↓
message_client.fire_event()
    ↓
Check message_routing:
  - mailbox_name LIKE "shared/support" ✓
  - event_type = "message-new" or "*" ✓
  - actor_moniker = NULL or matches ✓
    ↓
For each matching rule, call bbsengine6.message.send():
  notification_type: "mcfeely-message-new"
  recipients: [routing.recipient_moniker]
  data: {event details as JSON}
  urgency: "ROUTINE"
    ↓
bbsengine6.message consumes and delivers
(email, chat, in-app notification, webhook, etc.)
```

---

## Common Operations

### Add a Shared Mailbox

```
BBS Menu → postoffice → mailbox → add
├── Address: "shared/support@machine1.example.com"
├── Mail location: "maildir:~jam"
├── Member: (select user)
├── Password: (enter & verify)
└── Confirm: yes
```

Result: Mailbox added to `postoffice.__address` and `postoffice.mailbox_password`

### Add a Notification Route

```
Database (SQL insert):
INSERT INTO postoffice.message_routing
(mailbox_name, event_type, actor_moniker, recipient_moniker, urgency)
VALUES ('shared/support%', 'message-claimed', 'alice', 'bob', 'IMPORTANT');
```

Result: Bob gets notified (IMPORTANT) when Alice claims in shared/support

### Disable Event Type for a Mailbox

```sql
UPDATE postoffice.mailbox
SET enable_new_message_events = FALSE
WHERE mailbox_name = 'shared/support@machine1.example.com';
```

Result: Stop firing message-new events for that mailbox (too noisy).
Members can override via `postoffice.mailbox_member`.

### Change Polling Interval

```sql
UPDATE postoffice.mailbox
SET imap_poll_interval_seconds = 60
WHERE mailbox_name = 'shared/support@machine1.example.com';
```

Result: Check mailbox every 60 seconds instead of default 30

---

## Important Design Patterns

### CONN_POOL_PATTERN

All database functions use `**kwargs` to accept either:
- `conn` parameter (explicit connection)
- `pool` parameter (connection pool)

```python
def fire_event(args, mailbox_name, event_type, event_data, **kwargs):
    use_conn, should_close = lib.get_db_connection(args, **kwargs)
    try:
        # Use connection
        with database.cursor(use_conn) as cur:
            cur.execute(...)
    finally:
        if should_close:
            use_conn.close()
```

**Benefit:** Functions work in both daemon context (pool) and interactive context (explicit conn)

### Flag Obfuscation

Claim flags don't expose usernames:

```python
# Without obfuscation: ClaimedByAlice (exposes name)
# With obfuscation: ClaimedBy_a3f9k2m1 (HMAC-SHA256 truncated)

secret = os.environ.get("MCFEELY_OBFUSCATE_SECRET")
obfuscated = obfuscate_moniker("alice", secret)  # "a3f9k2m1"
flag_name = f"ClaimedBy_{obfuscated}"  # "ClaimedBy_a3f9k2m1"
```

**Benefit:** Claim information stored in Cyrus custom flags without exposing identities

### Thread-Safe Monitoring

IMAP monitor runs as daemon thread with lock-protected state:

```python
class IMAPMonitor:
    def __init__(self):
        self.mailbox_states = {}      # Message UIDs per mailbox
        self.lock = threading.Lock()  # Protect state
    
    def _poll_all_mailboxes(self):
        with self.lock:
            mailboxes = list(self.mailbox_states.keys())  # Snapshot
        
        for mailbox in mailboxes:
            self._poll_mailbox(mailbox)  # Parallel polling
```

**Benefit:** Multiple polls can happen safely, no race conditions

---

## Testing & Validation

### Run All Tests
```bash
cd /home/opencode/data/work/mistermcfeely
python -m pytest tests/
```

### Test Coverage
- **29 IMAP lib tests** - Connection, header parsing, flag detection
- **20 IMAP monitor tests** - Polling, message detection, state tracking
- **20 message client integration tests** - Event routing, obfuscation, rendering (renamed from test_notifyd_integration.py per 5ca992e)
- **24 Integration tests** - End-to-end workflows

**Result:** 93/93 passing (100%)

---

## Troubleshooting

### IMAP Monitor Not Starting
Check `startup.py:main()` for initialization errors:
```python
imap_monitor.initialize_monitor(args, poll_interval_seconds=30, pool=pool)
imap_monitor.start_monitor()
```

### Events Not Firing
1. Check `mailbox (per-mailbox default).enabled = TRUE` for mailbox
2. Check `message_routing` rules match mailbox pattern
3. Check `message_routing.enabled = TRUE`
4. Verify actor/recipient monikers exist in `engine.__member`

### Passwords Not Encrypting
Check that `util.getencryptedpassword()` from bbsengine6 is accessible

### No Message Detection
1. Check IMAP connection credentials in `args`
2. Check mailbox is being monitored via `imap_monitor.add_mailbox()`
3. Check poll interval isn't too long

---

## File Locations

```
Source Code:   /home/opencode/data/work/mistermcfeely/src/postoffice/
Tests:         /home/opencode/data/work/mistermcfeely/tests/
SQL Schema:    /home/opencode/data/work/mistermcfeely/sql/
Documentation: /home/opencode/data/work/mistermcfeely/README.md
               /home/opencode/data/work/mistermcfeely/PROJECT_ANALYSIS.md
               /home/opencode/data/work/mistermcfeely/IMPLEMENTATION_SUMMARY.md
```

---

**Last Updated:** May 20, 2026  
**Status:** Complete - All systems operational
