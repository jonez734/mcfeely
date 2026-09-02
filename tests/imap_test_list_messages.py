#!/usr/bin/env python3
# imap_test_list_messages.py
# Test IMAP login and list messages in a given folder.
# Prompts for username, password (password masked with X's), and folder name.

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from bbsengine6 import util
from bbsengine6.io import echo, inputstring


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

        folder = inputstring("Folder name (e.g. INBOX): ").strip()
        if not folder:
            echo("Cancelled", level="warn")
            return 1

        echo(f"Connecting to localhost:993 as {username}...")

        import imaplib
        try:
            imap = imaplib.IMAP4_SSL("localhost", 993)
            imap.login(username, password)
            echo("IMAP LOGIN OK")

            status, counts = imap.status(folder, "(MESSAGES RECENT UNSEEN)")
            if status == "OK":
                echo(f"Folder '{folder}' status: {counts[0].decode()}")
            else:
                echo(f"Could not get folder status", level="warn")

            status, msg_ids = imap.select(folder)
            if status != "OK":
                echo(f"Could not select folder '{folder}'", level="error")
                imap.logout()
                return 1

            status, msg_ids = imap.search(None, "ALL")
            if status != "OK":
                echo(f"Could not search folder", level="error")
                imap.logout()
                return 1

            message_ids = msg_ids[0].split()
            echo(f"Total messages in {folder}: {len(message_ids)}")

            if message_ids:
                echo("Recent messages (last 10):")
                recent = message_ids[-10:]
                for msg_id in recent:
                    status, msg_data = imap.fetch(msg_id, "(ENVELOPE)")
                    if status == "OK" and msg_data and msg_data[0]:
                        envelope = msg_data[0]
                        echo(f"  [{msg_id.decode()}] {envelope}")
                    else:
                        echo(f"  [{msg_id.decode()}] (could not fetch)")

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
