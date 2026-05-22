from bbsengine6 import io, util

# import ttyio5 as ttyio
# import bbsengine5 as bbsengine

from . import lib
from .imap_checker import IMAPChecker


def init(args, **kw):
    return True


def access(args, op, **kw):
    return True


def buildargs(args=None, **kw):
    return None


def _check_imap_connectivity(args):
    """
    Check if IMAP server is running on configured address/port.

    Args:
        args: bbsengine6 args object with IMAP configuration

    Returns:
        True if IMAP server is accessible, False otherwise
    """
    # Get IMAP configuration
    imap_host = getattr(args, "imaphost", "localhost")
    imap_port = getattr(args, "imapport", 993)

    if not imap_host:
        imap_host = "localhost"
    if not imap_port:
        imap_port = 993

    try:
        checker = IMAPChecker(imap_host, imap_port, timeout=5, verbose=False)
        all_pass, _ = checker.check_all()
        return all_pass
    except Exception as e:
        io.echo(f"Error checking IMAP connectivity: {e}", level="error")
        return False


def main(args, **kw):
    if args is not None and "debug" in args and args.debug is True:
        io.echo("postoffice.main.100: args=%r" % (args))

    # Check IMAP server connectivity before proceeding
    imap_host = getattr(args, "imaphost", "localhost")
    imap_port = getattr(args, "imapport", 993)

    if not imap_host:
        imap_host = "localhost"
    if not imap_port:
        imap_port = 993

    io.echo("")
    io.echo("Checking IMAP server connectivity...", level="debug")

    if not _check_imap_connectivity(args):
        io.echo("", level="error")
        io.echo("ERROR: IMAP server is not responding!", level="error")
        io.echo(f"  Configured: {imap_host}:{imap_port}", level="error")
        io.echo("", level="error")
        io.echo("Please verify:", level="error")
        io.echo("  1. IMAP server is installed and running", level="error")
        io.echo("  2. IMAP server is listening on the configured port", level="error")
        io.echo("  3. Network connectivity to the IMAP server", level="error")
        io.echo("  4. Firewall rules allow connections to the IMAP port", level="error")
        io.echo("", level="error")
        io.echo(
            "Run 'python -m postoffice imap-check -v' for more diagnostics",
            level="error",
        )
        io.echo("", level="error")

        # Ask user if they want to continue anyway
        ch = io.inputchar(
            "Continue without IMAP connection? {var:optioncolor}[Y/N]{var:promptcolor}: {var:inputcolor}",
            "YN",
            "N",
        )
        if ch != "Y":
            io.echo("Exiting.", level="info")
            return

    io.echo("✓ IMAP server is responding", level="debug")
    io.echo("")

    loop = True
    while loop:
        util.heading("postoffice")
        io.terminal.title("terminal title")
        io.echo(
            f"{{var:labelcolor}}database:{{var:valuecolor}}{args.databasename} {{var:labelcolor}}host:{{var:valuecolor}} {args.databasehost}:{args.databaseport}"
        )
        lib.setarea(args, "zoid postoffice main menu")
        io.echo("{var:optioncolor}[V]{var:labelcolor} Virtual")
        io.echo("{var:optioncolor}[M]{var:labelcolor} Mailbox")
        io.echo("{f6}{var:optioncolor}[Q]{var:labelcolor} Quit{f6}")
        ch = io.inputchar(
            "{var:promptcolor}postoffice {var:optioncolor}[VMQ]{var:promptcolor}: {var:inputcolor}",
            "VMQX",
            "",
        )
        if ch == "V":
            io.echo("Virtual")
            lib.runmodule(args, "virtual")
        elif ch == "M":
            io.echo("Mailboxes")
            lib.runmodule(args, "mailbox")
        elif ch == "Q" or ch == "X":
            io.echo("Quit")
            loop = False
            break
