# test_imap_lib.py
# Tests for imap_lib module (Cyrus IMAP utilities)

import unittest
from unittest.mock import MagicMock, patch
import imaplib
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import imap_lib


class TestConnectCyrus(unittest.TestCase):
    """Tests for connect_cyrus function."""

    def test_connect_cyrus_success(self):
        """Test successful connection to Cyrus IMAP server."""
        mock_args = MagicMock()
        mock_args.imaphost = "cyrus.example.com"
        mock_args.imapport = 993
        mock_args.imapuser = "testuser"
        mock_args.imappassword = "testpass"

        with patch("imaplib.IMAP4_SSL") as mock_imap:
            mock_instance = MagicMock()
            mock_imap.return_value = mock_instance

            result = imap_lib.connect_cyrus(mock_args)

            self.assertIsNotNone(result)
            mock_imap.assert_called_once_with("cyrus.example.com", 993, timeout=10)
            mock_instance.login.assert_called_once_with("testuser", "testpass")

    def test_connect_cyrus_missing_host(self):
        """Test connection fails when IMAP host is missing."""
        mock_args = MagicMock()
        mock_args.imaphost = None
        mock_args.imapport = 993
        mock_args.imapuser = "testuser"
        mock_args.imappassword = "testpass"
        mock_args.debug = False

        result = imap_lib.connect_cyrus(mock_args)

        self.assertIsNone(result)

    def test_connect_cyrus_missing_credentials(self):
        """Test connection fails when credentials are missing."""
        mock_args = MagicMock()
        mock_args.imaphost = "cyrus.example.com"
        mock_args.imapport = 993
        mock_args.imapuser = None
        mock_args.imappassword = None
        mock_args.debug = False

        result = imap_lib.connect_cyrus(mock_args)

        self.assertIsNone(result)

    def test_connect_cyrus_login_error(self):
        """Test connection fails on IMAP login error."""
        mock_args = MagicMock()
        mock_args.imaphost = "cyrus.example.com"
        mock_args.imapport = 993
        mock_args.imapuser = "baduser"
        mock_args.imappassword = "badpass"
        mock_args.debug = False

        with patch("imaplib.IMAP4_SSL") as mock_imap:
            mock_instance = MagicMock()
            mock_instance.login.side_effect = imaplib.IMAP4.error("Login failed")
            mock_imap.return_value = mock_instance

            result = imap_lib.connect_cyrus(mock_args)

            self.assertIsNone(result)

    def test_connect_cyrus_default_port(self):
        """Test connection uses default port 993 when not specified."""
        mock_args = MagicMock()
        mock_args.imaphost = "cyrus.example.com"
        mock_args.imapport = 993
        mock_args.imapuser = "testuser"
        mock_args.imappassword = "testpass"

        with patch("imaplib.IMAP4_SSL") as mock_imap:
            mock_instance = MagicMock()
            mock_imap.return_value = mock_instance

            imap_lib.connect_cyrus(mock_args)

            # Should use the port from args
            mock_imap.assert_called_once_with("cyrus.example.com", 993, timeout=10)


class TestSelectMailbox(unittest.TestCase):
    """Tests for select_mailbox function."""

    def test_select_mailbox_success(self):
        """Test successful mailbox selection."""
        mock_imap = MagicMock()
        mock_imap.select.return_value = ("OK", [b"123"])

        result = imap_lib.select_mailbox(mock_imap, "shared/support")

        self.assertTrue(result)
        mock_imap.select.assert_called_once_with("shared/support", readonly=True)

    def test_select_mailbox_failure(self):
        """Test mailbox selection fails on error."""
        mock_imap = MagicMock()
        mock_imap.select.return_value = ("NO", [b"Mailbox not found"])

        result = imap_lib.select_mailbox(mock_imap, "nonexistent")

        self.assertFalse(result)

    def test_select_mailbox_exception(self):
        """Test mailbox selection handles exceptions."""
        mock_imap = MagicMock()
        mock_imap.select.side_effect = Exception("Connection error")

        result = imap_lib.select_mailbox(mock_imap, "shared/support")

        self.assertFalse(result)


