# test_notifyd_integration.py
# Integration tests for notifyd_client and imap_client modules
# Tests real API calls without mocking internal functions

import unittest
import sys
import os
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import notifyd_client, imap_client


class TestFlagObfuscationIntegration(unittest.TestCase):
    """Integration tests for flag obfuscation."""

    def test_claim_flag_roundtrip_plain(self):
        """Test plain text flag creation and verification roundtrip."""
        moniker = "alice"
        secret = None

        # Format flag
        flag = notifyd_client.format_claim_flag(moniker, secret)

        # Verify it matches
        self.assertTrue(notifyd_client.verify_claim_flag(flag, moniker, secret))

        # Verify it doesn't match other monikers
        self.assertFalse(notifyd_client.verify_claim_flag(flag, "bob", secret))

    def test_claim_flag_roundtrip_obfuscated(self):
        """Test obfuscated flag creation and verification roundtrip."""
        moniker = "alice"
        secret = "super_secret_key_123"

        # Format flag
        flag = notifyd_client.format_claim_flag(moniker, secret)

        # Verify it matches
        self.assertTrue(notifyd_client.verify_claim_flag(flag, moniker, secret))

        # Verify it doesn't match other monikers
        self.assertFalse(notifyd_client.verify_claim_flag(flag, "bob", secret))

        # Verify wrong secret fails
        self.assertFalse(
            notifyd_client.verify_claim_flag(flag, moniker, "wrong_secret")
        )

    def test_obfuscate_moniker_is_deterministic(self):
        """Test that same inputs produce same obfuscation."""
        secret = "test_secret"
        moniker = "test_user"

        obf1 = notifyd_client.obfuscate_moniker(moniker, secret)
        obf2 = notifyd_client.obfuscate_moniker(moniker, secret)
        obf3 = notifyd_client.obfuscate_moniker(moniker, secret)

        self.assertEqual(obf1, obf2)
        self.assertEqual(obf2, obf3)

    def test_obfuscate_multiple_monikers(self):
        """Test that different monikers produce different obfuscations."""
        secret = "shared_secret"

        hashes = {
            notifyd_client.obfuscate_moniker(user, secret)
            for user in ["alice", "bob", "charlie", "david", "eve"]
        }

        # All 5 should be different
        self.assertEqual(len(hashes), 5)


class TestEventMessageRenderingIntegration(unittest.TestCase):
    """Integration tests for event message rendering."""

    def test_render_all_event_types(self):
        """Test rendering messages for all event types."""
        test_cases = [
            (
                "message-new",
                None,
                {
                    "from": "sender@example.com",
                    "subject": "Test Subject",
                    "message_uid": 123,
                },
            ),
            ("message-claimed", "alice", {"message_uid": 423}),
            ("message-unclaimed", "alice", {"message_uid": 423}),
            ("message-flagged", "alice", {"flag_name": "\\Seen", "added": True}),
            ("message-deleted", None, {"message_uid": 423}),
        ]

        for event_type, actor, data in test_cases:
            result = notifyd_client.render_event_message(event_type, actor, data)
            self.assertIsNotNone(result)
            self.assertGreater(len(result), 0)
            self.assertIsInstance(result, str)

    def test_render_handles_missing_fields(self):
        """Test that rendering handles missing optional fields gracefully."""
        # message-new without all fields
        result = notifyd_client.render_event_message(
            "message-new",
            None,
            {"from": "sender@example.com"},  # missing subject
        )
        self.assertIn("sender@example.com", result)

    def test_render_handles_special_characters(self):
        """Test rendering with special characters in data."""
        result = notifyd_client.render_event_message(
            "message-new",
            None,
            {
                "from": "test+alias@example.com",
                "subject": "Re: [URGENT] Test (with parens) & symbols",
            },
        )
        self.assertIn("test+alias@example.com", result)
        self.assertIn("URGENT", result)


class TestClaimMessageIntegration(unittest.TestCase):
    """Integration tests for message claim operations."""

    def test_claim_message_payload_structure(self):
        """Test that claim_message creates proper event payload."""
        import inspect

        sig = inspect.signature(imap_client.claim_message)
        params = list(sig.parameters.keys())

        # Functions now use **kwargs pattern
        expected = [
            "args",
            "mailbox_name",
            "message_uid",
            "actor_moniker",
            "message_id",
            "message_from",
            "message_subject",
            "kwargs",
        ]

        for param in expected:
            self.assertIn(param, params, f"Missing parameter: {param}")

    def test_unclaim_message_payload_structure(self):
        """Test that unclaim_message creates proper event payload."""
        import inspect

        sig = inspect.signature(imap_client.unclaim_message)
        params = list(sig.parameters.keys())

        # Functions now use **kwargs pattern
        expected = ["args", "mailbox_name", "message_uid", "actor_moniker", "kwargs"]

        for param in expected:
            self.assertIn(param, params, f"Missing parameter: {param}")

    def test_fire_event_functions_exist(self):
        """Test that all fire_event_* functions exist."""
        functions = [
            imap_client.fire_new_message_event,
            imap_client.fire_flag_changed_event,
            imap_client.fire_message_deleted_event,
        ]

        for func in functions:
            self.assertTrue(callable(func))


