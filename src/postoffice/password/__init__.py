# postoffice/password/__init__.py
# Bridge module: re-exports from bbsengine6.password
# The actual implementation has moved to bbsengine6 for reusability

from bbsengine6.password import (
    PasswordCipher,
    PasswordStorage,
    PasswordManager,
    get_password_manager,
)

__all__ = [
    "PasswordCipher",
    "PasswordStorage",
    "PasswordManager",
    "get_password_manager",
]
