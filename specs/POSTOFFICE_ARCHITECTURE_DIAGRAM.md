# Postoffice Architecture Diagram

## System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    POSTOFFICE MODULE SYSTEM                      │
└──────────────────────────────────────────────────────────────────┘

USER INTERFACES (Top Layer)
┌─────────────────────────────────────────────────────────────┐
│ TUI Interfaces                                              │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────┐  ┌──────────────────┐  ┌────────────┐  │
│ │   main.py       │  │ password_mgr.py  │  │ mailbox.py │  │
│ │ Main Menu       │  │ Password UI      │  │ CRUD UI    │  │
│ │ [V][M][Q]       │  │ [1][2][q]        │  │ [A][E][M]  │  │
│ └─────────────────┘  └──────────────────┘  └────────────┘  │
│                                                              │
│ CLI Entry Point (__main__.py)                               │
│ startup-check | startup-generate | startup-install         │
└─────────────────────────────────────────────────────────────┘
                              ↓
INITIALIZATION LAYER
┌─────────────────────────────────────────────────────────────┐
│ startup.py - Encryption Key Management                      │
├─────────────────────────────────────────────────────────────┤
│ get_encryption_key()                                        │
│   ↓ Priority:                                               │
│   1. POSTOFFICE_PASSWORD_KEY (env var)                      │
│   2. /etc/postoffice/password.key (file)                    │
│   3. ~/.postoffice/password.key (user file)                 │
│   4. ERROR                                                  │
│                                                              │
│ initialize_password_system()  ← Called once, cached         │
│   ├─ validate_encryption_key()                              │
│   └─ validate_password_config()                             │
│                                                              │
│ check_key_setup()     ← Diagnostic function                 │
│                                                              │
│ Key Properties: 32 bytes, AES-256-GCM, base64 encoded      │
└─────────────────────────────────────────────────────────────┘
                              ↓
PASSWORD AUTHENTICATION LAYER
┌─────────────────────────────────────────────────────────────┐
│ password_auth.py - Credential Resolution                    │
├─────────────────────────────────────────────────────────────┤
│ get_auth_password(mailbox_id, member, pwd_type)             │
│                                                              │
│ For Shared Mailbox (mailbox_id set):                        │
│   ├─ Try: member_password.get_shared_mailbox_password()    │
│   │        (from postoffice.member_mailbox_password)        │
│   └─ Fallback: _get_shared_mailbox_default_password()       │
│               (from postoffice.mailbox_password)            │
│                                                              │
│ For Personal Account (mailbox_id None):                     │
│   └─ member_password.get_personal_password()                │
│      (from engine.__member)                                 │
│                                                              │
│ validate_password() ← Extensible validation                │
└─────────────────────────────────────────────────────────────┘
                         ↙              ↘
       ┌──────────────────────┐  ┌──────────────────────┐
       │ MEMBER PASSWORDS     │  │ SHARED MAILBOX PWDS  │
       │ member_password.py   │  │ shared_mailbox_pw.py │
       └──────────────────────┘  └──────────────────────┘
       
       Personal Account Mgmt     Shared Mailbox Mgmt
       ┌──────────────────┐      ┌──────────────────┐
       │ set_personal()   │      │ set_shared()     │
       │ get_personal()   │      │ get_shared()     │
       │ list_personal()  │      │ list_shared()    │
       │ delete_personal()│      │ delete_shared()  │
       └──────────────────┘      └──────────────────┘
              ↓ Encrypt/Decrypt         ↓ Encrypt/Decrypt
       ┌──────────────────┐      ┌──────────────────┐
       │ bbsengine6.util  │      │ bbsengine6.util  │
       │ (AES-256-GCM)    │      │ (AES-256-GCM)    │
       └──────────────────┘      └──────────────────┘
                              ↓
