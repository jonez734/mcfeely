#!/usr/bin/env python3
# imap_test.py
# Test IMAP login to verify the postoffice-authd auth chain is working.
# Prompts for username and password (password masked with X's).

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

        echo(f"Connecting to localhost:993 as {username}...")

        import imaplib
        try:
            imap = imaplib.IMAP4_SSL("localhost", 993)
            imap.login(username, password)
            echo("IMAP LOGIN OK")
            imap.logout()
            return 0
        except imaplib.IMAP4.error as e:
            echo(f"IMAP login failed: {e}", level="error")
            return 1

    except KeyboardInterrupt:
        echo("{/all}**INTR**")
        return 1


if __name__ == "__main__":
    sys.exit(main())