# Password Systems Summary

> **Note [2026-10-09]:** This is the surviving `PASSWORD_*` spec
> in this repo. The following sibling specs were deleted on
> 2026-10-09 because they were duplicates or historical
> migration notes superseded by `ARCHITECTURE_MIGRATION.md`
> and the live code:
> - `specs/PASSWORD_FUNCTIONS_MOVED.md` (135 lines, migration
>   note superseded by `ARCHITECTURE_MIGRATION.md`)
> - `specs/PASSWORD_SYSTEMS_EXPLAINED.md` (307 lines, "two
>   systems" overview, outdated; this file has the post-SHA-512
>   "three systems" view)
> - `specs/PASSWORD_MANAGEMENT.md` (490 lines, had stale
>   `postoffice.member_mailbox_password` table name)
> - `specs/PLUGGABLE_ARCHITECTURE.md` (391 lines, Strategy
>   pattern description superseded by live code)
> - `specs/REFACTORING_SUMMARY.md` (312 lines, 2026-05
>   refactoring summary; content is in the per-topic
>   live code and `ARCHITECTURE_MIGRATION.md`)
> - `specs/FINAL_SUMMARY.md` (367 lines, "complete
>   implementation" title was wrong; the system has been
>   refactored twice since)
>
> The table-name fix in this pass: `postoffice.member_mailbox_password`
> is renamed to `postoffice.mailbox_password` + `postoffice.mailbox_member`
> per commit `9df06ac` (the 2026-09 mailbox_config split).

## Three-System Architecture

The system now uses **three complementary password systems**:

### System 1: SHA-256 Hashing (One-Way)
**Location**: `bbsengine6.password_hash`
**Purpose**: Member login passwords
**Algorithm**: SHA-256 with random 32-byte salt
**Can**: Hash, Verify, Prevent recovery
**Cannot**: Decrypt, Get plaintext

### System 2: AES-256-GCM Encryption (Reversible)
**Location**: `engine.__member` (inbound_password, outbound_password)
**Purpose**: IMAP/SMTP server credentials (used by postoffice)
**Algorithm**: AES-256-GCM with random nonce
**Can**: Encrypt, Decrypt, Get plaintext
**Cannot**: (safely) do one-way verification

### System 3: SHA-512 Crypt Hashes (SASL Authentication)
**Location**: `postoffice.sasl_password`
**Purpose**: IMAP authentication via saslauthd/postoffice-authd
**Algorithm**: SHA-512 crypt (compatible with PAM/system passwords)
**Can**: Verify passwords via crypt.crypt(), authenticate to IMAP
**Cannot**: Decrypt, Get plaintext (one-way like SHA-256)

---

## Usage Examples

### Member Sets Their Login Password (SHA-256)

```python
from bbsengine6.password_hash import hash_password

# Member provides password
plaintext = "myloginpass123"

# Hash it with salt
hashed, salt = hash_password(plaintext)

# Store both in database
db.update("engine.__member",
    password_hash=hashed,
    password_salt=salt,
    moniker=member_moniker
)
```

### Member Logs In (SHA-256 Verification)

```python
from bbsengine6.password_hash import verify_password

# Member provides password
provided = user_input()

# Verify against stored hash
is_correct = verify_password(provided, stored_hash, stored_salt)

if is_correct:
    authenticate_user()
```

### Member Sets IMAP Password (AES-256-GCM)

```python
from bbsengine6.password.config import get_password_manager

pm = get_password_manager(args=args)

# Member provides IMAP password
plaintext = "imappass456"

# Store encrypted
pm.set_personal_password("jam", "inbound", plaintext, "sysop")
```

### Daemon Uses IMAP Password (AES-256-GCM Decryption)

```python
from bbsengine6.password.config import get_password_manager
import imaplib

pm = get_password_manager(args=args)

# Retrieve decrypted password
password = pm.get_personal_password("jam", "inbound")

if password:
    # Use plaintext for IMAP authentication
    imap = imaplib.IMAP4_SSL(server, 993)
    imap.login(user, password)
```

---

## Database Schema

### Member Login Passwords (SHA-256)

```sql
ALTER TABLE engine.__member ADD COLUMN password_hash TEXT;
ALTER TABLE engine.__member ADD COLUMN password_salt TEXT;
```

**Example values**:
- `password_hash`: `QyDV6K8O7J3pL2mK9...` (base64-encoded SHA-256)
- `password_salt`: `rX4mK2L9sP8vQ3T6...` (base64-encoded salt)