IMAP INTEGRATION LAYER
┌─────────────────────────────────────────────────────────────┐
│ imap_lib.py - Cyrus IMAP Connection                         │
├─────────────────────────────────────────────────────────────┤
│ get_imap_credentials(member_moniker, mailbox_id)            │
│   1. Direct args: args.imaphost/imapuser/imappassword       │
│   2. Fallback: password_auth.get_auth_password()            │
│                                                              │
│ connect_cyrus(readonly=True, timeout=10)                    │
│   └─ Returns: imaplib.IMAP4_SSL connection                  │
│              (or None on error)                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
MESSAGE OPERATIONS LAYER
┌─────────────────────────────────────────────────────────────┐
│ imap_client.py - Message Claiming                           │
├─────────────────────────────────────────────────────────────┤
│ claim_message(mailbox, uid, actor_moniker)                  │
│   ├─ Set Cyrus flag: ClaimedBy<moniker>                     │
│   │  (optionally obfuscated: HMAC-SHA256)                    │
│   └─ fire_event("message-claimed", {...})                   │
│                                                              │
│ unclaim_message(mailbox, uid, actor_moniker)                │
│   ├─ Remove claim flag                                      │
│   └─ fire_event("message-unclaimed", {...})                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
BACKGROUND MONITORING LAYER
┌─────────────────────────────────────────────────────────────┐
│ imap_monitor.py - IMAP Mailbox Monitoring                   │
├─────────────────────────────────────────────────────────────┤
│ IMAPMonitor(args, poll_interval=30)                         │
│   ├─ start()  → Spawn polling thread                        │
│   └─ _run_loop()                                            │
│       ├─ For each mailbox: _check_mailbox()                 │
│       ├─ Detect: New messages                               │
│       ├─ Detect: Flag changes                               │
│       └─ Detect: Message deletions                          │
│                                                              │
│ State Tracking:                                             │
│   ├─ MailboxState: uid_validity, last_poll_time            │
│   └─ MessageState: uid, flags, message_id, from, subject   │
│                                                              │
│ Events Fired:                                               │
│   ├─ message-new      (new message detected)                │
│   ├─ message-flagged  (flags changed)                       │
│   └─ message-deleted  (message removed)                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
EVENT/NOTIFICATION LAYER
┌─────────────────────────────────────────────────────────────┐
│ message_client.py - Event Firing & Routing                  │
├─────────────────────────────────────────────────────────────┤
│ fire_event(mailbox, event_type, event_data)                 │
│   ├─ Call bbsengine6.message.send()                        │
│   └─ Route via postoffice.message_routing rules        │
│                                                              │
│ Event Types (events.py):                                    │
│   ├─ message-new                                            │
│   ├─ message-claimed                                        │
│   ├─ message-unclaimed                                      │
│   ├─ message-flagged                                        │
│   └─ message-deleted                                        │
│                                                              │
│ Obfuscation Functions:                                      │
│   ├─ obfuscate_moniker() → HMAC-SHA256(moniker, secret)    │
│   ├─ format_claim_flag() → Cyrus flag name                 │
│   └─ verify_claim_flag() → Verify flag matches moniker     │
│                                                              │
│ Secret Source Priority:                                     │
│   1. MCFEELY_OBFUSCATE_SECRET (env var)                     │
│   2. args.databasepassword                                  │
│   3. None (plain text)                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
AUDIT & LOGGING LAYER
┌─────────────────────────────────────────────────────────────┐
│ audit_log.py - Password Operation Logging                   │
├─────────────────────────────────────────────────────────────┤
│ log_password_operation(                                     │
│   action="set|delete|access",                              │
│   target_type="personal|shared_mailbox",                   │
│   target_moniker,                                          │
│   password_type="inbound|outbound",                        │
│   performed_by                                             │
│ )                                                           │
│                                                              │
│ log_auth_failure(member, pwd_type, reason)                 │
│                                                              │
│ Logged via: bbsengine6.logentry()                           │
│ Format: [PASSWORD] ACTION | key=value | key=value          │
└─────────────────────────────────────────────────────────────┘
                              ↓
DATABASE LAYER
┌─────────────────────────────────────────────────────────────┐
│ Database Tables                                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ engine.__member                                             │
│   ├─ inbound_password (encrypted)                           │
│   └─ outbound_password (encrypted)                          │
│                                                              │
│ postoffice.__address                                          │
│   ├─ id                                                     │
│   ├─ address (email address)                                │
│   ├─ enabled                                                │
│   ├─ maillocation (Cyrus path)                              │
│   └─ memberid                                               │
│                                                              │
│ postoffice.mailbox_password                                 │
│   ├─ address (FK from mailbox)                              │
│   ├─ kind ("inbound outbound")                              │
│   └─ password (encrypted legacy format)                     │
│                                                              │
│ postoffice.member_mailbox_password                          │
│   ├─ mailbox_id (FK)                                        │
│   ├─ member_moniker                                         │
│   ├─ password_type ("inbound"|"outbound")                   │
│   ├─ encrypted_password (AES-256-GCM)                       │
│   ├─ set_by_moniker                                         │
│   ├─ created_at                                             │
│   └─ updated_at                                             │
│                                                              │
│ postoffice.virtual                                          │
│   ├─ pattern (virtual pattern)                              │
│   ├─ result (delivery target)                               │
│   └─ enabled                                                │
│                                                              │
│ postoffice.message_routing                             │
│   ├─ event_type                                             │
│   ├─ condition                                              │
│   └─ action                                                 │
│                                                              │
│ postoffice.__address                              │
│   ├─ mailbox_id                                             │
│   └─ poll_interval_seconds                                  │
│                                                              │
│ bbsengine6.message transport                                │
│   ├─ event_type                                             │
│   ├─ mailbox_name                                           │
│   ├─ event_data (JSON)                                      │
│   └─ created_at                                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow Examples

