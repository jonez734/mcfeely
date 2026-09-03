# __main__.py
# postoffice package entry point for command-line usage
# Follows bbsengine6.module patterns with init/access/help/version handlers
# Can be run with: python -m postoffice [command] [options]

import sys
import argparse
import configparser
import subprocess
import termios
from pathlib import Path
from typing import Any

from bbsengine6.io import echo
from bbsengine6.io.echo import echo_traceback
from bbsengine6.io.inputchoice import inputchoice
from bbsengine6.io.inputboolean import inputboolean
from bbsengine6.io import inputstring
from bbsengine6 import database, member, util
from . import startup
from .imap_checker import IMAPChecker
from .tui.message_interface import run as _message_interface_run
from .tui.cyrus_admin import run as _cyrus_admin_run
from .tui.projects import run as projects_run
from .tui.address_manager import run as address_manager_run
from bbsengine6 import message as _message_module


def _notify_run(args, current_user):
    """Read pending notifications for ``current_user`` via the unified
    message system.

    Replacement for the deleted ``bbsengine6.notify.tui.run``. The old
    notify TUI showed the user's queued notifications; this stub does
    the same against ``bbsengine6.message.get_queue``, with no
    interactive navigation (the bottombar / F2 viewer in getch.py is the
    canonical interactive viewer). Used by the postoffice main menu's
    "(n)otifications" choice and the ``notify`` CLI subcommand.
    """
    from bbsengine6.io.echo import echo, echo_traceback
    from bbsengine6.io.inputstring import inputstring

    if not _message_module.is_enabled():
        echo("Messages unavailable.", level="warn")
        return 0

    try:
        pending = _message_module.get_queue(current_user)
    except Exception as e:
        echo_traceback("postoffice.__main__._notify_run.get_queue:")
        echo(f"Error loading notifications: {e}", level="error")
        return 1

    if not pending:
        echo("No pending messages.")
        return 0

    for n in pending:
        urgency = n.get("urgency", "ROUTINE")
        sender = n.get("sender_moniker", "system") or "system"
        datestamp = n.get("datestamp")
        when = datestamp.strftime("%Y-%m-%d %H:%M:%S") if datestamp else ""
        content = n.get("content", "")
        msg_id = n.get("id")
        echo(f"[{urgency:8}] {when}  from {sender}: {content}")
        if msg_id is not None:
            try:
                _message_module.mark_read(msg_id, current_user)
            except Exception as e:
                echo_traceback("postoffice.__main__._notify_run.mark_read:")
                echo(f"Failed to mark {msg_id} read: {e}", level="error")

    echo("")
    echo("Press RETURN to continue...")
    try:
        inputstring("")
    except (EOFError, KeyboardInterrupt):
        pass
    return 0


# ============================================================================
# Module API Functions (bbsengine6 pattern)
# ============================================================================


