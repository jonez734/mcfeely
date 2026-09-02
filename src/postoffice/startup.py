# startup.py
# Startup initialization for mistermcfeely password management system
# Sets up encryption keys and validates configuration
# Can be run directly from bash: python -m postoffice.startup

import os
import sys
import base64
from typing import Optional, Dict, Any

from bbsengine6.io import echo

import binascii


def get_encryption_key() -> Optional[bytes]:
    """
    Get encryption key from various sources in priority order.

    Priority:
    1. POSTOFFICE_PASSWORD_KEY environment variable
    2. /etc/postoffice/password.key file
    3. ~/.postoffice/password.key file
    4. None (error)

    Returns:
        32-byte key, or None if not found
    """
    # Try environment variable first (fastest, development)
    key_b64 = os.environ.get("POSTOFFICE_PASSWORD_KEY")
    if key_b64:
        try:
            key_bytes = base64.b64decode(key_b64)
            if len(key_bytes) == 32:
                return key_bytes
            else:
                echo(
                    f"ERROR: POSTOFFICE_PASSWORD_KEY must be 32 bytes (got {len(key_bytes)})",
                    level="error",
                )
                return None
        except Exception as e:
            echo(
                f"ERROR: POSTOFFICE_PASSWORD_KEY is not valid base64: {e}",
                level="error",
            )
            return None

    # Try system-wide key file (production)
    system_key_file = "/etc/postoffice/password.key"
    if os.path.exists(system_key_file):
        try:
            # Check file permissions (should be 0600 or 0400)
            stat_info = os.stat(system_key_file)
            mode = stat_info.st_mode
            if mode & 0o077:  # Group or other can read
                echo(
                    f"ERROR: {system_key_file} has insecure permissions (should be 0600)",
                    level="error",
                )
                echo(
                    f"  Fix with: sudo chmod 600 {system_key_file}",
                    level="error",
                )
                return None

            with open(system_key_file, "r") as f:
                key_b64 = f.read().strip()

            if not key_b64:
                echo(f"ERROR: {system_key_file} is empty", level="error")
                return None

            key_bytes = base64.b64decode(key_b64)
            if len(key_bytes) != 32:
                echo(
                    f"ERROR: {system_key_file} must contain 32 bytes (got {len(key_bytes)})",
                    level="error",
                )
                return None

            if getattr(get_encryption_key, "_verbose", False):
                echo(f"Loaded encryption key from {system_key_file}", level="debug")
            return key_bytes
        except binascii.Error as e:
            echo(f"ERROR: {system_key_file} is not valid base64: {e}", level="error")
            return None
        except Exception as e:
            echo(f"ERROR: Failed to read {system_key_file}: {e}", level="error")
            return None

    # Try user key file (personal development)
    user_key_file = os.path.expanduser("~/.postoffice/password.key")
    if os.path.exists(user_key_file):
        try:
            # Check file permissions (should be 0600 or 0400)
            stat_info = os.stat(user_key_file)
            mode = stat_info.st_mode
            if mode & 0o077:  # Group or other can read
                echo(
                    f"ERROR: {user_key_file} has insecure permissions (should be 0600)",
                    level="error",
                )
                echo(
                    f"  Fix with: chmod 600 {user_key_file}",
                    level="error",
                )
                return None

            with open(user_key_file, "r") as f:
                key_b64 = f.read().strip()

            if not key_b64:
                echo(f"ERROR: {user_key_file} is empty", level="error")
                return None

            key_bytes = base64.b64decode(key_b64)
            if len(key_bytes) != 32:
                echo(
                    f"ERROR: {user_key_file} must contain 32 bytes (got {len(key_bytes)})",
                    level="error",
                )
                return None

            if getattr(get_encryption_key, "_verbose", False):
                echo(f"Loaded encryption key from {user_key_file}", level="debug")
            return key_bytes
        except binascii.Error as e:
            echo(f"ERROR: {user_key_file} is not valid base64: {e}", level="error")
            return None
        except Exception as e:
            echo(f"ERROR: Failed to read {user_key_file}: {e}", level="error")
            return None

    # Not found anywhere
    return None


