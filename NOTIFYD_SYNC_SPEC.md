# Mistermcfeely NotifyD Sync Specification

**Date:** May 18, 2026  
**Status:** All Phases Complete (0-9) + CONN_POOL_PATTERN Refactoring  
**Architecture:** Integrated with bbsengine6 engine.__notify  
**Connection Pattern:** REQUIRED - Uses bbsengine6 **kwargs pattern (see CONN_POOL_PATTERN.md)

---

## Executive Summary

Sync mistermcfeely (basic IMAP client for shared Cyrus mailboxes) with bbsengine6's notifyd event system. Key requirements:

- **Cyrus as source of truth** for message claims (via custom flags)
- **Integrated with engine.__notify** (bbsengine6 core notification table)
- **Pattern-based flexible routing** for multi-machine scenarios
- **Obfuscated claim flags** using shared secret (reversible for debugging)
- **Five event types:** message-new, message-claimed, message-unclaimed, message-flagged, message-deleted

---

## Implementation Status

### ✅ COMPLETED (Phases 0-9 + Final Refactoring)

**Phase 0: Code Cleanup**
- ✅ Created `startup.py` with schema initialization (notification_routing, notification_config)
- ✅ Deleted dead `boot.py` code
- ✅ Created notification_history view (queries engine.__notify)

**Phase 2: Event Integration Layer** (`notifyd_client.py`)
- ✅ Functional approach (no OOP)
- ✅ Flag obfuscation with HMAC-SHA256
- ✅ Event configuration per-mailbox
- ✅ Routing with SQL LIKE pattern matching
- ✅ Integration with engine.__notify

**Phase 3: IMAP Client Operations** (`imap_client.py`)
- ✅ claim_message() / unclaim_message()
- ✅ Event firing for all 5 event types
- ✅ Cyrus flag management

**Phase 4: Event Firing**
- ✅ mailbox.py fires mailbox-created events
- ✅ virtual.py fires virtual-created events

**Phase 5: Pattern-Based Routing Enhancement**
- ✅ Fixed SQL LIKE pattern matching
- ✅ Enhanced actor_moniker filtering with SQL LIKE patterns
- ✅ Flexible wildcard support (NULL matches any, patterns match roles)

**Phase 6: IMAP Monitoring with Embedded Polling**
- ✅ Created imap_monitor.py (352 lines)
- ✅ MessageState and MailboxState dataclasses
- ✅ Thread-safe daemon polling thread
- ✅ Configurable per-mailbox poll intervals

**Phase 7: Comprehensive Tests**
- ✅ 64 total tests (all passing)
- ✅ 30 unit tests (notifyd_client)
- ✅ 14 unit tests (imap_monitor)
- ✅ 18 integration tests
- ✅ 2 pattern-based routing tests

**Phase 8: Documentation**
- ✅ Updated README.md with comprehensive documentation
- ✅ Detailed NOTIFYD_SYNC_SPEC.md (240+ lines)
- ✅ Created CONN_POOL_PATTERN.md (REQUIRED pattern docs)

**Phase 9: Code Cleanup & Polish**
- ✅ Applied ruff formatting to all modules
- ✅ Removed unused imports and variables
- ✅ Code follows bbsengine6 style guidelines

**Final: CONN_POOL_PATTERN Refactoring**
- ✅ All database functions use **kwargs pattern
- ✅ Follows bbsengine6 conventions exactly
- ✅ Marked as REQUIRED in documentation
- ✅ All 64 tests passing  

---

## Architecture

### Data Flow

```
User claims message
    ↓
Set Cyrus flag: ClaimedBy_<obfuscated>
    ↓
fire_event() in imap_client.py
    ├─ Check postoffice.notification_config (enabled?)
    ├─ Query postoffice.notification_routing (pattern-based match)
    └─ Insert into engine.__notify (for each recipient)
         └─ Other systems consume: email, chat, in-app, etc.
```

### Schema Design

**Existing:**
- `postoffice.mailbox` - mailbox definitions
- `postoffice.virtual` - virtual address mappings
- `postoffice.__message` - legacy message tracking (deprecated)
- `engine.__notify` - bbsengine6 core notifications

