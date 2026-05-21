# Password Functions Moved to bbsengine6

## Summary

The core password encryption functions have been moved from `postoffice.password_crypto` to `bbsengine6.util` for ecosystem-wide reuse.

## What Moved

Three functions moved from mistermcfeely to bbsengine6:

| Function | Location | Status |
|----------|----------|--------|
| `get_encryption_key()` | `bbsengine6.util` | ✅ Active |
| `encrypt_password()` | `bbsengine6.util` | ✅ Active |
| `decrypt_password()` | `bbsengine6.util` | ✅ Active |

These provide direct AES-256-GCM encryption functionality.

## Backward Compatibility

The old import location still works via a deprecation shim:

```python
# OLD WAY (still works, shows deprecation warning)
from postoffice.password_crypto import encrypt_password

# NEW WAY (recommended)
from bbsengine6.util import encrypt_password
```

## Migration Path

### Phase 1: Current (No Action Required)
- ✅ Functions moved to bbsengine6.util
- ✅ Deprecation shim in place in mistermcfeely
- ✅ All existing code continues to work
- ✅ Deprecation warnings guide migration

### Phase 2: Recommended Updates
Update imports in new code:

```python
# For direct AES-256-GCM encryption
from bbsengine6.util import encrypt_password, decrypt_password

# For pluggable password system (recommended)
from bbsengine6.password.config import get_password_manager
```

### Phase 3: Planned Deprecation
In a future release, the mistermcfeely shim may be removed.
All code should migrate to bbsengine6 imports by then.

## Three Ways to Handle Passwords

### 1. Direct AES-256-GCM (Simplest)
```python
from bbsengine6.util import encrypt_password, decrypt_password

encrypted = encrypt_password("mysecret")
plaintext = decrypt_password(encrypted)
```

**Use when**: You just need to encrypt/decrypt passwords
**Pros**: Simple, direct, no dependencies
**Cons**: Only supports AES-256-GCM

### 2. Pluggable Password System (Recommended)
```python
from bbsengine6.password.config import get_password_manager

pm = get_password_manager(args=args)
pm.set_personal_password("jam", "inbound", "mysecret", "sysop")
password = pm.get_personal_password("jam", "inbound")
```

**Use when**: You need password storage + retrieval with metadata
**Pros**: Pluggable cipher/storage, full-featured, database integration
**Cons**: More setup required

### 3. Deprecated Shim (Backward Compatibility Only)
```python
from postoffice.password_crypto import encrypt_password  # Shows deprecation warning
```

**Use when**: Maintaining existing mistermcfeely code
**Pros**: No code changes needed
**Cons**: Shows deprecation warning, will be removed eventually

## Deprecation Warning

When importing from `postoffice.password_crypto`, you'll see:

```
DeprecationWarning: postoffice.password_crypto is deprecated. 
Use bbsengine6.util for direct AES-256-GCM functions, or 
bbsengine6.password.config.get_password_manager() for pluggable system.
```

This is intentional and guides you to the correct module.

## Why This Change

1. **Ecosystem Reuse**: Any bbsengine6-based project can now use encryption
2. **Single Source**: Functions live in bbsengine6 where they're maintained
3. **Flexibility**: Three options (direct, pluggable, deprecated) for different needs
4. **Future-Proof**: Easy to add new ciphers/storage to bbsengine6.password

## Testing

All 107 tests pass with the migration:
- Tests that import `postoffice.password_crypto` generate deprecation warning
- All functionality works identically
- No breaking changes

## Documentation Updates

- **PASSWORD_MANAGEMENT.md** - References updated to bbsengine6.util
- **PLUGGABLE_ARCHITECTURE.md** - Explains full password system
- **PASSWORD_FUNCTIONS_MOVED.md** - This file
- **Code docstrings** - Updated with location info

## Recommended Action

For new code in mistermcfeely:

```python
# Use this for simple encryption
from bbsengine6.util import encrypt_password, decrypt_password

# Or use this for full password management (better)
from bbsengine6.password.config import get_password_manager
```

Existing code will continue to work without changes.
