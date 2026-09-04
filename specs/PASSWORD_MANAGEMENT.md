# Member Password Management System

This document describes the member password management system added to mistermcfeely, which allows members to have individual inbound and outbound passwords for both personal accounts and shared mailboxes.

## Overview

The password management system provides:

- **Personal Account Passwords**: Each member stores separate inbound (IMAP) and outbound (SMTP) passwords for their personal email account in `engine.__member` table
- **Shared Mailbox Per-Member Passwords**: Each member can have unique inbound and outbound passwords for each shared mailbox they access, stored in `postoffice.member_mailbox_password` table
- **Encryption**: All passwords are encrypted with AES-256-GCM before storage (database-agnostic format)
- **Authentication Fallback**: When accessing a shared mailbox, the system tries per-member password first, then falls back to the shared mailbox default
- **TUI Management**: Standalone interactive password manager for members and sysops
- **Audit Logging**: All password operations are logged via bbsengine6's `logentry()` function

## Architecture

### Database Schema

#### Personal Account Passwords
Stored in `engine.__member` (bbsengine6):
```sql
ALTER TABLE engine.__member ADD COLUMN inbound_password TEXT;
ALTER TABLE engine.__member ADD COLUMN outbound_password TEXT;
```

#### Shared Mailbox Per-Member Passwords
Stored in `postoffice.member_mailbox_password`:
```sql
CREATE TABLE postoffice.member_mailbox_password (
    id SERIAL PRIMARY KEY,
    mailbox_id INTEGER NOT NULL,
    member_moniker TEXT NOT NULL,
    password_type TEXT NOT NULL,  -- 'inbound' or 'outbound'
    encrypted_password TEXT NOT NULL,  -- Base64(nonce + ciphertext + auth_tag)
    set_by_moniker TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fk_mailbox FOREIGN KEY (mailbox_id) REFERENCES postoffice.__address(address),
    CONSTRAINT fk_member FOREIGN KEY (member_moniker) REFERENCES engine.__member(moniker),
    CONSTRAINT chk_password_type CHECK (password_type IN ('inbound', 'outbound')),
    UNIQUE(mailbox_id, member_moniker, password_type)
);
```

### Encryption Format

All passwords are encrypted with **AES-256-GCM** (NIST SP800-38D standard):

```
Stored format: Base64(nonce (12 bytes) + ciphertext + auth_tag (16 bytes))
Example: aBcD1eF2gH3iJ4kL5mN6oP7qR8sT9uV0wX1yZ2aB3cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5aB6cD7e==
```

**Why AES-256-GCM?**
- Cross-language compatible (JavaScript, Python, Rust, Perl, C, etc.)
- Authenticated encryption (detects tampering)
- NIST standard (SP800-38D)
- Database-agnostic (works with PostgreSQL, MySQL, SQLite, NoSQL, etc.)

### Key Management

The encryption key is derived from the `POSTOFFICE_PASSWORD_KEY` environment variable:

```bash
# Generate key once (32 bytes = 256 bits)
openssl rand -base64 32
# Output: K7nZ9pQmR2xLvW8yFhJdB3sC6eG1kL4mN9tU5vX2yZ3wA=

# Export for all processes
export POSTOFFICE_PASSWORD_KEY="K7nZ9pQmR2xLvW8yFhJdB3sC6eG1kL4mN9tU5vX2yZ3wA="

# Or store in systemd service, .env file, or k8s secret
```

## Modules

### `postoffice/password_crypto.py`

Core encryption/decryption with AES-256-GCM:
- `encrypt_password(plaintext: str) -> str` - Encrypt password, return base64
- `decrypt_password(encrypted_b64: str) -> str` - Decrypt from base64
- `get_encryption_key() -> bytes` - Get key from environment

### `postoffice/member_password.py`

Personal account password management:
- `set_personal_password(args, member_moniker, password_type, password, set_by_moniker)` - Store encrypted password
- `get_personal_password(args, member_moniker, password_type, requester_moniker)` - Retrieve and decrypt
- `delete_personal_password(args, member_moniker, password_type, requester_moniker)` - Remove password
- `list_personal_passwords(args, member_moniker, requester_moniker)` - List metadata

**Permission Model**:
- Members: Can only manage their own passwords
- Sysops: Can manage any member's passwords

### `postoffice/shared_mailbox_password.py`

Per-member shared mailbox password management:
- `set_shared_mailbox_password(args, mailbox_id, member_moniker, password_type, password, set_by_moniker)` - Store
- `get_shared_mailbox_password(args, mailbox_id, member_moniker, password_type, requester_moniker)` - Retrieve
- `delete_shared_mailbox_password(args, mailbox_id, member_moniker, password_type, requester_moniker)` - Remove
- `list_shared_mailbox_passwords(args, mailbox_id, member_moniker, requester_moniker)` - List metadata
- `get_member_mailboxes(args, member_moniker)` - List mailboxes member has passwords for

**Permission Model**: Same as personal passwords (members manage own, sysops manage any)

### `postoffice/password_auth.py`

