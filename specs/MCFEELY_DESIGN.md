# MCFEELY: Shared Mailbox Message Claiming System

## Overview
Enable an ops team (6-15 users) to claim individual messages in a shared IMAP mailbox to avoid duplicate work. Claims must be visible both as email headers and as tags/labels in email clients. Hashids (not emails) are used to protect op privacy.

## Recommended Architecture: Dovecot + IMAP Keywords + Sieve

### Why Dovecot
- Default IMAP server on Fedora, well-supported
- Easy to maintain, widely compatible
- Supports IMAP keywords (custom flags) that surface as tags in email clients

### Trade-offs
- **Cannot directly modify headers on stored messages** - IMAP (RFC 3501) requires message immutability
- Alternative (fetch→modify→append→delete) causes UID changes, breaks threading, client cache issues
- Tags + headers-on-reply is standards-compliant and cleaner

---

## Claim/Unclaim Mechanism

### HashID Generation

Use **HMAC-SHA256** with a shared secret to derive claim IDs from emails - deterministic and verifiable but not trivially reversible:

```
claim_id = HMAC-SHA256(secret, email) → first 8 chars → base62 encode
```

Example: `john@example.com` with secret `mcfeely-shared-secret` → `hJ7k2mNq`

This allows:
- Anyone with the secret can verify: "yes, this hashid maps to this email"
- Auditing: logs show hashid, admins can look up if needed
- No plaintext email in IMAP keywords

### Data Storage

Each claim stores:
1. **Claimer hashid** (keyword: `claimed-$HASHID`)
2. **Claim timestamp** (keyword: `claimed-$HASHID-since`)

Example keywords (user `hJ7k2mNq`, claimed at 2026-05-16 14:32:00Z):
- `claimed-hJ7k2mNq` (present = claimed)
- `claimed-hJ7k2mNq-since` = `20260516T143200Z`

### Claim/Unclaim Behavior

- **On claim**: Set both keywords with current timestamp (ISO compact form)
- **On unclaim**: Remove **both** keywords completely (identity AND timestamp)
- Claims without timestamps are invalid; timestamps without claims are invalid

### Reply/Forward Headers

| Header | Value |
|--------|-------|
| `X-Claimed-By` | HashID (e.g., `hJ7k2mNq`) |
| `X-Claimed-At` | ISO compact timestamp (e.g., `20260516T143200Z`) |

Both headers inserted by Sieve when replying/forwarding claimed messages.

---

## Configuration

Config stored in JSON file (`~/.mcfeely/config.json` or `/etc/mcfeely/mailboxes.json`):

```json
{
  "mailboxes": {
    "ops@example.com/imap/shared": {
      "secret": "mcfeely-shared-secret-ops"
    },
    "support@example.com/imap/shared": {
      "secret": "mcfeely-shared-secret-support"
    }
  },
  "current_mailbox": "ops@example.com/imap/shared"
}
```

Each shared mailbox gets its own secret for isolation.

---

## Claim Revocation/Reassignment

```bash
# Reassign all claims from old hashid to new hashid
mcfeely reassign --from hJ7k2mNq --to pQ9r3XvZ

# Or reassign by email
mcfeely reassign --email john@example.com --to jane@example.com

# Force unclaim (admin override)
mcfeely unclaim --force --uid 12345
```

### Reassignment Process

1. Fetch all messages with `claimed-$OLD_HASHID` keyword
2. For each message:
   - Remove `claimed-$OLD_HASHID` and `claimed-$OLD_HASHID-since`
   - Add `claimed-$NEW_HASHID` and `claimed-$NEW_HASHID-since` with current timestamp
3. **Audit log** (JSONLines format):
   ```json
   {"type": "reassign", "from": "hJ7k2mNq", "to": "pQ9r3XvZ", "count": 5, "timestamp": "20260516T150000Z"}
   {"type": "reassign_detail", "from": "hJ7k2mNq", "to": "pQ9r3XvZ", "uid": 12345, "original_claimed_at": "20260516T143200Z", "timestamp": "20260516T150000Z"}
   ```

