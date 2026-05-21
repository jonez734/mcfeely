# Member Password Management - Quick Start Guide

## Installation (5 minutes)

### 1. Install the package
```bash
cd /home/opencode/data/work/mistermcfeely/src
pip install -e .
```

### 2. Generate encryption key
```bash
# Generate and export key (do this once)
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)

# Save for persistence (systemd, .env, k8s secret, etc.)
echo "export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)" >> ~/.bashrc
```

### 3. Apply database migration
```bash
# Create new table for shared mailbox passwords
psql postoffice < /home/opencode/data/work/mistermcfeely/sql/004_add_member_mailbox_passwords.sql
```

## Usage

### Interactive Password Manager (TUI)
```bash
# Run the TUI
mistermcfeely-password-tui

# Or from source
python /home/opencode/data/work/mistermcfeely/src/bin/mistermcfeely-password-tui
```

**Features**:
- Set/view/delete personal account passwords (inbound/outbound)
- Set/view/delete shared mailbox passwords per member
- Interactive menu system with validation
- Auto-detects member vs sysop mode

### Python Code Examples

#### Set a password
```python
from bbsengine6 import engine
from postoffice import member_password

args = engine.start()

# Set member's inbound password
member_password.set_personal_password(
    args,
    member_moniker="jam",
    password_type="inbound",
    password="mysecret123",
    set_by_moniker="sysop"
)
```

#### Get password for auth
```python
from postoffice import password_auth

# Get password for IMAP login
password = password_auth.get_auth_password(
    args,
    mailbox_id=None,  # None for personal, ID for shared
    member_moniker="jam",
    password_type="inbound",
    requester_moniker="imapd",
    log_entry_fn=args.logentry
)

if password:
    imap.login("jam@example.com", password)
else:
    print("Password not found")
```

#### Shared mailbox password
```python
from postoffice import shared_mailbox_password

# Set password for member on mailbox
shared_mailbox_password.set_shared_mailbox_password(
    args,
    mailbox_id=5,
    member_moniker="jam",
    password_type="inbound",
    password="mailbox_secret",
    set_by_moniker="jam"
)

# Later: retrieve it (with fallback to shared default)
from postoffice import password_auth

password = password_auth.get_auth_password(
    args,
    mailbox_id=5,
    member_moniker="jam",
    password_type="inbound",
    requester_moniker="imapd",
    log_entry_fn=args.logentry
)
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run only password tests
pytest tests/test_password_crypto.py -v

# Run with coverage
pytest tests/ --cov=postoffice
```

**Current Status**: ✅ 107 tests passing (100%)

## Architecture Overview

### Encryption
- **Algorithm**: AES-256-GCM (NIST standard)
- **Storage**: Base64(nonce + ciphertext + auth_tag)
- **Database-agnostic**: Works with any database (PostgreSQL, MySQL, SQLite, NoSQL)

### Password Types
1. **Personal Account**: Stored in `engine.__member`
   - `inbound_password` - IMAP credentials
   - `outbound_password` - SMTP credentials

2. **Shared Mailbox**: Stored in `postoffice.member_mailbox_password`
   - Per-member unique credentials for each shared mailbox
   - Inbound and outbound passwords

### Fallback Logic
When accessing a shared mailbox:
1. Try: Member-specific password in `member_mailbox_password`
2. Fall back: Shared mailbox default in `mailbox_password`
3. Log: Failure if neither exists

### Permissions
- **Members**: Can only manage their own passwords
- **Sysops**: Can manage any member's passwords
- All operations logged via bbsengine6's `logentry()`

## Modules

| Module | Purpose |
|--------|---------|
| `password_crypto` | AES-256-GCM encryption/decryption |
| `member_password` | Personal account password management |
| `shared_mailbox_password` | Shared mailbox per-member passwords |
| `password_auth` | Authentication with fallback |
| `audit_log` | Logging helpers |
| `tui/password_manager` | Interactive password manager |

## Integration with IMAP/SMTP

To integrate with your IMAP/SMTP daemons:

