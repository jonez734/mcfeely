# startup.py
# Startup initialization for mistermcfeely password management system
# Sets up encryption keys and validates configuration

import os
import sys
import base64
from typing import Optional, Dict, Any

from bbsengine6.io import echo


def validate_encryption_key() -> bool:
    """
    Validate that POSTOFFICE_PASSWORD_KEY is set and valid.

    Returns:
        True if valid, False otherwise
    """
    key_b64 = os.environ.get("POSTOFFICE_PASSWORD_KEY")

    if not key_b64:
        echo(
            "ERROR: POSTOFFICE_PASSWORD_KEY environment variable not set",
            level="error",
        )
        echo(
            "  Set it with: export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)",
            level="error",
        )
        return False

    try:
        key_bytes = base64.b64decode(key_b64)
        if len(key_bytes) != 32:
            echo(
                f"ERROR: POSTOFFICE_PASSWORD_KEY must be 32 bytes (got {len(key_bytes)})",
                level="error",
            )
            return False
        return True
    except Exception as e:
        echo(f"ERROR: POSTOFFICE_PASSWORD_KEY is not valid base64: {e}", level="error")
        return False


def validate_password_config() -> Dict[str, str]:
    """
    Validate password system configuration.

    Returns:
        Dict with 'cipher' and 'storage' keys, or empty dict on error
    """
    cipher = os.environ.get("PASSWORD_CIPHER", "aes256gcm")
    storage = os.environ.get("PASSWORD_STORAGE", "postgresql")

    # Validate cipher
    valid_ciphers = ["aes256gcm", "plaintext"]
    if cipher not in valid_ciphers:
        echo(
            f"WARNING: Unknown PASSWORD_CIPHER '{cipher}', using default 'aes256gcm'",
            level="error",
        )
        cipher = "aes256gcm"

    # Validate storage
    valid_storages = ["postgresql"]
    if storage not in valid_storages:
        echo(
            f"WARNING: Unknown PASSWORD_STORAGE '{storage}', using default 'postgresql'",
            level="error",
        )
        storage = "postgresql"

    return {"cipher": cipher, "storage": storage}


def initialize_password_system() -> bool:
    """
    Initialize the password management system.

    Checks encryption key, validates configuration, and logs startup info.

    Returns:
        True if initialization successful, False otherwise
    """
    if getattr(initialize_password_system, "_initialized", False):
        return True

    echo("Initializing password management system...", level="debug")

    # Validate encryption key
    if not validate_encryption_key():
        return False

    # Validate configuration
    config = validate_password_config()
    if not config:
        return False

    echo(
        f"Password system initialized: cipher={config['cipher']}, storage={config['storage']}",
        level="debug",
    )

    initialize_password_system._initialized = True
    return True


def check_database_schema(args: Any) -> bool:
    """
    Check if postoffice database schema is initialized.

    Args:
        args: bbsengine6 args object with database connection

    Returns:
        True if schema exists, False otherwise
    """
    try:
        from bbsengine6 import database

        with database.connect(args) as conn:
            with conn.cursor() as cur:
                # Check if postoffice schema exists
                cur.execute(
                    """
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name = 'postoffice'
                """
                )
                result = cur.fetchone()
                if result:
                    return True
                else:
                    echo(
                        "WARNING: postoffice schema not found in database",
                        level="error",
                    )
                    return False
    except Exception as e:
        echo(f"WARNING: Could not check database schema: {e}", level="error")
        return False


def startup(args: Optional[Any] = None) -> bool:
    """
    Run full startup sequence for mistermcfeely.

    Initializes:
    1. Password system configuration
    2. Encryption key validation
    3. Database schema check (if args provided)

    Args:
        args: Optional bbsengine6 args object for database checks

    Returns:
        True if startup successful, False otherwise
    """
    echo("Starting mistermcfeely...", level="debug")

    # Initialize password system
    if not initialize_password_system():
        return False

    # Check database schema if args provided
    if args:
        if not check_database_schema(args):
            echo(
                "WARNING: Database schema check failed (non-fatal)",
                level="error",
            )

    echo("mistermcfeely startup complete", level="debug")
    return True


__all__ = [
    "validate_encryption_key",
    "validate_password_config",
    "initialize_password_system",
    "check_database_schema",
    "startup",
]