**New:**
- `postoffice.notification_routing` - flexible routing rules (pattern-based mailbox names)
- `postoffice.notification_config` - per-mailbox event configuration
- `postoffice.notification_history` - VIEW over engine.__notify (mistermcfeely-specific filtering)

---

## Feature Specifications

### 1. Obfuscated Claim Flags

**Purpose:** Security/privacy while maintaining reversibility for debugging.

**Implementation:**
```python
# Flag format: ClaimedBy_<8-char-obfuscated>
# Example: alice → ClaimedBy_a3f9k2m1

def obfuscate_moniker(moniker: str, secret: Optional[str] = None) -> str:
    """Uses HMAC-SHA256(moniker, secret), truncated to 8 hex chars."""
    pass

def format_claim_flag(moniker: str, secret: Optional[str] = None) -> str:
    """Convert moniker to Cyrus custom flag name."""
    pass

def verify_claim_flag(flag: str, moniker: str, secret: Optional[str] = None) -> bool:
    """Verify claim flag matches moniker (for audit/debugging)."""
    pass
```

**Shared Secret Storage:**
- Environment variable: `MCFEELY_OBFUSCATE_SECRET`
- Fallback: Use `args.databasepassword` if no env var
- If no secret: Fall back to plain text `ClaimedByAlice` (backward compat)

### 2. Pattern-Based Routing Rules

**Purpose:** Support multi-machine scenarios and flexible configuration.

**Mailbox Name Patterns:**
```sql
-- Exact match
INSERT INTO postoffice.notification_routing
(mailbox_name, event_type, recipient_moniker)
VALUES ('shared/support@example.com', 'message-claimed', 'admin');

-- Pattern match (SQL LIKE)
INSERT INTO postoffice.notification_routing
(mailbox_name, event_type, recipient_moniker)
VALUES ('shared/%', 'message-claimed', 'admin');  -- All shared mailboxes

INSERT INTO postoffice.notification_routing
(mailbox_name, event_type, recipient_moniker)
VALUES ('shared/%@machine%.example.com', '*', 'sysop');  -- Any machine
```

**Routing Query:**
```sql
SELECT * FROM postoffice.notification_routing
WHERE 'shared/support@machine1.example.com' LIKE mailbox_name
  AND (event_type = 'message-claimed' OR event_type = '*')
  AND (actor_moniker = 'alice' OR actor_moniker IS NULL)
  AND enabled = TRUE;
```

### 3. Event Types & Payloads

All events stored in `engine.__notify.data` as JSON.

#### **message-new**
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

#### **message-claimed**
```json
{
    "event_type": "message-claimed",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423,
    "message_id": "<abc123@example.com>",
    "from": "user@example.com",
    "subject": "Help: Password reset",
    "actor_moniker": "alice",
    "timestamp": "2026-05-18T14:31:00Z"
}
```

#### **message-unclaimed**
```json
{
    "event_type": "message-unclaimed",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423,
    "actor_moniker": "alice",
    "timestamp": "2026-05-18T14:32:00Z"
}
```

#### **message-flagged**
```json
{
    "event_type": "message-flagged",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423,
    "flag_name": "\\Seen",
    "added": true,
    "actor_moniker": "alice",
    "timestamp": "2026-05-18T14:33:00Z"
}
```

#### **message-deleted**
```json
{
    "event_type": "message-deleted",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423,
    "timestamp": "2026-05-18T14:34:00Z"
}
```

### 4. Integration with engine.__notify

When routing rule triggers:

```python
# Determine notification_type prefix
notification_type = f"mcfeely-{event_type}"  # e.g., "mcfeely-message-claimed"

# Insert into engine.__notify
database.execute("""
    INSERT INTO engine.__notify 
    (notification_type, sender_moniker, template, rendered_message, data, urgency, should_persist)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
""", [
    notification_type,
    actor_moniker,
    rule.notification_type or f"mcfeely-{event_type}",
    f"{actor_moniker} claimed message #{message_uid}",
    json.dumps(event_data),
    rule.urgency or "ROUTINE",
    True
])
```

