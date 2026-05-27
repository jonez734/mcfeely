# tests/test_imap_password_integration.py
# Integration tests for IMAP daemon with password management system

import os
import sys
import base64
import unittest
from unittest.mock import Mock, MagicMock, patch
import imaplib

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import imap_lib


class TestIMAPCredentialRetrieval(unittest.TestCase):
    """Test IMAP credential retrieval with password system fallback."""

    def setUp(self):
        """Set up test encryption key."""
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.debug = False

    def tearDown(self):
        """Clean up environment."""
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def test_get_imap_credentials_direct_args(self):
        """Test credentials from direct args (highest priority)."""
        self.args.imaphost = "mail.example.com"
        self.args.imapport = 993
        self.args.imapuser = "mailuser"
        self.args.imappassword = "direct_password"

        creds = imap_lib.get_imap_credentials(self.args)

        self.assertIsNotNone(creds)
        self.assertEqual(creds["host"], "mail.example.com")
        self.assertEqual(creds["port"], 993)
        self.assertEqual(creds["username"], "mailuser")
        self.assertEqual(creds["password"], "direct_password")

    def test_get_imap_credentials_default_port(self):
        """Test default IMAP port is 993."""
        self.args.imaphost = "mail.example.com"
        self.args.imapport = None
        self.args.imapuser = "mailuser"
        self.args.imappassword = "password"

        creds = imap_lib.get_imap_credentials(self.args)

        self.assertEqual(creds["port"], 993)

    @patch("postoffice.password_auth.get_auth_password")
    def test_get_imap_credentials_fallback_to_password_system(self, mock_get_auth):
        """Test fallback to password system when direct password missing."""
        self.args.imaphost = "mail.example.com"
        self.args.imapport = 993
        self.args.imapuser = "mailuser"
        self.args.imappassword = None

        mock_get_auth.return_value = "system_password"

        creds = imap_lib.get_imap_credentials(
            self.args,
            member_moniker="alice",
            mailbox_id=1,
        )

        self.assertIsNotNone(creds)
        self.assertEqual(creds["password"], "system_password")
        mock_get_auth.assert_called_once()

    @patch("postoffice.password_auth.get_auth_password")
    def test_get_imap_credentials_fallback_failure(self, mock_get_auth):
        """Test when password system also fails."""
        self.args.imaphost = "mail.example.com"
        self.args.imapuser = "mailuser"
        self.args.imappassword = None

        mock_get_auth.return_value = None

        creds = imap_lib.get_imap_credentials(
            self.args,
            member_moniker="alice",
        )

        self.assertIsNone(creds)

    def test_get_imap_credentials_no_member_no_fallback(self):
        """Test no fallback when member_moniker not provided."""
        self.args.imaphost = "mail.example.com"
        self.args.imapuser = "mailuser"
        self.args.imappassword = None

        creds = imap_lib.get_imap_credentials(self.args)

        self.assertIsNone(creds)

    def test_get_imap_credentials_missing_host(self):
        """Test failure when host is missing."""
        self.args.imaphost = None
        self.args.imapuser = "mailuser"
        self.args.imappassword = "password"

        creds = imap_lib.get_imap_credentials(self.args)

        self.assertIsNone(creds)


