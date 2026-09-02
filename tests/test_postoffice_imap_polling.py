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

    def test_fetch_envelopes_returns_envelopes_and_ids(self):
        """Test fetch_envelopes returns (envelopes, message_ids) tuple."""
        from postoffice.services.imap_client import fetch_envelopes

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2 3 4 5"])
        mock_conn.fetch.return_value = ("OK", [(b"1 (ENVELOPE (...)", b"ENVELOPE_DATA")])

        envelopes, message_ids = fetch_envelopes(mock_conn, limit=5)
        self.assertEqual(len(envelopes), 5)
        self.assertEqual(len(message_ids), 5)
        # By position: the i-th envelope came from the i-th id.
        self.assertEqual(message_ids[0], b"1")
        self.assertEqual(message_ids[-1], b"5")

    def test_fetch_envelopes_limits_to_n(self):
        """Test fetch_envelopes limits to N messages."""
        from postoffice.services.imap_client import fetch_envelopes

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2 3 4 5 6 7 8 9 10"])
        mock_conn.fetch.return_value = ("OK", [(b"1 (ENVELOPE (...)", b"ENVELOPE_DATA")])

        envelopes, message_ids = fetch_envelopes(mock_conn, limit=5)
        self.assertEqual(len(envelopes), 5)
        self.assertEqual(len(message_ids), 5)

    def test_fetch_envelopes_handles_no_messages(self):
        """Test fetch_envelopes with no UNSEEN messages."""
        from postoffice.services.imap_client import fetch_envelopes

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b""])

        envelopes, message_ids = fetch_envelopes(mock_conn, limit=5)
        self.assertEqual(envelopes, [])
        self.assertEqual(message_ids, [])

    def test_fetch_envelopes_skips_unfetchable_ids(self):
        """An id whose FETCH returns non-OK is skipped (and not added
        to the message_ids list, so the poller can't STORE a flag on
        something we never actually retrieved).
        """
        from postoffice.services.imap_client import fetch_envelopes

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2"])
        mock_conn.fetch.side_effect = [
            ("OK", [(b"1 (ENVELOPE (...)", b"DATA1")]),
            ("NO", [b""]),
        ]

        envelopes, message_ids = fetch_envelopes(mock_conn, limit=5)
        self.assertEqual(len(envelopes), 1)
        self.assertEqual(message_ids, [b"1"])


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


@pytest.mark.integration
class TestMailboxConfigRecipients(unittest.TestCase):
    """MailboxConfig.recipients: per-mailbox notification targeting."""

    def test_recipients_default_is_none(self):
        """MailboxConfig without an explicit recipients list keeps
        ``recipients=None`` so the poller falls back to ``@everyone``.
        """
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(host="imap.example.com", username="u", password="p")
        self.assertIsNone(mb.recipients)

    def test_recipients_round_trip(self):
        """MailboxConfig retains the recipients list it's given."""
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(
            host="imap.example.com",
            username="u",
            password="p",
            recipients=["alice", "@support"],
        )
        self.assertEqual(mb.recipients, ["alice", "@support"])

    def test_load_mailboxes_passes_recipients(self):
        """load_mailboxes reads ``recipients`` from each config entry."""
        from postoffice.services import MailboxConfig, load_mailboxes

        config = {
            "mailboxes": [
                {
                    "host": "imap.example.com",
                    "username": "shared",
                    "password": "p",
                    "recipients": ["@support"],
                },
                {
                    "host": "imap.example.com",
                    "username": "u2",
                    "password": "p",
                },
            ]
        }
        mailboxes = load_mailboxes(config)
        self.assertEqual(len(mailboxes), 2)
        self.assertEqual(mailboxes[0].recipients, ["@support"])
        self.assertIsNone(mailboxes[1].recipients)

    def test_load_mailboxes_rejects_non_list_recipients(self):
        """A non-list ``recipients`` value raises ValueError loudly
        instead of silently coercing to a malformed default.
        """
        from postoffice.services import load_mailboxes

        with self.assertRaises(ValueError):
            load_mailboxes(
                {
                    "mailboxes": [
                        {
                            "host": "imap.example.com",
                            "username": "shared",
                            "password": "p",
                            "recipients": "alice,@support",
                        }
                    ]
                }
            )


