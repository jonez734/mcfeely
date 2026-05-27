# Two Password Systems: When to Use Each

## Overview

bbsengine6 provides **two different password systems** for two different use cases:

### System 1: SHA-256 Hashing (One-Way)
**Location**: `bbsengine6.password_hash`
**Purpose**: Member login passwords to bbsengine6
**Properties**: One-way hash, can verify but NOT decrypt
**Use Case**: "Is this the correct login password?"

### System 2: AES-256-GCM Encryption (Reversible)
**Location**: `bbsengine6.util` or `bbsengine6.password`
**Purpose**: IMAP/SMTP server credentials
**Properties**: Reversible, can encrypt AND decrypt
**Use Case**: "Authenticate to external email servers"

---

## System 1: SHA-256 Hashing (bbsengine6.password_hash)

### Use This For:
- Member passwords for bbsengine6 login
- Any password that only needs verification
- Passwords that should NEVER be decrypted

### Cannot Do:
- ❌ Decrypt passwords
- ❌ Get plaintext password back
- ❌ Authenticate to external servers

### API

```python
from bbsengine6.password_hash import hash_password, verify_password, generate_salt

# Creating a hash
hashed, salt = hash_password("mypassword")
# Returns: (base64_hash, base64_salt)

# Verifying a password
is_correct = verify_password("mypassword", hashed, salt)
# Returns: True or False

# Generate salt for custom use
salt = generate_salt()
# Returns: base64-encoded 32 random bytes
```

### Algorithm
- **Hash**: SHA-256
- **Salt**: Random 32 bytes (256 bits)
- **Format**: base64-encoded
- **Security**: One-way, cannot be reversed

### Example: Store Member Password

```python
from bbsengine6.password_hash import hash_password

# When member sets their password
plaintext = user_input_password
hashed, salt = hash_password(plaintext)

# Store in database
db.update("engine.__member", 
    password_hash=hashed,
    password_salt=salt,
    moniker=member_moniker
)
```

### Example: Verify Login

```python
from bbsengine6.password_hash import verify_password

# During login
provided_password = user_input_password
is_correct = verify_password(provided_password, stored_hash, stored_salt)

if is_correct:
    # Login successful
    authenticate_user(member_moniker)
else:
    # Login failed
    deny_access()
```

---

## System 2: AES-256-GCM Encryption (Reversible)

### Use This For:
- IMAP server credentials
- SMTP server credentials
- Any password needed for external server authentication
- Passwords that MUST be decrypted to use

### Can Do:
- ✅ Encrypt passwords
- ✅ Decrypt passwords
- ✅ Get plaintext password back
- ✅ Authenticate to external servers

### Cannot Do:
- ❌ Verify without decryption
- ❌ Store safely if key is compromised

### API

```python
from bbsengine6.util import encrypt_password, decrypt_password, get_encryption_key

# Encrypt a password
plaintext = "imap_password_123"
encrypted = encrypt_password(plaintext)
# Returns: base64(nonce + ciphertext + auth_tag)

# Decrypt a password
plaintext = decrypt_password(encrypted)
# Returns: "imap_password_123"

# Or use pluggable system
from bbsengine6.password.config import get_password_manager
pm = get_password_manager(args=args)
pm.set_personal_password("jam", "inbound", "password123", "sysop")
password = pm.get_personal_password("jam", "inbound")
```

### Algorithm
- **Cipher**: AES-256-GCM (NIST SP800-38D)
- **Key**: 256 bits (32 bytes) from environment
- **Nonce**: 96 bits (12 bytes), random per encryption
- **Auth Tag**: 128 bits (16 bytes), detects tampering
- **Format**: base64(nonce + ciphertext + tag)
- **Reversible**: Yes, can decrypt

### Example: Store IMAP Password

```python
from bbsengine6.password.config import get_password_manager

pm = get_password_manager(args=args)

# When member sets their IMAP password
plaintext = user_input_password
pm.set_personal_password("jam", "inbound", plaintext, "sysop")
```

### Example: Use IMAP Password

```python
from bbsengine6.password.config import get_password_manager
import imaplib

pm = get_password_manager(args=args)

# Retrieve and use IMAP password
password = pm.get_personal_password("jam", "inbound")

if password:
    imap = imaplib.IMAP4_SSL(imap_server, 993)
    imap.login("jam@example.com", password)
else:
    echo("IMAP password not found", level="error")
```

