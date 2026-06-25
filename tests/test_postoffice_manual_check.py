#!/usr/bin/env python3
# mistermcfeely/tests/test_postoffice_manual_check.py
# Tests for the on-demand check_mail() service.
# (Now uses postoffice.services from mistermcfeely)

import pytest
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/home/opencode/data/work/mistermcfeely/src")


@pytest.mark.integration
class TestCheckMail(unittest.IsolatedAsyncioTestCase):
    """Test check_mail() function."""

    async def test_check_mail_no_mailboxes(self):
        """Test check_mail with no mailboxes configured."""
        from postoffice.services import check_mail

        result = await check_mail(
            config={"enabled": False, "poll_interval": 30, "mailboxes": []},
            moniker="testuser",
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["mailboxes_checked"], 0)
        self.assertEqual(result["total_unread"], 0)
        self.assertEqual(len(result["errors"]), 0)

    async def test_check_mail_with_mailboxes(self):
        """Test check_mail with mailboxes configured."""
        from postoffice.services import check_mail, check_mail_module

        mailboxes = [
            {"host": "imap.test.com", "username": "user", "password": "pass"}
        ]
        with patch.object(
            check_mail_module.svc_imap, "count_unseen", return_value=5
        ):
            result = await check_mail(
                config={"enabled": False, "poll_interval": 30, "mailboxes": mailboxes},
                moniker="testuser",
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["mailboxes_checked"], 1)
        self.assertEqual(result["total_unread"], 5)

    async def test_check_mail_multiple_mailboxes(self):
        """Test check_mail with multiple mailboxes."""
        from postoffice.services import check_mail, check_mail_module

        mailboxes = [
            {"host": "imap1.test.com", "username": "u1", "password": "p1"},
            {"host": "imap2.test.com", "username": "u2", "password": "p2"},
        ]
        with patch.object(
            check_mail_module.svc_imap,
            "count_unseen",
            side_effect=[3, 7],
        ):
            result = await check_mail(
                config={"enabled": False, "poll_interval": 30, "mailboxes": mailboxes},
                moniker="testuser",
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["mailboxes_checked"], 2)
        self.assertEqual(result["total_unread"], 10)

    async def test_check_mail_handles_errors(self):
        """Test check_mail handles mailbox errors."""
        from postoffice.services import check_mail, check_mail_module

        mailboxes = [
            {"host": "imap1.test.com", "username": "u1", "password": "p1"},
            {"host": "imap2.test.com", "username": "u2", "password": "p2"},
        ]
        with patch.object(
            check_mail_module.svc_imap,
            "count_unseen",
            side_effect=[3, Exception("Connection failed")],
        ):
            result = await check_mail(
                config={"enabled": False, "poll_interval": 30, "mailboxes": mailboxes},
                moniker="testuser",
            )
        self.assertTrue(result["success"])
        self.assertEqual(result["mailboxes_checked"], 2)
        self.assertEqual(result["total_unread"], 3)
        self.assertEqual(len(result["errors"]), 1)


@pytest.mark.integration
class TestCountUnseen(unittest.TestCase):
    """Test imap_client.count_unseen directly."""

    def test_count_unseen_returns_zero_on_error(self):
        """Test count_unseen returns 0 on connection error."""
        from postoffice.services import MailboxConfig
        from postoffice.services.imap_client import count_unseen

        mb = MailboxConfig(host="invalid.test.com", username="user", password="pass")
        with patch(
            "postoffice.services.imap_client.connect",
            side_effect=Exception("Connection refused"),
        ):
            count = count_unseen(mb)
        self.assertEqual(count, 0)

    def test_count_unseen_parses_unseen(self):
        """Test count_unseen correctly counts unseen messages."""
        from postoffice.services import MailboxConfig
        from postoffice.services.imap_client import count_unseen

        mb = MailboxConfig(host="mail.test.com", username="user", password="pass")
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2 3 4 5"])
        with patch("postoffice.services.imap_client.connect", return_value=mock_conn):
            count = count_unseen(mb)
        self.assertEqual(count, 5)

    def test_count_unseen_no_unseen(self):
        """Test count_unseen with no unseen messages."""
        from postoffice.services import MailboxConfig
        from postoffice.services.imap_client import count_unseen

        mb = MailboxConfig(host="mail.test.com", username="user", password="pass")
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b""])
        with patch("postoffice.services.imap_client.connect", return_value=mock_conn):
            count = count_unseen(mb)
        self.assertEqual(count, 0)


@pytest.mark.integration
class TestMailboxServiceHandler(unittest.IsolatedAsyncioTestCase):
    """Test MailboxServiceHandler (WebSocket handler)."""

    async def test_handler_returns_error_for_unauthenticated(self):
        """Test handler returns error for unauthenticated session."""
        from postoffice.api.handler import MailboxServiceHandler, SessionManager

        session_manager = SessionManager()
        session_manager.register_session(1, "testuser")

        args = MagicMock()
        args.databasename = "test"

        handler = MailboxServiceHandler(args, session_manager)

        mock_server = MagicMock()
        mock_ws = MagicMock()

        result = await handler.handle_message(
            mock_server, mock_ws, "default", {"type": "check_mail"}
        )
        self.assertEqual(result["code"], "not_authenticated")

    async def test_handler_processes_check_mail(self):
        """Test handler processes check_mail message."""
        from postoffice.api.handler import MailboxServiceHandler, SessionManager

        session_manager = SessionManager()
        session_manager.register_session(1, "testuser")

        args = MagicMock()
        args.databasename = "test"

        handler = MailboxServiceHandler(args, session_manager)

        mock_server = MagicMock()
        mock_ws = MagicMock()

        fake_result = {
            "success": True,
            "mailboxes_checked": 2,
            "total_unread": 5,
            "errors": [],
        }

        with patch(
            "postoffice.api.handler.check_mail", return_value=fake_result
        ) as mock_check:
            with patch("builtins.id", return_value=1):
                result = await handler.handle_message(
                    mock_server, mock_ws, "default", {"type": "check_mail"}
                )

        mock_check.assert_awaited_once()
        self.assertEqual(result["type"], "mail_check_result")
        self.assertTrue(result["success"])
        self.assertEqual(result["mailboxes_checked"], 2)
        self.assertEqual(result["total_unread"], 5)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestCheckMail))
    suite.addTests(loader.loadTestsFromTestCase(TestCountUnseen))
    suite.addTests(loader.loadTestsFromTestCase(TestMailboxServiceHandler))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
