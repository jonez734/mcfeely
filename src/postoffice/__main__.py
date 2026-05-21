# __main__.py
# postoffice package entry point for command-line usage
# Follows bbsengine6.module patterns with init/access/help/version handlers
# Can be run with: python -m postoffice [command] [options]

import sys
import argparse
from typing import Any

from bbsengine6.io import echo
from . import startup


# ============================================================================
# Module API Functions (bbsengine6 pattern)
# ============================================================================


def init_postoffice(args: Any) -> bool:
    """
    Initialize postoffice module.

    Args:
        args: bbsengine6 args object

    Returns:
        True if initialization successful
    """
    verbose = getattr(args, "verbose", False)
    if verbose:
        echo("Initializing postoffice module...", level="debug")

    # Initialize password system
    if not startup.initialize_password_system(verbose=verbose):
        echo("Failed to initialize postoffice module", level="error")
        return False

    if verbose:
        echo("✓ postoffice module initialized", level="debug")
    return True


def access_postoffice(args: Any) -> bool:
    """
    Check if postoffice module is accessible.

    Args:
        args: bbsengine6 args object

    Returns:
        True if module is ready
    """
    # Try to access encryption key
    key = startup.get_encryption_key()
    if key is None:
        echo("postoffice: encryption key not available", level="error")
        return False
    return True


def help_postoffice(args: Any) -> str:
    """
    Get help text for postoffice module.

    Args:
        args: bbsengine6 args object (unused)

    Returns:
        Help text
    """
    return """
postoffice - mistermcfeely password management system

Commands:
  startup-check                  Check encryption key setup
  startup-generate               Generate new encryption key
  startup-install                Install key to /etc/postoffice/
  startup-init                   Initialize password system

Options:
  --verbose, -v                  Show verbose output
  --help                         Show this help

Examples:
  python -m postoffice startup-check --verbose
  python -m postoffice startup-generate
  python -m postoffice startup-install
  python -m postoffice startup-init
"""


def version_postoffice(args: Any) -> str:
    """
    Get version information.

    Args:
        args: bbsengine6 args object (unused)

    Returns:
        Version string
    """
    return "postoffice 1.0.0 - mistermcfeely password management"


# ============================================================================
# Command Handlers
# ============================================================================


def handle_startup_check(args: argparse.Namespace) -> int:
    """Handle startup-check command."""
    success = startup.check_key_setup(verbose=args.verbose)
    return 0 if success else 1


def handle_startup_generate(args: argparse.Namespace) -> int:
    """Handle startup-generate command."""
    import os
    import base64

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
    echo(f'echo "{key_b64}" | sudo tee /etc/postoffice/password.key', level="debug")
    echo("sudo chmod 600 /etc/postoffice/password.key", level="debug")
    echo()
    return 0


def handle_startup_install(args: argparse.Namespace) -> int:
    """Handle startup-install command."""
    try:
        import subprocess
        import os
        import base64

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

        # Set ownership (optional)
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
                "Note: Could not set ownership to postoffice:postoffice", level="error"
            )

        echo(
            "✓ Encryption key installed to /etc/postoffice/password.key", level="debug"
        )
        echo("  Permissions set to 0600", level="debug")
        echo()
        echo("Verify installation with:", level="debug")
        echo("  python -m postoffice startup-check", level="debug")
        return 0
    except Exception as e:
        echo(f"✗ Failed to install key: {e}", level="error")
        return 1


def handle_startup_init(args: argparse.Namespace) -> int:
    """Handle startup-init command."""
    if startup.startup(verbose=args.verbose):
        echo("✓ Password system initialization successful", level="debug")
        return 0
    else:
        echo("✗ Password system initialization failed", level="error")
        return 1


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Main entry point for postoffice module."""
    parser = argparse.ArgumentParser(
        prog="python -m postoffice",
        description="mistermcfeely password management system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  startup-check                     Check encryption key setup
  startup-generate                  Generate new encryption key
  startup-install                   Install key to /etc/postoffice/
  startup-init                      Initialize password system

Options:
  --verbose, -v                     Show verbose output
  --help, -h                        Show this help
  --version                         Show version

Examples:
  python -m postoffice startup-check --verbose
  python -m postoffice startup-generate
  python -m postoffice startup-install
  python -m postoffice startup-init -v
""",
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="startup-check",
        help="Command to run (default: startup-check)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version",
    )

    args = parser.parse_args()

    # Handle version
    if args.version:
        echo(version_postoffice(args))
        return 0

    # Route commands
    command_map = {
        "startup-check": handle_startup_check,
        "startup-generate": handle_startup_generate,
        "startup-install": handle_startup_install,
        "startup-init": handle_startup_init,
    }

    handler = command_map.get(args.command)
    if not handler:
        echo(f"Unknown command: {args.command}", level="error")
        echo()
        echo(help_postoffice(args))
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
