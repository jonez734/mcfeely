# Pluggable Password Handling Architecture

## Overview

The password handling system uses the **Strategy Pattern** to allow easy swapping of cipher and storage implementations without modifying application code.

This document explains the architecture and how to extend it.

## Architecture

### Design Pattern: Strategy Pattern

```
┌─────────────────────────────────────────────────────┐
│         PasswordManager (Unified Interface)         │
│  set_personal_password(), get_personal_password()   │
│  set_shared_mailbox_password(), etc.                │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
      ┌────▼─────┐            ┌──────▼──────┐
      │  Cipher  │            │  Storage     │
      │ (Abstract)           │ (Abstract)   │
      └────┬─────┘            └──────┬──────┘
           │                         │
    ┌──────┴──────────┐      ┌──────┴──────────┐
    │                 │      │                 │
┌───▼──────┐ ┌───────▼───┐ ┌┴─────────┐ ┌─────▼────┐
│  AES-256 │ │ ChaCha20  │ │PostgreSQL│ │ MongoDB  │
│   GCM    │ │ (future)  │ │(current) │ │(future)  │
└──────────┘ └───────────┘ └──────────┘ └──────────┘
```

### Layer Responsibilities

**PasswordManager**:
- High-level API for password operations
- Orchestrates cipher and storage
- Handles errors and validation
- Application code uses only this layer

**PasswordCipher (Abstract)**:
- Encrypts/decrypts plaintext passwords
- Returns encrypted data in portable format
- Knows nothing about storage

**PasswordStorage (Abstract)**:
- Persists encrypted passwords
- Retrieves encrypted passwords
- Knows nothing about encryption

## Interface Specifications

### PasswordCipher Interface

```python
class PasswordCipher(ABC):
    @abstractmethod
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext password.
        
        Returns:
            Encrypted password (e.g., base64 for AES-256-GCM)
        """
        pass

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt encrypted password.
        
        Returns:
            Plaintext password
        
        Raises:
            ValueError: If decryption fails (wrong key, tampering, etc.)
        """
        pass
```

### PasswordStorage Interface

```python
class PasswordStorage(ABC):
    @abstractmethod
    def get_personal_password(
        self, member_moniker: str, password_type: str
    ) -> Optional[str]:
        """Get encrypted personal account password."""
        pass

    @abstractmethod
    def set_personal_password(
        self, member_moniker: str, password_type: str,
        encrypted_password: str, set_by_moniker: str
    ) -> bool:
        """Store encrypted personal account password."""
        pass

    # ... similar methods for shared mailbox passwords
```

## Current Implementations

### Ciphers

| Implementation | Use Case | Location |
|---|---|---|
| **AES256GCMCipher** | Production (default) | `password/ciphers/aes256gcm.py` |
| **PlaintextCipher** | Testing/migration only | `password/ciphers/plaintext.py` |

### Storage

| Implementation | Use Case | Location |
|---|---|---|
| **PostgreSQLStorage** | Production (default) | `password/storages/postgresql.py` |

## Usage Examples

### Using Default Configuration (AES-256-GCM + PostgreSQL)

```python
from postoffice.password.config import get_password_manager

pm = get_password_manager(args=args)

# All encrypted with AES-256-GCM, stored in PostgreSQL
pm.set_personal_password("jam", "inbound", "password123", "sysop")
password = pm.get_personal_password("jam", "inbound")
```

### Using Factory with Environment Variables

```bash
# In shell or systemd service
export PASSWORD_CIPHER=aes256gcm
export PASSWORD_STORAGE=postgresql
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)
```

```python
from postoffice.password.config import get_password_manager

# Automatically uses environment variable settings
pm = get_password_manager(args=args)
```

### Using Plaintext Cipher (Testing)

