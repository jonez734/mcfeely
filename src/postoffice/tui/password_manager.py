# tui/password_manager.py
# Text User Interface for managing member and shared mailbox passwords

from typing import Any
from bbsengine6.io import echo
from bbsengine6.util import inputpassword
from .. import member_password, shared_mailbox_password


class PasswordManager:
    """Interactive TUI for password management."""

    def __init__(self, args: Any):
        self.args = args
        self.current_user = getattr(args, "loginid", None)
        self.is_sysop = getattr(args, "issuperuser", False)

    def run(self) -> int:
        """Main TUI loop. Returns exit code."""
        if not self.current_user:
            echo("Error: Could not determine current user", level="error")
            return 1

        while True:
            echo("")
            echo("=== Password Manager ===", level="info")
            echo(f"User: {self.current_user}")
            if self.is_sysop:
                echo("Mode: Administrator", level="info")
            echo("")

            if self.is_sysop:
                self._show_sysop_menu()
            else:
                self._show_member_menu()

            try:
                choice = input("Enter choice (or 'q' to quit): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                echo("", level="info")
                echo("Goodbye!", level="info")
                return 0

            if choice == "q":
                echo("Goodbye!", level="info")
                return 0

            self._handle_choice(choice)

    def _show_member_menu(self) -> None:
        """Show member password management menu."""
        echo("1. Manage Personal Account Passwords")
        echo("   a. Set inbound password")
        echo("   b. Set outbound password")
        echo("   c. View password status")
        echo("   d. Delete inbound password")
        echo("   e. Delete outbound password")
        echo("")
        echo("2. Manage Shared Mailbox Passwords")
        echo("   a. Set password for a mailbox")
        echo("   b. View passwords for a mailbox")
        echo("   c. Delete password for a mailbox")
        echo("")
        echo("q. Quit")

    def _show_sysop_menu(self) -> None:
        """Show sysop password management menu."""
        echo("1. Manage Personal Account Passwords")
        echo("   a. Set password for any member")
        echo("   b. View password status for any member")
        echo("   c. Delete password for any member")
        echo("")
        echo("2. Manage Shared Mailbox Passwords")
        echo("   a. Set password for any member on any mailbox")
        echo("   b. View passwords for any member on any mailbox")
        echo("   c. Delete password for any member on any mailbox")
        echo("")
        echo("q. Quit")

    def _handle_choice(self, choice: str) -> None:
        """Handle user menu choice."""
        if choice == "1a":
            self._set_personal_password("inbound")
        elif choice == "1b":
            self._set_personal_password("outbound")
        elif choice == "1c":
            self._view_personal_passwords()
        elif choice == "1d":
            self._delete_personal_password("inbound")
        elif choice == "1e":
            self._delete_personal_password("outbound")
        elif choice == "2a":
            self._set_shared_mailbox_password()
        elif choice == "2b":
            self._view_shared_mailbox_passwords()
        elif choice == "2c":
            self._delete_shared_mailbox_password()
        else:
            echo("Invalid choice", level="error")

    def _set_personal_password(self, password_type: str) -> None:
        """Set personal account password."""
        if self.is_sysop:
            member = input("Enter member moniker to manage: ").strip()
        else:
            member = self.current_user

        if not member:
            echo("Invalid member moniker", level="error")
            return

        password = inputpassword(f"Enter {password_type} password: ")
        if not password:
            echo("Password cannot be empty", level="error")
            return

        confirm = inputpassword(f"Confirm {password_type} password: ")
        if password != confirm:
            echo("Passwords do not match", level="error")
            return

        if member_password.set_personal_password(
            self.args, member, password_type, password, self.current_user
        ):
            echo(
                f"✓ {password_type.capitalize()} password set for {member}",
                level="info",
            )
        else:
            echo(f"✗ Failed to set {password_type} password", level="error")

    def _view_personal_passwords(self) -> None:
        """View personal account password status."""
        if self.is_sysop:
            member = input("Enter member moniker: ").strip()
        else:
            member = self.current_user

        if not member:
            echo("Invalid member moniker", level="error")
            return

        passwords = member_password.list_personal_passwords(
            self.args, member, self.current_user
        )

        if not passwords:
            echo(f"No passwords found for {member}", level="info")
            return

        echo(f"Password status for {member}:", level="info")
        for pwd_type, info in passwords.items():
            status = "✓ Set" if info["exists"] else "✗ Not set"
            echo(f"  {pwd_type.capitalize()}: {status}")

    def _delete_personal_password(self, password_type: str) -> None:
        """Delete personal account password."""
        if self.is_sysop:
            member = input("Enter member moniker: ").strip()
        else:
            member = self.current_user

        if not member:
            echo("Invalid member moniker", level="error")
            return

        confirm = (
            input(f"Delete {password_type} password for {member}? (yes/no): ")
            .strip()
            .lower()
        )
        if confirm != "yes":
            echo("Cancelled", level="info")
            return

        if member_password.delete_personal_password(
            self.args, member, password_type, self.current_user
        ):
            echo(
                f"✓ {password_type.capitalize()} password deleted for {member}",
                level="info",
            )
        else:
            echo(f"✗ Failed to delete {password_type} password", level="error")

    def _set_shared_mailbox_password(self) -> None:
        """Set password for member on shared mailbox."""
        try:
            mailbox_id = int(input("Enter mailbox ID: ").strip())
        except ValueError:
            echo("Invalid mailbox ID", level="error")
            return

        password_type = (
            input("Enter password type (inbound/outbound): ").strip().lower()
        )
        if password_type not in ("inbound", "outbound"):
            echo("Invalid password type", level="error")
            return

        if self.is_sysop:
            member = input("Enter member moniker: ").strip()
        else:
            member = self.current_user

        if not member:
            echo("Invalid member moniker", level="error")
            return

        password = inputpassword(f"Enter {password_type} password: ")
        if not password:
            echo("Password cannot be empty", level="error")
            return

        confirm = inputpassword(f"Confirm {password_type} password: ")
        if password != confirm:
            echo("Passwords do not match", level="error")
            return

        if shared_mailbox_password.set_shared_mailbox_password(
            self.args, mailbox_id, member, password_type, password, self.current_user
        ):
            echo(f"✓ Password set for {member} on mailbox {mailbox_id}", level="info")
        else:
            echo("✗ Failed to set password", level="error")

    def _view_shared_mailbox_passwords(self) -> None:
        """View passwords for member on shared mailbox."""
        try:
            mailbox_id = int(input("Enter mailbox ID: ").strip())
        except ValueError:
            echo("Invalid mailbox ID", level="error")
            return

        if self.is_sysop:
            member = input("Enter member moniker: ").strip()
        else:
            member = self.current_user

        if not member:
            echo("Invalid member moniker", level="error")
            return

        passwords = shared_mailbox_password.list_shared_mailbox_passwords(
            self.args, mailbox_id, member, self.current_user
        )

        if not passwords:
            echo("No passwords found", level="info")
            return

        echo(f"Password status for {member} on mailbox {mailbox_id}:", level="info")
        for pwd_type, info in passwords.items():
            status = "✓ Set" if info["exists"] else "✗ Not set"
            details = ""
            if info["exists"]:
                details = f" (set by {info.get('set_by', '?')})"
            echo(f"  {pwd_type.capitalize()}: {status}{details}")

    def _delete_shared_mailbox_password(self) -> None:
        """Delete password for member on shared mailbox."""
        try:
            mailbox_id = int(input("Enter mailbox ID: ").strip())
        except ValueError:
            echo("Invalid mailbox ID", level="error")
            return

        password_type = (
            input("Enter password type (inbound/outbound): ").strip().lower()
        )
        if password_type not in ("inbound", "outbound"):
            echo("Invalid password type", level="error")
            return

        if self.is_sysop:
            member = input("Enter member moniker: ").strip()
        else:
            member = self.current_user

        if not member:
            echo("Invalid member moniker", level="error")
            return

        confirm = (
            input(f"Delete {password_type} password for {member}? (yes/no): ")
            .strip()
            .lower()
        )
        if confirm != "yes":
            echo("Cancelled", level="info")
            return

        if shared_mailbox_password.delete_shared_mailbox_password(
            self.args, mailbox_id, member, password_type, self.current_user
        ):
            echo(
                f"✓ Password deleted for {member} on mailbox {mailbox_id}", level="info"
            )
        else:
            echo("✗ Failed to delete password", level="error")


__all__ = ["PasswordManager"]
