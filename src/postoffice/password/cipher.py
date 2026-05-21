# password/cipher.py
# Abstract cipher interface for password encryption/decryption
# Supports pluggable implementations: AES-256-GCM, ChaCha20, plaintext, etc.

from abc import ABC, abstractmethod


class PasswordCipher(ABC):
    """Abstract interface for password encryption/decryption.
    
    Implementations must support:
    - Encryption to a portable format (e.g., base64)
    - Decryption from that format
    - Secure key management
    
    Examples:
        - AES256GCMCipher - AES-256-GCM (NIST standard)
        - ChaCha20Cipher - ChaCha20-Poly1305 (portable, hardware-independent)
        - PlaintextCipher - No encryption (testing/migration only)
    """

    @abstractmethod
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext password.
        
        Args:
            plaintext: Plaintext password string.
        
        Returns:
            Encrypted password in portable format (e.g., base64).
            Must be storable in TEXT database columns.
        
        Raises:
            ValueError: If encryption fails or key is invalid.
        """
        pass

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt encrypted password.
        
        Args:
            ciphertext: Encrypted password in format from encrypt().
        
        Returns:
            Plaintext password string.
        
        Raises:
            ValueError: If decryption fails, key is invalid, or data is tampered.
        """
        pass


__all__ = ["PasswordCipher"]
