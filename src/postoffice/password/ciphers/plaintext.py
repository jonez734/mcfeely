# password/ciphers/plaintext.py
# Plaintext "cipher" implementation (testing and migration only)
# WARNING: Stores passwords in plaintext - DO NOT USE IN PRODUCTION

from ..cipher import PasswordCipher


class PlaintextCipher(PasswordCipher):
    """Plaintext "cipher" that doesn't encrypt.
    
    WARNING: This cipher stores passwords in plaintext!
    
    Use cases:
    - Testing and unit tests
    - Migration from plaintext storage
    - Development environments only
    
    Never use in production! Implement a real cipher instead.
    """

    def __init__(self):
        """Initialize plaintext cipher."""
        pass

    def encrypt(self, plaintext: str) -> str:
        """Return plaintext unchanged.
        
        Args:
            plaintext: Password string.
        
        Returns:
            Same plaintext (not encrypted).
        """
        return plaintext

    def decrypt(self, ciphertext: str) -> str:
        """Return ciphertext unchanged (same as plaintext).
        
        Args:
            ciphertext: "Encrypted" password (actually plaintext).
        
        Returns:
            Same plaintext.
        """
        return ciphertext


__all__ = ["PlaintextCipher"]