class TestIMAPConnectionWithPasswordSystem(unittest.TestCase):
    """Test IMAP connection using password system."""

    def setUp(self):
        """Set up test encryption key."""
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.debug = False
        self.args.issuperuser = False

    def tearDown(self):
        """Clean up environment."""
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    @patch("imaplib.IMAP4_SSL")
    def test_connect_cyrus_with_direct_credentials(self, mock_imap_class):
        """Test IMAP connection with direct args credentials."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap

        self.args.imaphost = "mail.example.com"
        self.args.imapport = 993
        self.args.imapuser = "mailuser"
        self.args.imappassword = "direct_password"

        result = imap_lib.connect_cyrus(self.args)

        self.assertIsNotNone(result)
        mock_imap_class.assert_called_once_with("mail.example.com", 993, timeout=10)
        mock_imap.login.assert_called_once_with("mailuser", "direct_password")

    @patch("imaplib.IMAP4_SSL")
    @patch("postoffice.password_auth.get_auth_password")
    def test_connect_cyrus_with_password_system(self, mock_get_auth, mock_imap_class):
        """Test IMAP connection using password system fallback."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        mock_get_auth.return_value = "system_password"

        self.args.imaphost = "mail.example.com"
        self.args.imapport = 993
        self.args.imapuser = "mailuser"
        self.args.imappassword = None

        result = imap_lib.connect_cyrus(
            self.args,
            member_moniker="alice",
            mailbox_id=1,
        )

        self.assertIsNotNone(result)
        mock_imap.login.assert_called_once_with("mailuser", "system_password")

    @patch("imaplib.IMAP4_SSL")
    def test_connect_cyrus_login_error(self, mock_imap_class):
        """Test IMAP connection error handling."""
        mock_imap = MagicMock()
        mock_imap.login.side_effect = imaplib.IMAP4.error("Login failed")
        mock_imap_class.return_value = mock_imap

        self.args.imaphost = "mail.example.com"
        self.args.imapport = 993
        self.args.imapuser = "mailuser"
        self.args.imappassword = "wrong_password"

        result = imap_lib.connect_cyrus(self.args)

        self.assertIsNone(result)

    @patch("imaplib.IMAP4_SSL")
    def test_connect_cyrus_missing_credentials(self, mock_imap_class):
        """Test IMAP connection fails gracefully with no credentials."""
        self.args.imaphost = None
        self.args.imapuser = None
        self.args.imappassword = None

        result = imap_lib.connect_cyrus(self.args)

        self.assertIsNone(result)
        mock_imap_class.assert_not_called()

    @patch("imaplib.IMAP4_SSL")
    def test_connect_cyrus_debug_logging(self, mock_imap_class):
        """Test debug logging when enabled."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap

        self.args.imaphost = "mail.example.com"
        self.args.imapport = 993
        self.args.imapuser = "mailuser"
        self.args.imappassword = "password"
        self.args.debug = True

        result = imap_lib.connect_cyrus(self.args)

        self.assertIsNotNone(result)


class TestIMAPConnectionFlow(unittest.TestCase):
    """Test full IMAP connection flow with password management."""

    def setUp(self):
        """Set up test encryption key."""
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.debug = False
        self.args.issuperuser = False

    def tearDown(self):
        """Clean up environment."""
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    @patch("imaplib.IMAP4_SSL")
    @patch("postoffice.password_auth.get_auth_password")
    def test_shared_mailbox_member_password_flow(
        self, mock_get_auth, mock_imap_class
    ):
        """
        Test realistic flow: connect to shared mailbox using per-member password.

        Scenario: member 'alice' has specific password for mailbox 1 (support@example.com)
        """
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap

        # Simulate password system returning alice's per-member password
        mock_get_auth.return_value = "alice_mailbox_password"

        self.args.imaphost = "mail.example.com"
        self.args.imapport = 993
        self.args.imapuser = "support"
        self.args.imappassword = None  # Use password system

        result = imap_lib.connect_cyrus(
            self.args,
            member_moniker="alice",
            mailbox_id=1,  # support@example.com
        )

        self.assertIsNotNone(result)
        mock_get_auth.assert_called_once_with(
            self.args,
            mailbox_id=1,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )
        mock_imap.login.assert_called_once_with("support", "alice_mailbox_password")

    @patch("imaplib.IMAP4_SSL")
    @patch("postoffice.password_auth.get_auth_password")
    def test_personal_account_password_flow(self, mock_get_auth, mock_imap_class):
        """
        Test realistic flow: connect to personal IMAP account.

        Scenario: member 'bob' has personal mail server password
        """
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap

        # Simulate password system returning bob's personal password
        mock_get_auth.return_value = "bob_personal_password"

        self.args.imaphost = "imap.gmail.com"
        self.args.imapport = 993
        self.args.imapuser = "bob@gmail.com"
        self.args.imappassword = None

        result = imap_lib.connect_cyrus(
            self.args,
            member_moniker="bob",
            mailbox_id=None,  # None = personal account
        )

        self.assertIsNotNone(result)
        mock_imap.login.assert_called_once_with("bob@gmail.com", "bob_personal_password")


if __name__ == "__main__":
    unittest.main()
