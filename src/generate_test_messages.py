#!/usr/bin/env python3
# generate_test_messages.py
# Standalone script to generate random test messages and store to IMAP

import argparse
import configparser
import email
import imaplib
import random
import string
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from pathlib import Path
from typing import Optional

# Import postoffice modules
try:
    from postoffice import startup
    from bbsengine6.io import echo
except ImportError:
    print("Error: postoffice module not found. Run from mistermcfeely/src directory.")
    sys.exit(1)


class SimpleArgs:
    """Simple args object for IMAP configuration."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 993,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.imaphost = host
        self.imapport = port
        self.imapuser = user
        self.imappassword = password


class MessageGenerator:
    """Generate and store random test messages to IMAP."""

    def __init__(
        self,
        username: str,
        imap_password: str,
        verbose: bool = False,
        shared_mailbox: Optional[str] = None,
        imap_host: Optional[str] = None,
        imap_port: Optional[int] = None,
    ):
        self.username = username
        self.imap_password = imap_password
        self.verbose = verbose
        self.shared_mailbox = shared_mailbox  # e.g., "shared/support@local"

        # Load config from ~/.postoffice if not provided as args
        config_host, config_port = self._load_config()
        self.imap_host = imap_host or config_host or "localhost"
        self.imap_port = imap_port or config_port or 993

        if self.verbose:
            echo(f"IMAP config: host={self.imap_host}, port={self.imap_port}")

        self.imap: Optional[imaplib.IMAP4_SSL] = None

        self.subjects = [
            "Password reset request",
            "Support ticket: Cannot login",
            "Feature request: Two-factor auth",
            "Bug report: Messages not syncing",
            "Account issue: Missing emails",
            "Question about API limits",
            "Help with email forwarding",
            "Question about storage quota",
            "Request for feature X",
            "Issue with spam filtering",
            "Help: Setting up IMAP",
            "Urgent: Account locked",
            "Feedback on new interface",
            "Question about pricing",
            "Technical support needed",
            "Configuration assistance",
            "Data export request",
            "Account upgrade question",
            "Integration help needed",
            "Performance issue report",
        ]

        self.body_templates = [
            "Hi, I'm having trouble with my account. Can you help? {details}",
            "Hello, I have a question about {topic}. {details} Thanks!",
            "I encountered an issue when trying to {action}. {details} Please advise.",
            "Could you please help me with {topic}? {details} I would appreciate it.",
            "I'm reaching out because {reason}. {details} What should I do?",
            "Hi there, {details} Can someone take a look? {topic}",
            "I need assistance with {topic}. {details} Please let me know.",
            "Hello, {details} How can I resolve this {issue}?",
            "Hi, {reason}. {details} Can you help?",
            "I'm contacting you about {topic}. {details} Thank you!",
        ]

        self.details = [
            "I've tried everything I can think of",
            "This is urgent and affecting my work",
            "I'm not sure what to do",
            "Could you provide more information",
            "I have a few follow-up questions",
            "Please let me know as soon as possible",
            "I would really appreciate your help",
            "This is blocking my progress",
            "Can you look into this",
            "I'm stuck and need assistance",
        ]

        self.senders = [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com",
            "diana@example.com",
            "eve@example.com",
            "frank@example.com",
            "grace@example.com",
            "henry@example.com",
            "iris@example.com",
            "jack@example.com",
            "kate@example.com",
            "liam@example.com",
            "mona@example.com",
            "noah@example.com",
            "olivia@example.com",
        ]

    def run(self) -> bool:
        """Generate and store test messages."""
        if not startup.startup(verbose=self.verbose):
            echo("Failed to initialize postoffice", level="error")
            return False

        if not self._connect_imap():
            return False

        try:
            self._generate_and_store_messages()
            return True
        finally:
            if self.imap:
                try:
                    self.imap.logout()
                except Exception:
                    pass

    def _load_config(self) -> tuple:
        """Load IMAP configuration from ~/.postoffice file."""
        config_path = Path.home() / ".postoffice"
        imap_host = "localhost"
        imap_port = 993

        if config_path.exists():
            try:
                config = configparser.ConfigParser()
                config.read(config_path)
                if config.has_section("imap"):
                    imap_host = config.get("imap", "host", fallback="localhost")
                    imap_port = config.getint("imap", "port", fallback=993)
            except Exception as e:
                echo(f"Warning: Could not read config: {e}", level="error")

        return imap_host, imap_port

    def _connect_imap(self) -> bool:
        """Connect to IMAP server with provided credentials."""
        if self.verbose:
            echo(f"Connecting to IMAP {self.imap_host}:{self.imap_port}...", level="debug")

        try:
            self.imap = imaplib.IMAP4_SSL(
                self.imap_host, self.imap_port, timeout=10
            )

            # Login with provided credentials
            status, response = self.imap.login(self.username, self.imap_password)
            if status != "OK":
                echo(f"Failed to authenticate: {response}", level="error")
                return False

            if self.verbose:
                echo(f"✓ Connected to IMAP as {self.username}", level="debug")
            return True

        except imaplib.IMAP4.error as e:
            echo(f"IMAP authentication failed: {e}", level="error")
            return False
        except Exception as e:
            echo(f"Failed to connect to IMAP: {e}", level="error")
            return False

    def _generate_and_store_messages(self, count: int = 10) -> None:
        """Generate and store random test messages."""
        if self.verbose:
            echo(f"Generating {count} test messages...", level="debug")

        # Select mailbox
        mailbox = self.shared_mailbox or "INBOX"
        status, _ = self.imap.select(mailbox)
        if status != "OK":
            echo(f"Failed to select mailbox '{mailbox}'", level="error")
            return

        for i in range(count):
            msg = self._create_message()
            try:
                # Append to mailbox
                status, response = self.imap.append(
                    mailbox, None, None, msg.as_bytes()
                )
                if status == "OK":
                    if self.verbose:
                        echo(f"✓ Message {i+1}/{count} stored", level="debug")
                else:
                    echo(f"Failed to store message {i+1}: {response}", level="error")
            except Exception as e:
                echo(f"Error storing message {i+1}: {e}", level="error")

        echo(f"✓ Generated {count} test messages in '{mailbox}'", level="info")

    def _create_message(self) -> MIMEMultipart:
        """Create a random test message."""
        msg = MIMEMultipart("alternative")

        # Headers
        msg["From"] = random.choice(self.senders)
        msg["To"] = f"{self.username}@localhost"
        msg["Subject"] = random.choice(self.subjects)
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = email.utils.make_msgid()

        # Body
        topic = random.choice(["authentication", "storage", "sync", "performance"])
        action = random.choice(["log in", "configure", "upgrade", "migrate"])
        reason = random.choice(["I need help", "I have a question", "Something went wrong"])
        issue = random.choice(["problem", "issue", "error", "situation"])

        body_template = random.choice(self.body_templates)
        body_text = body_template.format(
            topic=topic,
            action=action,
            reason=reason,
            issue=issue,
            details=random.choice(self.details),
        )

        msg.attach(MIMEText(body_text, "plain"))

        return msg

    def _generate_password(self, length: int = 16) -> str:
        """Generate a random password."""
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(random.choice(chars) for _ in range(length))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="python generate_test_messages.py",
        description="Generate random test messages for IMAP mailbox",
    )

    parser.add_argument(
        "--username",
        "-u",
        required=True,
        help="IMAP username (login name)",
    )

    parser.add_argument(
        "--password",
        "-p",
        help="IMAP password (will prompt if not provided)",
    )

    parser.add_argument(
        "--number",
        "-n",
        type=int,
        default=10,
        help="Number of messages to generate (default: 10)",
    )

    parser.add_argument(
        "--imap-host",
        type=str,
        help="IMAP hostname (default: localhost or from ~/.postoffice)",
    )

    parser.add_argument(
        "--imap-port",
        type=int,
        help="IMAP port (default: 993)",
    )

    parser.add_argument(
        "--shared-mailbox",
        type=str,
        help="Shared mailbox name (e.g., 'shared/support')",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )

    args = parser.parse_args()

    # Get password if not provided
    password = args.password
    if not password:
        import getpass

        password = getpass.getpass(f"Enter IMAP password for {args.username}: ")

    if not password:
        echo("Error: Password required", level="error")
        return 1

    # Initialize password system
    echo("Ensuring ~/.password directory exists...", level="debug")
    echo("Initializing postoffice database schema...", level="debug")

    # Create generator
    generator = MessageGenerator(
        username=args.username,
        imap_password=password,
        verbose=args.verbose,
        shared_mailbox=args.shared_mailbox,
        imap_host=args.imap_host,
        imap_port=args.imap_port,
    )

    # Run generator
    echo(f"Generating {args.number} test messages for {args.username}...", level="info")

    if generator.run():
        echo(f"✓ Successfully generated {args.number} test messages", level="info")
        return 0
    else:
        echo("Failed to generate test messages", level="error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
