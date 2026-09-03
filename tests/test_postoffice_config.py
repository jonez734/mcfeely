#!/usr/bin/env python3
# mistermcfeely/tests/test_postoffice_config.py
# Tests for postoffice configuration loading
# (Now uses postoffice.services from mistermcfeely)

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/home/opencode/data/work/mistermcfeely/src")


class TestPostofficeConfig(unittest.TestCase):
    """Test postoffice configuration loading."""

    def setUp(self):
        self.env_vars_to_clean = [
            "POSTOFFICE_ENABLED",
            "POSTOFFICE_POLL_INTERVAL",
            "CASINO_DEBUG",
        ]
        for var in self.env_vars_to_clean:
            if var in os.environ:
                del os.environ[var]

    def tearDown(self):
        for var in self.env_vars_to_clean:
            if var in os.environ:
                del os.environ[var]

    def test_get_postoffice_config_default(self):
        """Test getting postoffice config with no defaults."""
        from postoffice.config import get_postoffice_config

        config = get_postoffice_config()
        self.assertEqual(config, {})

    def test_config_priority_env_overrides_file(self):
        """Test that env vars override config file."""
        os.environ["POSTOFFICE_ENABLED"] = "true"
        os.environ["POSTOFFICE_POLL_INTERVAL"] = "60"

        from postoffice.config import load_config, get_postoffice_config

        config = load_config()
        self.assertTrue(config["postoffice"]["enabled"])
        self.assertEqual(config["postoffice"]["poll_interval"], 60)

        postoffice_config = get_postoffice_config(config)
        self.assertTrue(postoffice_config["enabled"])
        self.assertEqual(postoffice_config["poll_interval"], 60)

    def test_config_priority_file_only(self):
        """Test that config file provides all values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "postoffice": {
                    "enabled": True,
                    "poll_interval": 120,
                    "mailboxes": [
                        {"host": "mail.example.com", "username": "test", "password": "pass"}
                    ]
                }
            }, f)
            config_file = f.name

        try:
            from postoffice.config import load_config

            loaded_config = load_config(config_file=config_file)
            self.assertTrue(loaded_config["postoffice"]["enabled"])
            self.assertEqual(loaded_config["postoffice"]["poll_interval"], 120)
            self.assertEqual(len(loaded_config["postoffice"]["mailboxes"]), 1)
        finally:
            os.unlink(config_file)

    def test_config_priority_overrides_highest(self):
        """Test that overrides have highest priority."""
        os.environ["POSTOFFICE_ENABLED"] = "true"
        os.environ["POSTOFFICE_POLL_INTERVAL"] = "45"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "postoffice": {
                    "enabled": False,
                    "poll_interval": 90,
                }
            }, f)
            config_file = f.name

        try:
            from postoffice.config import load_config

            config = load_config(
                config_file=config_file,
                postoffice={"enabled": True, "poll_interval": 15}
            )
            self.assertTrue(config["postoffice"]["enabled"])
            self.assertEqual(config["postoffice"]["poll_interval"], 15)
        finally:
            os.unlink(config_file)

    def test_mailboxes_loaded_correctly(self):
        """Test that mailboxes are loaded from config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "postoffice": {
                    "enabled": True,
                    "poll_interval": 30,
                    "mailboxes": [
                        {
                            "host": "imap.gmail.com",
                            "username": "user@gmail.com",
                            "password": "apppassword",
                            "mailbox": "INBOX",
                            "use_ssl": True,
                            "port": 993
                        },
                        {
                            "host": "imap.example.com",
                            "username": "other",
                            "password": "secret",
                            "mailbox": "Work",
                            "use_ssl": False,
                            "port": 143
                        }
                    ]
                }
            }, f)
            config_file = f.name

        try:
            from postoffice.config import load_config

            loaded_config = load_config(config_file=config_file)
            mailboxes = loaded_config["postoffice"]["mailboxes"]

            self.assertEqual(len(mailboxes), 2)
            self.assertEqual(mailboxes[0]["host"], "imap.gmail.com")
            self.assertEqual(mailboxes[0]["port"], 993)
            self.assertTrue(mailboxes[0]["use_ssl"])
            self.assertEqual(mailboxes[1]["host"], "imap.example.com")
            self.assertEqual(mailboxes[1]["port"], 143)
            self.assertFalse(mailboxes[1]["use_ssl"])
        finally:
            os.unlink(config_file)

    def test_env_var_boolean_parsing(self):
        """Test that env var booleans are parsed correctly."""
        os.environ["POSTOFFICE_ENABLED"] = "True"
        from postoffice.config import load_config
        config = load_config()
        self.assertTrue(config["postoffice"]["enabled"])

        os.environ["POSTOFFICE_ENABLED"] = "false"
        config = load_config()
        self.assertFalse(config["postoffice"]["enabled"])

    def test_env_var_integer_parsing(self):
        """Test that env var integers are parsed correctly."""
        os.environ["POSTOFFICE_POLL_INTERVAL"] = "300"
        from postoffice.config import load_config
        config = load_config()
        self.assertEqual(config["postoffice"]["poll_interval"], 300)


