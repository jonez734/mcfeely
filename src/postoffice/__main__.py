# __main__.py
# postoffice package entry point for command-line usage
# Follows bbsengine6.module patterns with init/access/help/version handlers
# Can be run with: python -m postoffice [command] [options]

import sys
import argparse
import configparser
from pathlib import Path
from typing import Any

from bbsengine6.io import echo
from bbsengine6.io.inputchoice import inputchoice
from bbsengine6.io import inputstring
from . import startup
from .imap_checker import IMAPChecker
from .tui.message_interface import MessageInterface
from .tui.cyrus_admin import CyrusAdmin


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
  menu                           Interactive menu (default)
  tui                            Message interface
  accounts                       Account management (admin only)
  imap-check                     Check IMAP server connectivity
  startup-check                  Check encryption key setup
  startup-generate               Generate new encryption key
  startup-install                Install key to /etc/postoffice/
  startup-init                   Initialize password system

Options:
  --verbose, -v                  Show verbose output
  --help                         Show this help

Examples:
  python -m postoffice                          (runs menu)
  python -m postoffice imap-check
  python -m postoffice imap-check --verbose
  python -m postoffice tui
  python -m postoffice accounts
  python -m postoffice startup-check --verbose
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


def _load_imap_config() -> tuple:
    """
    Load IMAP configuration from config files.

    Priority:
    1. /etc/postoffice/imapd.conf (system-wide config)
    2. ~/.postoffice (user development config)

    Returns:
        Tuple of (host, port) with defaults if config not found
    """
    imap_host = "localhost"
    imap_port = 993

    # Try system-wide config first (production)
    system_config_path = Path("/etc/postoffice/imapd.conf")
    if system_config_path.exists():
        try:
            config = configparser.ConfigParser()
            config.read(system_config_path)
            if config.has_section("imap"):
                imap_host = config.get("imap", "host", fallback="localhost")
                imap_port = config.getint("imap", "port", fallback=993)
            return imap_host, imap_port
        except Exception as e:
            echo(f"Warning: Could not read system config file: {e}", level="error")

    # Fall back to user config for development
    user_config_path = Path.home() / ".postoffice"
    if user_config_path.exists():
        try:
            config = configparser.ConfigParser()
            config.read(user_config_path)
            if config.has_section("imap"):
                imap_host = config.get("imap", "host", fallback="localhost")
                imap_port = config.getint("imap", "port", fallback=993)
        except Exception as e:
            echo(f"Warning: Could not read user config file: {e}", level="error")

    return imap_host, imap_port


def handle_imap_check(args: argparse.Namespace) -> int:
    """Handle imap-check command to verify IMAP server connectivity."""
    # Load config
    imap_host, imap_port = _load_imap_config()

    # Allow command-line overrides
    if hasattr(args, "imaphost") and args.imaphost:
        imap_host = args.imaphost
    if hasattr(args, "imapport") and args.imapport:
        imap_port = args.imapport

    echo(f"Checking IMAP server at {imap_host}:{imap_port}...", level="info")
    echo("")

    # Create checker and run all checks
    try:
        checker = IMAPChecker(imap_host, imap_port, timeout=5, verbose=args.verbose)
        all_pass, results = checker.check_all()
        checker.print_results(all_pass, results)
        return 0 if all_pass else 1
    except ValueError as e:
        echo(f"Invalid IMAP configuration: {e}", level="error")
        return 1
    except Exception as e:
        echo(f"Error checking IMAP connectivity: {e}", level="error")
        return 1


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


def handle_menu(args: argparse.Namespace) -> int:
    """Handle main menu - let user choose what to do."""
    # Check if encryption key is available
    key = startup.get_encryption_key()
    if key is None:
        echo("Error: Encryption key not available", level="error")
        echo(
            "Please run 'python -m postoffice startup-check' to diagnose", level="error"
        )
        return 1

    is_sysop = getattr(args, "issuperuser", False)

    while True:
        echo("")
        echo("=== postoffice ===", level="info")
        echo("")

        if is_sysop:
            choice = inputchoice(
                "Choose action: ",
                "tmaqx",
                default="m",
                help="(t)ui messages, (m)anage accounts, (a)dmin menu, (q)uit, e(x)it",
            )
        else:
            choice = inputchoice(
                "Choose action: ",
                "tmqx",
                default="m",
                help="(t)ui messages, (m)anage accounts, (q)uit, e(x)it",
            )

        if choice in ("Q", "X"):
            echo("Goodbye!")
            return 0
        elif choice == "T":
            try:
                tui = MessageInterface(args)
                result = tui.run()
                if result != 0:
                    return result
            except KeyboardInterrupt:
                echo("", level="info")
                echo("Interrupted by user", level="info")
            except Exception as e:
                echo(f"Error running message interface: {e}", level="error")
        elif choice == "M":
            if is_sysop:
                try:
                    admin = CyrusAdmin(args)
                    result = admin.run()
                    if result != 0:
                        return result
                except KeyboardInterrupt:
                    echo("", level="info")
                    echo("Interrupted by user", level="info")
                except Exception as e:
                    echo(f"Error running account management: {e}", level="error")
            else:
                echo(
                    "Error: Only administrators can access account management",
                    level="error",
                )
        elif choice == "A" and is_sysop:
            echo("Admin features not yet implemented", level="error")


