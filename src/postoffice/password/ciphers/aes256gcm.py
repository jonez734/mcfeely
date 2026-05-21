# password/ciphers/aes256gcm.py
# AES-256-GCM cipher implementation (NIST SP800-38D standard)
# Cross-language compatible: Python, JavaScript, Rust, Perl, C, PHP, etc.

import os
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..cipher import PasswordCipher


class AES256GCMCipher(PasswordCipher):
    """AES-256-GCM encryption cipher.
    
    Algorithm: AES-256-GCM (Galois/Counter Mode)
    - Key size: 256 bits (32 bytes)
    - Nonce size: 96 bits (12 bytes) - random per message
    - Auth tag: 128 bits (16 bytes)
    - Storage format: Base64(nonce + ciphertext + auth_tag)
    
    Supports encrypted password interchange with:
    - Python: cryptography library
    - JavaScript/Node: crypto.createCipheriv('aes-256-gcm')
    - Rust: aes-gcm crate
    - Perl: Crypt::AESGCM
    - C: OpenSSL EVP functions
    - PHP: openssl_encrypt('aes-256-gcm')
    - Cyrus IMAP: System crypto libraries
    """

    def __init__(self, key_b64: str):
        """Initialize cipher with base64-encoded encryption key.
        
        Args:
            key_b64: Base64-encoded 256-bit (32-byte) encryption key.
                    Generate with: openssl rand -base64 32
        
        Raises:
            ValueError: If key is invalid.
        """
        try:
            self.key = base64.b64decode(key_b64)
        except Exception as e:
            raise ValueError(f"Invalid base64 key: {e}")

        if len(self.key) != 32:
            raise ValueError(
                f"Key must be 32 bytes (256 bits), got {len(self.key)} bytes"
            )

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext with AES-256-GCM.
        
        Args:
            plaintext: Password string to encrypt.
        
        Returns:
            Base64-encoded encrypted password: base64(nonce + ciphertext + auth_tag)
        
        Raises:
            ValueError: If encryption fails.
        """
        try:
            nonce = os.urandom(12)
            cipher = AESGCM(self.key)
            ciphertext = cipher.encrypt(nonce, plaintext.encode("utf-8"), None)
            encrypted = nonce + ciphertext
            return base64.b64encode(encrypted).decode("utf-8")
        except Exception as e:
            raise ValueError(f"Encryption failed: {e}")

    def decrypt(self, ciphertext_b64: str) -> str:
        """Decrypt AES-256-GCM encrypted password.
        
        Args:
            ciphertext_b64: Base64-encoded encrypted password.
        
        Returns:
            Decrypted plaintext password.
        
        Raises:
            ValueError: If decryption fails (tampering detected, wrong key, etc.)
        """
        try:
            encrypted = base64.b64decode(ciphertext_b64)
        except Exception as e:
            raise ValueError(f"Invalid base64 ciphertext: {e}")

        if len(encrypted) < 28:  # 12 bytes nonce + 16 bytes tag minimum
            raise ValueError(
                f"Ciphertext too short: {len(encrypted)} bytes "
                "(expected at least 28 bytes)"
            )

        try:
            nonce = encrypted[:12]
            ciphertext = encrypted[12:]
            cipher = AESGCM(self.key)
            plaintext = cipher.decrypt(nonce, ciphertext, None)
            return plaintext.decode("utf-8")
        except Exception as e:
            raise ValueError(
                f"Decryption failed (authentication tag verification failed): {e}"
            )


__all__ = ["AES256GCMCipher"]