### Audit Log Location

`~/.mcfeely/audit.log` (or configurable path)

---

## Architecture: sharedmailboxd Daemon

```
┌─────────────────────────────────────────────────────────┐
│                    sharedmailboxd                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │ IMAP Client │  │  IDLE/Pol   │  │   HTTP API     │   │
│  │ (pooled)    │  │ (monitor)   │  │  (:8080)       │   │
│  └─────────────┘  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────┘
         ▲                 ▲                 ▲
         │                 │                 │
    ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
    │ mcfeely │      │ Events  │      │ Future  │
    │  CLI    │      │ Scripts │      │   TUI   │
    └─────────┘      └─────────┘      └─────────┘
```

### Components

| Component | Purpose |
|-----------|---------|
| `sharedmailboxd` | Daemon: IMAP connection pool, message monitoring, API server |
| `mcfeely` CLI | Client that talks to daemon API |
| `mcfeely events` | Event trigger system for claim/unclaim hooks |
| `bbsengine6 TUI` | Later: interactive terminal UI |

### Daemon Features

- **Connection pooling**: Keep IMAP connections open, reuse across requests
- **IDLE command**: Real-time new message detection AND flag change detection (no polling)
  - Detects when ANY client claims/unclaims messages via IMAP
  - Triggers immediate state refresh and client notification
- **Real-time client sync**: Push claim updates to all connected TUI/GUI clients via WebSocket
  - When message claim state changes, all clients receive immediate notification
  - Eliminates stale data between polling intervals
- **Cyrus notifyd**: Alternative: receive real-time events via Cyrus `notifyd` (see [MCFEELY_CYRUS_IMAP.md](MCFEELY_CYRUS_IMAP.md))
  - Can integrate with **bbsengine6.notify** for user-facing BBS notifications on mail events
- **HTTP API**: `localhost:8080` for CLI and future integrations
- **WebSocket endpoint**: `ws://localhost:8080/ws` for real-time TUI/GUI clients
- **Event hooks**: Run scripts on claim/unclaim (e.g., notify Slack, update dashboard)
- **Config reloading**: SIGHUP to reload `mailboxes.json` without restart
- **Health check**: `GET /health` endpoint

### CLI to Daemon Communication

```bash
# CLI → Daemon API
mcfeely claim 12345      → POST /api/v1/mailbox/ops/claim {"uid": 12345}
mcfeely unclaim 12345    → POST /api/v1/mailbox/ops/unclaim {"uid": 12345}
mcfeely list             → GET  /api/v1/mailbox/ops/messages?claimed=true
mcfeely status           → GET  /health
```

### Data/Message Formats

#### HTTP API Request/Response

**Claim Message**
```json
// POST /api/v1/mailbox/{name}/claim
// Request:
{"uid": 12345}

// Response:
{"success": true, "claimed_by": "hJ7k2mNq", "claimed_at": "20260517T143200Z"}
```

**List Messages**
```json
// GET /api/v1/mailbox/{name}/messages

// Response:
{
  "messages": [
    {
      "uid": 12345,
      "subject": "Server down!",
      "from": "john@example.com",
      "date": "20260517T140000Z",
      "claimed_by": "hJ7k2mNq",
      "claimed_at": "20260517T143200Z"
    }
  ],
  "total": 150,
  "claimed_count": 45,
  "has_more": true
}
```

**Health Check**
```json
// GET /health

// Response:
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime_seconds": 3600,
  "mailboxes": ["ops", "support"],
  "connections": 3
}
```

#### WebSocket Messages

**Claim Update** (server → client)
```json
{
  "type": "claim_update",
  "mailbox": "ops",
  "uid": 12345,
  "claimed_by": "hJ7k2mNq",
  "claimed_at": "20260517T143200Z"
}
```

**Unclaim Update** (server → client)
```json
{
  "type": "unclaim_update",
  "mailbox": "ops",
  "uid": 12345
}
```