def handle_tui(args: argparse.Namespace) -> int:
    """Handle TUI command for interactive message interface."""
    # Check if encryption key is available
    key = startup.get_encryption_key()
    if key is None:
        echo("Error: Encryption key not available", level="error")
        echo(
            "Please run 'python -m postoffice startup-check' to diagnose", level="error"
        )
        return 1

    # Run message interface TUI
    try:
        tui = MessageInterface(args)
        return tui.run()
    except KeyboardInterrupt:
        echo("", level="info")
        echo("Interrupted by user", level="info")
        return 0
    except Exception as e:
        echo(f"Error running TUI: {e}", level="error")
        return 1


def handle_accounts(args: argparse.Namespace) -> int:
    """Handle accounts command for account management."""
    # Check if encryption key is available
    key = startup.get_encryption_key()
    if key is None:
        echo("Error: Encryption key not available", level="error")
        echo(
            "Please run 'python -m postoffice startup-check' to diagnose", level="error"
        )
        return 1

    # Check if user is sysop
    is_sysop = getattr(args, "issuperuser", False)
    if not is_sysop:
        echo("Error: Only administrators can access account management", level="error")
        return 1

    # Run account management TUI
    try:
        admin = CyrusAdmin(args)
        return admin.run()
    except KeyboardInterrupt:
        echo("", level="info")
        echo("Interrupted by user", level="info")
        return 0
    except Exception as e:
        echo(f"Error running account management: {e}", level="error")
        return 1


# ============================================================================
# Main Entry Point
# ============================================================================