### 5. Multi-Machine Support

**How it works:**

1. **Cyrus Replication:** Machine A and Machine B replicate mailbox state (including flags) via Cyrus native sync
2. **Shared IMAP Namespace:** Both machines see same logical mailbox: `shared/support@example.com`
3. **Shared PostgreSQL:** Both machines query same routing rules and write to same engine.__notify
4. **Pattern-based routing:** Rules like `shared/%` match mailboxes on any machine

---

## SQL Schema

### notification_routing

```sql
CREATE TABLE postoffice.notification_routing (
    id BIGSERIAL PRIMARY KEY,
    mailbox_name TEXT NOT NULL,            -- Pattern: 'shared/support@%', 'shared/%', etc.
    event_type TEXT NOT NULL,              -- 'message-new', 'message-claimed', '*' for all
    actor_moniker TEXT,                    -- Specific user or NULL for any
    recipient_moniker TEXT NOT NULL,       -- Who gets notified
    notification_type TEXT,                -- Template type (optional, auto-generated if NULL)
    urgency TEXT DEFAULT 'ROUTINE',        -- ROUTINE, IMPORTANT, URGENT, CRITICAL
    delivery_method TEXT DEFAULT 'engine', -- 'engine' (engine.__notify) or future: 'email', 'chat'
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (actor_moniker) REFERENCES engine.__member(moniker),
    FOREIGN KEY (recipient_moniker) REFERENCES engine.__member(moniker),
    UNIQUE(mailbox_name, event_type, COALESCE(actor_moniker, ''), recipient_moniker)
);

CREATE INDEX idx_notification_routing_lookup 
    ON postoffice.notification_routing(mailbox_name, event_type, recipient_moniker)
    WHERE enabled = TRUE;
```

### notification_config

```sql
CREATE TABLE postoffice.notification_config (
    id BIGSERIAL PRIMARY KEY,
    mailbox_name TEXT NOT NULL UNIQUE,
    enable_new_message_events BOOLEAN DEFAULT TRUE,
    enable_claimed_events BOOLEAN DEFAULT TRUE,
    enable_flag_change_events BOOLEAN DEFAULT FALSE,
    enable_delete_events BOOLEAN DEFAULT FALSE,
    imap_poll_interval_seconds INTEGER DEFAULT 30,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_notification_config_mailbox 
    ON postoffice.notification_config(mailbox_name);
```

### notification_history (VIEW)

```sql
CREATE VIEW postoffice.notification_history AS
    SELECT
        n.id,
        n.notification_type,
        n.sender_moniker,
        n.rendered_message,
        n.data,
        n.urgency,
        n.datecreated,
        (n.data->>'mailbox_name')::TEXT as mailbox_name,
        (n.data->>'event_type')::TEXT as event_type,
        (n.data->>'message_uid')::INTEGER as message_uid,
        (n.data->>'actor_moniker')::TEXT as actor_moniker
    FROM engine.__notify n
    WHERE n.notification_type LIKE 'mcfeely-%'
    ORDER BY n.datecreated DESC;
```

---

## Modules

### notifyd_client.py

**Core functions for event firing and routing (using **kwargs pattern):**

All functions follow the REQUIRED **kwargs pattern for connection management (see CONN_POOL_PATTERN.md):

- `get_obfuscate_secret(args)` - Get shared secret for flag obfuscation
- `obfuscate_moniker(moniker, secret)` - Generate 8-char HMAC hash
- `format_claim_flag(moniker, secret)` - Create Cyrus flag name
- `verify_claim_flag(flag, moniker, secret)` - Verify flag matches moniker
- `is_event_enabled(args, mailbox_name, event_type, **kwargs)` - Check if event enabled (kwargs: conn, pool)
- `get_routing_rules(args, mailbox_name, event_type, actor_moniker, **kwargs)` - Query routing rules (kwargs: conn, pool)
- `render_event_message(event_type, actor_moniker, event_data)` - Human-readable messages
- `fire_event(args, mailbox_name, event_type, event_data, actor_moniker, **kwargs)` - Fire events (kwargs: conn, pool)

### imap_client.py

**Message-level operations (using **kwargs pattern):**