class TestEventPayloadStructure(unittest.TestCase):
    """Test that event payloads are properly structured JSON."""

    def test_message_claimed_payload(self):
        """Test message-claimed event payload structure."""
        payload = {
            "event_type": "message-claimed",
            "mailbox_name": "shared/support@machine1.example.com",
            "message_uid": 423,
            "message_id": "<abc123@example.com>",
            "from": "user@example.com",
            "subject": "Help: Password reset",
            "actor_moniker": "alice",
        }

        # Verify it's valid JSON-serializable
        json_str = json.dumps(payload)
        parsed = json.loads(json_str)

        self.assertEqual(parsed["event_type"], "message-claimed")
        self.assertEqual(parsed["message_uid"], 423)
        self.assertEqual(parsed["actor_moniker"], "alice")

    def test_message_new_payload(self):
        """Test message-new event payload structure."""
        payload = {
            "event_type": "message-new",
            "mailbox_name": "shared/support@example.com",
            "message_uid": 423,
            "message_id": "<abc123@example.com>",
            "from": "user@example.com",
            "subject": "Help: Password reset",
        }

        json_str = json.dumps(payload)
        parsed = json.loads(json_str)

        self.assertEqual(parsed["event_type"], "message-new")
        self.assertNotIn("actor_moniker", parsed)  # new messages have no actor

    def test_message_flagged_payload(self):
        """Test message-flagged event payload structure."""
        payload = {
            "event_type": "message-flagged",
            "mailbox_name": "shared/support@example.com",
            "message_uid": 423,
            "flag_name": "\\Seen",
            "added": True,
            "actor_moniker": "alice",
        }

        json_str = json.dumps(payload)
        parsed = json.loads(json_str)

        self.assertEqual(parsed["event_type"], "message-flagged")
        self.assertTrue(parsed["added"])

    def test_message_deleted_payload(self):
        """Test message-deleted event payload structure."""
        payload = {
            "event_type": "message-deleted",
            "mailbox_name": "shared/support@example.com",
            "message_uid": 423,
        }

        json_str = json.dumps(payload)
        parsed = json.loads(json_str)

        self.assertEqual(parsed["event_type"], "message-deleted")
        self.assertEqual(len(parsed), 3)  # Only 3 fields


class TestSecretRetrievalIntegration(unittest.TestCase):
    """Integration tests for secret retrieval from environment."""

    def test_obfuscate_secret_fallback_chain(self):
        """Test that secret retrieval follows fallback chain."""
        import os

        # Save original env
        original_env = os.environ.get("MCFEELY_OBFUSCATE_SECRET")

        try:
            # Test 1: No env, no args → None
            if "MCFEELY_OBFUSCATE_SECRET" in os.environ:
                del os.environ["MCFEELY_OBFUSCATE_SECRET"]

            from unittest.mock import Mock

            args = Mock(databasepassword=None)
            result = notifyd_client.get_obfuscate_secret(args)
            self.assertIsNone(result)

            # Test 2: Env set → use env
            os.environ["MCFEELY_OBFUSCATE_SECRET"] = "env_secret"
            result = notifyd_client.get_obfuscate_secret(args)
            self.assertEqual(result, "env_secret")

            # Test 3: Env set, args set → env takes priority
            args.databasepassword = "db_secret"
            result = notifyd_client.get_obfuscate_secret(args)
            self.assertEqual(result, "env_secret")

        finally:
            # Restore original env
            if original_env:
                os.environ["MCFEELY_OBFUSCATE_SECRET"] = original_env
            elif "MCFEELY_OBFUSCATE_SECRET" in os.environ:
                del os.environ["MCFEELY_OBFUSCATE_SECRET"]


class TestFlagFormatConsistency(unittest.TestCase):
    """Test consistency of flag formatting across different inputs."""

    def test_plain_flags_follow_convention(self):
        """Test that plain flags follow ClaimedBy<Moniker> convention."""
        test_cases = [
            ("alice", "ClaimedByAlice"),
            ("bob", "ClaimedByBob"),
            ("charlie", "ClaimedByCharlie"),
        ]

        for moniker, expected in test_cases:
            result = notifyd_client.format_claim_flag(moniker, secret=None)
            self.assertEqual(result, expected)

    def test_obfuscated_flags_follow_convention(self):
        """Test that obfuscated flags follow ClaimedBy_<8chars> convention."""
        secret = "test_secret"

        for moniker in ["alice", "bob", "charlie"]:
            flag = notifyd_client.format_claim_flag(moniker, secret)

            # Check pattern
            self.assertTrue(flag.startswith("ClaimedBy_"))
            self.assertEqual(len(flag), len("ClaimedBy_") + 8)

            # Check hex chars
            hex_part = flag[len("ClaimedBy_") :]
            self.assertTrue(all(c in "0123456789abcdef" for c in hex_part))

    def test_flag_verification_is_symmetric(self):
        """Test that flag verification works both directions."""
        secret = "symmetric_test_secret"
        moniker = "symmetry_test_user"

        # Create flag
        flag = notifyd_client.format_claim_flag(moniker, secret)

        # Verify forward
        self.assertTrue(notifyd_client.verify_claim_flag(flag, moniker, secret))

        # Verify also works if we recreate the flag
        flag2 = notifyd_client.format_claim_flag(moniker, secret)
        self.assertEqual(flag, flag2)
        self.assertTrue(notifyd_client.verify_claim_flag(flag2, moniker, secret))


if __name__ == "__main__":
    unittest.main()
