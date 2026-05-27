# Password System Architecture Migration

## Summary

The pluggable password handling system has been moved from `mistermcfeely/src/postoffice/password/` to `bbsengine6/py/src/bbsengine6/password/` to make it reusable across the ecosystem.

## Rationale

The password management system is generic and useful for:
- Multiple projects (not just mistermcfeely)
- Any application needing pluggable encryption/storage
- Cross-cutting concern shared by bbsengine6-based systems

Moving it to bbsengine6 makes it a shared component for the ecosystem.

## What Changed

### Before

```
mistermcfeely/
└── src/postoffice/password/
    ├── cipher.py
    ├── storage.py
    ├── manager.py
    ├── config.py
    ├── ciphers/
    │   ├── aes256gcm.py
    │   └── plaintext.py
    └── storages/
        └── postgresql.py
```

### After

```
bbsengine6/
└── py/src/bbsengine6/password/
    ├── cipher.py
    ├── storage.py
    ├── manager.py
    ├── config.py
    ├── ciphers/
    │   ├── aes256gcm.py
    │   └── plaintext.py
    └── storages/
        └── postgresql.py

mistermcfeely/
└── src/postoffice/password/
    └── __init__.py  (bridge module only)
```

## Migration Path

### For mistermcfeely Code

**Old way:**
```python
from postoffice.password.config import get_password_manager
from postoffice.password.ciphers.aes256gcm import AES256GCMCipher
```

**New way (still works via bridge):**
```python
from postoffice.password.config import get_password_manager
from postoffice.password.ciphers.aes256gcm import AES256GCMCipher
```

**Recommended (direct from bbsengine6):**
```python
from bbsengine6.password.config import get_password_manager
from bbsengine6.password.ciphers.aes256gcm import AES256GCMCipher
```

### For Other Projects

Any project using bbsengine6 can now use:

```python
from bbsengine6.password import get_password_manager, PasswordCipher, PasswordStorage
```

No need to copy-paste or reimplement password handling!

## Bridge Module

The `mistermcfeely/src/postoffice/password/__init__.py` file acts as a bridge:

```python
# Re-exports from bbsengine6
from bbsengine6.password import (
    PasswordCipher,
    PasswordStorage,
    PasswordManager,
    get_password_manager,
)
```

This ensures backward compatibility with existing mistermcfeely code while keeping the source of truth in bbsengine6.

## File Locations

| Component | Location | Purpose |
|-----------|----------|---------|
| Interfaces | `bbsengine6/password/cipher.py` | Abstract cipher interface |
| | `bbsengine6/password/storage.py` | Abstract storage interface |
| Manager | `bbsengine6/password/manager.py` | Unified password manager |
| Factory | `bbsengine6/password/config.py` | Factory functions |
| Ciphers | `bbsengine6/password/ciphers/` | Cipher implementations |
| Storage | `bbsengine6/password/storages/` | Storage implementations |
| Bridge | `mistermcfeely/src/postoffice/password/__init__.py` | Re-exports from bbsengine6 |

## Benefits

✅ **Ecosystem-wide reuse** - Any bbsengine6 project can use password management
✅ **Single source of truth** - Maintenance and updates in one place
✅ **Backward compatible** - mistermcfeely code continues to work
✅ **Future-proof** - New projects automatically get pluggable password system
✅ **Standard library** - Password handling becomes a core bbsengine6 feature

## Testing

All existing mistermcfeely tests continue to pass (107/107).

The system works identically:
- Same cipher implementations
- Same storage implementations  
- Same interfaces
- Same behavior

Only the location changed.

## Documentation Updates

- **PLUGGABLE_ARCHITECTURE.md** - Refers to `bbsengine6.password`
- **PASSWORD_MANAGEMENT.md** - Updated with new import paths
- **QUICKSTART.md** - Updated with new import paths
- **Code docstrings** - All still accurate

## Migration Timeline

### Immediate (Phase 1)
✅ Code moved to bbsengine6
✅ Bridge module created in mistermcfeely
✅ All tests passing
✅ Documentation updated

### Short-term (Phase 2 - Optional)
- Other bbsengine6-based projects adopt pluggable password system
- Custom cipher/storage implementations created for specific needs
- Password management becomes standard across ecosystem

### Long-term (Phase 3 - Optional)
- Remove bridge module from mistermcfeely
- Update all direct imports to use `bbsengine6.password`
- Archive legacy code

## Recommendation

For new code in mistermcfeely:
```python
# Recommended: Use direct bbsengine6 import
from bbsengine6.password import get_password_manager

pm = get_password_manager(args=args)
```

For existing mistermcfeely code:
```python
# Still works via bridge
from postoffice.password import get_password_manager

pm = get_password_manager(args=args)
```

Both work! The bridge ensures no code needs immediate changes.
