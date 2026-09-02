#!/usr/bin/env python3
# imap_test_delete_mailbox.py
# Test IMAP: deletes a mailbox after showing message count and confirming.

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from bbsengine6 import util
from bbsengine6.io import echo, inputstring, inputboolean


def get_message_count(imap: "imaplib.IMAP4", mailbox: str) -> int | None:
    status, data = imap.status(mailbox, "(MESSAGES)")
    if status != "OK":
        return None
    try:
        response = data[0].decode()
        parts = response.split()
        for i, part in enumerate(parts):
            if part == b"MESSAGES" and i + 1 < len(parts):
                return int(parts[i + 1].rstrip(b")"))
    except (IndexError, ValueError):
        pass
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

        mailbox = inputstring("Mailbox name to delete (e.g. INBOX or user.name): ").strip()
        if not mailbox:
            echo("Cancelled", level="warn")
            return 1

        echo(f"Connecting to localhost:993 as {username}...")

        import imaplib
        try:
            imap = imaplib.IMAP4_SSL("localhost", 993)
            imap.login(username, password)
            echo("IMAP LOGIN OK")

            status, _ = imap.status(mailbox, "(MESSAGES)")
            if status != "OK":
                echo(f"Mailbox '{mailbox}' does not exist", level="error")
                imap.logout()
                return 1

            count = get_message_count(imap, mailbox)

            echo(f"\nMailbox: {mailbox}")
            if count is not None:
                echo(f"Messages: {count}")
            else:
                echo("Messages: unknown")

            echo()
            confirm = inputboolean(f"Permanently DELETE mailbox '{mailbox}' and all {count if count else 0} messages? (Y/N)")
            if confirm is None or not confirm:
                echo("Cancelled", level="warn")
                imap.logout()
                return 1

            status, data = imap.delete(mailbox)
            if status == "OK":
                echo(f"Deleted mailbox: {mailbox}")
            else:
                echo(f"Delete failed: {data}", level="error")
                imap.logout()
                return 1

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
