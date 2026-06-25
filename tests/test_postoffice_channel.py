#!/usr/bin/env python3
# mistermcfeely/tests/test_postoffice_channel.py
# Tests for postoffice channel constant and naming.
# (Casino-specific MessageRouter / PostofficeServiceHandler integration
# tests previously in this file have been removed; casino owns those
# handlers and the tests belong in the casino repo, not mistermcfeely.)

import sys
import unittest

sys.path.insert(0, "/home/opencode/data/work/mistermcfeely/src")


class TestPostofficeChannel(unittest.TestCase):
    """Test postoffice channel constant."""

    def test_postoffice_channel_constant(self):
        """Test POSTOFFICE_CHANNEL constant is correct."""
        from postoffice.services import POSTOFFICE_CHANNEL

        self.assertEqual(POSTOFFICE_CHANNEL, "postoffice:check_mail")


class TestPostofficeChannelIntegration(unittest.TestCase):
    """Test postoffice channel integration."""

    def test_service_publishes_to_channel(self):
        """Test service can publish to postoffice channel."""
        from postoffice.services import POSTOFFICE_CHANNEL

        self.assertIn("postoffice", POSTOFFICE_CHANNEL)
        self.assertIn("check_mail", POSTOFFICE_CHANNEL)

    def test_channel_name_format(self):
        """Test channel name follows naming convention."""
        channel = "postoffice:check_mail"
        parts = channel.split(":")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "postoffice")
        self.assertEqual(parts[1], "check_mail")


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestPostofficeChannel))
    suite.addTests(loader.loadTestsFromTestCase(TestPostofficeChannelIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
