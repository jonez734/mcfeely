#!/usr/bin/env python3
# mistermcfeely/tests/test_postoffice_notification.py
# Tests for notification content / formatting.
# (Now uses postoffice.services.notification from mistermcfeely)

import pytest
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "/home/opencode/data/work/mistermcfeely/src")


def _envelope(from_, subject, body):
    """Build a real RFC822 envelope for testing."""
    from email.parser import BytesParser
    from email.policy import default
    parser = BytesParser(policy=default)
    raw = (
        f"From: {from_}\r\n"
        f"Subject: {subject}\r\n"
        "\r\n"
        f"{body}"
    ).encode()
    return parser.parsebytes(raw).as_bytes()


@pytest.mark.integration
class TestBuildEmailPayload(unittest.TestCase):
    """Test notification payload formatting (build_email_payload)."""

    def test_notification_includes_sender(self):
        """Notification includes sender address and display name."""
        from postoffice.services.notification import build_email_payload
        payload = build_email_payload(_envelope("John Doe <john@example.com>", "Hi", "body"))
        self.assertIn("john@example.com", payload)
        self.assertIn("John Doe", payload)

    def test_notification_includes_subject(self):
        """Notification includes subject."""
        from postoffice.services.notification import build_email_payload
        payload = build_email_payload(_envelope("sender@example.com", "Important Message", "body"))
        self.assertIn("Important Message", payload)

    def test_notification_includes_body_preview(self):
        """Notification includes body preview."""
        from postoffice.services.notification import build_email_payload
        payload = build_email_payload(_envelope("a@b.c", "Test", "This is the preview text."))
        self.assertIn("This is the preview text.", payload)

    def test_notification_sender_moniker(self):
        """notify_new_messages uses postoffice as sender_moniker."""
        from postoffice.services.notification import notify_new_messages
        with patch("postoffice.services.notification.message_send") as mock_send:
            notify_new_messages([_envelope("a@b.c", "Test", "Body.")])
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["sender_moniker"], "postoffice")

    def test_notification_recipient_is_everyone(self):
        """notify_new_messages sends to @everyone by default."""
        from postoffice.services.notification import notify_new_messages
        with patch("postoffice.services.notification.message_send") as mock_send:
            notify_new_messages([_envelope("a@b.c", "Test", "Body.")])
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["recipients"], ["@everyone"])

    def test_notification_message_type(self):
        """Notification uses postoffice.email message type."""
        from postoffice.services.notification import notify_new_messages
        with patch("postoffice.services.notification.message_send") as mock_send:
            notify_new_messages([_envelope("a@b.c", "Test", "Body.")])
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["notification_type"], "postoffice.email")

    def test_notification_format(self):
        """Notification format includes From / Subject / body lines."""
        from postoffice.services.notification import build_email_payload
        payload = build_email_payload(
            _envelope("test@sender.com", "Newsletter", "This is the email content.")
        )
        self.assertTrue(payload.startswith("From:"))
        self.assertIn("Subject:", payload)
        self.assertIn("This is the email content.", payload)


@pytest.mark.integration
class TestNotificationErrors(unittest.TestCase):
    """Test notification graceful handling of missing headers."""

    def test_handles_missing_from_header(self):
        """Missing From header renders as 'Unknown'."""
        from postoffice.services.notification import build_email_payload
        payload = build_email_payload(_envelope("", "No From Header", "Body."))
        self.assertIn("Unknown", payload)

    def test_handles_missing_subject(self):
        """Missing Subject header renders as 'No Subject'."""
        from postoffice.services.notification import build_email_payload
        payload = build_email_payload(_envelope("sender@example.com", "", "Body."))
        self.assertIn("No Subject", payload)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestBuildEmailPayload))
    suite.addTests(loader.loadTestsFromTestCase(TestNotificationErrors))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