def handle_install_postoffice(args: argparse.Namespace) -> int:
    """
    Install postoffice configuration files to /etc/postoffice/.

    Prompts for installation directory, creates it, copies config files,
    sets proper permissions, and installs encryption key.

    Returns:
        0 on success, 1 on failure
    """
    try:
        echo("")
        echo("╔════════════════════════════════════════════════════════════════╗")
        echo("║         postoffice Configuration Installation                  ║")
        echo("╚════════════════════════════════════════════════════════════════╝")
        echo("")

        # Prompt for installation directory
        echo("Enter the directory where config files should be installed:")
        echo("(default: /etc/postoffice)", level="debug")
        install_dir = inputstring("Config directory: ", oldvalue="/etc/postoffice")

        if not install_dir:
            install_dir = "/etc/postoffice"

        # Normalize path
        install_dir = install_dir.strip()
        if not install_dir.startswith("/"):
            echo(
                f"Error: Installation directory must be absolute (got: {install_dir})",
                level="error",
            )
            return 1

        echo(f"Installing to: {install_dir}", level="debug")
        echo("")

        # Step 1: Create directory
        echo("Step 1/5: Creating directory structure...")
        try:
            import subprocess

            result = subprocess.run(
                ["sudo", "mkdir", "-p", install_dir],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                echo(f"  ✗ Failed to create directory: {result.stderr}", level="error")
                return 1

            echo(f"  ✓ Created {install_dir}", level="debug")
        except Exception as e:
            echo(f"  ✗ Error creating directory: {e}", level="error")
            return 1

        # Step 2: Set directory permissions
        echo("Step 2/5: Setting directory permissions...")
        try:
            result = subprocess.run(
                ["sudo", "chmod", "755", install_dir],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                echo(
                    f"  ✗ Failed to set directory permissions: {result.stderr}",
                    level="error",
                )
                return 1

            echo("  ✓ Set directory permissions to 755", level="debug")
        except Exception as e:
            echo(f"  ✗ Error setting directory permissions: {e}", level="error")
            return 1

        # Step 3: Copy config files
        echo("Step 3/5: Copying configuration files...")
        config_files = ["cyrus.conf", "imapd.conf", "imapd.annotations"]
        script_dir = Path(__file__).parent.parent.parent / "config"

        for config_file in config_files:
            src_file = script_dir / config_file
            dest_file = f"{install_dir}/{config_file}"

            if not src_file.exists():
                echo(f"  ✗ Source file not found: {src_file}", level="error")
                return 1

            try:
                result = subprocess.run(
                    ["sudo", "cp", str(src_file), dest_file],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode != 0:
                    echo(
                        f"  ✗ Failed to copy {config_file}: {result.stderr}",
                        level="error",
                    )
                    return 1

                echo(f"  ✓ Copied {config_file}", level="debug")
            except Exception as e:
                echo(f"  ✗ Error copying {config_file}: {e}", level="error")
                return 1

        # Step 4: Set file permissions
        echo("Step 4/5: Setting file permissions...")
        try:
            result = subprocess.run(
                [
                    "sudo",
                    "chmod",
                    "644",
                    f"{install_dir}/cyrus.conf",
                    f"{install_dir}/imapd.conf",
                    f"{install_dir}/imapd.annotations",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                echo(
                    f"  ✗ Failed to set file permissions: {result.stderr}",
                    level="error",
                )
                return 1

            echo("  ✓ Set config file permissions to 644", level="debug")
        except Exception as e:
            echo(f"  ✗ Error setting file permissions: {e}", level="error")
            return 1

        # Step 5: Install encryption key
        echo("Step 5/5: Installing encryption key...")
        try:
            # Call startup-install to handle encryption key
            result = subprocess.run(
                [sys.executable, "-m", "postoffice.startup", "--install"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                echo(
                    f"  ✗ Failed to install encryption key: {result.stderr}",
                    level="error",
                )
                echo(
                    "  Note: Config files were installed, but encryption key setup failed.",
                    level="warning",
                )
                # Don't fail here - config files are installed
            else:
                echo("  ✓ Encryption key installed", level="debug")
        except subprocess.TimeoutExpired:
            echo("  ✗ Encryption key installation timed out", level="error")
            echo(
                "  Note: Config files were installed, but encryption key setup failed.",
                level="warning",
            )
        except Exception as e:
            echo(f"  ✗ Error installing encryption key: {e}", level="error")
            echo(
                "  Note: Config files were installed, but encryption key setup failed.",
                level="warning",
            )

        # Summary
        echo("")
        echo("╔════════════════════════════════════════════════════════════════╗")
        echo("║                    Installation Complete                       ║")
        echo("╚════════════════════════════════════════════════════════════════╝")
        echo("")
        echo("✓ Configuration files installed to:", level="info")
        echo(f"  • {install_dir}/cyrus.conf", level="info")
        echo(f"  • {install_dir}/imapd.conf", level="info")
        echo(f"  • {install_dir}/imapd.annotations", level="info")
        echo(
            f"  • {install_dir}/password.key (if encryption key installed)",
            level="info",
        )
        echo("")
        echo("Next steps:", level="info")
        echo("  1. Review and customize the config files as needed", level="info")
        echo(
            "  2. Restart the IMAP daemon: sudo systemctl restart cyrus-imapd",
            level="info",
        )
        echo(
            "  3. Test connectivity: python -m postoffice imap-check --verbose",
            level="info",
        )
        echo("")

        return 0

    except KeyboardInterrupt:
        echo("", level="info")
        echo("Installation cancelled by user", level="info")
        return 1
    except Exception as e:
        echo(f"Error during installation: {e}", level="error")
        return 1


def main():
    """Main entry point for postoffice module."""
    parser = argparse.ArgumentParser(
        prog="python -m postoffice",
        description="mistermcfeely password management system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  menu                               Interactive menu (default)
  tui                                Message interface
  accounts                           Account management (admin only)
  imap-check                         Check IMAP server connectivity
  install-postoffice                 Install config files to /etc/postoffice/
  startup-check                      Check encryption key setup
  startup-generate                   Generate new encryption key
  startup-install                    Install key to /etc/postoffice/
  startup-init                       Initialize password system

Options:
  --verbose, -v                      Show verbose output
  --help, -h                         Show this help
  --version                          Show version
  --imaphost HOST                    IMAP host (for imap-check)
  --imapport PORT                    IMAP port (for imap-check)

Examples:
  python -m postoffice                          (runs menu)
  python -m postoffice imap-check
  python -m postoffice imap-check -v
  python -m postoffice imap-check --imaphost mail.example.com
  python -m postoffice tui
  python -m postoffice accounts
  python -m postoffice startup-check --verbose
""",
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="menu",
        help="Command to run (default: menu)",
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
    parser.add_argument(
        "--imaphost",
        type=str,
        help="IMAP host override (for imap-check)",
    )
    parser.add_argument(
        "--imapport",
        type=int,
        help="IMAP port override (for imap-check)",
    )

    args = parser.parse_args()

    # Handle version
    if args.version:
        echo(version_postoffice(args))
        return 0

    # Route commands
    command_map = {
        "menu": handle_menu,
        "tui": handle_tui,
        "accounts": handle_accounts,
        "imap-check": handle_imap_check,
        "install-postoffice": handle_install_postoffice,
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