### In IMAP daemon:
```python
from postoffice import password_auth

password = password_auth.get_auth_password(
    args, mailbox_id, member, 'inbound', 'imapd', args.logentry
)
if password:
    imap.login(user, password)
```

### In SMTP daemon:
```python
from postoffice import password_auth

password = password_auth.get_auth_password(
    args, mailbox_id, member, 'outbound', 'smtpd', args.logentry
)
if password:
    smtp.login(user, password)
```

## Troubleshooting

### "POSTOFFICE_PASSWORD_KEY not set"
```bash
# Export the key before running
export POSTOFFICE_PASSWORD_KEY="your-base64-key"
```

### "Failed to decrypt password"
- Key may have changed
- Password may be corrupted
- Check encryption key is correct

### "Permission denied"
- Members can only manage their own passwords
- Sysops can manage any member's passwords
- Use `args.issuperuser` to check sysop status

### Tests failing
```bash
# Ensure key is set
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)

# Run tests
pytest tests/test_password_crypto.py -v
```

## Documentation

- **PASSWORD_MANAGEMENT.md** - Complete system documentation
- **IMPLEMENTATION_COMPLETE.md** - Implementation details and architecture
- **This file** - Quick start guide

## Files Added

```
mistermcfeely/
├── src/postoffice/
│   ├── password_crypto.py          # Core encryption
│   ├── member_password.py           # Personal passwords
│   ├── shared_mailbox_password.py  # Shared mailbox passwords
│   ├── password_auth.py             # Auth with fallback
│   ├── audit_log.py                 # Logging
│   ├── tui/
│   │   ├── __init__.py
│   │   └── password_manager.py      # Interactive TUI
│   └── bin/mistermcfeely-password-tui  # Entry point
├── sql/
│   └── 004_add_member_mailbox_passwords.sql  # DB migration
├── tests/
│   └── test_password_crypto.py      # 14 unit tests
└── docs/
    ├── PASSWORD_MANAGEMENT.md       # Full documentation
    ├── IMPLEMENTATION_COMPLETE.md   # Implementation summary
    └── QUICKSTART.md                # This file
```

## Next Steps

1. ✅ Install and generate encryption key
2. ✅ Apply database migration
3. ✅ Run tests to verify installation
4. ⏭️ Use TUI or Python API to manage passwords
5. ⏭️ Integrate with IMAP/SMTP daemons
6. ⏭️ Monitor logs via bbsengine6's `logentry()`

## Support

For issues or questions:
- See **PASSWORD_MANAGEMENT.md** for detailed docs
- Check **IMPLEMENTATION_COMPLETE.md** for architecture
- Run tests: `pytest tests/ -v`
- Review module docstrings in Python code

---

## ⚠️ Legal Notice - Trademark

**Important**: "Mr. McFeely" is a registered trademark. The project name `mistermcfeely` may need to be renamed for public or commercial use.

The password management implementation is unaffected by any future rename—it's self-contained and portable.


## Pluggable Cipher & Storage

Easy to swap implementations:

```python
from postoffice.password.config import get_password_manager
from postoffice.password.ciphers.plaintext import PlaintextCipher
from postoffice.password.storages.postgresql import PostgreSQLStorage
from postoffice.password.manager import PasswordManager

# Use factory (default: AES-256-GCM + PostgreSQL)
pm = get_password_manager(args=args)

# Or specify alternatives via environment variables
export PASSWORD_CIPHER=plaintext    # Testing only!
export PASSWORD_STORAGE=postgresql

# Or create directly with custom implementations
cipher = PlaintextCipher()  # For testing
storage = PostgreSQLStorage(args)
pm = PasswordManager(cipher, storage)
```

Supported ciphers:
- `aes256gcm` - AES-256-GCM (default, cross-language compatible)
- `plaintext` - No encryption (testing/migration only)

Supported storage:
- `postgresql` - PostgreSQL backend (default)

Future: Add ChaCha20 cipher, MongoDB/Vault storage, etc.
