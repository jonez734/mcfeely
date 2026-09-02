# tui/cyrus_admin.py
# Text User Interface for managing Cyrus IMAP accounts and shared mailboxes

from typing import Any
from bbsengine6.io import echo
from bbsengine6.io.echo import echo_traceback
from bbsengine6.io.inputchoice import inputchoice
from bbsengine6.util import inputpassword, heading
from bbsengine6 import database
from .. import member_password, shared_mailbox_password


DEFAULT_EMAIL_DOMAIN = "local"


class CyrusAdmin:
    """Interactive TUI for Cyrus IMAP administration."""

    def __init__(self, args: Any):
        self.args = args
        self.current_user = getattr(args, "loginid", None)
        self.is_sysop = getattr(args, "issuperuser", False)
        self.pool = database.getpool(self.args)

    def run(self) -> int:
        """Main TUI loop. Returns exit code."""
        if not self.current_user:
            echo("Error: Could not determine current user", level="error")
            return 1

        if not self.is_sysop:
            echo(
                "Error: Only administrators can access account management",
                level="error",
            )
            return 1

        while True:
            echo("")
            heading("Cyrus Account Management")
            echo(f"Administrator: {self.current_user}")
            echo("")

            choice = inputchoice(
                "Choose action: ",
                "acsmxq",
                default="m",
                help="(a)ccounts, (c)reate account, (s)hared mailboxes, (m)anage mailbox, e(x)it, (q)uit",
            )

            if choice in ("X", "Q"):
                echo("Goodbye!")
                return 0
            elif choice == "A":
                self._list_accounts()
            elif choice == "C":
                self._create_account()
            elif choice == "S":
                self._list_shared_mailboxes()
            elif choice == "M":
                self._manage_shared_mailbox()

    def _list_accounts(self) -> None:
        """List all user accounts with details."""
        echo("")
        heading("User Accounts")

        sql = "SELECT moniker, datecreated FROM engine.__member ORDER BY moniker"

        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    rows = cur.fetchall()

                    if not rows:
                        echo("No accounts found")
                        return

                    echo(f"Found {len(rows)} account(s):")
                    echo("")

                    for row in rows:
                        moniker = row["moniker"]
                        datecreated = row["datecreated"]
                        echo(f"  • {moniker} (created: {datecreated})")

                    echo("")
                    echo(f"Total: {len(rows)} account(s)")

        except Exception:
            echo_traceback("Error listing accounts")

    def _create_account(self) -> None:
        """Create a new user account."""
        echo("")
        heading("Create New Account")

        moniker = input("Enter moniker for new account: ").strip()
        if not moniker:
            echo("Moniker cannot be empty", level="error")
            return

        # Check if account already exists
        sql = "SELECT moniker FROM engine.__member WHERE moniker = %s"
        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (moniker,))
                    if cur.rowcount > 0:
                        echo(f"Account '{moniker}' already exists", level="error")
                        return
        except Exception:
            echo_traceback("Error checking account existence")
            return

        # Get inbound password
        inbound_pwd = inputpassword("Enter inbound (IMAP) password: ")
        if not inbound_pwd:
            echo("Password cannot be empty", level="error")
            return

        confirm = inputpassword("Confirm inbound password: ")
        if inbound_pwd != confirm:
            echo("Passwords do not match", level="error")
            return

        # Create account in database
        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with conn.cursor() as cur:
                    sql = """
                        INSERT INTO engine.__member (moniker, email, datecreated, dateupdated)
                        VALUES (%s, %s, NOW(), NOW())
                    """
                    cur.execute(sql, (moniker, f"{moniker}@{DEFAULT_EMAIL_DOMAIN}"))

            echo(f"✓ Account '{moniker}' created")

            # Set inbound password
            assert self.current_user is not None
            if member_password.set_personal_password(
                self.args, moniker, "inbound", inbound_pwd, self.current_user
            ):
                echo("✓ Inbound password set")
            else:
                echo("⚠ Failed to set inbound password", level="error")

            # Optionally set outbound password
            set_outbound = (
                input("Set outbound (SMTP) password? (yes/no): ").strip().lower()
            )
            if set_outbound == "yes":
                outbound_pwd = inputpassword("Enter outbound password: ")
                if not outbound_pwd:
                    echo("Password cannot be empty", level="error")
                    return

                confirm = inputpassword("Confirm outbound password: ")
                if outbound_pwd != confirm:
                    echo("Passwords do not match", level="error")
                    return

                assert self.current_user is not None
                if member_password.set_personal_password(
                    self.args, moniker, "outbound", outbound_pwd, self.current_user
                ):
                    echo("✓ Outbound password set")
                else:
                    echo("✗ Failed to set outbound password", level="error")

            echo("")
            echo(f"✓ Account '{moniker}' created successfully")

        except Exception:
            echo_traceback("Error creating account")

    def _list_shared_mailboxes(self) -> None:
        """List all shared mailboxes with details."""
        echo("")
        heading("Shared Mailboxes")

        sql = (
            "SELECT id, name, datecreated FROM postoffice.shared_mailbox ORDER BY name"
        )

        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    rows = cur.fetchall()

                    if not rows:
                        echo("No shared mailboxes found")
                        return

                    echo(f"Found {len(rows)} mailbox(es):")
                    echo("")

                    for row in rows:
                        mailbox_id = row["id"]
                        name = row["name"]

                        # Count members with access
                        member_sql = """
                            SELECT COUNT(DISTINCT member_moniker) as member_count
                            FROM postoffice.member_mailbox_password
                            WHERE mailbox_id = %s
                        """
                        cur.execute(member_sql, (mailbox_id,))
                        member_count = cur.fetchone()["member_count"]

                        echo(f"  • {name} (ID: {mailbox_id}, members: {member_count})")

                    echo("")
                    echo(f"Total: {len(rows)} mailbox(es)")

        except Exception:
            echo_traceback("Error listing shared mailboxes")

    def _manage_shared_mailbox(self) -> None:
        """Manage a specific shared mailbox."""
        echo("")
        heading("Manage Shared Mailbox")

        # First, let user choose mailbox
        try:
            mailbox_id = int(input("Enter mailbox ID: ").strip())
        except ValueError:
            echo("Invalid mailbox ID", level="error")
            return

        # Verify mailbox exists and get details
        sql = "SELECT id, name FROM postoffice.shared_mailbox WHERE id = %s"
        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (mailbox_id,))
                    if cur.rowcount == 0:
                        echo(f"Mailbox ID {mailbox_id} not found", level="error")
                        return
                    mailbox = cur.fetchone()
                    mailbox_name = mailbox["name"]
        except Exception:
            echo_traceback("Error retrieving mailbox")
            return

        echo(f"Mailbox: {mailbox_name} (ID: {mailbox_id})")
        echo("")

        while True:
            choice = inputchoice(
                "Choose action: ",
                "vcsbx",
                default="v",
                help="(v)iew members, (c)reate mailbox, (s)et password, (b)ack, e(x)it",
            )

            if choice == "X":
                return
            elif choice == "B":
                return
            elif choice == "V":
                self._view_mailbox_members(mailbox_id, mailbox_name)
            elif choice == "C":
                self._create_shared_mailbox()
                return  # Return to main menu after creating
            elif choice == "S":
                self._set_shared_mailbox_password(mailbox_id, mailbox_name)

    def _view_mailbox_members(self, mailbox_id: int, mailbox_name: str) -> None:
        """View members with access to a shared mailbox."""
        echo("")
        echo(f"=== Members of {mailbox_name} ===")

        sql = """
            SELECT DISTINCT member_moniker
            FROM postoffice.member_mailbox_password
            WHERE mailbox_id = %s
            ORDER BY member_moniker
        """

        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (mailbox_id,))
                    rows = cur.fetchall()

                    if not rows:
                        echo("No members have access to this mailbox")
                        return

                    echo("Members with access:")
                    for row in rows:
                        member = row["member_moniker"]
                        echo(f"  • {member}")

        except Exception:
            echo_traceback("Error listing mailbox members")

    def _create_shared_mailbox(self) -> None:
        """Create a new shared mailbox."""
        echo("")
        heading("Create Shared Mailbox")

        name = input("Enter name for shared mailbox: ").strip()
        if not name:
            echo("Name cannot be empty", level="error")
            return

        # Verify unique name
        sql = "SELECT id FROM postoffice.shared_mailbox WHERE name = %s"
        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (name,))
                    if cur.rowcount > 0:
                        echo(f"Mailbox '{name}' already exists", level="error")
                        return

                    # Create the mailbox
                    insert_sql = """
                        INSERT INTO postoffice.shared_mailbox (name, createdbymoniker, datecreated, dateupdated)
                        VALUES (%s, %s, NOW(), NOW())
                    """
                    cur.execute(insert_sql, (name, self.current_user))

            echo(f"✓ Shared mailbox '{name}' created")

        except Exception:
            echo_traceback("Error creating shared mailbox")

    def _set_shared_mailbox_password(self, mailbox_id: int, mailbox_name: str) -> None:
        """Set password for a member on a shared mailbox."""
        echo("")
        echo(f"=== Set Password for {mailbox_name} ===")

        member = input("Enter member moniker: ").strip()
        if not member:
            echo("Member moniker cannot be empty", level="error")
            return

        # Verify member exists
        sql = "SELECT moniker FROM engine.__member WHERE moniker = %s"
        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (member,))
                    if cur.rowcount == 0:
                        echo(f"Member '{member}' not found", level="error")
                        return
        except Exception:
            echo_traceback("Error verifying member")
            return

        # Ask which password type(s)
        pwd_type = inputchoice(
            "Set which password? ",
            "iob",
            default="i",
            help="(i)nbound, (o)utbound, (b)oth",
        )

        password_types = []
        if pwd_type in ("I", "B"):
            password_types.append("inbound")
        if pwd_type in ("O", "B"):
            password_types.append("outbound")

        for ptype in password_types:
            password = inputpassword(f"Enter {ptype} password: ")
            if not password:
                echo(f"{ptype.capitalize()} password cannot be empty", level="error")
                continue

            confirm = inputpassword(f"Confirm {ptype} password: ")
            if password != confirm:
                echo(f"{ptype.capitalize()} passwords do not match", level="error")
                continue

            assert self.current_user is not None
            if shared_mailbox_password.set_shared_mailbox_password(
                self.args,
                mailbox_id,
                member,
                ptype,
                password,
                self.current_user,
            ):
                echo(f"✓ {ptype.capitalize()} password set for {member}")
            else:
                echo(f"✗ Failed to set {ptype} password", level="error")


def run(args: Any, current_user=None, pool=None) -> int:
    """Module-level entry point for the Cyrus admin TUI.

    Wraps :class:`CyrusAdmin` so callers (e.g. ``postoffice.__main__``)
    can invoke ``from .tui.cyrus_admin import run`` and call
    ``run(args, current_user, pool=pool)`` uniformly. The legacy
    signature accepted ``(args, current_user, pool)``; the current
    :class:`CyrusAdmin` takes only ``args`` and pulls ``loginid`` /
    ``issuperuser`` from the namespace.
    """
    if current_user is not None:
        args.loginid = current_user
    return CyrusAdmin(args).run()