### Example 1: Setting a Member's Shared Mailbox Password

```
User → TUI (password_manager.py)
    ↓
_set_shared_mailbox_password()
    ↓
shared_mailbox_password.set_shared_mailbox_password(
    args,
    mailbox_id=5,
    member_moniker="alice",
    password_type="inbound",
    password="<plaintext>",
    set_by_moniker="alice"
)
    ↓
1. Encrypt password → bbsengine6.util.encrypt_password()
       Uses: get_encryption_key() → POSTOFFICE_PASSWORD_KEY
       Cipher: AES-256-GCM
       Result: <ciphertext>
    
2. INSERT/UPDATE postoffice.member_mailbox_password
       mailbox_id=5
       member_moniker="alice"
       password_type="inbound"
       encrypted_password=<ciphertext>
       set_by_moniker="alice"
       created_at=NOW()
       updated_at=NOW()
    
3. Return: True/False
    ↓
User sees: "✓ inbound password set for alice"
```

### Example 2: Alice Accessing Shared Mailbox Support@Example.com

```
IMAP Server receives: alice@example.com login request
    ↓
imap_client.py needs to open: "shared/support@example.com"
    ↓
imap_lib.connect_cyrus(
    args,
    member_moniker="alice",
    mailbox_id=5         # support@example.com
)
    ↓
1. get_imap_credentials(member_moniker="alice", mailbox_id=5)
    ├─ Check: args.imaphost/imapuser/imappassword? No
    └─ Fall back: password_auth.get_auth_password(
         args,
         mailbox_id=5,
         member_moniker="alice",
         password_type="inbound",
         requester_moniker="alice"
       )
    ↓
2. get_auth_password() logic:
    ├─ Is shared mailbox (mailbox_id=5)?
    └─ Try per-member password first:
       shared_mailbox_password.get_shared_mailbox_password(
           args,
           mailbox_id=5,
           member_moniker="alice",
           password_type="inbound",
           requester_moniker="alice"
       )
       ├─ Query: SELECT encrypted_password FROM 
       │         postoffice.member_mailbox_password 
       │         WHERE mailbox_id=5 AND member_moniker="alice" 
       │         AND password_type="inbound"
       ├─ Found: <ciphertext>
       └─ Decrypt: bbsengine6.util.decrypt_password(<ciphertext>)
          Returns: "shared_mailbox_password_123"
    ↓
3. Result: IMAP credentials ready
    {
        "host": "imap.example.com",
        "port": 993,
        "username": "support@example.com",
        "password": "shared_mailbox_password_123"
    }
    ↓
4. connect_cyrus() opens IMAP4_SSL connection
    ↓
✓ Connection established
```

### Example 3: Monitoring Detects New Message in Shared Mailbox

```
IMAPMonitor._run_loop() (background thread)
    ├─ Polls every 30 seconds (configurable)
    └─ _check_mailbox("shared/support@example.com")
        ↓
1. Fetch mailbox status: imap.select("shared/support@example.com")
    
2. Fetch message list: imap.search(None, "ALL")
    
3. For each message: imap.fetch(uid, "(FLAGS BODY.PEEK[HEADER])")
    
4. Compare with MailboxState:
    - UID 42 not in previous state
    - → NEW MESSAGE DETECTED
    
5. Parse message headers:
    - message_id: "<msg42@example.com>"
    - from: "customer@example.com"
    - subject: "Help needed"
    
6. Create MessageState for UID 42:
    MessageState(
        uid=42,
        flags={"\\Seen"},
        message_id="<msg42@example.com>",
        from_addr="customer@example.com",
        subject="Help needed"
    )
    
7. Fire event: message_client.fire_event(
       args,
       mailbox_name="shared/support@example.com",
       event_type="message-new",
       event_data={
           "event_type": "message-new",
           "mailbox_name": "shared/support@example.com",
           "message_uid": 42,
           "message_id": "<msg42@example.com>",
           "from": "customer@example.com",
           "subject": "Help needed"
       }
   )
    ↓
8. fire_event() calls bbsengine6.message.send:
    bbsengine6.message.send(
        notification_type="message-new",
        recipients=[...],
        data={"event_type":"message-new",...},
        urgency="ROUTINE"
    )
    ↓
9. Notification routing (postoffice.message_routing):
    SELECT * FROM postoffice.message_routing
    WHERE event_type="message-new"
    AND condition MATCHES mailbox_name
    → Take action (email, webhook, etc.)
```

### Example 4: Member Claims a Message

