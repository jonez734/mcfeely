#!/usr/bin/env python3
# imap_test_admin.py
# Test IMAP: grant permissions using admin account.
# Prompts for admin username, password, and action.

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from bbsengine6 import util
from bbsengine6.io import echo, inputstring


def main() -> int:
    try:
        admin_user = inputstring("IMAP admin username [cyrus]: ").strip()
        if not admin_user:
            admin_user = "cyrus"

        password = util.inputpassword("Password: ", mask="X")
        if not password:
            echo("Cancelled", level="warn")
            return 1

        echo(f"\nConnecting to localhost:143 as {admin_user}...")

        from postoffice.cyrus_admin import CyrusAdmin

        try:
            with CyrusAdmin("localhost", 143, admin_user) as admin:
                admin.login(password)
                echo("IMAP LOGIN OK\n")

                echo("Actions:")
                echo("  1 - Grant folder creation rights to user")
                echo("  2 - List mailboxes")
                echo("  3 - Grant admin rights on user's mailbox")
                echo("  4 - Create user's mailbox if missing")
                echo()

                choice = inputstring("Action: ").strip()
                if choice == "1":
                    target = inputstring("Username to grant: ").strip()
                    if not target:
                        echo("Cancelled", level="warn")
                        return 1
                    mailbox = f"user.{target}"
                    echo(f"Granting create rights on {mailbox} to {target}...")
                    if admin.set_acl(mailbox, target, "lrswcd"):
                        echo("Done - user can now create mailboxes.")
                    else:
                        echo("Failed", level="error")

                elif choice == "2":
                    mailboxes = admin.list_mailboxes()
                    echo(f"\nMailboxes ({len(mailboxes)}):")
                    for mb in mailboxes:
                        echo(f"  {mb}")

                elif choice == "3":
                    target = inputstring("Username: ").strip()
                    if not target:
                        echo("Cancelled", level="warn")
                        return 1
                    mailbox = f"user.{target}"
                    echo(f"Granting admin rights on {mailbox} to {target}...")
                    if admin.set_acl(mailbox, target, "lrswcida"):
                        echo("Done.")
                    else:
                        echo("Failed", level="error")

                elif choice == "4":
                    target = inputstring("Username: ").strip()
                    if not target:
                        echo("Cancelled", level="warn")
                        return 1
                    mailbox = f"user.{target}"
                    echo(f"Creating mailbox {mailbox}...")
                    if admin.create_user_mailbox(target):
                        echo("Done.")
                    else:
                        echo("Failed", level="error")

                else:
                    echo("Unknown action.", level="warn")
                    return 1

                return 0

        except Exception as e:
            echo(f"Error: {e}", level="error")
            return 1

    except KeyboardInterrupt:
        echo("{/all}**INTR**")
        return 1


if __name__ == "__main__":
    sys.exit(main())
