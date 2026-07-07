#!/usr/bin/env python3
# imap_test_list_mailboxes.py
# Test IMAP login and list mailboxes with their ACL/permissions.
# Prompts for username and password (password masked with X's).

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from bbsengine6 import util
from bbsengine6.io import echo, inputstring
from postoffice.lib import cyrusperms


def main() -> int:
    try:
        username = inputstring("IMAP username: ").strip()
        if not username:
            echo("Cancelled", level="warn")
            return 1

        password = util.inputpassword("Password: ", mask="X")
        if not password:
            echo("Cancelled", level="warn")
            return 1

        echo(f"Connecting to localhost:993 as {username}...")

        import imaplib
        try:
            imap = imaplib.IMAP4_SSL("localhost", 993)
            imap.login(username, password)
            echo("IMAP LOGIN OK")

            status, mailbox_list = imap.list()
            if status != "OK":
                echo("Could not list mailboxes", level="error")
                imap.logout()
                return 1

            echo(f"\nMailboxes ({len(mailbox_list)}):\n")

            for entry in mailbox_list:
                parts = entry.decode().split(' "/" ')
                if len(parts) == 2:
                    flags_and_delim, mailbox_name = parts
                    flags_and_delim = flags_and_delim.strip('()')
                    echo(f"  {mailbox_name}")

                    try:
                        status, acl_data = imap.lsub('""', mailbox_name)
                        if status == "OK" and acl_data:
                            echo(f"    Subscribed: yes")
                        else:
                            echo(f"    Subscribed: no")
                    except Exception:
                        pass

                    try:
                        status, myrights = imap.myrights(mailbox_name)
                        if status == "OK":
                            echo(f"    My rights: {cyrusperms(myrights[0].decode().strip('() '))}")
                    except Exception:
                        pass

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
