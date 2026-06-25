#!/usr/bin/env python3
# mistermcfeely/tests/test_postoffice_background_task.py
# Tests for background polling task.
# (Now uses postoffice.services from mistermcfeely)

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, "/home/opencode/data/work/mistermcfeely/src")


class TestMailboxPollerBackgroundTask(unittest.IsolatedAsyncioTestCase):
    """Test background polling task functionality."""

    def setUp(self):
        from postoffice.services import reset_service
        reset_service()

    async def test_poll_loop_runs_and_stops(self):
        """Test poll loop runs and can be stopped."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 1,
            "mailboxes": []
        })

        async def stop_after_short_delay():
            await asyncio.sleep(0.1)
            poller.stop()

        task = asyncio.create_task(stop_after_short_delay())
        await poller._poll_loop()
        await task
        self.assertFalse(poller._running)

    async def test_poll_loop_catches_exceptions(self):
        """Test poll loop handles exceptions without crashing."""
        from postoffice.services import MailboxPoller

        call_count = 0

        async def failing_poll():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Test error")
            poller._running = False

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 1,
            "mailboxes": []
        })
        poller._running = True

        with patch.object(poller, "_poll_all_mailboxes", side_effect=failing_poll):
            await poller._poll_loop()

        self.assertEqual(call_count, 3)

    async def test_poll_all_mailboxes_empty(self):
        """Test polling with no mailboxes configured."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 30,
            "mailboxes": []
        })

        await poller._poll_all_mailboxes()

    async def test_poll_all_mailboxes_calls_check(self):
        """Test polling iterates through all mailboxes."""
        from postoffice.services import MailboxPoller, MailboxConfig

        mailboxes = [
            MailboxConfig(host="mail1.example.com", username="u1", password="p1"),
            MailboxConfig(host="mail2.example.com", username="u2", password="p2"),
        ]

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 30,
            "mailboxes": [vars(mb) for mb in mailboxes]
        })

        with patch.object(poller, "_check_mailbox", new_callable=AsyncMock) as mock_check:
            await poller._poll_all_mailboxes()
            self.assertEqual(mock_check.call_count, 2)

    async def test_check_mailbox_runs_in_executor(self):
        """Test _check_mailbox runs sync IMAP in executor."""
        from postoffice.services import MailboxPoller, MailboxConfig

        mb = MailboxConfig(host="mail.example.com", username="user", password="pass")
        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 30,
            "mailboxes": [vars(mb)]
        })

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock()
            await poller._check_mailbox(mb)
            mock_loop.return_value.run_in_executor.assert_called_once()


class TestStartStopFunctions(unittest.IsolatedAsyncioTestCase):
    """Test start/stop module functions."""

    def setUp(self):
        from postoffice.services import reset_service
        reset_service()

    async def test_start_service(self):
        """Test start_service() function."""
        from postoffice.services import start_service, get_service, reset_service

        reset_service()
        get_service({"enabled": True, "poll_interval": 30, "mailboxes": []})

        start_service()
        poller = get_service()
        self.assertIsNotNone(poller)
        self.assertTrue(poller.is_enabled)

        poller.stop()
        reset_service()

    async def test_stop_service(self):
        """Test stop_service() function."""
        from postoffice.services import MailboxPoller, get_service, stop_service

        get_service({
            "enabled": True,
            "poll_interval": 1,
            "mailboxes": [],
        })
        get_service().start()

        stop_service()
        from postoffice.services import get_service as _get
        # After stop_service, the singleton is cleared
        self.assertIsNone(_get.__globals__["_service_instance"])


class TestServiceLifecycle(unittest.IsolatedAsyncioTestCase):
    """Test service lifecycle scenarios."""

    def setUp(self):
        from postoffice.services import reset_service
        reset_service()

    async def test_service_restart(self):
        """Test service can be restarted after stopping."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 1,
            "mailboxes": []
        })

        poller.start()
        self.assertTrue(poller._running)
        task1 = poller._task

        poller.stop()
        self.assertFalse(poller._running)

        poller.start()
        self.assertTrue(poller._running)
        self.assertIsNotNone(poller._task)

        poller.stop()

    async def test_multiple_services_independent(self):
        """Test multiple poller instances are independent."""
        from postoffice.services import MailboxPoller

        poller1 = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 1,
            "mailboxes": []
        })
        poller2 = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 2,
            "mailboxes": []
        })

        poller1.start()
        poller2.start()

        self.assertTrue(poller1._running)
        self.assertTrue(poller2._running)
        self.assertEqual(poller1.poll_interval, 1)
        self.assertEqual(poller2.poll_interval, 2)

        poller1.stop()
        poller2.stop()


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestMailboxPollerBackgroundTask))
    suite.addTests(loader.loadTestsFromTestCase(TestStartStopFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestServiceLifecycle))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