### Personal IMAP/SMTP Passwords (AES-256-GCM)

```sql
ALTER TABLE engine.__member ADD COLUMN inbound_password TEXT;
ALTER TABLE engine.__member ADD COLUMN outbound_password TEXT;
```

**Example values**:
- `inbound_password`: `aBcD1eF2gH3iJ4...` (base64(nonce + cipher + tag))
- `outbound_password`: `xYz9aB2cD3eF4...` (base64(nonce + cipher + tag))

### Shared Mailbox Credentials (AES-256-GCM)

```sql
-- Renamed from postoffice.member_mailbox_password in commit 9df06ac;
-- the table was split into mailbox_password (per-moniker credentials)
-- + mailbox_member (per-mailbox membership). See sql/mailbox_config.sql.
CREATE TABLE postoffice.mailbox_password (
    moniker TEXT PRIMARY KEY,
    encrypted_password TEXT NOT NULL,  -- base64(nonce + cipher + tag)
    -- ... other columns
);
```

### SASL Passwords for IMAP Auth (SHA-512 Crypt)

```sql
CREATE TABLE postoffice.sasl_password (
    member_moniker citext PRIMARY KEY REFERENCES engine.__member(moniker),
    crypt_hash text NOT NULL,  -- SHA-512 crypt hash ($6$<salt>$<hash>)
    enabled boolean DEFAULT true,
    datecreated timestamp with time zone DEFAULT now(),
    dateupdated timestamp with time zone DEFAULT now(),
    updated_by text
);
```

**Example values**:
- `crypt_hash`: `$6$hMhmq8RKz5FNfVuLh$oY9e7YLKbM7.nIY5...` (SHA-512 crypt format)

---

## Security Model

### SHA-512 Crypt Hashing (IMAP Authentication)

```
Plaintext Password
        ↓
    [crypt.mksalt(crypt.METHOD_SHA512)]
        ↓
    [SHA-512 + Random Salt]
        ↓
    Stored Hash ($6$<salt>$<hash>)

To Verify:
    Provided Password + Stored Hash → [crypt.crypt(password, hash)]
    Compare result with stored hash
```

**Security**:
- ✅ One-way: Cannot recover plaintext
- ✅ Salt: Prevents rainbow tables
- ✅ Standard: Compatible with PAM/system passwords
- ✅ Used by: saslauthd, PAM, postoffice-authd

### SHA-256 Hashing (Member Login)

```
Plaintext Password
        ↓
    [SHA-256]
        ↓
   [+ Random Salt] (32 bytes)
        ↓
   [Base64 Encode]
        ↓
   Stored Hash + Salt

To Verify:
    Provided Password + Stored Salt → [SHA-256] → Compare with Stored Hash
```

**Security**:
- ✅ One-way: Cannot recover plaintext
- ✅ Salt: Prevents rainbow tables
- ✅ Fast: <1ms to verify
- ✅ Standard: Industry best practice

### AES-256-GCM Encryption (IMAP/SMTP)

```
Plaintext Password
        ↓
    [Random Nonce] (12 bytes)
        ↓
    [AES-256-GCM]
        ↓
   [+ Auth Tag] (16 bytes)
        ↓
   [Nonce + Cipher + Tag]
        ↓
   [Base64 Encode]
        ↓
   Stored Encrypted Password

To Decrypt:
    Stored → [Base64 Decode] → Extract Nonce/Cipher/Tag
        ↓
    [AES-256-GCM Decrypt] → Plaintext Password
        ↓
    [Verify Auth Tag] → Tamper Detection
```

**Security**:
- ✅ Reversible: Can get plaintext when needed
- ✅ Authenticated: Detects tampering (auth tag)
- ✅ Random nonce: No patterns in ciphertexts
- ✅ Key-based: Depends on protecting POSTOFFICE_PASSWORD_KEY

---

## API Reference

### SHA-256 Hashing Functions

```python
from bbsengine6.password_hash import (
    hash_password,
    verify_password,
    generate_salt,
    is_hashed_password
)

# Create hash with auto-generated salt
hashed, salt = hash_password("mypassword")

# Create hash with specific salt
hashed, salt = hash_password("mypassword", salt="base64encodedSalt...")

# Verify password
is_correct = verify_password("mypassword", hashed, salt)

# Generate salt
salt = generate_salt(length=32)

# Check if value looks like a hash
is_hash = is_hashed_password(value)
```

### AES-256-GCM Encryption Functions

