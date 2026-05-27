# test_message_interface.py
# Tests for MessageInterface (non-admin user TUI flow)

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice.tui.message_interface import MessageInterface


class TestMessageInterfaceNonAdmin(unittest.TestCase):
    """Tests ensuring non-admin users can use postoffice TUI."""

    def setUp(self):
        self.mock_args = MagicMock()
        self.mock_args.loginid = "testuser"
        self.mock_args.issuperuser = False
        self.mock_args.imaphost = "mail.example.com"
        self.mock_args.imapport = 993
        self.mock_args.imapuser = "testuser"
        self.mock_args.imappassword = None
        self.mock_args.debug = False

    def test_current_user_extracted_from_args(self):
        """Test current_user is set from args.loginid."""
        iface = MessageInterface(self.mock_args)

        self.assertEqual(iface.current_user, "testuser")

    def test_non_admin_flag_from_args(self):
        """Test is_sysop is False for non-admin user."""
        iface = MessageInterface(self.mock_args)

        self.assertFalse(iface.is_sysop)

    def test_sysop_flag_true_when_issuperuser(self):
        """Test is_sysop is True when args.issuperuser is True."""
        self.mock_args.issuperuser = True
        iface = MessageInterface(self.mock_args)

        self.assertTrue(iface.is_sysop)

    def test_connect_imap_passes_args_not_string(self):
        """Test _connect_imap passes args object, not user string, to get_imap_credentials.

        This is the critical regression test: the bug was that
        get_imap_credentials was called with self.current_user (a string)
        instead of self.args (the bbsengine6 args object). Without the args
        object, get_imap_credentials couldn't access args.imaphost/imapuser
        settings needed for the password lookup fallback.
        """
        with patch("postoffice.tui.message_interface.imap_lib") as mock_imap_lib:
            mock_creds = {
                "host": "mail.example.com",
                "port": 993,
                "username": "testuser",
                "password": "fallback_pass",
            }
            mock_imap_lib.get_imap_credentials.return_value = mock_creds
            mock_imap_lib.connect_cyrus.return_value = MagicMock()

            iface = MessageInterface(self.mock_args)
            iface._connect_imap()

            mock_imap_lib.get_imap_credentials.assert_called_once()
            call_args = mock_imap_lib.get_imap_credentials.call_args

            self.assertIs(call_args[0][0], self.mock_args)
            self.assertEqual(call_args[1]["member_moniker"], "testuser")

    def test_connect_imap_with_direct_password(self):
        """Test _connect_imap succeeds when direct password is available."""
        self.mock_args.imappassword = "direct_password"

        with patch("postoffice.tui.message_interface.imap_lib") as mock_imap_lib:
            mock_creds = {
                "host": "mail.example.com",
                "port": 993,
                "username": "testuser",
                "password": "direct_password",
            }
            mock_imap_lib.get_imap_credentials.return_value = mock_creds
            mock_imap_lib.connect_cyrus.return_value = MagicMock()

            iface = MessageInterface(self.mock_args)
            result = iface._connect_imap()

            self.assertIsNotNone(result)

    def test_connect_imap_returns_none_when_no_credentials(self):
        """Test _connect_imap returns None when credentials not available."""
        with patch("postoffice.tui.message_interface.imap_lib") as mock_imap_lib:
            mock_imap_lib.get_imap_credentials.return_value = None

            with patch("postoffice.tui.message_interface.echo"):
                iface = MessageInterface(self.mock_args)
                result = iface._connect_imap()

                self.assertIsNone(result)

    def test_connect_imap_uses_fallback_password_system(self):
        """Test _connect_imap falls back to password system when direct pass missing."""
        self.mock_args.imappassword = None

        with patch("postoffice.tui.message_interface.imap_lib") as mock_imap_lib:
            mock_creds = {
                "host": "mail.example.com",
                "port": 993,
                "username": "testuser",
                "password": "from_password_system",
            }
            mock_imap_lib.get_imap_credentials.return_value = mock_creds
            mock_imap_lib.connect_cyrus.return_value = MagicMock()

            iface = MessageInterface(self.mock_args)
            iface._connect_imap()

            mock_imap_lib.get_imap_credentials.assert_called_once()
            self.assertEqual(
                mock_imap_lib.get_imap_credentials.call_args[1]["member_moniker"],
                "testuser",
            )

    def test_connect_imap_connects_using_creds_dict(self):
        """Test _connect_imap passes creds dict to connect_cyrus."""
        with patch("postoffice.tui.message_interface.imap_lib") as mock_imap_lib:
            mock_creds = {
                "host": "mail.example.com",
                "port": 993,
                "username": "testuser",
                "password": "some_pass",
            }
            mock_imap_lib.get_imap_credentials.return_value = mock_creds
            mock_imap_lib.connect_cyrus.return_value = MagicMock()

            iface = MessageInterface(self.mock_args)
            iface._connect_imap()

            mock_imap_lib.connect_cyrus.assert_called_once_with(mock_creds)

    def test_no_current_user_returns_error(self):
        """Test run() returns 1 when current_user cannot be determined."""
        mock_args = MagicMock(spec=[])
        mock_args.loginid = None

        iface = MessageInterface(mock_args)

        with patch("postoffice.tui.message_interface.echo"):
            result = iface.run()

            self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
