#!/usr/bin/env python3
# imap_test_create_mailbox_with_acl.py
# Test IMAP: creates or updates a mailbox and optionally sets ACL permissions for a user.
# Prompts for IMAP admin username/password, mailbox name, shared status, and permissions.

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from bbsengine6 import util
from bbsengine6.io import echo, inputstring, inputboolean
from postoffice.lib import cyrusperms


def mailbox_exists(imap: "imaplib.IMAP4", mailbox: str) -> bool:
    status, _ = imap.status(mailbox, "(MESSAGES)")
    return status == "OK"


def get_current_acl(imap: "imaplib.IMAP4", mailbox: str, target_user: str) -> str | None:
    status, data = imap.getacl(mailbox)
    if status != "OK":
        return None
    for entry in data:
        parts = entry.decode().split()
        if parts and parts[0] == target_user:
            return parts[1] if len(parts) > 1 else None
    return None


def main() -> int:
    try:
        username = inputstring("IMAP admin username: ").strip()
        if not username:
            echo("Cancelled", level="warn")
            return 1

        password = util.inputpassword("Password: ", mask="X")
        if not password:
            echo("Cancelled", level="warn")
            return 1

        mailbox = inputstring("Mailbox name (e.g. INBOX or user.name): ").strip()
        if not mailbox:
            echo("Cancelled", level="warn")
            return 1

        shared = inputboolean("Shared mailbox? (Y/N)")
        if shared is None:
            echo("Cancelled", level="warn")
            return 1

        target_user = None
        permissions = None

        if shared:
            from postoffice.lib import CYRUS_PERMISSIONS

            while True:
                target_user = inputstring("Grant permissions to user: ").strip()
                if not target_user:
                    echo("Cancelled", level="warn")
                    return 1
                if len(target_user) >= 2 and all(c.lower() in CYRUS_PERMISSIONS for c in target_user):
                    echo("That looks like permissions, not a username. Enter the IMAP username.", level="warn")
                    continue
                break

            echo("\nPermissions (combine letters):")
            echo("  l - lookup (see mailbox in list)")
            echo("  r - read (select, fetch)")
            echo("  s - seen (see unseen count)")
            echo("  w - write (set flags)")
            echo("  i - insert (append/copy into mailbox)")
            echo("  p - post (submit to mailbox)")
            echo("  d - delete (expunge messages)")
            echo("  a - admin (setacl)")
            echo("  c - create subfolder")
            echo("  k - create subfolder (alias)")
            echo("  t - delete messages (soft expunge)")
            echo("  x - delete mailbox")
            echo("  n - rename folder")
            echo("  e - delete folder")

            permissions = inputstring("Permissions (e.g. lrspi): ").strip()
            if not permissions:
                echo("Cancelled", level="warn")
                return 1

        echo("\nSummary:")
        echo(f"  Mailbox: {mailbox}")
        echo(f"  Shared: {'Yes' if shared else 'No'}")
        if shared:
            echo(f"  User: {target_user}")
            echo(f"  Permissions: {cyrusperms(permissions)}")
        echo()

        confirm = inputboolean("Apply? (Y/N)")
        if confirm is None or not confirm:
            echo("Cancelled", level="warn")
            return 1

        echo(f"Connecting to localhost:993 as {username}...")

        import imaplib
        try:
            imap = imaplib.IMAP4_SSL("localhost", 993)
            imap.login(username, password)
            echo("IMAP LOGIN OK")

            exists = mailbox_exists(imap, mailbox)

            if shared and target_user and permissions:
                if not exists:
                    status, data = imap.create(mailbox)
                    if status != "OK":
                        echo(f"Create mailbox failed: {data}", level="error")
                        imap.logout()
                        return 1
                    echo(f"Created mailbox: {mailbox}")

                current_acl = get_current_acl(imap, mailbox, target_user)
                if current_acl:
                    echo(f"Current ACL for {target_user}: {cyrusperms(current_acl)}")

                update_acl = inputboolean(f"Update ACL for {target_user} to '{permissions}'? (Y/N)")
                if update_acl is None:
                    imap.logout()
                    echo("Cancelled", level="warn")
                    return 1

                if update_acl:
                    status, data = imap.setacl(mailbox, target_user, permissions)
                    if status == "OK":
                        echo(f"Set ACL: {target_user} = {permissions}")
                    else:
                        echo(f"Set ACL failed: {data}", level="error")
                        imap.logout()
                        return 1
            elif not exists:
                status, data = imap.create(mailbox)
                if status != "OK":
                    echo(f"Create mailbox failed: {data}", level="error")
                    imap.logout()
                    return 1
                echo(f"Created mailbox: {mailbox}")
            else:
                echo("Mailbox already exists, no changes needed")

            status, myrights = imap.myrights(mailbox)
            if status == "OK":
                echo(f"My rights on {mailbox}: {cyrusperms(myrights[0].decode().strip('() '))}")

            imap.logout()
            return 0

        except imaplib.IMAP4.error as e:
            echo(f"IMAP error: {e}", level="error")
            return 1

    except KeyboardInterrupt:
        echo("{/all}**INTR**")
        return 1


if __name__ == "__main__":
    sys.exit(main())