All functions follow the REQUIRED **kwargs pattern for connection management:

- `claim_message(args, mailbox_name, message_uid, actor_moniker, ..., **kwargs)` - Claim message + fire event (kwargs: imap_conn, conn, pool)
- `unclaim_message(args, mailbox_name, message_uid, actor_moniker, **kwargs)` - Unclaim message + fire event (kwargs: imap_conn, conn, pool)
- `fire_new_message_event(args, mailbox_name, message_uid, ..., **kwargs)` - Fire message-new event (kwargs: conn, pool)
- `fire_flag_changed_event(args, mailbox_name, message_uid, flag_name, added, ..., **kwargs)` - Fire message-flagged event (kwargs: conn, pool)
- `fire_message_deleted_event(args, mailbox_name, message_uid, **kwargs)` - Fire message-deleted event (kwargs: conn, pool)

### imap_monitor.py

**IMAP monitoring with embedded polling thread:**

- `MessageState(uid, flags, message_id, from_addr, subject)` - Message state dataclass
- `MailboxState(mailbox_name, messages, uidvalidity, last_poll_time)` - Mailbox state dataclass
- `IMAPMonitor(args, poll_interval_seconds, pool)` - Monitor class with daemon thread
  - `start()` - Start background polling thread
  - `stop(timeout_seconds)` - Stop polling gracefully
  - `add_mailbox(mailbox_name)` - Register mailbox for monitoring
  - `remove_mailbox(mailbox_name)` - Unregister mailbox
- `initialize_monitor(args, poll_interval_seconds, pool)` - Global monitor initialization
- `get_monitor()` - Get global monitor instance
- `start_monitor()` - Start global monitor thread
- `stop_monitor(timeout_seconds)` - Stop global monitor thread

---

## Configuration

### Environment Variables

```bash
# Obfuscation secret for claim flags (optional)
export MCFEELY_OBFUSCATE_SECRET="your-shared-secret-key-here"

# If not set, falls back to database password
# If neither set, uses plain text (backward compat)
```

### Example Routing Setup (SQL)

```sql
-- Admin sees all events for all shared mailboxes
INSERT INTO postoffice.notification_routing
(mailbox_name, event_type, actor_moniker, recipient_moniker, urgency)
VALUES ('shared/%', '*', NULL, 'admin', 'ROUTINE');

-- Team members notified when someone claims (exclude self)
INSERT INTO postoffice.notification_routing
(mailbox_name, event_type, actor_moniker, recipient_moniker, urgency)
VALUES 
  ('shared/support%', 'message-claimed', 'alice', 'bob', 'IMPORTANT'),
  ('shared/support%', 'message-claimed', 'alice', 'charlie', 'IMPORTANT'),
  ('shared/support%', 'message-claimed', 'bob', 'alice', 'IMPORTANT'),
  ('shared/support%', 'message-claimed', 'bob', 'charlie', 'IMPORTANT'),
  ('shared/support%', 'message-claimed', 'charlie', 'alice', 'IMPORTANT'),
  ('shared/support%', 'message-claimed', 'charlie', 'bob', 'IMPORTANT');

-- Disable new message events (too noisy)
INSERT INTO postoffice.notification_config
(mailbox_name, enable_new_message_events)
VALUES ('shared/support@machine1.example.com', FALSE);
```

---

## Implementation Notes

- **Backward Compatibility:** Claims can still use plain text `ClaimedByAlice` if no secret is configured
- **Obfuscation Reversibility:** Deobfuscation only works if secret is known (required for audit trails)
- **Pattern Matching:** Use SQL LIKE patterns; wildcards are `%` (any chars) and `_` (single char)
- **Multi-Machine:** Cyrus replication handles flag sync; PostgreSQL is shared between machines
- **Event History:** Queries `engine.__notify` view; retention policy is per-bbsengine6 config

---

## Testing

See `tests/` directory for comprehensive unit and integration tests.

**Test Coverage:**
- Flag obfuscation/deobfuscation
- Event configuration checking
- Routing rule queries
- Event message rendering
- Message claim/unclaim operations
- Error handling and edge cases

---