```
Alice clicks: [CLAIM] message 42 in support@example.com
    ↓
TUI calls: imap_client.claim_message(
    args,
    mailbox_name="shared/support@example.com",
    message_uid=42,
    actor_moniker="alice",
    message_id="<msg42@example.com>",
    message_from="customer@example.com",
    message_subject="Help needed"
)
    ↓
1. Get obfuscation secret:
    message_client.get_obfuscate_secret(args)
    → Checks: MCFEELY_OBFUSCATE_SECRET env var
    → If not found: args.databasepassword
    → If not found: None (use plaintext)
    
2. Format claim flag:
    If secret="my_secret":
        obfuscate_moniker("alice", "my_secret")
        → HMAC-SHA256("alice", "my_secret").hex()[:8]
        → "a3f9k2m1"
        
        format_claim_flag("alice", "my_secret")
        → "ClaimedBy_a3f9k2m1"
    
    If no secret:
        format_claim_flag("alice", None)
        → "ClaimedByAlice"
    
3. Set Cyrus flag:
    imap_conn.select("shared/support@example.com")
    imap_conn.store("42", "+FLAGS", "(ClaimedBy_a3f9k2m1)")
    
4. Fire event:
    message_client.fire_event(
        args,
        "shared/support@example.com",
        "message-claimed",
        {
            "event_type": "message-claimed",
            "mailbox_name": "shared/support@example.com",
            "message_uid": 42,
            "actor_moniker": "alice",
            "message_id": "<msg42@example.com>",
            "from": "customer@example.com",
            "subject": "Help needed"
        },
        actor_moniker="alice"
    )
    ↓
5. Call bbsengine6.message.send() + route
    
✓ Message claimed by alice
```

---

## Key Design Patterns

### 1. Single Encryption Key Pattern
All passwords use ONE key from POSTOFFICE_PASSWORD_KEY, enabling:
- Per-server encryption of passwords
- Cross-server password sharing
- Simplified key rotation

### 2. Credential Fallback Pattern
Shared mailbox access tries:
1. Per-member password (allows per-person overrides)
2. Shared mailbox default (fallback for new members)

Enables flexible permission models.

### 3. Connection Pool Pattern
Functions accept `conn` or `pool` in kwargs:
```python
def my_function(args, **kwargs):
    conn, should_close = lib.get_db_connection(args, **kwargs)
    try:
        # use conn
    finally:
        if should_close and conn:
            conn.close()
```

### 4. Event-Driven Notifications
Changes trigger events that route to notification handlers:
- IMAP monitor detects changes
- Fires events via bbsengine6.message.send
- Notification routing rules determine actions

### 5. State-Based Change Detection
IMAPMonitor tracks mailbox state:
- UID validity (handles mailbox resets)
- Message flags (detects claimed messages)
- Message presence (detects new/deleted)

### 6. Obfuscation for Privacy
Claim flags can hide member identities:
- Plain: `ClaimedByAlice` (reveals identity)
- Obfuscated: `ClaimedBy_a3f9k2m1` (hides identity)

Uses HMAC-SHA256 for deterministic mapping.

---

## Module Dependencies

```
startup.py
    ├─ bbsengine6.io.echo
    └─ base64, os, sys

password_auth.py
    ├─ member_password
    ├─ shared_mailbox_password
    ├─ bbsengine6.database
    └─ bbsengine6.io.echo

member_password.py
    ├─ password_crypto (deprecated shim)
    ├─ bbsengine6.util (for actual encryption)
    ├─ bbsengine6.database
    └─ bbsengine6.io.echo

shared_mailbox_password.py
    ├─ password_crypto (deprecated shim)
    ├─ bbsengine6.util (for actual encryption)
    ├─ bbsengine6.database
    └─ bbsengine6.io.echo

imap_lib.py
    ├─ password_auth
    ├─ imaplib
    ├─ email
    └─ bbsengine6.io.echo

imap_client.py
    ├─ message_client
    └─ bbsengine6.io.echo

imap_monitor.py
    ├─ imap_lib
    ├─ imap_client
    ├─ threading
    └─ bbsengine6 (database, io)

message_client.py
    ├─ bbsengine6.database
    ├─ bbsengine6.io.echo
    ├─ json, os, hmac, hashlib
    └─ lib (for database helpers)

audit_log.py
    └─ bbsengine6.io.echo

mailbox.py
    ├─ lib
    ├─ message_client
    └─ bbsengine6 (io, database, member, util, screen)

virtual.py
    ├─ lib
    └─ bbsengine6 (io, database, member)

main.py
    ├─ lib
    └─ bbsengine6 (io, util, screen)

tui/password_manager.py
    ├─ member_password
    ├─ shared_mailbox_password
    ├─ bbsengine6.io.echo
    └─ bbsengine6.console.inputpassword

__main__.py
    ├─ startup
    ├─ argparse
    └─ bbsengine6.io.echo

__init__.py
    └─ lib

lib.py
    ├─ bbsengine6 (module, io, member, util, screen, database)
    ├─ argparse
    └─ (various postoffice modules)
```

