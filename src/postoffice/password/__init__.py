# password/__init__.py
# Pluggable password management system with strategy pattern
# Supports swappable cipher and storage implementations

from .cipher import PasswordCipher
from .storage import PasswordStorage
from .manager import PasswordManager
from .config import get_password_manager

__all__ = [
    "PasswordCipher",
    "PasswordStorage",
    "PasswordManager",
    "get_password_manager",
]
