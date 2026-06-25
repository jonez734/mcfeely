#!/usr/bin/env python3
# mistermcfeely/tests/test_postoffice_imap_polling.py
# Tests for IMAP connection and envelope handling.
# (Now uses postoffice.services from mistermcfeely)

import imaplib
import pytest
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/home/opencode/data/work/mistermcfeely/src")


@pytest.mark.integration
class TestIMAPCountUnseen(unittest.TestCase):
    """Test IMAP count_unseen service function."""

    def test_count_unseen_with_ssl(self):
        """Test count_unseen with SSL connection."""
        from postoffice.services import MailboxConfig
        from postoffice.services.imap_client import count_unseen

        mb = MailboxConfig(host="imap.test.com", username="user", password="pass", use_ssl=True)

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2 3"])

        with patch("postoffice.services.imap_client.connect", return_value=mock_conn):
            count = count_unseen(mb)
        self.assertEqual(count, 3)

    def test_count_unseen_without_ssl(self):
        """Test count_unseen without SSL connection."""
        from postoffice.services import MailboxConfig
        from postoffice.services.imap_client import count_unseen

        mb = MailboxConfig(host="imap.test.com", username="user", password="pass", use_ssl=False, port=143)

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b""])

        with patch("postoffice.services.imap_client.connect", return_value=mock_conn):
            count = count_unseen(mb)
        self.assertEqual(count, 0)

    def test_count_unseen_handles_connection_error(self):
        """Test count_unseen handles connection error."""
        from postoffice.services import MailboxConfig
        from postoffice.services.imap_client import count_unseen

        mb = MailboxConfig(host="invalid.test.com", username="user", password="pass")

        with patch("postoffice.services.imap_client.connect", side_effect=Exception("Connection refused")):
            count = count_unseen(mb)
        self.assertEqual(count, 0)


@pytest.mark.integration
class TestFetchEnvelopes(unittest.TestCase):
    """Test fetch_envelopes service function."""

    def test_fetch_envelopes_returns_list(self):
        """Test fetch_envelopes returns envelope list."""
        from postoffice.services.imap_client import fetch_envelopes

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2 3 4 5"])
        mock_conn.fetch.return_value = ("OK", [(b"1 (ENVELOPE (...)", b"ENVELOPE_DATA")])

        envelopes = fetch_envelopes(mock_conn, limit=5)
        self.assertEqual(len(envelopes), 5)

    def test_fetch_envelopes_limits_to_n(self):
        """Test fetch_envelopes limits to N messages."""
        from postoffice.services.imap_client import fetch_envelopes

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2 3 4 5 6 7 8 9 10"])
        mock_conn.fetch.return_value = ("OK", [(b"1 (ENVELOPE (...)", b"ENVELOPE_DATA")])

        envelopes = fetch_envelopes(mock_conn, limit=5)
        self.assertEqual(len(envelopes), 5)

    def test_fetch_envelopes_handles_no_messages(self):
        """Test fetch_envelopes with no UNSEEN messages."""
        from postoffice.services.imap_client import fetch_envelopes

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b""])

        envelopes = fetch_envelopes(mock_conn, limit=5)
        self.assertEqual(envelopes, [])


@pytest.mark.integration
class TestExtractPreview(unittest.TestCase):
    """Test extract_preview service function."""

    def test_extract_preview_basic(self):
        """Test basic envelope preview extraction."""
        from postoffice.services.imap_client import extract_preview
        from email.parser import BytesParser
        from email.policy import default

        parser = BytesParser(policy=default)
        raw_msg = (
            "From: sender@example.com\r\n"
            "Subject: Test Subject\r\n"
            "\r\n"
            "This is the body."
        ).encode()
        msg = parser.parsebytes(raw_msg)
        envelope = msg.as_bytes()

        result = extract_preview(envelope)
        self.assertIn("sender@example.com", result["sender"])
        self.assertIn("Test Subject", result["subject"])
        self.assertIn("This is the body.", result["preview"])

    def test_extract_preview_multipart(self):
        """Test preview extraction with multipart message."""
        from postoffice.services.imap_client import extract_preview
        from email.parser import BytesParser
        from email.policy import default

        parser = BytesParser(policy=default)
        raw_msg = (
            "From: sender@example.com\r\n"
            "Subject: Multipart Test\r\n"
            "MIME-Version: 1.0\r\n"
            "Content-Type: multipart/alternative; boundary=boundary\r\n"
            "\r\n"
            "--boundary\r\n"
            "Content-Type: text/plain\r\n"
            "\r\n"
            "Plain text body."
            "\r\n--boundary\r\n"
            "Content-Type: text/html\r\n"
            "\r\n"
            "<html>HTML body</html>"
            "\r\n--boundary--"
        ).encode()
        msg = parser.parsebytes(raw_msg)
        envelope = msg.as_bytes()

        result = extract_preview(envelope)
        self.assertIn("sender@example.com", result["sender"])
        self.assertIn("Multipart Test", result["subject"])
        self.assertIn("Plain text body.", result["preview"])

    def test_extract_preview_body_limit(self):
        """Test body preview is limited."""
        from postoffice.services.imap_client import extract_preview
        from email.parser import BytesParser
        from email.policy import default

        long_body = "A" * 1000
        parser = BytesParser(policy=default)
        raw_msg = (
            "From: sender@example.com\r\n"
            "Subject: Long Body Test\r\n"
            "\r\n"
            + long_body
        ).encode()
        msg = parser.parsebytes(raw_msg)
        envelope = msg.as_bytes()

        result = extract_preview(envelope, body_limit=500)
        self.assertLessEqual(len(result["preview"]), 500)


@pytest.mark.integration
class TestNotifyNewMessages(unittest.TestCase):
    """Test notify_new_messages service function."""

    def test_notify_new_messages_calls_message_send(self):
        """Test notify_new_messages calls bbsengine6 message_send once per envelope."""
        from postoffice.services import notification as svc_notification
        from postoffice.services.notification import notify_new_messages

        envelopes = [b"from a", b"from b"]
        with patch("postoffice.services.notification.message_send") as mock_send:
            sent = notify_new_messages(envelopes)
        self.assertEqual(sent, 2)
        self.assertEqual(mock_send.call_count, 2)

    def test_notify_new_messages_uses_postoffice_sender(self):
        """Test notify_new_messages uses postoffice as sender_moniker."""
        from postoffice.services.notification import notify_new_messages

        with patch("postoffice.services.notification.message_send") as mock_send:
            notify_new_messages([b"x"])
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["sender_moniker"], "postoffice")
        self.assertEqual(call_kwargs["notification_type"], "postoffice.email")
        self.assertEqual(call_kwargs["recipients"], ["@everyone"])


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestIMAPCountUnseen))
    suite.addTests(loader.loadTestsFromTestCase(TestFetchEnvelopes))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractPreview))
    suite.addTests(loader.loadTestsFromTestCase(TestNotifyNewMessages))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
