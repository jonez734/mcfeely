#!/usr/bin/env python3
# imap_test_send.py
# Test IMAP: creates a message and appends it to a folder.
# Prompts for username, password (masked), folder name, subject, and body.

import sys
import os
import time
from datetime import datetime

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

        subject = inputstring("Subject: ").strip()
        if not subject:
            echo("Cancelled", level="warn")
            return 1

        echo("Body (end with empty line):")
        lines = []
        while True:
            try:
                line = inputstring("")
                if line == "":
                    break
                lines.append(line)
            except EOFError:
                break

        body = "\r\n".join(lines)

        echo(f"Connecting to localhost:993 as {username}...")

        import imaplib
        try:
            imap = imaplib.IMAP4_SSL("localhost", 993)
            imap.login(username, password)
            echo("IMAP LOGIN OK")

            status, _ = imap.status(folder, "(MESSAGES)")
            if status != "OK":
                echo(f"Folder '{folder}' does not exist", level="error")
                imap.logout()
                return 1

            now = datetime.now().strftime("%d-%b-%Y %H:%M:%S +0000")
            message = (
                f"From: {username}@localhost\r\n"
                f"Date: {now}\r\n"
                f"Subject: {subject}\r\n"
                f"To: {username}@localhost\r\n"
                f"\r\n"
                f"{body}\r\n"
            )

            imap.append(folder, "", imaplib.Time2Internaldate(time.time()), message.encode())
            echo(f"Message appended to {folder}")

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