def show_key_setup_help():
    """Show help for setting up encryption key."""
    echo("\nTo set up encryption key, choose one method:", level="error")
    echo("\n1. Environment Variable (Development/Testing):", level="error")
    echo(
        "   export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)",
        level="error",
    )

    echo("\n2. System-wide File (Single Server):", level="error")
    echo(
        "   KEY=$(openssl rand -base64 32)",
        level="error",
    )
    echo(
        '   echo "$KEY" | sudo tee /etc/postoffice/password.key',
        level="error",
    )
    echo(
        "   sudo chmod 600 /etc/postoffice/password.key",
        level="error",
    )
    echo(
        "   sudo chown postoffice:postoffice /etc/postoffice/password.key",
        level="error",
    )

    echo("\n3. User File (Personal Development):", level="error")
    echo(
        "   mkdir -p ~/.postoffice",
        level="error",
    )
    echo(
        "   openssl rand -base64 32 > ~/.postoffice/password.key",
        level="error",
    )
    echo(
        "   chmod 600 ~/.postoffice/password.key",
        level="error",
    )

    echo("\nAfter setup, verify with:", level="error")
    echo("   python -m postoffice.startup --check", level="error")
    echo()


def validate_encryption_key(verbose: bool = False) -> bool:
    """
    Validate that encryption key is available and valid.

    Args:
        verbose: If True, show debug messages

    Returns:
        True if valid, False otherwise
    """
    assert callable(get_encryption_key)
    get_encryption_key.__dict__["_verbose"] = verbose  # type: ignore[attr-defined]

    key = get_encryption_key()

    if key is None:
        echo("ERROR: POSTOFFICE_PASSWORD_KEY not found", level="error")
        show_key_setup_help()
        return False

    if verbose:
        echo(f"✓ Encryption key valid ({len(key)} bytes)", level="debug")
    return True


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


def initialize_password_system(verbose: bool = False) -> bool:
    """
    Initialize the password management system.

    Checks encryption key, validates configuration, and logs startup info.

    Args:
        verbose: If True, show debug messages

    Returns:
        True if initialization successful, False otherwise
    """
    if getattr(initialize_password_system, "_initialized", False):
        return True

    if verbose:
        echo("Initializing password management system...", level="debug")

    # Validate encryption key
    if not validate_encryption_key(verbose=verbose):
        return False

    # Validate configuration
    config = validate_password_config()
    if not config:
        return False

    if verbose:
        echo(
            f"✓ Password system initialized: cipher={config['cipher']}, storage={config['storage']}",
            level="debug",
        )

    assert callable(initialize_password_system)
    initialize_password_system.__dict__["_initialized"] = True  # type: ignore[attr-defined]
    return True