```python
from postoffice.password.ciphers.plaintext import PlaintextCipher
from postoffice.password.storages.postgresql import PostgreSQLStorage
from postoffice.password.manager import PasswordManager

# For testing - NO encryption
cipher = PlaintextCipher()
storage = PostgreSQLStorage(args)
pm = PasswordManager(cipher, storage)

# Plaintext stored in database - for testing only!
pm.set_personal_password("jam", "inbound", "password123", "test")
```

### Direct Instantiation with Custom Implementations

```python
from postoffice.password.ciphers.aes256gcm import AES256GCMCipher
from postoffice.password.storages.postgresql import PostgreSQLStorage
from postoffice.password.manager import PasswordManager

key = "base64-encoded-32-byte-key"
cipher = AES256GCMCipher(key)
storage = PostgreSQLStorage(args)
pm = PasswordManager(cipher, storage)
```

## Creating Custom Implementations

### Creating a Custom Cipher (Example: ChaCha20)

```python
# password/ciphers/chacha20.py
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
import os
import base64
from ..cipher import PasswordCipher

class ChaCha20Cipher(PasswordCipher):
    """ChaCha20-Poly1305 cipher (portable, hardware-independent)."""
    
    def __init__(self, key_b64: str):
        self.key = base64.b64decode(key_b64)
        if len(self.key) != 32:
            raise ValueError("Key must be 32 bytes")
    
    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        cipher = ChaCha20Poly1305(self.key)
        ciphertext = cipher.encrypt(nonce, plaintext.encode("utf-8"), None)
        encrypted = nonce + ciphertext
        return base64.b64encode(encrypted).decode("utf-8")
    
    def decrypt(self, ciphertext_b64: str) -> str:
        encrypted = base64.b64decode(ciphertext_b64)
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        cipher = ChaCha20Poly1305(self.key)
        plaintext = cipher.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
```

Then register in `password/config.py`:

```python
# In get_cipher() factory function
elif cipher_name == "chacha20":
    return ChaCha20Cipher(key_b64)
```

### Creating a Custom Storage (Example: MongoDB)

```python
# password/storages/mongodb.py
from ..storage import PasswordStorage
import pymongo

class MongoDBStorage(PasswordStorage):
    """MongoDB password storage backend."""
    
    def __init__(self, connection_string: str):
        self.client = pymongo.MongoClient(connection_string)
        self.db = self.client['postoffice']
        self.personal_pwd = self.db['personal_passwords']
        self.mailbox_pwd = self.db['mailbox_passwords']
    
    def get_personal_password(self, member_moniker: str, password_type: str):
        doc = self.personal_pwd.find_one({
            'member_moniker': member_moniker,
            'password_type': password_type
        })
        return doc['encrypted_password'] if doc else None
    
    def set_personal_password(self, member_moniker, password_type, 
                             encrypted_password, set_by_moniker):
        self.personal_pwd.update_one(
            {'member_moniker': member_moniker, 'password_type': password_type},
            {'$set': {
                'encrypted_password': encrypted_password,
                'set_by': set_by_moniker,
                'updated_at': datetime.utcnow()
            }},
            upsert=True
        )
        return True
    
    # ... implement other abstract methods
```

Register in `password/config.py`:

```python
elif storage_name == "mongodb":
    connection_string = os.environ.get("MONGODB_URI")
    return MongoDBStorage(connection_string)
```

## Testing with Custom Implementations

### Unit Testing with Plaintext Cipher

```python
def test_password_operations():
    from postoffice.password.ciphers.plaintext import PlaintextCipher
    from postoffice.password.storages.postgresql import PostgreSQLStorage
    from postoffice.password.manager import PasswordManager
    
    cipher = PlaintextCipher()  # Testing - no encryption
    storage = PostgreSQLStorage(mock_args)
    pm = PasswordManager(cipher, storage)
    
    pm.set_personal_password("testuser", "inbound", "test123", "test")
    password = pm.get_personal_password("testuser", "inbound")
    assert password == "test123"  # Plaintext, easy to debug
```

### Testing with Mock Storage

