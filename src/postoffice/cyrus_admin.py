# cyrus_admin.py
# Programmatic Cyrus IMAP administration via imaplib

import imaplib
from typing import Optional


class CyrusAdmin:
    """Programmatic Cyrus IMAP administration."""

    def __init__(self, host: str = "localhost", port: int = 143, admin_user: str = "cyrus", admin_password: Optional[str] = None):
        self.host = host
        self.port = port
        self.admin_user = admin_user
        self.admin_password = admin_password
        self.conn: Optional[imaplib.IMAP4] = None

    def login(self, password: str) -> bool:
        """Connect and authenticate as admin."""
        try:
            self.conn = imaplib.IMAP4(self.host, self.port)
            self.conn.login(self.admin_user, password)
            return True
        except Exception as e:
            self.conn = None
            raise ConnectionError(f"Failed to connect as {self.admin_user}: {e}")

    def logout(self) -> None:
        """Close connection."""
        if self.conn:
            try:
                self.conn.logout()
            except Exception:
                self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()

    def create_mailbox(self, name: str) -> bool:
        """Create a mailbox."""
        if not self.conn:
            raise ConnectionError("Not connected. Call login() first.")
        typ, data = self.conn.create(name)
        return typ == "OK"

    def delete_mailbox(self, name: str) -> bool:
        """Delete a mailbox."""
        if not self.conn:
            raise ConnectionError("Not connected. Call login() first.")
        typ, data = self.conn.delete(name)
        return typ == "OK"

    def list_mailboxes(self, reference: str = "", mailbox: str = "*") -> list[str]:
        """List mailboxes matching pattern."""
        if not self.conn:
            raise ConnectionError("Not connected. Call login() first.")
        typ, data = self.conn.list(reference, mailbox)
        if typ != "OK" or not data:
            return []
        mailboxes = []
        for item in data:
            if item and isinstance(item, bytes):
                parts = item.split()
                if parts and len(parts) >= 4:
                    mb = parts[3].strip(b'"').decode()
                    mailboxes.append(mb)
        return mailboxes

    def get_acl(self, mailbox: str) -> dict[str, str]:
        """Get ACLs for a mailbox. Returns dict of user -> rights."""
        if not self.conn:
            raise ConnectionError("Not connected. Call login() first.")
        typ, data = self.conn.getacl(mailbox)
        if typ != "OK":
            return {}
        acl_dict = {}
        for entry in data:
            parts = entry.decode().split()
            if len(parts) >= 2:
                user = parts[1]
                rights = parts[2] if len(parts) > 2 else ""
                acl_dict[user] = rights
        return acl_dict

    def set_acl(self, mailbox: str, user: str, rights: str) -> bool:
        """Set ACL for user on mailbox. rights='' removes ACL."""
        if not self.conn:
            raise ConnectionError("Not connected. Call login() first.")
        typ, data = self.conn.setacl(mailbox, user, rights)
        return typ == "OK"

    def delete_acl(self, mailbox: str, user: str) -> bool:
        """Remove ACL for user on mailbox."""
        return self.set_acl(mailbox, user, "")

    def create_user_mailbox(self, username: str, user_rights: str = "lrsd") -> bool:
        """Create a user mailbox with ACL for the user."""
        mailbox = f"user.{username}"
        success = self.create_mailbox(mailbox)
        if success and user_rights:
            self.set_acl(mailbox, username, user_rights)
        return success

    def create_shared_mailbox(self, name: str, owner: str = "cyrus", owner_rights: str = "lrsd") -> bool:
        """Create a shared mailbox with admin ACL."""
        mailbox = f"user.{name}"
        success = self.create_mailbox(mailbox)
        if success:
            self.set_acl(mailbox, owner, owner_rights)
        return success

    def add_user_to_shared_mailbox(self, mailbox: str, user: str, rights: str = "lr") -> bool:
        """Add user to shared mailbox with specified rights."""
        return self.set_acl(mailbox, user, rights)

    def remove_user_from_shared_mailbox(self, mailbox: str, user: str) -> bool:
        """Remove user from shared mailbox."""
        return self.set_acl(mailbox, user, "")


# Convenience functions for common operations
def create_shared_mailbox(
    name: str,
    admin_password: str,
    host: str = "localhost",
    port: int = 143,
    admin_user: str = "cyrus",
    owner: str = "cyrus",
    owner_rights: str = "lrsd",
) -> bool:
    """Create a shared mailbox with owner ACL."""
    with CyrusAdmin(host, port, admin_user) as admin:
        admin.login(admin_password)
        return admin.create_shared_mailbox(name, owner, owner_rights)


def add_user_to_mailbox(
    mailbox: str,
    username: str,
    rights: str,
    admin_password: str,
    host: str = "localhost",
    port: int = 143,
    admin_user: str = "cyrus",
) -> bool:
    """Add user to mailbox with ACL."""
    with CyrusAdmin(host, port, admin_user) as admin:
        admin.login(admin_password)
        return admin.add_user_to_shared_mailbox(mailbox, username, rights)


def remove_user_from_mailbox(
    mailbox: str,
    username: str,
    admin_password: str,
    host: str = "localhost",
    port: int = 143,
    admin_user: str = "cyrus",
) -> bool:
    """Remove user from mailbox."""
    with CyrusAdmin(host, port, admin_user) as admin:
        admin.login(admin_password)
        return admin.remove_user_from_shared_mailbox(mailbox, username)


# ACL rights reference:
# l = lookup (see mailbox)
# r = read (fetch messages)
# s = seen (set \Seen flag)
# w = write (set other flags)
# i = insert (add messages)
# p = post (send via LMTP)
# c = create (sub-mailboxes)
# d = delete (set \Deleted flag)
# a = admin (change ACLs)
# all = all permissions
# none = remove all permissions
#
# Common combinations:
# read_only = "lr"
# read_write = "lrsd"
# full = "lrsd"
# admin = "lrsdwa"