---

## Comparison Table

| Feature | SHA-256 Hashing | AES-256-GCM Encryption |
|---------|-----------------|----------------------|
| **Purpose** | Member login verification | IMAP/SMTP authentication |
| **Reversible** | ❌ No | ✅ Yes |
| **Can Decrypt** | ❌ No | ✅ Yes |
| **Can Verify** | ✅ Yes | ✅ Yes (via decryption) |
| **Use Case** | "Is password correct?" | "Get plaintext to authenticate" |
| **Security Level** | Very high (one-way) | High (reversible, needs key) |
| **Key Required** | ❌ No (uses salt) | ✅ Yes (POSTOFFICE_PASSWORD_KEY) |
| **Cross-Language** | ✅ Yes (SHA-256) | ✅ Yes (AES-256-GCM) |
| **Storage** | Hash + Salt | Base64(nonce+cipher+tag) |
| **Decryption Time** | N/A | <1ms |
| **Verification Time** | <1ms | <1ms (via decryption) |

---

## When to Use Each

### Use SHA-256 Hashing When:
- ✅ Storing member passwords for bbsengine6 login
- ✅ Password only needs to be verified, never used for auth
- ✅ You want maximum security (one-way is better)
- ✅ You don't need plaintext password

### Use AES-256-GCM When:
- ✅ Storing IMAP server credentials
- ✅ Storing SMTP server credentials
- ✅ Password must be decrypted to authenticate
- ✅ You need plaintext password for external services

### Examples

**Member Setting Their bbsengine6 Password** (SHA-256):
```python
from bbsengine6.password_hash import hash_password

hashed, salt = hash_password(member_password)
# Store hashed and salt in engine.__member
```

**Member Setting Their IMAP Password** (AES-256-GCM):
```python
from bbsengine6.password.config import get_password_manager

pm = get_password_manager(args=args)
pm.set_personal_password("jam", "inbound", imap_password, "sysop")
# Store encrypted password in postoffice
```

**Member Logging In** (SHA-256 verification):
```python
from bbsengine6.password_hash import verify_password

if verify_password(provided_password, stored_hash, stored_salt):
    authenticate_user()
```

**Connecting to IMAP** (AES-256-GCM decryption):
```python
from bbsengine6.password.config import get_password_manager

pm = get_password_manager(args=args)
password = pm.get_personal_password("jam", "inbound")
imap.login(user, password)  # Uses plaintext password
```

---

## Database Storage

### SHA-256 Hashed Passwords

```sql
ALTER TABLE engine.__member ADD COLUMN password_hash TEXT;
ALTER TABLE engine.__member ADD COLUMN password_salt TEXT;

-- Example:
-- password_hash: "QyDV6K8O7J3..." (base64-encoded SHA-256)
-- password_salt: "rX4mK2L9..." (base64-encoded salt)
```

### AES-256-GCM Encrypted Passwords

```sql
-- Personal account passwords
ALTER TABLE engine.__member ADD COLUMN inbound_password TEXT;
ALTER TABLE engine.__member ADD COLUMN outbound_password TEXT;

-- Example:
-- inbound_password: "aBcD1eF2gH3iJ4..." (base64(nonce+cipher+tag))

-- Shared mailbox passwords
CREATE TABLE postoffice.member_mailbox_password (
    encrypted_password TEXT NOT NULL,  -- base64(nonce+cipher+tag)
    -- ... other columns
);
```

---

## Configuration

### SHA-256 Hashing
No configuration required. Uses salt built into each hash.

### AES-256-GCM Encryption
Requires environment variable:
```bash
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)
```

---

## Security Implications

### SHA-256 Hashing
- ✅ **Secure**: Even if database is compromised, passwords cannot be recovered
- ✅ **Salt**: Prevents rainbow table attacks
- ✅ **One-way**: Attacker cannot decrypt

### AES-256-GCM Encryption
- ✅ **Reversible**: Needed for external authentication
- ⚠️ **Key-dependent**: Security depends on protecting POSTOFFICE_PASSWORD_KEY
- ✅ **Auth tag**: Detects tampering
- ✅ **Nonce**: Random per message prevents patterns

---

## Summary

Use **SHA-256 hashing** for member login passwords (bbsengine6 authentication).
Use **AES-256-GCM encryption** for IMAP/SMTP credentials (external server authentication).

Never mix them up!