class TestGetAllUids(unittest.TestCase):
    """Tests for get_all_uids function."""

    def test_get_all_uids_success(self):
        """Test retrieval of all UIDs from mailbox."""
        mock_imap = MagicMock()
        mock_imap.uid.return_value = ("OK", [b"1 2 3 4 5"])

        result = imap_lib.get_all_uids(mock_imap)

        self.assertEqual(result, {1, 2, 3, 4, 5})

    def test_get_all_uids_empty_mailbox(self):
        """Test retrieval from empty mailbox returns empty set."""
        mock_imap = MagicMock()
        mock_imap.uid.return_value = ("OK", [b""])

        result = imap_lib.get_all_uids(mock_imap)

        self.assertEqual(result, set())

    def test_get_all_uids_search_error(self):
        """Test UID retrieval fails on search error."""
        mock_imap = MagicMock()
        mock_imap.uid.return_value = ("NO", [])

        result = imap_lib.get_all_uids(mock_imap)

        self.assertEqual(result, set())

    def test_get_all_uids_exception(self):
        """Test UID retrieval handles exceptions."""
        mock_imap = MagicMock()
        mock_imap.uid.side_effect = Exception("Connection error")

        result = imap_lib.get_all_uids(mock_imap)

        self.assertEqual(result, set())


class TestGetMessageFlags(unittest.TestCase):
    """Tests for get_message_flags function."""

    def test_get_message_flags_success(self):
        """Test retrieval of flags for a message."""
        mock_imap = MagicMock()
        mock_imap.uid.return_value = (
            "OK",
            [b"123 (FLAGS (\\Seen \\Flagged ClaimedBy_a3f9k2m1))"],
        )

        result = imap_lib.get_message_flags(mock_imap, 123)

        self.assertEqual(result, {"\\Seen", "\\Flagged", "ClaimedBy_a3f9k2m1"})

    def test_get_message_flags_no_flags(self):
        """Test retrieval when message has no flags."""
        mock_imap = MagicMock()
        mock_imap.uid.return_value = ("OK", [b"123 (FLAGS ())"])

        result = imap_lib.get_message_flags(mock_imap, 123)

        self.assertEqual(result, set())

    def test_get_message_flags_fetch_error(self):
        """Test flag retrieval fails on fetch error."""
        mock_imap = MagicMock()
        mock_imap.uid.return_value = ("NO", [])

        result = imap_lib.get_message_flags(mock_imap, 123)

        self.assertEqual(result, set())

    def test_get_message_flags_exception(self):
        """Test flag retrieval handles exceptions."""
        mock_imap = MagicMock()
        mock_imap.uid.side_effect = Exception("Connection error")

        result = imap_lib.get_message_flags(mock_imap, 123)

        self.assertEqual(result, set())


class TestGetMessageHeaders(unittest.TestCase):
    """Tests for get_message_headers function."""

    def test_get_message_headers_success(self):
        """Test retrieval of message headers."""
        mock_imap = MagicMock()

        # Mock RFC822.HEADER response
        header_bytes = b"""From: sender@example.com\r
Subject: Test Subject\r
Message-ID: <abc123@example.com>\r
Date: Mon, 1 Jan 2024 12:00:00 +0000\r
\r
"""

        mock_imap.uid.return_value = ("OK", [(b"123 (RFC822.HEADER", header_bytes)])

        result = imap_lib.get_message_headers(mock_imap, 123)

        self.assertIsNotNone(result)
        self.assertEqual(result["from_addr"], "sender@example.com")
        self.assertEqual(result["subject"], "Test Subject")
        self.assertEqual(result["message_id"], "<abc123@example.com>")

    def test_get_message_headers_fetch_error(self):
        """Test header retrieval fails on fetch error."""
        mock_imap = MagicMock()
        mock_imap.uid.return_value = ("NO", [])

        result = imap_lib.get_message_headers(mock_imap, 123)

        self.assertEqual(result, {})

    def test_get_message_headers_exception(self):
        """Test header retrieval handles exceptions."""
        mock_imap = MagicMock()
        mock_imap.uid.side_effect = Exception("Connection error")

        result = imap_lib.get_message_headers(mock_imap, 123)

        self.assertEqual(result, {})


