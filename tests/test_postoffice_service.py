#!/usr/bin/env python3
# mistermcfeely/tests/test_postoffice_service.py
# Tests for MailboxPoller and MailboxConfig (formerly PostofficeService).
# (Now uses postoffice.services from mistermcfeely)

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/home/opencode/data/work/mistermcfeely/src")


class TestMailboxConfig(unittest.TestCase):
    """Test MailboxConfig class."""

    def test_mailbox_config_defaults(self):
        """Test mailbox config default values."""
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(host="imap.example.com", username="user", password="pass")
        self.assertEqual(mb.host, "imap.example.com")
        self.assertEqual(mb.username, "user")
        self.assertEqual(mb.password, "pass")
        self.assertEqual(mb.mailbox, "INBOX")
        self.assertTrue(mb.use_ssl)
        self.assertEqual(mb.port, 993)

    def test_mailbox_config_custom_values(self):
        """Test mailbox config with custom values."""
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(
            host="mail.test.com",
            username="testuser",
            password="secret",
            mailbox="Work",
            use_ssl=False,
            port=143
        )
        self.assertEqual(mb.host, "mail.test.com")
        self.assertEqual(mb.mailbox, "Work")
        self.assertFalse(mb.use_ssl)
        self.assertEqual(mb.port, 143)


class TestMailboxPoller(unittest.IsolatedAsyncioTestCase):
    """Test MailboxPoller class."""

    def setUp(self):
        from postoffice.services import reset_service
        reset_service()

    def test_service_initialization_disabled(self):
        """Test poller initializes correctly when disabled."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": False,
            "poll_interval": 30,
            "mailboxes": []
        })
        self.assertFalse(poller.is_enabled)
        self.assertEqual(poller.poll_interval, 30)
        self.assertFalse(poller._running)
        self.assertIsNone(poller._task)

    def test_service_initialization_enabled(self):
        """Test poller initializes correctly when enabled."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 60,
            "mailboxes": [
                {"host": "imap.test.com", "username": "user", "password": "pass"}
            ]
        })
        self.assertTrue(poller.is_enabled)
        self.assertEqual(poller.poll_interval, 60)
        self.assertEqual(len(poller.mailboxes), 1)

    def test_service_loads_mailboxes(self):
        """Test poller loads mailbox configurations."""
        from postoffice.services import MailboxPoller, MailboxConfig

        mailboxes = [
            {"host": "imap.gmail.com", "username": "user", "password": "pass", "use_ssl": True},
            {"host": "imap.work.com", "username": "worker", "password": "secret", "use_ssl": True, "port": 993}
        ]
        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 30,
            "mailboxes": mailboxes
        })
        self.assertEqual(len(poller.mailboxes), 2)
        self.assertIsInstance(poller.mailboxes[0], MailboxConfig)
        self.assertEqual(poller.mailboxes[0].host, "imap.gmail.com")
        self.assertEqual(poller.mailboxes[1].host, "imap.work.com")

    def test_service_handles_invalid_mailbox_config(self):
        """Test poller handles invalid mailbox config gracefully."""
        from postoffice.services import MailboxPoller

        mailboxes = [
            {"host": "valid.com", "username": "user", "password": "pass"},
            {"host": "", "username": "", "password": ""},  # Invalid - empty values
        ]
        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 30,
            "mailboxes": mailboxes
        })
        # All entries are loaded; empty/invalid ones are still represented.
        self.assertEqual(len(poller.mailboxes), 2)


class TestMailboxPollerStartStop(unittest.IsolatedAsyncioTestCase):
    """Test poller start/stop functionality."""

    def setUp(self):
        from postoffice.services import reset_service
        reset_service()

    async def test_start_disabled_service(self):
        """Test starting a disabled poller does nothing."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": False,
            "poll_interval": 30,
            "mailboxes": []
        })
        poller.start()
        self.assertFalse(poller._running)
        self.assertIsNone(poller._task)

    async def test_start_enabled_service(self):
        """Test starting an enabled poller creates background task."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 1,
            "mailboxes": []
        })
        poller.start()
        self.assertTrue(poller._running)
        self.assertIsNotNone(poller._task)
        poller.stop()

    async def test_start_already_running_service(self):
        """Test starting an already running poller logs warning."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 1,
            "mailboxes": []
        })
        poller.start()
        self.assertTrue(poller._running)
        poller.start()  # Should log warning
        poller.stop()

    async def test_stop_service(self):
        """Test stopping a running poller."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 1,
            "mailboxes": []
        })
        poller.start()
        self.assertTrue(poller._running)
        poller.stop()
        self.assertFalse(poller._running)
        self.assertIsNone(poller._task)

    async def test_stop_not_running_service(self):
        """Test stopping a non-running poller does nothing."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": False,
            "poll_interval": 30,
            "mailboxes": []
        })
        poller.stop()
        self.assertFalse(poller._running)


class TestPostofficeSingleton(unittest.IsolatedAsyncioTestCase):
    """Test singleton pattern for postoffice service."""

    def setUp(self):
        from postoffice.services import reset_service
        reset_service()

    async def test_get_service_singleton(self):
        """Test get_service returns singleton."""
        from postoffice.services import get_service, MailboxPoller

        cfg = {"enabled": False, "poll_interval": 30, "mailboxes": []}
        service1 = get_service(cfg)
        service2 = get_service(cfg)
        self.assertIs(service1, service2)
        self.assertIsInstance(service1, MailboxPoller)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestMailboxConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestMailboxPoller))
    suite.addTests(loader.loadTestsFromTestCase(TestMailboxPollerStartStop))
    suite.addTests(loader.loadTestsFromTestCase(TestPostofficeSingleton))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
