# Mistermcfeely: IMAP Postoffice with NotifyD Integration

**Mr. McFeely was the postman on Mr. Rogers' Neighborhood**

A basic IMAP client for shared Cyrus mailboxes, integrated with bbsengine6's notifyd event system. Enables real-time notifications when messages are claimed/unclaimed in shared mailboxes.

## Overview

**Purpose:** Sync mistermcfeely with bbsengine6's core notification system to enable event-driven workflows for shared mailbox operations (support queues, team inboxes, etc.).

**Key Features:**
- **Cyrus as source of truth** - Custom flags store message claim state
- **NotifyD integration** - Events fire to `engine.__notify` for consumption by other systems
- **Pattern-based routing** - Flexible mailbox patterns (`shared/%`, `shared/%@machine%.example.com`)
- **Obfuscated flags** - HMAC-SHA256 hashing for claim flag obfuscation (reversible with secret)
- **Five event types:** message-new, message-claimed, message-unclaimed, message-flagged, message-deleted
- **Background monitoring** - Embedded polling thread detects mailbox changes
- **Configurable intervals** - Per-mailbox poll intervals via PostgreSQL config

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
         └─ Other systems consume: email, chat, in-app, webhooks, etc.
```

### Modules

| Module | Purpose | Status |
|--------|---------|--------|
| `notifyd_client.py` | Event firing, routing, flag obfuscation | ✅ Complete |
| `imap_client.py` | Message-level operations (claim/unclaim) | ✅ Complete |
| `imap_monitor.py` | Background polling for mailbox changes | ✅ Complete |
| `startup.py` | Schema initialization, monitor startup | ✅ Complete |

## Configuration

### Environment Variables

```bash
# Obfuscation secret for claim flags (optional)
export MCFEELY_OBFUSCATE_SECRET="your-shared-secret-key-here"

# If not set, falls back to database password
# If neither set, uses plain text (backward compat)
```

### Database Setup (SQL)

#### Routing Rules

```sql
-- Admin sees all events for all shared mailboxes
INSERT INTO postoffice.notification_routing
(mailbox_name, event_type, actor_moniker, recipient_moniker, urgency)
VALUES ('shared/%', '*', NULL, 'admin', 'ROUTINE');

-- Team members notified when someone claims
INSERT INTO postoffice.notification_routing
(mailbox_name, event_type, actor_moniker, recipient_moniker, urgency)
VALUES 
  ('shared/support%', 'message-claimed', 'alice', 'bob', 'IMPORTANT'),
  ('shared/support%', 'message-claimed', 'bob', 'alice', 'IMPORTANT');
```

#### Per-Mailbox Config

```sql
-- Disable new message events (too noisy)
INSERT INTO postoffice.notification_config
(mailbox_name, enable_new_message_events, imap_poll_interval_seconds)
VALUES ('shared/support@machine1.example.com', FALSE, 30);
```

## Event Payloads

All events stored in `engine.__notify.data` as JSON.

### message-new
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

### message-claimed / message-unclaimed
```json
{
    "event_type": "message-claimed",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423,
    "actor_moniker": "alice",
    "timestamp": "2026-05-18T14:31:00Z"
}
```

### message-flagged
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

### message-deleted
```json
{
    "event_type": "message-deleted",
    "mailbox_name": "shared/support@machine1.example.com",
    "message_uid": 423,
    "timestamp": "2026-05-18T14:34:00Z"
}
```

## Usage

### Claiming a Message

```python
from postoffice import imap_client

# Claim message (sets flag + fires event)
success = imap_client.claim_message(
    args,
    mailbox_name="shared/support@example.com",
    message_uid=423,
    actor_moniker="alice",
    message_id="<abc@example.com>",
    message_from="user@example.com",
    message_subject="Help needed"
)
```

### Unclaiming a Message

```python
# Unclaim message (removes flag + fires event)
success = imap_client.unclaim_message(
    args,
    mailbox_name="shared/support@example.com",
    message_uid=423,
    actor_moniker="alice"
)
```

### Manual Event Firing

```python
# Fire custom event
success = imap_client.fire_new_message_event(
    args,
    mailbox_name="shared/support@example.com",
    message_uid=423,
    message_id="<abc@example.com>",
    message_from="user@example.com",
    message_subject="Help needed"
)
```

## IMAP Monitoring

The background polling thread automatically monitors configured mailboxes:

- Detects new messages → fires `message-new` event
- Detects flag changes → fires `message-flagged` event
- Detects deletions → fires `message-deleted` event
- Configurable per-mailbox poll intervals (default: 30 seconds)
- Thread-safe state tracking
- Graceful error handling (continues on IMAP errors)

### Registering Mailboxes for Monitoring

```python
from postoffice import imap_monitor

monitor = imap_monitor.get_monitor()
monitor.add_mailbox("shared/support@example.com")
monitor.add_mailbox("shared/sales@example.com")
```

## Testing

Run test suite:

```bash
python -m pytest tests/ -v
```

Current test coverage:
- **64 tests** - All passing
- Flag obfuscation and verification
- Event routing with pattern matching
- Message operations (claim/unclaim)
- Monitor lifecycle and polling
- Event payload structure validation

## Multi-Machine Support

Pattern-based routing enables multi-machine scenarios:

1. **Cyrus Replication** - Machine A and Machine B replicate mailbox state (flags) via Cyrus sync
2. **Shared IMAP Namespace** - Both machines see same logical mailbox: `shared/support@example.com`
3. **Shared PostgreSQL** - Both machines query same routing rules and write to same `engine.__notify`
4. **Pattern Rules** - Rules like `shared/%` match mailboxes on any machine

Example:
```sql
-- Single rule matches across all machines
INSERT INTO postoffice.notification_routing
(mailbox_name, event_type, recipient_moniker)
VALUES ('shared/%@%.example.com', 'message-claimed', 'admin');
```

## Complete Specification

For comprehensive documentation including SQL schema, implementation notes, and API reference, see [`NOTIFYD_SYNC_SPEC.md`](./NOTIFYD_SYNC_SPEC.md).

## Implementation Status

### ✅ Completed (Phases 0-6)

- Phase 0: Code cleanup and schema initialization
- Phase 2: Event integration layer with flag obfuscation
- Phase 3: IMAP client operations (claim/unclaim)
- Phase 4: Event firing integration
- Phase 5: Enhanced pattern-based routing with actor_moniker wildcards
- Phase 6: IMAP monitoring with embedded polling thread

### 🔮 Future (Phases 7-9)

- Phase 7: IDLE-based monitoring (optional optimization)
- Phase 8: README documentation (in progress)
- Phase 9: Final cleanup and polish

## References

- [Dovecot Shared Mailboxes](https://doc.dovecot.org/configuration_manual/shared_mailboxes/)
- [Python IMAP Documentation](https://docs.python.org/3/library/imaplib.html)
- [bbsengine6 Documentation](https://github.com/anomalyco/bbsengine6)