@pytest.mark.integration
class TestMailboxPollerRecipients(unittest.TestCase):
    """MailboxPoller passes MailboxConfig.recipients through to
    notify_new_messages (instead of hard-coding ``@everyone``)."""

    def _new_poller(self):
        """Return a MailboxPoller bypassing __init__."""
        from postoffice.services import mailbox_poller

        return mailbox_poller.MailboxPoller.__new__(mailbox_poller.MailboxPoller)

    def test_poller_forwards_recipients(self):
        """When a mailbox configures recipients, those are passed
        through verbatim to notify_new_messages.
        """
        from postoffice.services import MailboxConfig

        poller = self._new_poller()
        mb = MailboxConfig(
            host="imap.example.com",
            username="shared",
            password="p",
            recipients=["alice", "bob", "@support"],
        )
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2"])
        mock_conn.fetch.return_value = ("OK", [(b"1 (ENVELOPE ...)", b"DATA")])

        with patch(
            "postoffice.services.mailbox_poller.svc_imap.connect",
            return_value=mock_conn,
        ), patch(
            "postoffice.services.notification.notify_new_messages",
        ) as mock_notify:
            poller._check_mailbox_sync(mb)

        mock_notify.assert_called_once()
        kwargs = mock_notify.call_args.kwargs
        self.assertEqual(kwargs["recipients"], ["alice", "bob", "@support"])
        # The ``to`` label should reflect the configured mailbox.
        self.assertIn("shared@imap.example.com/INBOX", kwargs["to"])

    def test_poller_falls_back_to_everyone(self):
        """A mailbox without recipients gets the @everyone fallback
        passed through (None -> notify_new_messages defaults to it).
        """
        from postoffice.services import MailboxConfig

        poller = self._new_poller()
        mb = MailboxConfig(
            host="imap.example.com", username="u", password="p"
        )  # recipients=None
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.fetch.return_value = ("OK", [(b"1 (ENVELOPE ...)", b"DATA")])

        with patch(
            "postoffice.services.mailbox_poller.svc_imap.connect",
            return_value=mock_conn,
        ), patch(
            "postoffice.services.notification.notify_new_messages",
        ) as mock_notify:
            poller._check_mailbox_sync(mb)

        mock_notify.assert_called_once()
        kwargs = mock_notify.call_args.kwargs
        self.assertIsNone(kwargs["recipients"])  # let notify_new_messages default it


@pytest.mark.integration
class TestMailboxPollerMarksSeen(unittest.TestCase):
    """After notifying, the poller marks the fetched messages \\Seen
    so the next poll doesn't re-notify the same batch."""

    def _new_poller(self):
        from postoffice.services import mailbox_poller

        return mailbox_poller.MailboxPoller.__new__(mailbox_poller.MailboxPoller)

    def test_marks_all_fetched_ids_seen(self):
        """Each id returned by fetch_envelopes is STOREd with +FLAGS \\Seen."""
        from postoffice.services import MailboxConfig

        poller = self._new_poller()
        mb = MailboxConfig(
            host="imap.example.com", username="u", password="p"
        )
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2 3"])
        mock_conn.fetch.return_value = ("OK", [(b"1 (ENVELOPE ...)", b"DATA")])

        with patch(
            "postoffice.services.mailbox_poller.svc_imap.connect",
            return_value=mock_conn,
        ), patch(
            "postoffice.services.notification.notify_new_messages",
        ):
            poller._check_mailbox_sync(mb)

        self.assertEqual(mock_conn.store.call_count, 3)
        for call in mock_conn.store.call_args_list:
            args, _ = call
            self.assertEqual(args[1], "+FLAGS")
            self.assertEqual(args[2], "\\Seen")

    def test_no_store_when_no_messages(self):
        """An empty mailbox produces no STORE calls (no work to ack)."""
        from postoffice.services import MailboxConfig

        poller = self._new_poller()
        mb = MailboxConfig(
            host="imap.example.com", username="u", password="p"
        )
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b""])

        with patch(
            "postoffice.services.mailbox_poller.svc_imap.connect",
            return_value=mock_conn,
        ), patch(
            "postoffice.services.notification.notify_new_messages",
        ) as mock_notify:
            poller._check_mailbox_sync(mb)

        mock_notify.assert_not_called()
        mock_conn.store.assert_not_called()

    def test_store_failure_does_not_abort_others(self):
        """A STORE failure on one id is logged and the loop continues
        for the remaining ids.
        """
        from postoffice.services import MailboxConfig

        poller = self._new_poller()
        mb = MailboxConfig(
            host="imap.example.com", username="u", password="p"
        )
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2 3"])
        mock_conn.fetch.return_value = ("OK", [(b"1 (ENVELOPE ...)", b"DATA")])

        # Fail on the second STORE; first and third succeed.
        responses = [None, Exception("STORE failed"), None]
        mock_conn.store.side_effect = responses

        with patch(
            "postoffice.services.mailbox_poller.svc_imap.connect",
            return_value=mock_conn,
        ), patch(
            "postoffice.services.notification.notify_new_messages",
        ):
            poller._check_mailbox_sync(mb)

        self.assertEqual(mock_conn.store.call_count, 3)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestIMAPCountUnseen))
    suite.addTests(loader.loadTestsFromTestCase(TestFetchEnvelopes))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractPreview))
    suite.addTests(loader.loadTestsFromTestCase(TestNotifyNewMessages))
    suite.addTests(loader.loadTestsFromTestCase(TestMailboxConfigRecipients))
    suite.addTests(loader.loadTestsFromTestCase(TestMailboxPollerRecipients))
    suite.addTests(loader.loadTestsFromTestCase(TestMailboxPollerMarksSeen))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