**New Message** (server → client)
```json
{
  "type": "message_new",
  "mailbox": "ops",
  "uid": 12346,
  "subject": "Urgent issue",
  "from": "alice@example.com",
  "date": "20260517T143500Z"
}
```

**Message Expunge** (server → client)
```json
{
  "type": "message_expunge",
  "mailbox": "ops",
  "uid": 12340
}
```

**Full Sync** (server → client, on connect or after gap)
```json
{
  "type": "full_sync",
  "mailbox": "ops",
  "messages": [
    {
      "uid": 12345,
      "subject": "Server down!",
      "from": "john@example.com",
      "claimed_by": "hJ7k2mNq"
    }
  ]
}
```

**Error** (server → client)
```json
{
  "type": "error",
  "code": "claim_failed",
  "message": "Message already claimed by another user",
  "claimed_by": "pQ9r3XvZ"
}
```

**Claim Conflict** (server → client, pushed to all clients when conflict detected)
```json
{
  "type": "claim_conflict",
  "mailbox": "ops",
  "uid": 12345,
  "claimed_by": "pQ9r3XvZ",
  "attempted_by": "hJ7k2mNq"
}
```

#### IMAP Claim Storage

**Dovecot (Keywords)**
```
\Keyword: claimed-hJ7k2mNq
\Keyword: claimed-hJ7k2mNq-since=20260517T143200Z
```

**Cyrus (Annotations)**
```
/vendor/mcfeely/claimed-by: "hJ7k2mNq"
/vendor/mcfeely/claimed-at: "20260517T143200Z"
```

### Race Condition Handling (Concurrent Claim Attempts)

When two clients attempt to claim the same message simultaneously, the system must handle the conflict gracefully:

#### Scenario

```
Client A                    Client B                    Daemon
   │                          │                           │
   │── claim 12345 ──────────►│                           │
   │                          │── claim 12345 ───────────►│
   │                          │                           │
   │                          │                    ┌──────┴──────┐
   │                          │                    │ RACE CONDITION│
   │                          │                    └──────┬──────┘
   │                          │                           │
```

#### Approaches

**1. First-Write-Wins (Recommended)**

The first claim to complete wins. The second receives an error.

```python
@app.route('/api/v1/mailbox/<name>/claim', methods=['POST'])
def claim_message(name: str):
    data = request.json
    uid = data['uid']
    claimed_by = data['claimed_by']
    
    client = get_mailbox_client(name)
    
    # Check if already claimed
    existing = client.get_claim(name, uid)
    if existing:
        return {
            'success': False,
            'error': 'already_claimed',
            'claimed_by': existing['claimed_by']
        }, 409
    
    # Attempt claim
    success = client.set_claim(name, uid, claimed_by, claimed_at)
    
    if success:
        # Verify we actually got it (another client might have claimed between check and set)
        verify = client.get_claim(name, uid)
        if verify['claimed_by'] != claimed_by:
            return {
                'success': False,
                'error': 'claim_conflict',
                'claimed_by': verify['claimed_by']
            }, 409
        
        trigger_event('on_claim', {...})
        return {'success': True}
    else:
        return {'success': False, 'error': 'imap_error'}, 500
```

**2. Optimistic Locking with Version**

Include a version/check in the claim request:

```json
// POST /api/v1/mailbox/ops/claim
{"uid": 12345, "expected_claimed_by": null}

// If already claimed:
// {"success": false, "error": "already_claimed", "claimed_by": "hJ7k2mNq"}
```

**3. Forced Claim (Admin Override)**

Allow forced claims with override capability:

```json
// POST /api/v1/mailbox/ops/claim
{"uid": 12345, "force": true}
```

This allows taking ownership even if already claimed (with audit logging).

#### Client Handling

TUI/GUI clients should handle the conflict response:

```python
if response.status_code == 409:
    error = response.json()
    if error['error'] == 'already_claimed':
        show_error(f"Already claimed by {error['claimed_by']}")
    elif error['error'] == 'claim_conflict':
        show_error("Claim taken by another user, refreshing...")
        refresh_message_list()
```

