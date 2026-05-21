# password_crypto.py
# AES-256-GCM encryption/decryption for member passwords
# Database-agnostic: works with PostgreSQL, MySQL, SQLite, NoSQL, etc.

import os
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def get_encryption_key() -> bytes:
    """Get AES-256 key from POSTOFFICE_PASSWORD_KEY environment variable.

    Returns:
        Decrypted 32-byte key from base64-encoded environment variable.

    Raises:
        ValueError: If POSTOFFICE_PASSWORD_KEY is not set.
        ValueError: If key is not valid base64 or wrong length.
    """
    key_b64 = os.environ.get("POSTOFFICE_PASSWORD_KEY")
    if not key_b64:
        raise ValueError(
            "POSTOFFICE_PASSWORD_KEY environment variable not set. "
            "Generate with: openssl rand -base64 32"
        )

    try:
        key = base64.b64decode(key_b64)
    except Exception as e:
        raise ValueError(f"POSTOFFICE_PASSWORD_KEY is not valid base64: {e}")

    if len(key) != 32:
        raise ValueError(
            f"POSTOFFICE_PASSWORD_KEY must be 32 bytes (256 bits), got {len(key)} bytes"
        )

    return key


def encrypt_password(plaintext: str) -> str:
    """Encrypt plaintext password with AES-256-GCM.

    Generates a random 96-bit nonce, encrypts the plaintext, and returns
    the result as base64(nonce + ciphertext + auth_tag).

    Args:
        plaintext: Password string to encrypt (plaintext).

    Returns:
        Base64-encoded string containing nonce + ciphertext + auth_tag.

    Raises:
        ValueError: If encryption key is not set or invalid.
    """
    key = get_encryption_key()

    # Generate random 96-bit nonce (12 bytes)
    nonce = os.urandom(12)

    # Create cipher and encrypt
    cipher = AESGCM(key)
    ciphertext = cipher.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Concatenate nonce + ciphertext (ciphertext includes 128-bit auth tag)
    encrypted = nonce + ciphertext

    # Encode as base64 for database storage
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_password(encrypted_b64: str) -> str:
    """Decrypt base64-encoded AES-256-GCM encrypted password.

    Args:
        encrypted_b64: Base64-encoded string (nonce + ciphertext + auth_tag).

    Returns:
        Decrypted plaintext password.

    Raises:
        ValueError: If decryption key is not set or invalid.
        ValueError: If base64 decoding fails.
        ValueError: If authentication tag verification fails (tampering detected).
    """
    key = get_encryption_key()

    try:
        encrypted = base64.b64decode(encrypted_b64)
    except Exception as e:
        raise ValueError(f"Failed to decode base64 encrypted password: {e}")

    if len(encrypted) < 28:  # 12 bytes nonce + 16 bytes auth tag minimum
        raise ValueError(
            f"Encrypted password too short: {len(encrypted)} bytes "
            "(expected at least 28 bytes)"
        )

    # Extract nonce and ciphertext
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]

    # Decrypt and verify auth tag
    cipher = AESGCM(key)
    try:
        plaintext = cipher.decrypt(nonce, ciphertext, None)
    except Exception as e:
        raise ValueError(
            f"Failed to decrypt password (authentication tag verification failed): {e}"
        )

    return plaintext.decode("utf-8")


__all__ = [
    "get_encryption_key",
    "encrypt_password",
    "decrypt_password",
]