class TestPostofficeServiceConfig(unittest.TestCase):
    """Test that MailboxPoller uses config correctly."""

    def test_service_disabled_by_default(self):
        """Test poller is disabled when enabled=false in config."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={"enabled": False, "poll_interval": 30, "mailboxes": []})
        self.assertFalse(poller.is_enabled)
        self.assertEqual(poller.poll_interval, 30)

    def test_service_enabled_when_configured(self):
        """Test poller is enabled when enabled=true in config."""
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={"enabled": True, "poll_interval": 60, "mailboxes": []})
        self.assertTrue(poller.is_enabled)
        self.assertEqual(poller.poll_interval, 60)

    def test_mailboxes_loaded_from_config(self):
        """Test mailboxes are loaded from config into poller."""
        from postoffice.services import MailboxPoller, MailboxConfig

        mailboxes = [
            {"host": "imap.test.com", "username": "user", "password": "pass", "use_ssl": True}
        ]
        poller = MailboxPoller(config={"enabled": True, "poll_interval": 30, "mailboxes": mailboxes})

        self.assertEqual(len(poller.mailboxes), 1)
        self.assertIsInstance(poller.mailboxes[0], MailboxConfig)
        self.assertEqual(poller.mailboxes[0].host, "imap.test.com")

    def test_mailbox_config_accept_self_signed_default_true(self):
        """MailboxConfig defaults accept_self_signed to True so self-signed
        local Cyrus certs work without extra configuration."""
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(host="h", username="u", password="p")
        self.assertTrue(mb.accept_self_signed)

    def test_mailbox_config_accept_self_signed_false(self):
        """MailboxConfig honors explicit accept_self_signed=False."""
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(
            host="h", username="u", password="p", accept_self_signed=False
        )
        self.assertFalse(mb.accept_self_signed)

    def test_load_mailboxes_accept_self_signed_from_dict(self):
        """load_mailboxes propagates accept_self_signed from the dict."""
        from postoffice.services import load_mailboxes

        mbs = load_mailboxes({
            "mailboxes": [
                {
                    "host": "h1",
                    "username": "u",
                    "password": "p",
                    "accept_self_signed": False,
                },
                {
                    "host": "h2",
                    "username": "u",
                    "password": "p",
                    # omitted → default True
                },
            ]
        })
        self.assertEqual(len(mbs), 2)
        self.assertFalse(mbs[0].accept_self_signed)
        self.assertTrue(mbs[1].accept_self_signed)


class TestPostofficeEnvMailboxConfig(unittest.TestCase):
    """Test the POSTOFFICE_MAILBOX(ES) DSN loader's accept_self_signed handling."""

    def setUp(self):
        self._saved = {}
        for k in ("POSTOFFICE_MAILBOXES", "POSTOFFICE_MAILBOX"):
            if k in os.environ:
                self._saved[k] = os.environ[k]
                del os.environ[k]

    def tearDown(self):
        for k in ("POSTOFFICE_MAILBOXES", "POSTOFFICE_MAILBOX"):
            if k in os.environ:
                del os.environ[k]
        for k, v in self._saved.items():
            os.environ[k] = v

    def test_env_single_mailbox_default_accept_self_signed(self):
        """Omitted accept_self_signed in DSN defaults to True."""
        from postoffice.config import _load_mailboxes_from_env

        os.environ["POSTOFFICE_MAILBOX"] = (
            "host=imap.example.com user=admin password=secret"
        )
        mbs = _load_mailboxes_from_env()
        self.assertEqual(len(mbs), 1)
        self.assertTrue(mbs[0]["accept_self_signed"])

    def test_env_single_mailbox_accept_self_signed_false(self):
        """accept_self_signed=false in DSN is honored."""
        from postoffice.config import _load_mailboxes_from_env

        os.environ["POSTOFFICE_MAILBOX"] = (
            "host=imap.example.com user=admin password=secret accept_self_signed=false"
        )
        mbs = _load_mailboxes_from_env()
        self.assertEqual(len(mbs), 1)
        self.assertFalse(mbs[0]["accept_self_signed"])

    def test_env_mailboxes_list_with_insecure_alias(self):
        """insecure=true is accepted as an alias for accept_self_signed=true."""
        from postoffice.config import _load_mailboxes_from_env

        os.environ["POSTOFFICE_MAILBOXES"] = (
            "host=imap1.example.com user=u1 password=p1 insecure=true,"
            "host=imap2.example.com user=u2 password=p2 insecure=false"
        )
        mbs = _load_mailboxes_from_env()
        self.assertEqual(len(mbs), 2)
        self.assertTrue(mbs[0]["accept_self_signed"])
        self.assertFalse(mbs[1]["accept_self_signed"])


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestPostofficeConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestPostofficeServiceConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestPostofficeEnvMailboxConfig))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