```python
from unittest.mock import Mock
from postoffice.password.ciphers.aes256gcm import AES256GCMCipher

def test_with_mock_storage():
    key = base64.b64encode(os.urandom(32)).decode()
    cipher = AES256GCMCipher(key)
    
    mock_storage = Mock()
    mock_storage.get_personal_password.return_value = cipher.encrypt("secret")
    
    pm = PasswordManager(cipher, mock_storage)
    password = pm.get_personal_password("user", "inbound")
    assert password == "secret"
    mock_storage.get_personal_password.assert_called_once()
```

## Environment Variable Configuration

| Variable | Values | Default | Example |
|----------|--------|---------|---------|
| `PASSWORD_CIPHER` | `aes256gcm`, `plaintext`, `chacha20` | `aes256gcm` | `export PASSWORD_CIPHER=aes256gcm` |
| `PASSWORD_STORAGE` | `postgresql`, `mongodb`, `vault` | `postgresql` | `export PASSWORD_STORAGE=postgresql` |
| `POSTOFFICE_PASSWORD_KEY` | Base64 32 bytes | (required for AES-256-GCM) | `openssl rand -base64 32` |
| `MONGODB_URI` | Connection string | (required for MongoDB) | `mongodb://localhost:27017` |

## Migration Scenarios

### Migrate from One Cipher to Another

1. Keep PostgreSQL storage
2. Create new cipher implementation (e.g., ChaCha20Cipher)
3. Set `PASSWORD_CIPHER=chacha20` environment variable
4. On first password operation, new cipher is used
5. Old encrypted passwords can be gradually re-encrypted

```python
# Migration script example
old_cipher = AES256GCMCipher(old_key)
new_cipher = ChaCha20Cipher(new_key)

for member in all_members():
    encrypted_old = storage.get_personal_password(member, "inbound")
    if encrypted_old:
        plaintext = old_cipher.decrypt(encrypted_old)
        encrypted_new = new_cipher.encrypt(plaintext)
        storage.set_personal_password(member, "inbound", encrypted_new, "migration")
```

### Migrate from One Storage to Another

1. Keep cipher implementation
2. Create new storage implementation
3. Copy all passwords from old storage to new storage
4. Update configuration to use new storage

```python
# Migration script
old_storage = PostgreSQLStorage(old_args)
new_storage = MongoDBStorage(mongo_uri)

for member in all_members():
    # Copy all passwords
    inbound = old_storage.get_personal_password(member, "inbound")
    outbound = old_storage.get_personal_password(member, "outbound")
    
    if inbound:
        new_storage.set_personal_password(member, "inbound", inbound, "migration")
    if outbound:
        new_storage.set_personal_password(member, "outbound", outbound, "migration")
```

## Future Implementations

Recommended next cipher implementations:
- **ChaCha20Poly1305**: Hardware-independent, excellent performance
- **RSA**: For key-less encryption (public key infrastructure)
- **HMAC-SIV**: Nonce misuse resistant

Recommended next storage implementations:
- **FileSystemStorage**: Encrypted files (testing/backup)
- **MongoDBStorage**: NoSQL persistence
- **VaultStorage**: HashiCorp Vault (enterprise secrets management)
- **LDAPStorage**: LDAP directory integration
- **RedisStorage**: In-memory cache (session passwords)

## Benefits of This Architecture

✅ **Easy to extend**: Add new cipher/storage without modifying existing code
✅ **Testable**: Mock cipher/storage in unit tests
✅ **Configurable**: Switch implementations via environment variables
✅ **Decoupled**: Cipher knows nothing about storage, vice versa
✅ **Maintainable**: Each implementation is independent and focused
✅ **Future-proof**: New ciphers/storage can be added without breaking existing code
✅ **Production-ready**: Default implementations (AES-256-GCM + PostgreSQL) are secure

## Summary

The pluggable architecture makes it trivial to:
- Try different encryption algorithms
- Switch storage backends
- Test without real encryption
- Migrate to new systems
- Implement custom requirements

All while keeping the application code simple and focused on business logic.