def check_database_schema(args: Any, verbose: bool = False) -> bool:
    """
    Check if postoffice database schema is initialized.

    Args:
        args: bbsengine6 args object with database connection
        verbose: If True, show debug messages

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
                    if verbose:
                        echo("✓ postoffice schema exists", level="debug")
                    return True
                else:
                    if verbose:
                        echo(
                            "WARNING: postoffice schema not found in database",
                            level="error",
                        )
                    return False
    except Exception as e:
        if verbose:
            echo(f"WARNING: Could not check database schema: {e}", level="error")
        return False


def startup(args: Optional[Any] = None, verbose: bool = False) -> bool:
    """
    Run full startup sequence for mistermcfeely.

    Initializes:
    1. Password system configuration
    2. Encryption key validation
    3. Database schema check (if args provided)

    Args:
        args: Optional bbsengine6 args object for database checks
        verbose: If True, show debug messages

    Returns:
        True if startup successful, False otherwise
    """
    if verbose:
        echo("Starting mistermcfeely password system...", level="debug")

    # Initialize password system
    if not initialize_password_system(verbose=verbose):
        return False

    # Check database schema if args provided
    if args:
        if not check_database_schema(args, verbose=verbose):
            if verbose:
                echo(
                    "WARNING: Database schema check failed (non-fatal)",
                    level="error",
                )

    if verbose:
        echo("✓ mistermcfeely startup complete", level="debug")
    return True


def check_key_setup(verbose: bool = True) -> bool:
    """
    Check if encryption key is properly set up.

    Args:
        verbose: If True, show detailed output

    Returns:
        True if key is set up, False otherwise
    """
    echo("Checking encryption key setup...", level="debug")
    echo()

    # Check environment variable
    env_key = os.environ.get("POSTOFFICE_PASSWORD_KEY")
    if env_key:
        echo("✓ POSTOFFICE_PASSWORD_KEY environment variable is set", level="debug")
    else:
        echo("✗ POSTOFFICE_PASSWORD_KEY environment variable not set", level="error")

    # Check system file
    system_key_file = "/etc/postoffice/password.key"
    if os.path.exists(system_key_file):
        stat_info = os.stat(system_key_file)
        mode_octal = oct(stat_info.st_mode & 0o777)
        if stat_info.st_mode & 0o077:
            echo(
                f"✗ {system_key_file} exists but has insecure permissions: {mode_octal}",
                level="error",
            )
        else:
            echo(
                f"✓ {system_key_file} exists with secure permissions: {mode_octal}",
                level="debug",
            )
    else:
        echo(f"✗ {system_key_file} does not exist", level="error")

    # Check user file
    user_key_file = os.path.expanduser("~/.postoffice/password.key")
    if os.path.exists(user_key_file):
        stat_info = os.stat(user_key_file)
        mode_octal = oct(stat_info.st_mode & 0o777)
        if stat_info.st_mode & 0o077:
            echo(
                f"✗ {user_key_file} exists but has insecure permissions: {mode_octal}",
                level="error",
            )
        else:
            echo(
                f"✓ {user_key_file} exists with secure permissions: {mode_octal}",
                level="debug",
            )
    else:
        echo(f"✗ {user_key_file} does not exist", level="error")

    echo()

    # Check if key can be loaded
    key = get_encryption_key()
    if key:
        echo("✓ Encryption key successfully loaded", level="debug")
        return True
    else:
        echo("✗ Could not load encryption key from any source", level="error")
        show_key_setup_help()
        return False


def main():
    """Main entry point for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="mistermcfeely password system startup and configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m postoffice.startup --check         Check if key is set up
  python -m postoffice.startup --generate      Generate a new key
  python -m postoffice.startup --install       Install to /etc/postoffice/
  python -m postoffice.startup --init          Full initialization
