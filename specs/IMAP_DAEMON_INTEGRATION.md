# IMAP Daemon Integration with Password Management System

## Overview

The mistermcfeely password management system has been fully integrated with the IMAP daemon. This allows IMAP connections to use:

1. **Direct configuration** (args.imaphost/imapuser/imappassword) - highest priority
2. **Password management system** - fallback for member-specific passwords
3. **Both personal and shared mailbox passwords** - per-member credentials

## Quick Start

### 1. Set Up Encryption Key

```bash
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)
```

### 2. Import Startup

In your main mistermcfeely application:

```python
from postoffice import startup

# Run during application initialization
if not startup.startup(args):
    sys.exit("Failed to initialize password system")
```

### 3. Use Enhanced IMAP Connection

```python
from postoffice import imap_lib

# Option A: Direct credentials (backward compatible)
imap = imap_lib.connect_cyrus(args)

# Option B: With member password lookup
imap = imap_lib.connect_cyrus(
    args,
    member_moniker="alice",
    mailbox_id=1  # Shared mailbox ID
)

# Option C: Personal account
imap = imap_lib.connect_cyrus(
    args,
    member_moniker="bob",
    mailbox_id=None  # None = personal account
)
```

## Architecture

### Connection Priority

The `connect_cyrus()` function uses the following priority order:

```
1. args.imaphost + args.imapuser + args.imappassword
   ↓ (if password missing)
2. Password management system (requires member_moniker)
   ↓ (if not found)
3. Connection fails with error
```

### Credential Retrieval

```python
from postoffice.imap_lib import get_imap_credentials

creds = get_imap_credentials(
    args,
    member_moniker="alice",
    mailbox_id=1
)
# Returns: {
#     'host': 'mail.example.com',
#     'port': 993,
#     'username': 'support',
#     'password': 'alice_specific_password'  # from password system
# }
```

## Use Cases

### Shared Mailbox with Per-Member Passwords

**Scenario**: Support team has shared mailbox `support@example.com`, each member has unique password.

```python
# Connect as alice to shared mailbox (mailbox_id=1)
imap = imap_lib.connect_cyrus(
    args,
    member_moniker="alice",
    mailbox_id=1
)
# Flow:
# 1. Checks args.imappassword (not set)
# 2. Calls password_auth.get_auth_password()
#    - Tries alice's per-member password for mailbox 1
#    - Falls back to shared default if needed
# 3. Connects with retrieved password
```

### Personal Email Account

**Scenario**: Member bob has personal Gmail account with stored password.

```python
# Connect to bob's personal account
imap = imap_lib.connect_cyrus(
    args,
    member_moniker="bob",
    mailbox_id=None  # None indicates personal account
)
# Flow:
# 1. Retrieves bob's personal inbound password
# 2. Connects using bob@gmail.com + personal password
```

### Direct Configuration (Backward Compatible)

**Scenario**: Service account with static credentials.

```python
args.imaphost = "mail.internal.example.com"
args.imapuser = "serviceaccount"
args.imappassword = "static_password"

imap = imap_lib.connect_cyrus(args)
# Direct args take priority, password system is not used
```

## Integration Points

### IMAP Monitor

The `imap_monitor.py` should be updated to pass member context:

```python
# Before
imap = imap_lib.connect_cyrus(self.args, readonly=True)

# After
imap = imap_lib.connect_cyrus(
    self.args,
    readonly=True,
    member_moniker=self.current_member,
    mailbox_id=self.current_mailbox_id
)
```

### IMAP Client

Operations requiring member-specific passwords:

```python
# Before
imap_conn = imap_lib.connect_cyrus(args)

# After
imap_conn = imap_lib.connect_cyrus(
    args,
    member_moniker=actor_moniker,  # Who is claiming the message
    mailbox_id=mailbox_id
)
```

## API Reference

### `get_imap_credentials()`

Get credentials with password system fallback.

```python
def get_imap_credentials(
    args: Any,
    member_moniker: Optional[str] = None,
    mailbox_id: Optional[int] = None,
) -> Optional[Dict[str, str]]:
    """
    Returns:
        {
            'host': 'mail.example.com',
            'port': 993,
            'username': 'user',
            'password': 'decrypted_password'
        }
        or None if no credentials available
    """
```

