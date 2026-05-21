# password/config.py
# Factory and configuration for password manager

import os
from typing import Optional, Type

from bbsengine6.io import echo

from .cipher import PasswordCipher
from .ciphers.aes256gcm import AES256GCMCipher
from .ciphers.plaintext import PlaintextCipher
from .manager import PasswordManager
from .storage import PasswordStorage
from .storages.postgresql import PostgreSQLStorage


def get_cipher(cipher_name: str = "aes256gcm") -> PasswordCipher:
    """Get cipher instance by name.
    
    Args:
        cipher_name: Cipher name ('aes256gcm', 'plaintext', etc.)
                    Defaults to 'aes256gcm'.
                    Can be overridden via PASSWORD_CIPHER env var.
    
    Returns:
        PasswordCipher implementation instance.
    
    Raises:
        ValueError: If cipher name is unknown or initialization fails.
    """
    # Allow env var override
    cipher_name = os.environ.get("PASSWORD_CIPHER", cipher_name).lower()

    if cipher_name == "aes256gcm":
        key_b64 = os.environ.get("POSTOFFICE_PASSWORD_KEY")
        if not key_b64:
            raise ValueError(
                "POSTOFFICE_PASSWORD_KEY environment variable required "
                "for AES-256-GCM cipher"
            )
        return AES256GCMCipher(key_b64)

    elif cipher_name == "plaintext":
        echo(
            "WARNING: Using plaintext cipher! Passwords NOT encrypted!",
            level="warn",
        )
        return PlaintextCipher()

    else:
        raise ValueError(f"Unknown cipher: {cipher_name}")


def get_storage(
    storage_name: str = "postgresql", args=None
) -> PasswordStorage:
    """Get storage instance by name.
    
    Args:
        storage_name: Storage name ('postgresql', etc.)
                     Defaults to 'postgresql'.
                     Can be overridden via PASSWORD_STORAGE env var.
        args: bbsengine6 args object (required for postgresql).
    
    Returns:
        PasswordStorage implementation instance.
    
    Raises:
        ValueError: If storage name is unknown or initialization fails.
    """
    # Allow env var override
    storage_name = os.environ.get("PASSWORD_STORAGE", storage_name).lower()

    if storage_name == "postgresql":
        if not args:
            raise ValueError("args required for postgresql storage")
        return PostgreSQLStorage(args)

    else:
        raise ValueError(f"Unknown storage: {storage_name}")


def get_password_manager(
    cipher_name: str = "aes256gcm",
    storage_name: str = "postgresql",
    args=None,
) -> PasswordManager:
    """Factory function to create configured password manager.
    
    Reads environment variables for default cipher/storage selection:
    - PASSWORD_CIPHER: Cipher to use ('aes256gcm', 'plaintext', etc.)
    - PASSWORD_STORAGE: Storage to use ('postgresql', etc.)
    - POSTOFFICE_PASSWORD_KEY: Key for AES-256-GCM cipher
    
    Args:
        cipher_name: Default cipher name ('aes256gcm').
        storage_name: Default storage name ('postgresql').
        args: bbsengine6 args object (required for postgresql storage).
    
    Returns:
        Fully configured PasswordManager instance.
    
    Raises:
        ValueError: If cipher or storage initialization fails.
    
    Example:
        # Use defaults (AES-256-GCM + PostgreSQL)
        pm = get_password_manager(args=args)
        
        # Use plaintext cipher for testing
        pm = get_password_manager(cipher_name="plaintext", args=args)
    """
    cipher = get_cipher(cipher_name)
    storage = get_storage(storage_name, args)
    return PasswordManager(cipher, storage)


__all__ = [
    "get_cipher",
    "get_storage",
    "get_password_manager",
]