Authentication with fallback logic:
- `get_auth_password(args, mailbox_id, member_moniker, password_type, requester_moniker, log_entry_fn)` - Get password with fallback
  1. If mailbox_id: Try per-member password → Fall back to shared mailbox default
  2. If no mailbox_id: Get personal account password
  3. Log failures to `log_entry_fn`
- `validate_password(password_type, password)` - Extensible validation (for future strength checking)

### `postoffice/audit_log.py`

Logging helpers:
- `log_password_operation(action, target_type, target_moniker, password_type, performed_by, mailbox_id, reason, log_entry_fn)` - Log via bbsengine6
- `log_auth_failure(member_moniker, password_type, reason, mailbox_id, log_entry_fn)` - Log auth failure

### `postoffice/tui/password_manager.py`

Interactive TUI for password management:
- `PasswordManager` class with full member and sysop interfaces
- Auto-detects sysop status via bbsengine6 args
- Interactive menu system

### `bin/mistermcfeely-password-tui`

Standalone entry point script for TUI:
```bash
# Run as any member
./mistermcfeely-password-tui

# Sysop mode auto-detected
# Can manage any member's passwords
```

## Usage

### Installation

```bash
# Install mistermcfeely with password management support
cd mistermcfeely/src
pip install -e .

# Set encryption key (required for operation)
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)
```

### Database Setup

Apply the migration to create the new table:

```bash
psql postoffice < sql/004_add_member_mailbox_passwords.sql
```

### Interactive TUI

```bash
# Launch password manager
mistermcfeely-password-tui

# Or from src directory
python bin/mistermcfeely-password-tui
```

**Member Interface**:
```
=== Password Manager ===
User: jam

1. Manage Personal Account Passwords
   a. Set inbound password
   b. Set outbound password
   c. View password status
   d. Delete inbound password
   e. Delete outbound password

2. Manage Shared Mailbox Passwords
   a. Set password for a mailbox
   b. View passwords for a mailbox
   c. Delete password for a mailbox

q. Quit
```

**Sysop Interface**: Same options, plus ability to select which member to manage

### Python API

#### Set a member's personal password:

```python
from bbsengine6 import engine
from postoffice import member_password

args = engine.start()

member_password.set_personal_password(
    args,
    member_moniker="jam",
    password_type="inbound",
    password="mysecretpassword",
    set_by_moniker="sysop"
)
```

#### Get password for IMAP authentication:

```python
from postoffice import password_auth

password = password_auth.get_auth_password(
    args,
    mailbox_id=None,  # None for personal, mailbox ID for shared
    member_moniker="jam",
    password_type="inbound",
    requester_moniker="imapd",
    log_entry_fn=args.logentry
)

if password:
    imap.login(username, password)
else:
    echo(f"Auth failed for {member_moniker}: password not found", level="error")
```

#### List all passwords for a member:

```python
from postoffice import member_password

personal = member_password.list_personal_passwords(
    args, "jam", "jam"  # requester must be member or sysop
)
# Returns: {'inbound': {'exists': True}, 'outbound': {'exists': False}}

from postoffice import shared_mailbox_password

mailbox_pwds = shared_mailbox_password.list_shared_mailbox_passwords(
    args, mailbox_id=1, member_moniker="jam", requester_moniker="jam"
)
# Returns: {'inbound': {'exists': True, 'set_by': 'jam'}, 'outbound': {'exists': False}}
```

## Security Considerations

### Encryption
- Passwords are encrypted with AES-256-GCM before storage
- Each encryption uses a random 96-bit nonce (unique per message)
- Auth tag prevents tampering detection
- Encryption key must be kept secret (stored in environment variable)

### Key Management
- Keep `POSTOFFICE_PASSWORD_KEY` secure (not in version control)
- Consider using secrets management (k8s secrets, HashiCorp Vault, etc.)
- Key rotation: Requires re-encrypting all passwords with new key

### Access Control
- Members can only manage their own passwords
- Sysops can manage any member's passwords
- All operations logged via bbsengine6's `logentry()`

### Database
- Passwords stored encrypted in database (never plaintext)
- Foreign keys ensure referential integrity
- Timestamps track who set password and when

## Testing

```bash
# Run all tests including password tests
cd mistermcfeely
pytest tests/ -v

# Run only password crypto tests
pytest tests/test_password_crypto.py -v

# Run with coverage
pytest tests/ --cov=postoffice --cov-report=html
```

All 107 tests pass (93 existing + 14 new encryption tests).

## Integration with IMAP/SMTP Daemons

### IMAP Monitor

Update `postoffice/imap_monitor.py` to use encrypted passwords:

```python
from postoffice import password_auth

# In connect function:
password = password_auth.get_auth_password(
    args,
    mailbox_id=None,  # or mailbox.id for shared mailbox
    member_moniker=user,
    password_type="inbound",
    requester_moniker="imapd",
    log_entry_fn=args.logentry
)

if password:
    imap = imaplib.IMAP4_SSL(host, port)
    imap.login(user, password)
else:
    echo(f"IMAP auth failed for {user}: no password", level="error")
    return None
```

### SMTP Sender

Update `postoffice/smtp_sender.py`:

```python
password = password_auth.get_auth_password(
    args,
    mailbox_id=None,
    member_moniker=sender,
    password_type="outbound",
    requester_moniker="smtpd",
    log_entry_fn=args.logentry
)

if password:
    smtp.login(sender, password)
else:
    echo(f"SMTP auth failed for {sender}: no password", level="error")
```

## Future Enhancements

- Password strength validation (extensible via `validate_password()`)
- Password expiry/rotation policies
- Password history tracking
- UI/web interface for password management
- Integration with LDAP/Active Directory for automatic password sync
- Key rotation mechanism
- Hardware security module (HSM) support for key storage

## Migration from Old System

If you have existing plaintext passwords in `mailbox_password`:
1. No migration required for `postoffice.member_mailbox_password` (new feature)
2. Existing `mailbox_password` entries continue to work as fallback
3. Per-member passwords take precedence over shared defaults

## References

- AES-256-GCM: NIST SP800-38D (https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-38d.pdf)
- Python cryptography library: https://cryptography.io/
- bbsengine6 encryption: See `bbsengine6/util.py`

---

## ⚠️ Important Legal Note

**Trademark Notice**: "Mr. McFeely" is a registered trademark. The project name `mistermcfeely` may require renaming in the future to ensure compliance with trademark law. This should be considered during any public release or commercial deployment.

When renaming becomes necessary, the password management system implementation will remain unchanged—only the project directory and package names will need to be updated.


---

## Pluggable Architecture (Strategy Pattern)

The password system is designed to be easily extensible. You can swap cipher and storage implementations without modifying application code.

### Cipher Strategies

**Interface**: `postoffice.password.PasswordCipher`

Implementations:
- **AES256GCMCipher** (default) - AES-256-GCM, cross-language compatible
- **PlaintextCipher** - Testing/migration only (no encryption)
- Future: ChaCha20Cipher, RSACipher, HSM-backed, etc.

### Storage Strategies

**Interface**: `postoffice.password.PasswordStorage`

Implementations:
- **PostgreSQLStorage** (default) - PostgreSQL backend
- Future: FileSystemStorage, MongoDBStorage, VaultStorage, LDAPStorage, etc.

### Using the Pluggable System

```python
from postoffice.password.config import get_password_manager
from postoffice.password.ciphers.aes256gcm import AES256GCMCipher
from postoffice.password.storages.postgresql import PostgreSQLStorage
from postoffice.password.manager import PasswordManager

# Use factory with environment variables
pm = get_password_manager(args=args)

# Or create directly with custom implementations
cipher = AES256GCMCipher(key_b64)
storage = PostgreSQLStorage(args)
pm = PasswordManager(cipher, storage)

# Use unified interface
pm.set_personal_password("jam", "inbound", "password123", "sysop")
password = pm.get_personal_password("jam", "inbound")
```

### Configuration via Environment Variables

```bash
# Specify cipher implementation
export PASSWORD_CIPHER=aes256gcm  # or plaintext

# Specify storage implementation
export PASSWORD_STORAGE=postgresql  # or future: mongodb, vault, etc.

# AES-256-GCM key
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)
```

### Creating Custom Implementations

To implement a custom cipher:

```python
from postoffice.password.cipher import PasswordCipher

class MyCustomCipher(PasswordCipher):
    def encrypt(self, plaintext: str) -> str:
        # Your encryption logic
        return encrypted_string
    
    def decrypt(self, ciphertext: str) -> str:
        # Your decryption logic
        return plaintext
```

To implement custom storage:

```python
from postoffice.password.storage import PasswordStorage

class MyCustomStorage(PasswordStorage):
    def get_personal_password(self, member_moniker, password_type):
        # Your retrieval logic
        return encrypted_password
    
    # ... implement other abstract methods
```

Then register in `password/config.py` factory.

---

## AES-256-GCM Algorithm Details

**Cipher**: AES (Advanced Encryption Standard)
**Mode**: GCM (Galois/Counter Mode)
**Key Size**: 256 bits (32 bytes)
**Nonce Size**: 96 bits (12 bytes) - random, unique per encryption
**Authentication Tag**: 128 bits (16 bytes) - prevents tampering
**Standard**: NIST SP 800-38D

### Format

```
Encrypted password = Base64(nonce[12] + ciphertext + auth_tag[16])
```

### Cross-Language Support

The AES-256-GCM format is compatible with:

| Language | Library/Function |
|----------|-----------------|
| Python | `cryptography.hazmat.primitives.ciphers.aead.AESGCM` |
| JavaScript/Node | `crypto.createCipheriv('aes-256-gcm')` or `crypto.subtle.encrypt()` |
| Rust | `aes-gcm` crate from RustCrypto |
| Perl | `Crypt::AESGCM` |
| C | OpenSSL `EVP_aes_256_gcm()` or libsodium `crypto_aead_aes256gcm_*` |
| PHP | `openssl_encrypt('aes-256-gcm')` (PHP 7.1+) or `sodium_crypto_aead_aes256gcm_*` (PHP 7.2+) |
| Cyrus IMAP | System crypto libraries (OpenSSL, libsodium) |

The plaintext format (nonce + ciphertext + tag stored as base64) is standard and interoperable across all these languages.