### `connect_cyrus()`

Connect to Cyrus IMAP with automatic password fallback.

```python
def connect_cyrus(
    args,
    readonly: bool = True,
    timeout: int = 10,
    member_moniker: Optional[str] = None,
    mailbox_id: Optional[int] = None,
) -> Optional[imaplib.IMAP4_SSL]:
    """
    Enhanced signature now supports:
    - member_moniker: Member for password lookup
    - mailbox_id: Shared mailbox ID (None = personal account)
    
    Returns connected IMAP4_SSL or None
    """
```

## Startup Module

### `startup.startup()`

Initialize password system and validate configuration.

```python
from postoffice import startup

# Full initialization
if not startup.startup(args):
    sys.exit("Password system initialization failed")

# Or check individual components
startup.initialize_password_system()  # Encryption key validation
startup.validate_password_config()    # Cipher/storage validation
startup.check_database_schema(args)   # Database schema check
```

### Environment Variables

Required:
```bash
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)
```

Optional:
```bash
export PASSWORD_CIPHER=aes256gcm      # Default
export PASSWORD_STORAGE=postgresql    # Default
```

## Error Handling

### Missing Encryption Key

```
ERROR: POSTOFFICE_PASSWORD_KEY environment variable not set
  Set it with: export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)
```

### Missing Credentials

```
imap_lib.connect_cyrus: Missing IMAP credentials (host/user/pass)
```

### Password System Failure

If password_auth.get_auth_password() fails:
- Logs error with `io.echo()` at "error" level
- Returns None
- IMAP connection fails gracefully

## Testing

All integration tested with 145 test cases:

- **25 password integration tests** - Member/shared mailbox operations
- **13 IMAP password integration tests** - Credential retrieval and connection
- **107 existing tests** - Backward compatibility verified

Run tests:

```bash
pytest tests/ -v
pytest tests/test_password_integration.py -v
pytest tests/test_imap_password_integration.py -v
```

## Migration Guide

### For Existing Code

If you have IMAP code using direct credentials:

```python
# Before (still works - backward compatible)
args.imaphost = "mail.example.com"
args.imapuser = "user"
args.imappassword = "password"
imap = imap_lib.connect_cyrus(args)

# After (enhanced with password system)
# No change needed if using direct credentials
# But can now add member_moniker for per-member passwords
imap = imap_lib.connect_cyrus(
    args,
    member_moniker="alice",
    mailbox_id=1
)
```

### For New Code

Always pass member_moniker when available:

```python
# Good - member-aware
imap = imap_lib.connect_cyrus(
    args,
    member_moniker=current_member,
    mailbox_id=mailbox_id
)

# Acceptable - direct credentials only
imap = imap_lib.connect_cyrus(args)
```

## Database Schema

Passwords are stored encrypted in:

1. **Personal passwords** (engine.__member)
   - inbound_password (IMAP)
   - outbound_password (SMTP)

2. **Shared mailbox passwords** (postoffice.member_mailbox_password)
   - password_type: 'inbound' | 'outbound'
   - encrypted_password: base64(nonce + ciphertext + tag)

All passwords encrypted with AES-256-GCM.

## Troubleshooting

### "Missing IMAP credentials"

1. Check args.imaphost, args.imapuser set
2. If using password system, verify POSTOFFICE_PASSWORD_KEY set
3. Ensure member_moniker is provided if using password system
4. Check database for password entries

### "IMAP login failed"

1. Verify credentials are correct
2. Check encryption key matches database key
3. Verify IMAP server connectivity
4. Check firewall/network access

### "Password system not initialized"

1. Call `startup.startup(args)` first
2. Verify POSTOFFICE_PASSWORD_KEY set
3. Check environment variables with: `env | grep PASSWORD`

## Future Enhancements

Potential improvements:

1. **SMTP Integration** - Similar password fallback for SMTP
2. **Connection Pooling** - Cache connections per member
3. **Credential Caching** - TTL cache to reduce lookups
4. **Audit Logging** - Log all connection attempts
5. **Metrics** - Track password system usage