class TestDetectNewMessages(unittest.TestCase):
    """Tests for detect_new_messages function."""

    def test_detect_new_messages_found(self):
        """Test detection of new messages."""
        current = {1, 2, 3, 4, 5}
        stored = {1, 2, 3}

        result = imap_lib.detect_new_messages(current, stored)

        self.assertEqual(result, {4, 5})

    def test_detect_new_messages_none(self):
        """Test detection when no new messages."""
        current = {1, 2, 3}
        stored = {1, 2, 3}

        result = imap_lib.detect_new_messages(current, stored)

        self.assertEqual(result, set())

    def test_detect_new_messages_all_new(self):
        """Test detection when all messages are new."""
        current = {1, 2, 3, 4, 5}
        stored = set()

        result = imap_lib.detect_new_messages(current, stored)

        self.assertEqual(result, {1, 2, 3, 4, 5})


class TestDetectDeletedMessages(unittest.TestCase):
    """Tests for detect_deleted_messages function."""

    def test_detect_deleted_messages_found(self):
        """Test detection of deleted messages."""
        current = {1, 2, 3}
        stored = {1, 2, 3, 4, 5}

        result = imap_lib.detect_deleted_messages(current, stored)

        self.assertEqual(result, {4, 5})

    def test_detect_deleted_messages_none(self):
        """Test detection when no messages deleted."""
        current = {1, 2, 3, 4, 5}
        stored = {1, 2, 3, 4, 5}

        result = imap_lib.detect_deleted_messages(current, stored)

        self.assertEqual(result, set())

    def test_detect_deleted_messages_all_deleted(self):
        """Test detection when all messages are deleted."""
        current = set()
        stored = {1, 2, 3, 4, 5}

        result = imap_lib.detect_deleted_messages(current, stored)

        self.assertEqual(result, {1, 2, 3, 4, 5})


class TestDetectFlagChanges(unittest.TestCase):
    """Tests for detect_flag_changes function."""

    def test_detect_flag_changes_additions(self):
        """Test detection of added flags."""
        current = {"\\Seen", "\\Flagged", "Custom"}
        stored = {"\\Seen"}

        added, removed = imap_lib.detect_flag_changes(current, stored)

        self.assertEqual(added, {"\\Flagged", "Custom"})
        self.assertEqual(removed, set())

    def test_detect_flag_changes_removals(self):
        """Test detection of removed flags."""
        current = {"\\Seen"}
        stored = {"\\Seen", "\\Flagged", "Custom"}

        added, removed = imap_lib.detect_flag_changes(current, stored)

        self.assertEqual(added, set())
        self.assertEqual(removed, {"\\Flagged", "Custom"})

    def test_detect_flag_changes_both(self):
        """Test detection of both additions and removals."""
        current = {"\\Seen", "\\Draft", "New"}
        stored = {"\\Seen", "\\Flagged", "Old"}

        added, removed = imap_lib.detect_flag_changes(current, stored)

        self.assertEqual(added, {"\\Draft", "New"})
        self.assertEqual(removed, {"\\Flagged", "Old"})

    def test_detect_flag_changes_none(self):
        """Test detection when no changes."""
        current = {"\\Seen", "\\Flagged"}
        stored = {"\\Seen", "\\Flagged"}

        added, removed = imap_lib.detect_flag_changes(current, stored)

        self.assertEqual(added, set())
        self.assertEqual(removed, set())


if __name__ == "__main__":
    unittest.main()