""",
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if encryption key is properly set up",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate a new encryption key",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install encryption key to /etc/postoffice/password.key",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Full password system initialization",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output",
    )

    args = parser.parse_args()

    # Default action if no flags
    if not (args.check or args.generate or args.install or args.init):
        args.check = True

    # Check setup
    if args.check:
        success = check_key_setup(verbose=args.verbose)
        sys.exit(0 if success else 1)

    # Generate new key
    if args.generate:
        echo("Generating new encryption key...", level="debug")
        key = os.urandom(32)
        key_b64 = base64.b64encode(key).decode()
        echo()
        echo("New encryption key (base64 encoded):", level="debug")
        echo(key_b64)
        echo()
        echo("To use this key, run one of:", level="debug")
        echo()
        echo("Option 1 - Environment variable (development):", level="debug")
        echo(f'export POSTOFFICE_PASSWORD_KEY="{key_b64}"', level="debug")
        echo()
        echo("Option 2 - System file (production):", level="debug")
        echo(
            f'echo "{key_b64}" | sudo tee /etc/postoffice/password.key',
            level="debug",
        )
        echo("sudo chmod 600 /etc/postoffice/password.key", level="debug")
        echo()
        sys.exit(0)

    # Install to system
    if args.install:
        try:
            import subprocess

            key = os.urandom(32)
            key_b64 = base64.b64encode(key).decode()

            echo(
                "Installing encryption key to /etc/postoffice/password.key...",
                level="debug",
            )

            # Create directory
            subprocess.run(
                ["sudo", "mkdir", "-p", "/etc/postoffice"],
                check=True,
                capture_output=True,
            )

            # Write key
            subprocess.run(
                ["sudo", "tee", "/etc/postoffice/password.key"],
                input=key_b64.encode(),
                capture_output=True,
                check=True,
            )

            # Set permissions
            subprocess.run(
                ["sudo", "chmod", "600", "/etc/postoffice/password.key"],
                check=True,
                capture_output=True,
            )

            # Set ownership (optional, requires postoffice user)
            try:
                subprocess.run(
                    [
                        "sudo",
                        "chown",
                        "postoffice:postoffice",
                        "/etc/postoffice/password.key",
                    ],
                    check=True,
                    capture_output=True,
                )
            except Exception:
                echo(
                    "Note: Could not set ownership to postoffice:postoffice",
                    level="error",
                )

            echo(
                "✓ Encryption key installed to /etc/postoffice/password.key",
                level="debug",
            )
            echo("  Permissions set to 0600", level="debug")
            echo()
            echo("Verify installation with:", level="debug")
            echo("  python -m postoffice.startup --check", level="debug")
            sys.exit(0)
        except Exception as e:
            echo(f"✗ Failed to install key: {e}", level="error")
            sys.exit(1)

    # Full initialization
    if args.init:
        if startup(verbose=args.verbose):
            echo("✓ Password system initialization successful", level="debug")
            sys.exit(0)
        else:
            echo("✗ Password system initialization failed", level="error")
            sys.exit(1)


if __name__ == "__main__":
    main()


def init(args, **kwargs) -> bool:
    return True


def access(args, op, **kwargs) -> bool:
    return True


def buildargs(args, **kwargs):
    return None


def startup_main(args, **kwargs) -> bool:
    from bbsengine6 import database, io

    def _work(conn):
        io.echo("running postoffice startup...")

        # --- schema ---
        io.echo("{{var:labelcolor}}schema {{var:valuecolor}}postoffice{{var:labelcolor}}: ", end="")
        if database.schemaexists(args, "postoffice", conn=conn) is False:
            if database.createschema(args, "postoffice", conn=conn) is False:
                io.echo("fail", level="error")
                return False
        io.echo(" ok ", level="ok")

        # --- schema privs ---
        for role in ("web", "term", "sysop"):
            database.manage_schema_priv(args, "grant", "usage", "postoffice", role, conn=conn)
        database.manage_schema_priv(args, "grant", "create", "postoffice", "sysop", conn=conn)

        # --- classes in dependency order ---
        classes = (
            ("postoffice.mailbox", "mailbox.sql"),
            ("postoffice.shared_mailbox", "shared_mailbox.sql"),
            ("postoffice.virtual", "virtual.sql"),
            ("postoffice.__message", "message.sql"),
            ("postoffice.member_mailbox_password", "member_mailbox_password.sql"),
            ("postoffice.message_routing", "message_routing.sql"),
            ("postoffice.message_config", "message_config.sql"),
        )

        failcount = 0
        for cls, sql in classes:
            io.echo(
                f"{{var:labelcolor}}class {{var:valuecolor}}{cls}{{var:labelcolor}}: ",
                end="",
            )
            if database.classexists(args, cls, conn=conn) is False:
                io.echo("import ", end="")
                if database.importsql(args, sql, conn=conn, package="postoffice") is False:
                    io.echo("fail", level="error")
                    failcount += 1
                else:
                    io.echo(" ok ", level="ok")
            else:
                io.echo("ok", level="ok")

        if failcount > 0:
            io.echo("postoffice startup failed", level="error")
            conn.rollback()
            return False

        io.echo("postoffice startup complete", level="ok")
        conn.commit()
        return True

    conn = kwargs.get("conn", None)
    if conn is None:
        pool = kwargs.get("pool", None)
        if pool is None:
            io.echo("postoffice.startup.startup_main: pool is None", level="error")
            return False
        with database.connect(args, pool=pool) as conn:
            return _work(conn)
    return _work(conn)


__all__ = [
    "get_encryption_key",
    "validate_encryption_key",
    "validate_password_config",
    "initialize_password_system",
    "check_database_schema",
    "startup",
    "check_key_setup",
    "init",
    "access",
    "buildargs",
    "startup_main",
]