def init(args: Any, **kwargs) -> bool | None:
    """
    Initialize postoffice module.

    Args:
        args: bbsengine6 args object
        **kwargs: framework-supplied keyword arguments (ignored).

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


def access(args: Any, op: str, **kwargs) -> bool | None:
    """
    Check if postoffice module is accessible.

    Args:
        args: bbsengine6 args object
        op: Operation name (the bbsengine6 access-check op string;
            required to match the ``_stub_access`` signature, even
            though ``access`` ignores it).
        **kwargs: framework-supplied keyword arguments (ignored).

    Returns:
        True if module is ready
    """
    # Try to access encryption key
    key = startup.get_encryption_key()
    if key is None:
        echo("postoffice: encryption key not available", level="error")
        return False
    return True


def check_sysop_flag(args: Any, moniker: str, pool: Any) -> bool:
    """
    Check if a member has the SYSOP flag set.

    Args:
        args: bbsengine6 args object
        moniker: The member's moniker to check
        pool: Database connection pool

    Returns:
        True if member has SYSOP flag, False otherwise
    """
    try:
        with database.connect(args, pool=pool) as conn:
            with database.cursor(conn) as cur:
                cur.execute(
                    """
                    SELECT value
                    FROM engine.map_member_flag
                    WHERE moniker = %s AND name = 'SYSOP'
                    """,
                    (moniker,),
                )
                row = cur.fetchone()
                if row is not None and len(row) > 0:
                    return bool(row["value"])
    except Exception:
        echo_traceback("Error checking sysop flag")
    return False


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
  sasl-password                  Manage SASL passwords (set/get/delete/disable/enable/list/reset)

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
        except Exception:
            echo_traceback("Error reading system config")
        return imap_host, imap_port

    # Fall back to user config for development
    user_config_path = Path.home() / ".postoffice"
    if user_config_path.exists():
        try:
            config = configparser.ConfigParser()
            config.read(user_config_path)
            if config.has_section("imap"):
                imap_host = config.get("imap", "host", fallback="localhost")
                imap_port = config.getint("imap", "port", fallback=993)
        except Exception:
            echo_traceback("Error reading user config")

    return imap_host, imap_port


def handle_imap_check(args: argparse.Namespace) -> bool:
    """Handle imap-check command to verify IMAP server connectivity."""
    imap_host, imap_port = _load_imap_config()

    if hasattr(args, "imaphost") and args.imaphost:
        imap_host = args.imaphost
    if hasattr(args, "imapport") and args.imapport:
        imap_port = args.imapport

    cafile = getattr(args, "cafile", None)
    capath = getattr(args, "capath", None)
    insecure = getattr(args, "insecure", False)

    echo(f"Checking IMAP server at {imap_host}:{imap_port}...", level="info")
    echo("")

    try:
        checker = IMAPChecker(
            imap_host,
            imap_port,
            timeout=5,
            verbose=args.verbose,
            cafile=cafile,
            capath=capath,
            insecure=insecure,
        )
        all_pass, results = checker.check_all()
        checker.print_results(all_pass, results)
        return all_pass
    except ValueError as e:
        echo_traceback(f"Invalid IMAP configuration: {e}")
        return False
    except Exception:
        echo_traceback("Error checking IMAP connectivity")
        return False


def handle_startup_check(args: argparse.Namespace) -> bool:
    """Handle startup-check command."""
    return startup.check_key_setup(verbose=args.verbose)


def handle_sasl_password(args: argparse.Namespace) -> int:
    """Handle sasl-password command for SASL password management."""
    key = startup.get_encryption_key()
    if key is None:
        echo("Error: Encryption key not available", level="error")
        echo(
            "Please run 'python -m postoffice startup-check' to diagnose", level="error"
        )
        return 1

    pool = None
    is_sysop = getattr(args, "issuperuser", False)
    current_user = getattr(args, "loginid", None)

    if current_user is None:
        try:
            pool = database.getpool(args)
            current_user = member.getcurrentmoniker(args, pool=pool)
        except Exception:
            echo_traceback("Error getting current user")
            return 1

    if current_user is None:
        echo("Error: Could not determine current user", level="error")
        return 1

    args.loginid = current_user
    args.issuperuser = is_sysop

    target_moniker = args.target_moniker
    action = args.sasl_action

    if target_moniker and not is_sysop and target_moniker != current_user:
        echo(
            "Error: Only sysops can manage another member's SASL password",
            level="error",
        )
        echo(f"  Your moniker: {current_user}", level="error")
        echo(f"  Target moniker: {target_moniker}", level="error")
        return 1

    if action != "list" and not target_moniker:
        echo("Error: --target-moniker is required for this action", level="error")
        return 1

    from . import sasl_password

    if action == "set":
        password = args.password
        if not password:
            echo("Error: --password is required for 'set' action", level="error")
            return 1
        try:
            success = sasl_password.set_sasl_password(
                args, target_moniker, password, current_user
            )
            if success:
                echo(f"OK: SASL password set for {target_moniker}")
                return 0
            else:
                echo(f"Failed to set SASL password for {target_moniker}", level="error")
                return 1
        except PermissionError as e:
            echo(f"Permission denied: {e}", level="error")
            return 1

    elif action == "get":
        exists = sasl_password.exists_sasl_password(args, target_moniker)
        if exists:
            echo(f"EXISTS: {target_moniker} has a SASL password entry")
            enabled = sasl_password.get_sasl_password(args, target_moniker) is not None
            echo(f"  enabled: {enabled}")
            return 0
        else:
            echo(f"NONE: {target_moniker} has no SASL password entry")
            return 1

    elif action == "delete":
        try:
            success = sasl_password.delete_sasl_password(args, target_moniker)
            if success:
                echo(f"OK: SASL password deleted for {target_moniker}")
                return 0
            else:
                echo(
                    f"Failed to delete SASL password for {target_moniker}",
                    level="error",
                )
                return 1
        except PermissionError as e:
            echo(f"Permission denied: {e}", level="error")
            return 1

    elif action == "disable":
        success = sasl_password.disable_sasl_password(args, target_moniker)
        if success:
            echo(f"OK: SASL password disabled for {target_moniker}")
            return 0
        else:
            echo(f"Failed to disable SASL password for {target_moniker}", level="error")
            return 1

    elif action == "enable":
        success = sasl_password.enable_sasl_password(args, target_moniker)
        if success:
            echo(f"OK: SASL password enabled for {target_moniker}")
            return 0
        else:
            echo(f"Failed to enable SASL password for {target_moniker}", level="error")
            return 1

    elif action == "list":
        entries = sasl_password.list_sasl_passwords(args)
        if not entries:
            echo("No SASL password entries found")
            return 0
        echo(f"{'moniker':<20} {'enabled':<8} {'updated_by':<20} {'dateupdated'}")
        echo("-" * 80)
        for entry in entries:
            dateupdated = entry.get("dateupdated") or "never"
            echo(
                f"{entry['member_moniker']:<20} {str(entry['enabled']):<8} "
                f"{entry['updated_by']:<20} {dateupdated}"
            )
        echo(f"\n{len(entries)} entries")
        return 0

    elif action == "reset":
        password = args.password
        if not password:
            echo("Error: --password is required for 'reset' action", level="error")
            return 1
        try:
            success, error = sasl_password.set_sasl_password_for_sync(
                args, target_moniker, password, current_user
            )
            if success:
                echo(f"OK: SASL password reset for {target_moniker}")
                return 0
            else:
                echo(f"Failed to reset SASL password: {error}", level="error")
                return 1
        except PermissionError as e:
            echo(f"Permission denied: {e}", level="error")
            return 1

    else:
        echo(f"Unknown action: {action}", level="error")
        return 1


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
            echo_traceback("Error setting ownership")
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

    pool = None
    current_user = getattr(args, "loginid", None)

    if current_user is None:
        try:
            pool = database.getpool(args)
            current_user = member.getcurrentmoniker(args, pool=pool)
        except Exception:
            echo_traceback("Error getting current user")
            return 1

    args.loginid = current_user

    imap_host, imap_port = _load_imap_config()
    args.imaphost = imap_host
    args.imapport = imap_port

    # Check if user has SYSOP flag
    if pool is None:
        pool = database.getpool(args)

    is_bbsengine_sysop = check_sysop_flag(args, current_user, pool)

    # If user is BBS engine sysop, ask if they want to admin postoffice
    is_sysop = getattr(args, "issuperuser", False)
    if is_bbsengine_sysop and not is_sysop:
        try:
            echo("")
            echo(f"You have SYSOP access as {current_user}")
            ch = inputboolean(
                "Administer postoffice? [Y/N]: ",
                default="Y",
            )
            if ch is True:
                is_sysop = True
        except termios.error:
            is_sysop = False

    while True:
        util.heading("postoffice")

        if is_sysop:
            choice = inputchoice(
                "Choose action: ",
                "tnmax",
                default="m",
                help="(t)ui messages, (n)otifications, (m)anage accounts, (a)dmin menu, e(x)it",
            )
        else:
            choice = inputchoice(
                "Choose action: ",
                "tnqx",
                default="m",
                help="(t)ui messages, (n)otifications, (m)anage accounts, e(x)it",
            )

        if choice in ("Q", "X"):
            echo("Goodbye!")
            return 0
        elif choice == "T":
            from bbsengine6 import screen

            try:
                screen.init()
            except termios.error:
                echo_traceback("Terminal error during message interface")
            try:
                result = _message_interface_run(args, current_user, pool=pool)
                if result != 0:
                    return result
            except KeyboardInterrupt:
                echo("{/all}*INTR*")
            except EOFError:
                echo("{/all}*EOF*")
            except termios.error:
                echo_traceback("Terminal error during message interface")
            finally:
                from bbsengine6.io import terminal

                try:
                    echo(
                        f"{{savecursor}}{{curpos:{terminal.height()},0}}{{el}}{{reset}}{{restorecursor}}"
                    )
                except termios.error:
                    pass
        elif choice == "N":
            from bbsengine6 import screen

            try:
                screen.init()
            except termios.error:
                echo_traceback("Terminal error during message interface")
            try:
                result = _notify_run(args, current_user)
                if result != 0:
                    return result
            except KeyboardInterrupt:
                echo("{/all}*INTR*")
            except EOFError:
                echo("{/all}*EOF*")
            except termios.error:
                echo_traceback("Terminal error during message interface")
            finally:
                from bbsengine6.io import terminal

                try:
                    echo(
                        f"{{savecursor}}{{curpos:{terminal.height()},0}}{{el}}{{reset}}{{restorecursor}}"
                    )
                except termios.error:
                    pass
        elif choice == "M":
            if is_sysop:
                from bbsengine6 import screen

                try:
                    screen.init()
                except termios.error:
                    pass
                try:
                    result = _cyrus_admin_run(args, current_user, pool=pool)
                except KeyboardInterrupt:
                    echo("{/all}*INTR*")
                except EOFError:
                    echo("{/all}*EOF*")
                except termios.error:
                    pass
                finally:
                    from bbsengine6.io import terminal

                    try:
                        echo(
                            f"{{savecursor}}{{curpos:{terminal.height()},0}}{{el}}{{reset}}{{restorecursor}}"
                        )
                    except termios.error:
                        pass
            else:
                echo(
                    "Error: Only administrators can access account management",
                    level="error",
                )
        elif choice == "A" and is_sysop:
            echo("Admin features not yet implemented", level="error")


def handle_tui(args: argparse.Namespace) -> int:
    """Handle TUI command for interactive message interface."""
    key = startup.get_encryption_key()
    if key is None:
        echo("Error: Encryption key not available", level="error")
        echo(
            "Please run 'python -m postoffice startup-check' to diagnose", level="error"
        )
        return 1

    pool = None
    current_user = getattr(args, "loginid", None)

    if current_user is None:
        try:
            pool = database.getpool(args)
            current_user = member.getcurrentmoniker(args, pool=pool)
        except Exception:
            echo_traceback("Error getting current user")
            return 1

    if current_user is None:
        echo("Error: Could not determine current user", level="error")
        return 1

    args.loginid = current_user

    from bbsengine6 import screen

    try:
        screen.init()
    except termios.error:
        pass

    try:
        result = _message_interface_run(args, current_user, pool=pool)
        return result
    except KeyboardInterrupt:
        echo("{/all}*INTR*")
    except EOFError:
        echo("{/all}*EOF*")
    except termios.error:
        pass
    finally:
        from bbsengine6.io import terminal

        try:
            echo(
                f"{{savecursor}}{{curpos:{terminal.height()},0}}{{el}}{{reset}}{{restorecursor}}"
            )
        except termios.error:
            pass
    return 0


def handle_notify(args: argparse.Namespace) -> int:
    """Handle notify command for notification interface."""
    pool = None
    current_user = getattr(args, "loginid", None)

    if current_user is None:
        try:
            pool = database.getpool(args)
            current_user = member.getcurrentmoniker(args, pool=pool)
        except Exception:
            echo_traceback("Error getting current user")
            return 1

    args.loginid = current_user

    from bbsengine6 import screen

    try:
        screen.init()
    except termios.error:
        pass

    try:
        result = _notify_run(args, current_user)
        return result
    except KeyboardInterrupt:
        echo("{/all}*INTR*")
    except EOFError:
        echo("{/all}*EOF*")
    except termios.error:
        pass
    finally:
        from bbsengine6.io import terminal

        try:
            echo(
                f"{{savecursor}}{{curpos:{terminal.height()},0}}{{el}}{{reset}}{{restorecursor}}"
            )
        except termios.error:
            pass
    return 0


def handle_accounts(args: argparse.Namespace) -> int:
    """Handle accounts command for account management."""
    key = startup.get_encryption_key()
    if key is None:
        echo("Error: Encryption key not available", level="error")
        echo(
            "Please run 'python -m postoffice startup-check' to diagnose", level="error"
        )
        return 1

    pool = None
    is_sysop = getattr(args, "issuperuser", False)
    current_user = getattr(args, "loginid", None)

    if current_user is None:
        try:
            pool = database.getpool(args)
            current_user = member.getcurrentmoniker(args, pool=pool)
        except Exception:
            echo_traceback("Error getting current user")
            return False
        echo("Error: Could not determine current user", level="error")
        return False

    args.loginid = current_user

    # Check if user has SYSOP flag (for non-cli sysop mode)
    if pool is None:
        pool = database.getpool(args)

    is_bbsengine_sysop = check_sysop_flag(args, current_user, pool)

    # If user is BBS engine sysop and not already in admin mode, ask
    if is_bbsengine_sysop and not is_sysop:
        try:
            echo("")
            echo(f"You have SYSOP access as {current_user}")
            ch = inputboolean(
                "Administer postoffice? [Y/N]: ",
                default="Y",
            )
            if ch is True:
                is_sysop = True
            elif ch is False or ch is None:
                # None means non-interactive or invalid input; False means "N"
                # Both mean: don't admin this session
                echo("Goodbye!")
                return 0
        except termios.error:
            echo("Terminal not available for interactive prompt", level="error")
            return 1

    if not is_sysop:
        echo("Error: Only administrators can access account management", level="error")
        return 1

    from bbsengine6 import screen

    try:
        screen.init()
    except Exception:
        pass

    try:
        return _cyrus_admin_run(args, current_user, pool=pool)
    except KeyboardInterrupt:
        echo("{/all}*INTR*")
    except EOFError:
        echo("{/all}*EOF*")
    except termios.error:
        pass
    finally:
        from bbsengine6.io import terminal

        try:
            echo(
                f"{{savecursor}}{{curpos:{terminal.height()},0}}{{el}}{{reset}}{{restorecursor}}"
            )
        except termios.error:
            pass
    return 0


def handle_projects(args: argparse.Namespace) -> int:
    """Handle projects command for projects address management."""
    key = startup.get_encryption_key()
    if key is None:
        echo("Error: Encryption key not available", level="error")
        echo(
            "Please run 'python -m postoffice startup-check' to diagnose", level="error"
        )
        return 1

    pool = None
    is_sysop = getattr(args, "issuperuser", False)
    current_user = getattr(args, "loginid", None)

    if current_user is None:
        try:
            pool = database.getpool(args)
            current_user = member.getcurrentmoniker(args, pool=pool)
        except Exception:
            echo_traceback("Error getting current user")
            return 1
        echo("Error: Could not determine current user", level="error")
        return 1

    args.loginid = current_user
    args.issuperuser = is_sysop

    return projects_run(args, current_user, pool=pool)


def handle_addresses(args: argparse.Namespace) -> int:
    """Handle addresses command for generic address management."""
    key = startup.get_encryption_key()
    if key is None:
        echo("Error: Encryption key not available", level="error")
        echo(
            "Please run 'python -m postoffice startup-check' to diagnose", level="error"
        )
        return 1

    pool = None
    is_sysop = getattr(args, "issuperuser", False)
    current_user = getattr(args, "loginid", None)

    if current_user is None:
        try:
            pool = database.getpool(args)
            current_user = member.getcurrentmoniker(args, pool=pool)
        except Exception:
            echo_traceback("Error getting current user")
            return 1

    args.loginid = current_user
    args.issuperuser = is_sysop

    return address_manager_run(args, current_user, pool=pool)


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
            result = subprocess.run(
                ["sudo", "mkdir", "-p", install_dir],
                capture_output=True,
                text=True,
                timeout=10,
                stdin=subprocess.DEVNULL,
            )

            if result.returncode != 0:
                if (
                    "sudo" in result.stderr.lower()
                    or "password" in result.stderr.lower()
                ):
                    echo(
                        "  ✗ Sudo password required. Please run with sudo or configure passwordless sudo.",
                        level="error",
                    )
                    echo("", level="error")
                    echo(
                        "To configure passwordless sudo for this command, add the following to /etc/sudoers:",
                        level="info",
                    )
                    echo(
                        "  %sudoers ALL=(ALL) NOPASSWD: /bin/mkdir, /bin/chmod, /bin/cp",
                        level="info",
                    )
                else:
                    echo(
                        f"  ✗ Failed to create directory: {result.stderr}",
                        level="error",
                    )
                return 1

            echo(f"  ✓ Created {install_dir}", level="debug")
        except subprocess.TimeoutExpired:
            echo(
                "  ✗ Command timed out. This may indicate sudo is waiting for a password.",
                level="error",
            )
            echo(
                "  Please run with passwordless sudo or use 'sudo python -m postoffice install-postoffice'",
                level="error",
            )
            return 1
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
                stdin=subprocess.DEVNULL,
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
                    stdin=subprocess.DEVNULL,
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
                stdin=subprocess.DEVNULL,
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
                stdin=subprocess.DEVNULL,
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


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the postoffice CLI.

    Returns:
        The fully-configured ArgumentParser. Split out from ``main`` so
        that :func:`buildargs` (the bbsengine6 module-API hook) can hand
        the same parser back to ``bbsengine6.module.run``.
    """
    parser = argparse.ArgumentParser(
        prog="python -m postoffice",
        description="mistermcfeely password management system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  menu                               Interactive menu (default)
  tui                                Message interface
  notify                             Notification interface
  accounts                           Account management (admin only)
  addresses                          Address manager (domains + addresses)
  sasl-password                      Manage SASL passwords (set/get/delete/disable/enable/list/reset)
  imap-check                         Check IMAP server connectivity
  install-postoffice                 Install config files to /etc/postoffice/
  startup-check                      Check encryption key setup
  startup-generate                   Generate new encryption key
  startup-install                    Install key to /etc/postoffice/
  startup-init                       Initialize password system

Options:
  --verbose                          Show verbose output
  --help, -h                         Show this help
  --version                          Show version
  --imaphost HOST                    IMAP host (for imap-check)
  --imapport PORT                    IMAP port (for imap-check)
  --cafile PATH                      PEM file of CAs to trust for IMAP TLS (for imap-check)
  --capath PATH                      Directory of CA certs to trust for IMAP TLS (for imap-check)
  --insecure                         Skip TLS cert verification for IMAP check (DEV ONLY)

Examples:
  python -m postoffice                          (runs menu)
  python -m postoffice imap-check
  python -m postoffice imap-check --verbose
  python -m postoffice imap-check --imaphost mail.example.com
  python -m postoffice imap-check --cafile /etc/pki/cyrus-imapd/cyrus-imapd-ca.pem
  python -m postoffice imap-check --insecure   # dev only: skip TLS verification
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
    parser.add_argument(
        "--cafile",
        type=str,
        help="Path to a PEM file of CAs to trust for IMAP TLS verification (for imap-check)",
    )
    parser.add_argument(
        "--capath",
        type=str,
        help="Path to a directory of CA certs (c_rehash format) to trust for IMAP TLS verification (for imap-check)",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS certificate verification for IMAP check (DEV ONLY)",
    )
    parser.add_argument(
        "--loginid",
        type=str,
        dest="loginid",
        help="Login ID for the current user (for account management)",
    )
    parser.add_argument(
        "--issuperuser",
        action="store_true",
        dest="issuperuser",
        default=False,
        help="Run as superuser/administrator (required for accounts command)",
    )
    parser.add_argument(
        "--target-moniker",
        type=str,
        dest="target_moniker",
        help="Target member moniker (for sasl-password)",
    )
    parser.add_argument(
        "--sasl-action",
        type=str,
        dest="sasl_action",
        choices=["set", "get", "delete", "disable", "enable", "list", "reset"],
        help="SASL password action (for sasl-password command)",
    )
    parser.add_argument(
        "--password",
        type=str,
        dest="password",
        help="Password value (for set/reset actions)",
    )

    defaults = {
        # TODO(postoffice-config): databasename intentionally has no
        # default here. Long-term, postoffice should load DB params
        # from a JSON config file and default missing entries to the
        # literal sentinel "NEEDINFO". See TODO.md entry.
        "databasehost": "localhost",
        "databaseport": 5432,
    }
    database.buildargdatabasegroup(parser, defaults)

    return parser


def buildargs(args: Any, **kwargs) -> argparse.ArgumentParser | None:
    """bbsengine6 module-API hook: build the postoffice CLI parser.

    Required by ``bbsengine6.module.check`` (see bbsengine6/module.py).
    The ``args`` and ``**kwargs`` parameters follow the standard
    ``init/access/buildargs/main`` 4-function module signature so the
    function passes ``bbsengine6.module._check_func_signature`` against
    the ``_stub_buildargs`` stub.

    Args:
        args: bbsengine6 args object (unused; the parser is module-static).
        **kwargs: framework-supplied keyword arguments (ignored).

    Returns:
        The postoffice ArgumentParser.
    """
    return _build_parser()


def main(args: Any, **kwargs):
    """Main entry point for the postoffice module.

    Conforms to the bbsengine6 standard module interface
    ``main(args, **kwargs) -> bool`` so the package can be dispatched
    from a custom shell via
    ``bbsengine6.module.runmodule(args, "postoffice")`` (or with an
    explicit ``argv=[...]`` kwarg). The ``args`` parameter is required
    (no default value) so the signature matches ``_stub_main``; callers
    that previously invoked ``main()`` with no positional should pass
    ``main(None)`` instead (the ``__main__`` block does this).

    Three call shapes are supported:

    1. ``main(None)`` or ``main(argv=[...])`` -- parse ``sys.argv[1:]``
       (the ``python -m postoffice`` / ``bin/postoffice`` entry point)
       or the supplied argv. Used when the caller hasn't parsed argv
       itself.
    2. ``main(args=argparse.Namespace(...), **kwargs)`` -- the caller
       has already parsed argv (the bbsengine6 module runner case
       after ``bbsengine6.module.run`` invoked ``buildargs`` and
       parsed argv on our behalf).

    For backward compatibility, a positional list is also treated as
    argv, matching the previous ``main(["tui"])`` call shape.

    Returns:
        ``True`` for exit code 0, ``False`` for any non-zero outcome,
        or ``None`` for success-but-uncertain (matches the
        ``_stub_main`` ``bool | None`` contract).
    """
    argv = kwargs.pop("argv", None)

    # Backward-compat: legacy callers passed a list positionally.
    if argv is None and isinstance(args, list):
        argv = args
        args = None

    if isinstance(args, argparse.Namespace):
        parsed = args
        if argv:
            parsed = _build_parser().parse_args(argv)
    else:
        if argv is None:
            argv = sys.argv[1:]
        parsed = _build_parser().parse_args(argv)

    parsed.debug = False  # Ensure debug attribute exists for bbsengine6 functions

    # Handle version
    if parsed.version:
        echo(version_postoffice(parsed))
        return True

    # Route commands
    command_map = {
        "menu": handle_menu,
        "tui": handle_tui,
        "notify": handle_notify,
        "accounts": handle_accounts,
        "addresses": handle_addresses,
        "projects": handle_projects,
        "imap-check": handle_imap_check,
        "install-postoffice": handle_install_postoffice,
        "startup-check": handle_startup_check,
        "startup-generate": handle_startup_generate,
        "startup-install": handle_startup_install,
        "startup-init": handle_startup_init,
        "sasl-password": handle_sasl_password,
    }

    handler = command_map.get(parsed.command)
    if not handler:
        echo(f"Unknown command: {parsed.command}", level="error")
        echo()
        echo(help_postoffice(parsed))
        return False

    result = handler(parsed)
    if result is True or result is None or result == 0:
        return True
    if result is False:
        return False
    return False


def _coerce_main_exit(value: Any) -> int:
    """Coerce ``main()``'s return value into an integer exit code."""
    if value is True or value is None:
        return 0
    if value is False:
        return 1
    if isinstance(value, int):
        return value
    return 1


# ---------------------------------------------------------------------------
# Backward-compatibility aliases
#
# The canonical bbsengine6 module-API names are ``init`` and ``access``
# (defined above). Earlier versions of this module exposed them as
# ``init_postoffice`` and ``access_postoffice``; keep those names working
# so external callers (custom shells, docs, tests) keep compiling.
# ---------------------------------------------------------------------------
init_postoffice = init
access_postoffice = access


if __name__ == "__main__":
    sys.exit(_coerce_main_exit(main(None)))