#### User Feedback

- **Immediate**: Show "claiming..." spinner while request in flight
- **Success**: Show success, update UI immediately
- **Conflict**: Show clear error: "Message already claimed by alice"
- **Conflict resolved**: If user A claimed and user B tried, B sees "alice claimed this 2 seconds ago"

#### Audit Logging

Log all claim attempts (success and failed):

```json
{"type": "claim_attempt", "uid": 12345, "claimed_by": "hJ7k2mNq", "success": false, "reason": "already_claimed", "claimed_by_winner": "pQ9r3XvZ", "timestamp": "..."}
```

### Event Hooks

```json
{
  "hooks": {
    "on_claim": ["/usr/local/bin/slack-notify.sh", "/usr/local/bin/update-dashboard.sh"],
    "on_unclaim": ["/usr/local/bin/update-dashboard.sh"]
  }
}
```

### Real-time Client Synchronization

When any client claims or unclaims a message, all other connected clients should see the update immediately:

```
┌────────────┐      ┌─────────────┐       ┌────────────┐
│  TUI       │      │   Daemon    │       │   TUI      │
│  Client A  │      │             │       │  Client B  │
└─────┬──────┘      └──────┬──────┘       └─────┬──────┘
      │                    │                    │
      │ claim 12345       │                    │
      │──────────────────►│                    │
      │                    │                    │
      │              IDLE detects              │
      │              flag change              │
      │                    │                    │
      │     push update   │   push update      │
      │◄──────────────────│◄───────────────────│
      │ {uid:12345,       │ {uid:12345,        │
      │  claimed_by: A}  │  claimed_by: A}   │
      │                    │                    │
```

#### How It Works

1. **Client A** calls `POST /api/v1/mailbox/ops/claim` to claim message 12345
2. **Daemon** writes claim to IMAP (keyword or annotation)
3. **IDLE loop** detects flag change on IMAP connection
4. **Daemon** broadcasts update to all WebSocket clients:
   ```json
   {
     "type": "claim_update",
     "mailbox": "ops",
     "uid": 12345,
     "claimed_by": "alice",
     "claimed_at": "20260517T143200Z"
   }
   ```
5. **Client B** receives push notification and updates local state
6. **UI** immediately reflects the new claim status

#### WebSocket Protocol

```python
# Client connects to ws://localhost:8080/ws
# Server sends messages:

# Claim update
{"type": "claim_update", "mailbox": "ops", "uid": 12345, "claimed_by": "alice", "claimed_at": "..."}

# Unclaim update
{"type": "unclaim_update", "mailbox": "ops", "uid": 12345}

# New message
{"type": "message_new", "mailbox": "ops", "uid": 12346, "subject": "...", "from": "..."}

# Message expunged
{"type": "message_expunge", "mailbox": "ops", "uid": 12340}

# Full refresh (on connect or after gap)
{"type": "full_sync", "mailbox": "ops", "messages": [...]}
```

#### IDLE + WebSocket Architecture

```
                           IMAP IDLE
                    ┌─────────────────────┐
                    │    watches mailbox   │
                    │   for ANY flag change│
                    └──────────┬────────────┘
                               │
                    ┌──────────┴────────────┐
                    │  sharedmailboxd        │
                    │                       │
                    │  ┌─────────────────┐   │
                    │  │ WebSocket       │   │
                    │  │ Clients         │   │
                    │  └────────┬────────┘   │
                    └──────────┴────────────┘
```

The daemon uses a single IMAP IDLE connection per mailbox. When ANY client (even outside mcfeely) modifies flags, IDLE triggers, daemon detects the change, and broadcasts to all mcfeely clients.

---

## Implementation Steps

### 1. Environment Setup
- Install/configure Dovecot on Fedora if not already present
- Enable IMAP and ACL plugins
- Configure shared mailbox with team ACLs (shared namespace or folder ACLs)

