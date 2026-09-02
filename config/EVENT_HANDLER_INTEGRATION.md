# Event Handler Integration: Cyrus notifyd → mistermcfeely

## Overview

The Cyrus IMAPd configuration has been updated to use **external event handling**, integrating Cyrus's built-in `notifyd` daemon directly with mistermcfeely's `message_client.py` module.

**Status:** ✅ Complete - Ready for deployment

## What Changed

### 1. imapd.conf Configuration

**Before:**
```conf
event_notifier: log
# event_notifier_path: /usr/local/bin/mcfeely-notify
```

**After:**
```conf
event_notifier: external
event_notifier_path: /usr/local/bin/mcfeely-notify
```

This tells Cyrus to send events to an external handler script instead of just logging them.

### 2. New Event Handler Script

**File:** `mcfeely-notify` (5.7 KB)
**Language:** Python 3
**Purpose:** Bridge between Cyrus events and mistermcfeely event routing

## How It Works

### Event Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Message Claim in Shared Mailbox                     │
│ User "alice" claims message UID 42 in shared/support        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Step 2: Cyrus IMAP Daemon Detects Change                    │
│ imapd sets ANNOTATE: /vendor/mcfeely/claimed-by = hash(...) │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Step 3: Cyrus notifyd Fires Event                           │
│ notifyd detects flag change, generates RFC 5423 event       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Step 4: Calls External Handler                              │
│ /usr/local/bin/mcfeely-notify -c MessageRead -u alice \     │
│   -m shared/support@localhost -p normal < json_event.json   │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Step 5: mcfeely-notify Script                               │
│ • Parses Cyrus event arguments                              │
│ • Reads JSON event data from stdin                          │
│ • Filters to shared/* mailboxes only                        │
│ • Converts event class to mistermcfeely type                │
│ • Imports and calls message_client.fire_event()             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Step 6: message_client.py Processing                        │
│ • Checks message_config (enabled?)                     │
│ • Queries message_routing (pattern match)              │
│ • Obfuscates actor moniker (HMAC-SHA256)                    │
│ • Constructs event payload JSON                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Step 7: Route to Recipients                                 │
│ For each matching rule in message_routing:             │
│ • Insert into engine.__notify (async)                       │
│ • Set urgency, recipient_moniker, etc.                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│ Step 8: External Systems Consume                            │
│ • Email notifier sends update                               │
│ • Chat bot posts to Slack                                   │
│ • Dashboard updates claim state                             │
│ • Webhook calls external API                                │
└─────────────────────────────────────────────────────────────┘
```

## mcfeely-notify Script Details

### Location
```
./mistermcfeely/config/mcfeely-notify
Deploy to: /usr/local/bin/mcfeely-notify
```

### Execution
Called by Cyrus notifyd with:
```bash
/usr/local/bin/mcfeely-notify -c <CLASS> -u <USER> -m <MAILBOX> -p <PRIORITY> < event.json
```

### Arguments
- `-c CLASS` : Event class (MessageNew, MessageExpunge, MessageRead, etc.)
- `-u USER` : Username that triggered the event
- `-m MAILBOX` : Mailbox name
- `-p PRIORITY` : Event priority (normal, urgent, etc.)
- `stdin` : JSON event data with uid, subject, from, date, etc.

### Event Class Mapping

Cyrus → mistermcfeely event type conversion:

| Cyrus Event Class | mistermcfeely Event Type | Description |
|------------------|-------------------------|-------------|
| MessageNew | message-new | New message arrived |
| MessageExpunge | message-deleted | Message deleted/expunged |
| MessageMove | message-moved | Message moved to folder |
| MessageRead | message-flagged | Flags changed (includes claims) |
| MailboxCreate | mailbox-created | Shared mailbox created |
| MailboxDelete | mailbox-deleted | Shared mailbox deleted |
| MailboxRename | mailbox-renamed | Shared mailbox renamed |

### Error Handling

The script gracefully handles errors:

1. **Missing mistermcfeely**: Logs warning, continues (returns 0)
2. **Invalid JSON**: Logs error, continues (returns 0)
3. **Database errors**: Logs error, continues (returns 0)
4. **All errors are non-fatal** - notifyd won't crash

Errors are logged to syslog:
```bash
journalctl -u cyrus-imapd | grep mcfeely-notify
```

## Deployment

### 1. Deploy Configuration Files

```bash
sudo cp ./mistermcfeely/config/cyrus.conf /etc/
sudo cp ./mistermcfeely/config/imapd.conf /etc/
sudo cp ./mistermcfeely/config/imapd.annotations /etc/
```

### 2. Deploy Event Handler Script

```bash
sudo cp ./mistermcfeely/config/mcfeely-notify /usr/local/bin/
sudo chmod 755 /usr/local/bin/mcfeely-notify
```

### 3. Initialize Cyrus

```bash
sudo mkdir -p /var/lib/imap /var/spool/imap
sudo chown -R cyrus:cyrus /var/lib/imap /var/spool/imap
sudo /usr/lib/cyrus-imapd/tools/mkimap
```

### 4. Start Service

```bash
sudo systemctl enable cyrus-imapd
sudo systemctl start cyrus-imapd
```

### 5. Verify Event Handler

```bash
# Check script deployment
ls -la /usr/local/bin/mcfeely-notify

# Check configuration
grep event_notifier_path /etc/postoffice/imapd.conf

# Check service started
systemctl status cyrus-imapd

# Watch events
journalctl -u cyrus-imapd -f | grep mcfeely-notify
```

## Database Configuration

To enable event routing, configure the database:

### 1. Create Notification Config

```sql
INSERT INTO postoffice.message_config
(mailbox_name, enable_new_message_events, imap_poll_interval_seconds)
VALUES 
  ('shared/%', TRUE, 5),
  ('shared/support@%', TRUE, 2);
```

### 2. Create Notification Routing

```sql
INSERT INTO postoffice.message_routing
(mailbox_name, event_type, actor_moniker, recipient_moniker, urgency)
VALUES 
  -- Admin sees all events
  ('shared/%', '*', NULL, 'admin', 'ROUTINE'),
  
  -- Team members notified when message is claimed
  ('shared/support%', 'message-flagged', NULL, 'support-team', 'IMPORTANT'),
  
  -- Alert when new message arrives
  ('shared/support%', 'message-new', NULL, 'support-oncall', 'URGENT');
```

## Testing

### Test 1: Service Health

```bash
systemctl status cyrus-imapd
```

### Test 2: Script Exists

```bash
file /usr/local/bin/mcfeely-notify
# Should show: Python script, ASCII text executable
```

### Test 3: Create Test Mailbox

```bash
sudo cyradm -u cyrus localhost <<'CYRADM'
cm shared/test@localhost
quit
CYRADM
```

### Test 4: Send Test Message

```bash
echo "Test message" | mail -s "Test" shared-test@localhost
```

### Test 5: Check Logs

```bash
# Watch logs in real-time
journalctl -u cyrus-imapd -f | grep mcfeely-notify

# Or check after the fact
journalctl -u cyrus-imapd | grep mcfeely-notify | tail -10
```

Expected log output:
```
mcfeely-notify: Event: MessageNew | Mailbox: shared/test@localhost | User: postfix | UID: 1 | Priority: normal
mcfeely-notify: Processing shared mailbox event: message-new in shared/test@localhost
mcfeely-notify: Event routed: message-new for shared/test@localhost
```

## Troubleshooting

### Events Not Being Fired

**Check 1: Script Permissions**
```bash
ls -la /usr/local/bin/mcfeely-notify
# Should be: -rwxr-xr-x
```

**Check 2: Configuration Syntax**
```bash
grep event_notifier /etc/postoffice/imapd.conf
# Should show: event_notifier: external
# Should show: event_notifier_path: /usr/local/bin/mcfeely-notify
```

**Check 3: Service Restarted**
```bash
sudo systemctl restart cyrus-imapd
journalctl -u cyrus-imapd | tail -20
```

**Check 4: Logs for Errors**
```bash
journalctl -u cyrus-imapd | grep -i "error\|warn" | head -20
```

### Script Not Being Called

Verify the handler is being invoked:
```bash
# Add a simple test to mcfeely-notify to see if it's called
# Edit /usr/local/bin/mcfeely-notify and add logging at the start:
# syslog.openlog('mcfeely-notify', syslog.LOG_PID, syslog.LOG_MAIL)
# syslog.syslog('mcfeely-notify invoked')
```

### mistermcfeely Not Imported

The script gracefully handles this - check logs:
```bash
journalctl -u cyrus-imapd | grep "mistermcfeely not available"
```

This is expected if mistermcfeely isn't installed. The script will log and continue.

## Event Payload Example

When a message is claimed, the event payload contains:

```json
{
  "event_type": "message-flagged",
  "mailbox_name": "shared/support@localhost",
  "message_uid": 42,
  "message_id": "<abc123@customer.example.com>",
  "from": "customer@example.com",
  "subject": "Urgent: System Down",
  "date": "2026-05-21T14:30:00Z",
  "actor": "alice",
  "priority": "urgent"
}
```

This is inserted into `bbsengine6.engine.__notify` for distribution to:
- Email notifier
- Chat/Slack integration
- Dashboard updates
- Webhook handlers
- Custom event consumers

## Integration with mistermcfeely Modules

The script integrates with:

### message_client.py
- `fire_event()` - Main function to route events
- `is_event_enabled()` - Checks if event type is enabled
- `get_routing_rules()` - Loads rules from database
- `obfuscate_moniker()` - HMAC hashing for actor privacy

### imap_client.py
- Called when message is claimed/unclaimed
- Sets ANNOTATE flags on message
- Triggers notifyd event

### imap_monitor.py
- Polls for changes in shared mailboxes
- Also can trigger events on detected changes

## Performance Considerations

1. **Non-blocking**: Handler is called asynchronously by notifyd
2. **Graceful degradation**: Errors in handler don't crash Cyrus
3. **Filtered**: Only shared/* mailboxes are processed
4. **Async insertion**: Events inserted into engine.__notify asynchronously
5. **Syslog buffering**: Log messages are buffered by syslog daemon

## Security

### What the Script Does

✓ Parses untrusted input from Cyrus
✓ Validates JSON event data
✓ Filters to shared mailboxes only
✓ Obfuscates actor identity (HMAC)
✓ Logs to syslog (no console output)

### What the Script Doesn't Do

✗ Execute arbitrary commands
✗ Write files (only logs to syslog)
✗ Access network directly
✗ Store credentials
✗ Import untrusted modules

### Recommended Permissions

```bash
# Script should be:
-rwxr-xr-x root:root /usr/local/bin/mcfeely-notify

# Log file should be:
-rw-r----- syslog:adm /var/log/syslog
# or
-rw------- root:root /var/log/maillog
```

## Related Documentation

- **CYRUS_SETUP.md** - Installation and configuration guide
- **README.md** - Configuration overview
- **imapd.conf** - IMAP daemon configuration with comments
- **../message_client.py** - Event routing implementation
- **../README.md** - mistermcfeely project overview

## Files Summary

| File | Purpose | Location |
|------|---------|----------|
| cyrus.conf | Service configuration | /etc/postoffice/cyrus.conf |
| imapd.conf | IMAP daemon config | /etc/postoffice/imapd.conf |
| imapd.annotations | Annotation schema | /etc/postoffice/imapd.annotations |
| mcfeely-notify | Event handler | /usr/local/bin/mcfeely-notify |

## Version Information

- **Cyrus IMAPd**: 3.0+ (tested with 3.4+)
- **Python**: 3.6+
- **RFC 5423**: IMAP4 Notifications (event spec)
- **mistermcfeely**: message_client.py module integration

## Summary

The Cyrus IMAPd configuration now provides **real-time event routing** from mailbox changes directly to mistermcfeely's notification system. This enables:

1. **Real-time notifications** when messages are claimed/unclaimed
2. **Integration with bbsengine6.__notify** for multi-channel distribution
3. **Flexible routing** based on message_routing database rules
4. **Secure event handling** with obfuscated actor identity
5. **Graceful degradation** if mistermcfeely unavailable

The event handler script bridges the gap between Cyrus's RFC 5423 event system and mistermcfeely's Python-based notification routing, making it a seamless integration.

