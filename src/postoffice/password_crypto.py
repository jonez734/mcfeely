# password_crypto.py
# DEPRECATED: Functions moved to bbsengine6.util and bbsengine6.password
# This module remains for backward compatibility only

import warnings
from bbsengine6.util import (
    get_encryption_key,
    encrypt_password,
    decrypt_password,
)

warnings.warn(
    "postoffice.password_crypto is deprecated. "
    "Use bbsengine6.util for direct AES-256-GCM functions, or "
    "bbsengine6.password.config.get_password_manager() for pluggable system.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["get_encryption_key", "encrypt_password", "decrypt_password"]