### 2. sharedmailboxd
- Create daemon with IMAP client pool and HTTP API
- Implement IDLE for real-time message monitoring
- Add event hook system

### 3. mcfeely CLI
- Create CLI tool that communicates with daemon API
- Implement claim/unclaim/reassign commands

### 4. Sieve Configuration
- Install Dovecot Sieve plugin (dovecot-pigeonhole)
- Write Sieve rule: when user replies to/forwards message with keyword, add `X-Claimed-By` and `X-Claimed-At` headers to outgoing mail

### 5. Client Setup

Email clients need to display IMAP keywords as tags/labels. Here's how to configure the main clients:

#### Thunderbird Configuration

**Step 1: Enable custom keywords as tags**

Thunderbird shows custom IMAP keywords as "User Tags". By default it maps several keywords, but we need to ensure our claim keywords are visible:

1. Open Thunderbird → Settings → Tags
2. Click "Add" to create a new tag
3. Name it "Claimed by me" (or similar)
4. The tag will automatically associate with the IMAP keyword `claimed-<hashid>`

**Step 2: View claimed messages**

The claim keywords are stored as IMAP flags like `\Keyword claimed-hJ7k2mNq`. To see them in Thunderbird:

1. Open the shared mailbox
2. View → Show → Tags (ensure this is checked)
3. Messages with claim keywords will show colored tags based on the associated tag

**Step 3: Manual refresh**

Thunderbird may not auto-refresh tags immediately. Press Ctrl+Shift+R (or View → Refresh) to reload the folder and see updated claim status.

**Note on claim visibility:**
- Each user's hashid is unique (e.g., `hJ7k2mNq`)
- When YOU claim a message, your keyword `claimed-hJ7k2mNq` is added
- You'll see your own claim as the associated tag color
- Other users' claims appear as their unique keyword - you won't see "who" claimed it, just that it's claimed by someone else
- To see WHO claimed it, use the mcfeely CLI (`mcfeely list`) or TUI

**Step 4: Create filters (optional)**

Create a Thunderbird filter to highlight claimed messages:

1. Edit → Filters → New
2. Match: "Keyword" "contains" "claimed-"
3. Action: "Tag" "Claimed" (or custom tag)

#### Outlook Configuration

- Outlook uses "Categories" which map to IMAP keywords
- May require third-party plugin for full keyword support
- Alternative: Use mcfeely CLI/TUI to see claim status

#### Roundcube Configuration

- Install "managesieve" plugin on server
- Create a Sieve rule to add visual indicators based on keywords
- Or use mcfeely TUI/GUI as the primary claim interface

#### CLI as Alternative

For users who prefer not to configure email client tags:
- Use `mcfeely list` to see all messages with claim status
- Use `mcfeely claim <uid>` to claim messages
- Use mcfeely TUI for a dedicated claim management interface

---

## Files to Create

- `sharedmailboxd/` - Daemon source
  - `main.go` - Entry point
  - `imap/client.go` - IMAP client with connection pool
  - `imap/idle.go` - IDLE command handling
  - `api/server.go` - HTTP API server
  - `config/config.go` - Config loading from JSON
  - `claims/claims.go` - Claim/unclaim/reassign logic
  - `hashid/hashid.go` - HMAC-SHA256 hashid generation
  - `events/hooks.go` - Event hook system

- `mcfeely/` - CLI source
  - `main.go` - Entry point
  - `cmd/claim.go` - Claim command
  - `cmd/unclaim.go` - Unclaim command
  - `cmd/list.go` - List command
  - `cmd/reassign.go` - Reassign command

- `sieve/claim-header.sieve` - Sieve script for headers on reply/forward
- `tests/` - Comprehensive test suite
- `docker/Dockerfile.dovecot` - Test Dovecot container

---

## Testing Strategy (Headless Only)

All tests run via CLI/API against containerized IMAP server - no GUI email client testing.