```python
from bbsengine6.util import (
    encrypt_password,
    decrypt_password,
    get_encryption_key
)

# Encrypt password
encrypted = encrypt_password("mypassword")

# Decrypt password
plaintext = decrypt_password(encrypted)

# Get encryption key
key = get_encryption_key()  # From POSTOFFICE_PASSWORD_KEY env var
```

### Pluggable Password Manager

```python
from bbsengine6.password.config import get_password_manager

# Create manager with AES-256-GCM + PostgreSQL (defaults)
pm = get_password_manager(args=args)

# Or customize
pm = get_password_manager(
    cipher_name="aes256gcm",
    storage_name="postgresql",
    args=args
)

# Store IMAP/SMTP passwords
pm.set_personal_password("jam", "inbound", "imap_pass", "sysop")
pm.set_personal_password("jam", "outbound", "smtp_pass", "sysop")

# Retrieve encrypted passwords
imap_pass = pm.get_personal_password("jam", "inbound")
smtp_pass = pm.get_personal_password("jam", "outbound")

# Shared mailbox passwords
pm.set_shared_mailbox_password(5, "jam", "inbound", "pass", "sysop")
password = pm.get_shared_mailbox_password(5, "jam", "inbound")
```

---

## Configuration

### SHA-256 Hashing
No configuration required. Salt is generated and stored with each hash.

### AES-256-GCM Encryption
Set environment variable:

```bash
# Generate a new key
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)

# Or use existing key
export POSTOFFICE_PASSWORD_KEY="your-base64-key-here"

# Optional: specify cipher/storage
export PASSWORD_CIPHER=aes256gcm        # Default
export PASSWORD_STORAGE=postgresql      # Default
```

---

## When to Use Each

### Use SHA-256 Hashing When:
- ✅ Storing member login passwords
- ✅ Need one-way security (password recovery impossible)
- ✅ Only need to verify passwords, never use them
- ✅ Maximum security important

### Use AES-256-GCM When:
- ✅ Storing IMAP server credentials (for postoffice daemon retrieval)
- ✅ Storing SMTP server credentials
- ✅ Need to retrieve plaintext password
- ✅ Authenticating to external servers

### Use SHA-512 Crypt When:
- ✅ Authenticating to IMAP via saslauthd/postoffice-authd
- ✅ Need PAM-compatible password format
- ✅ One-way verification sufficient
- ✅ Password must work with system auth (PAM fallback)

---

## Comparison

| Feature | SHA-256 Hashing | AES-256-GCM | SHA-512 Crypt |
|---------|-----------------|-------------|---------------|
| **One-Way** | ✅ Yes | ❌ No | ✅ Yes |
| **Can Decrypt** | ❌ No | ✅ Yes | ❌ No |
| **Salt/Nonce** | ✅ Salt | ✅ Nonce | ✅ Salt |
| **Key Storage** | None needed | POSTOFFICE_PASSWORD_KEY | None needed |
| **Speed** | <1ms | <1ms | <1ms |
| **Use Case** | Member login | IMAP/SMTP daemon | IMAP auth |
| **Security Model** | Hashing | Encryption | Hashing |
| **Recovery** | Impossible | Possible (if key safe) | Impossible |

---

## Workflow Example

### Complete Flow

1. **Member Creates Account**
   ```
   Sets login password "member_pass"
   → SHA-256 hash + salt
   → Store in engine.__member
   ```

2. **Member Logs Into bbsengine6**
   ```
   Provides "member_pass"
   → Verify against SHA-256 hash
   → Authenticate if correct
   ```

3. **Member Sets IMAP Password**
   ```
   Sets IMAP password "imap_pass"
   → AES-256-GCM encrypt
   → Store in engine.__member.inbound_password
   ```

4. **Daemon Connects to IMAP**
   ```
   Retrieves stored encrypted password
   → AES-256-GCM decrypt
   → Get plaintext "imap_pass"
   → Use for IMAP login
   ```

---

## Testing

All 107 tests pass with both systems:
- ✅ SHA-256 hashing tested
- ✅ AES-256-GCM encryption tested
- ✅ Verification functions tested
- ✅ Decryption tested
- ✅ Permission controls verified
- ✅ Backward compatibility verified

---

## Summary

**SHA-256 + AES-256-GCM** provides the best of both worlds:

- **Maximum security** for member login (one-way hashing)
- **Flexible authentication** for email servers (reversible encryption)
- **Clear separation** of concerns
- **Industry standard** algorithms
- **Easy to use** APIs