### Test Environment
- **Docker container** with Dovecot + pigeonhole (Sieve)
- **Test fixtures**: Pre-populated messages in shared mailbox
- **Isolated per test**: Fresh mailbox per test or cleanup after each

### Test Categories

**1. Claim/Unclaim Tests** (CLI + IMAP)
- `test_claim_sets_keywords` - Verify both keywords set on claim
- `test_unclaim_removes_both_keywords` - Verify cleanup
- `test_claim_idempotent` - Same user claiming twice succeeds
- `test_claim_overwrite` - Different user can overwrite claim
- `test_unclaim_ownership` - Cannot unclaim another's claim
- `test_hashid_deterministic` - Same email → same hashid

**2. Reply/Forward Tests** (Sieve + IMAP)
- `test_reply_includes_headers` - Sieve adds X-Claimed-By, X-Claimed-At
- `test_forward_includes_headers` - Sieve adds headers on forward
- `test_no_headers_unclaimed` - No headers when message not claimed

**3. Revocation/Reassignment Tests** (CLI + IMAP)
- `test_reassign_transfers_all` - All messages transferred
- `test_reassign_updates_timestamp` - New timestamp on reassign
- `test_reassign_logs_audit` - Audit log includes original hashid
- `test_force_unclaim_admin` - Admin can override

**4. Concurrency Tests**
- `test_concurrent_claim` - Race condition handling
- `test_concurrent_unclaim_and_reply` - No data corruption

**5. Identity/Hashid Tests**
- `test_hashid_generation` - Correct HMAC output
- `test_hashid_verification` - Can verify email ↔ hashid mapping

---

## Open Questions
1. Should the claiming tool be CLI or web-based?
2. Is there an existing web framework in mrmcfeely to integrate with?
3. Want me to explore existing mrmcfeely code to see how this might fit in?

---

## Tkinter GUI Plan

### Overview
Create a native desktop GUI using Python's tkinter library for claiming/unclaiming messages in shared mailboxes. The GUI will communicate with `sharedmailboxd` via its HTTP API.

### GUI Features

1. **Mailbox Selection**
   - Dropdown to select configured mailbox
   - Display current mailbox status

2. **Message List View**
   - Table showing: UID, Subject, From, Claim Status, Claimed By, Claimed At
   - Color-coded claim status (green=claimed, white=unclaimed)
   - Sortable columns

3. **Claim/Unclaim Actions**
   - Select message(s) and click Claim/Unclaim
   - Confirmation dialog for unclaim
   - Keyboard shortcuts (C=claim, U=unclaim)

4. **Real-time Updates**
   - Poll daemon API every 5 seconds for changes
   - Or use daemon push notifications if implemented

5. **Connection Status**
   - Status bar showing daemon connection health
   - Auto-reconnect on failure

### UI Layout

```
┌─────────────────────────────────────────────────────────┐
│ [Mailbox: ▼ ops@example.com]  [Refresh] [Settings]      │
├─────────────────────────────────────────────────────────┤
│ UID  │ Subject          │ From          │ Status       │
├──────┼──────────────────┼───────────────┼──────────────┤
│ 1234 │ Server down!     │ john@...      │ [Claimed by] │
│ 1235 │ Question about   │ jane@...      │ [Unclaimed]  │
│ 1236 │ Urgent: outage   │ bob@...       │ [Claimed by] │
├─────────────────────────────────────────────────────────┤
│ [Claim] [Unclaim] [Refresh]           Status: Connected│
└─────────────────────────────────────────────────────────┘
```

### File Structure

```
mcfeely/
├── gui/
│   ├── main.py          # GUI entry point
│   ├── app.py           # Main application class
│   ├── message_list.py  # Message table widget
│   ├── dialogs.py       # Confirmation dialogs
│   └── api_client.py    # HTTP client for daemon
```

### Implementation Steps

1. **API Client** (`api_client.py`)
   - `get_messages(mailbox)` - Fetch all messages
   - `claim_message(mailbox, uid)` - Claim a message
   - `unclaim_message(mailbox, uid)` - Unclaim a message
   - `get_status()` - Health check

2. **Main Window** (`app.py`)
   - Initialize tkinter window
   - Create toolbar with mailbox selector
   - Create message table (Treeview)
   - Create action buttons
   - Add status bar

3. **Message List** (`message_list.py`)
   - Use tkinter.ttk.Treeview
   - Implement column sorting
   - Add row coloring based on claim status

4. **Dialogs** (`dialogs.py`)
   - Confirmation dialog for destructive actions
   - Error dialogs for API failures
   - About dialog

### Configuration

Store GUI preferences in `~/.mcfeely/gui.json`:
```json
{
  "refresh_interval": 5,
  "window_size": "800x600",
  "remember_mailbox": true
}
```

### Dependencies

- Python 3.9+ (tkinter built-in)
- `requests` library for HTTP API calls

---

## TUI Plan (using bbsengine6.listbox.ListboxCursor)

### Overview
Create a terminal UI using bbsengine6's `ListboxCursor` class for claiming/unclaiming messages. The TUI provides an interactive, keyboard-driven interface that works well in terminal environments.

### Key Integration Points

- Use `ListboxCursor` with lazy-loading via daemon API cursor
- Leverage existing bbsengine6 IO, theming, and keyboard handling
- Custom keys for claim/unclaim actions

### TUI Features

1. **Mailbox Selection**
   - Initial selection screen to choose mailbox
   - Store last-used mailbox in config

2. **Message List View**
   - Use `ListboxCursor` with custom `MessageItem` class
   - Display: UID, Subject (truncated), From, Claim Status
   - Color coding via bbsengine6 themes (claimed = distinct color)
   - Lazy loading for large message lists

3. **Claim/Unclaim Actions**
   - Custom keyboard bindings:
     - `c` - Claim selected message
     - `u` - Unclaim selected message
     - `r` - Refresh message list
   - Confirmation prompt for unclaim

4. **Status Display**
   - Title shows: mailbox name, total messages, claimed count
   - Footer shows: connection status, current user hashid

5. **Real-time Updates (WebSocket)**
   - Connect to daemon WebSocket endpoint `ws://localhost:8080/ws`
   - Receive instant updates when any client claims/unclaims messages
   - Updates trigger immediate UI refresh without manual poll
   - Visual indicator when connection is live vs disconnected
   - Auto-reconnect on disconnect

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│ MCFeely TUI - ops@example.com - 150 messages (45 claimed)   │
├─────────────────────────────────────────────────────────────┤
│ Subject                  │ From           │ Status         │
├──────────────────────────┼────────────────┼────────────────┤
│ Server down!             │ john@...       │ CLAIMED hJ7..  │
│ Question about...       │ jane@...       │ ─────────────  │
│ Urgent: outage          │ bob@...        │ CLAIMED pQ9..  │
├──────────────────────────┴────────────────┴────────────────┤
│ [c]Claim [u]Unclaim [r]Refresh [q]Quit    │ Connected     │
└─────────────────────────────────────────────────────────────┘
```

Note: UID hidden by default to maximize subject visibility. Use `Enter` to view full message details including UID.

### File Structure

```
mcfeely/
├── tui/
│   ├── main.py          # TUI entry point
│   ├── app.py          # Main TUI application
│   ├── message_item.py # ListboxItem subclass for messages
│   ├── api_client.py   # HTTP client for daemon (can share with GUI)
│   ├── websocket.py    # WebSocket client for real-time updates
│   └── state.py        # Application state (current mailbox, etc.)
```

### Implementation Steps

1. **MessageItem** (`message_item.py`)
   - Subclass `ListboxItem` from bbsengine6.listbox
   - Format message row with padding/truncation
   - Add claim status color based on content

2. **API Cursor** (`api_client.py`)
   - Add cursor-based pagination to daemon API: `GET /api/v1/mailbox/{name}/messages?cursor={offset}&limit={count}`
   - Return cursor object that supports `scroll()` and `fetchmany()`

3. **Main App** (`app.py`)
   - Initialize bbsengine6 screen/io
   - Create `ListboxCursor` with API cursor
   - Register custom keys for claim/unclaim/refresh
   - Handle navigation and actions

4. **WebSocket Client** (`websocket.py`)
   - Connect to `ws://localhost:8080/ws` on startup
   - Handle incoming `claim_update`, `unclaim_update`, `message_new` events
   - Trigger UI refresh on received updates
   - Auto-reconnect on disconnect with exponential backoff
   - Show connection status in footer

4. **State Management** (`state.py`)
   - Track current mailbox
   - Track selected message UID
   - Store user hashid for display

### API Extensions for Cursor Support

Add to daemon API:
```python
# GET /api/v1/mailbox/{name}/messages?offset=0&limit=20
# Returns: {"messages": [...], "total": 150, "has_more": true}
```

### Configuration

Store TUI preferences in `~/.mcfeely/tui.json`:
```json
{
  "refresh_interval": 10,
  "items_per_page": 20,
  "last_mailbox": "ops@example.com/imap/shared"
}
```

### Dependencies

- Python 3.9+
- bbsengine6 (from local path)
- `requests` library for HTTP API calls

### IMAP Servers for Fedora with Header Modification

#### Cyrus IMAP
- Available in Fedora repos (`cyrus-imapd`)
- Supports ANNOTATE extension (RFC 5257) and METADATA extension
- Allows storing per-message metadata/annotations
- More complex setup than Dovecot

#### Dovecot
- Default on Fedora, very well supported
- Does NOT allow direct header modification (messages immutable per RFC 3501)
- Alternative: Use IMAP keywords/flags (custom flags like `$Label1-$Label5`)
- See [MCFEELY_DOVECOT.md](MCFEELY_DOVECOT.md) for detailed setup

### IMAP Header Modification Approaches

1. **IMAP ANNOTATE Extension (Cyrus)** - RFC 5257
   - Supports annotations on messages
   - Different from email headers, but can store metadata

2. **IMAP METADATA Extension** - RFC 5464
   - GETMETADATA/SETMETADATA commands
   - Server/mailbox annotations, some support for message annotations

3. **Fetch → Modify → Append → Delete**
   - Works with any IMAP server
   - Breaks threading, causes UID changes, client cache issues

4. **IMAP Keywords (Flags)**
   - Standard way to mark messages without modifying them
   - Visible as tags/labels in email clients
   - `$Label1` through `$Label5` standard, plus custom keywords

---

See [MCFEELY_CYRUS_IMAP.md](MCFEELY_CYRUS_IMAP.md) for detailed Cyrus IMAPd configuration.

### Comparison: Cyrus vs Dovecot

| Feature | Cyrus IMAPd | Dovecot |
|---------|-------------|---------|
| Per-message annotations | Yes (native) | Via plugin |
| Header modification | Via annotations | Not supported |
| Setup complexity | Higher | Lower |
| Fedora support | Good | Excellent |
| LMTP integration | Native | Via dovecot-lda |
| Shared mailboxes | ACL-based | ACL-based |
| Sieve support | Built-in | Via pigeonhole |

### Recommendation

- **Use Cyrus** if you need per-message metadata/annotations and can manage complexity
- **Use Dovecot** if you prefer simpler setup and can work with IMAP keywords instead

---

## Implementation Guides

See detailed setup guides in separate documents:

- **[MCFEELY_DOVECOT.md](MCFEELY_DOVECOT.md)** - Dovecot implementation using IMAP keywords
- **[MCFEELY_CYRUS_IMAP.md](MCFEELY_CYRUS_IMAP.md)** - Cyrus IMAPd implementation using ANNOTATE extension
- **[MCFEELY_POSTFIX.md](MCFEELY_POSTFIX.md)** - Postfix MTA configuration
- **[MCFEELY_SIEVE.md](MCFEELY_SIEVE.md)** - Sieve script configuration