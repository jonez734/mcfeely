# test_message_client.py
# Unit tests for message_client module
# Tests flag obfuscation, event configuration, routing, and event message rendering

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import message_client


class TestFlagObfuscation(unittest.TestCase):
    """Test Cyrus flag obfuscation with HMAC-SHA256."""

    def test_obfuscate_moniker_without_secret(self):
        """Moniker without secret returns plain moniker (fallback)."""
        result = message_client.obfuscate_moniker("alice", secret=None)
        self.assertEqual(result, "alice")

    def test_obfuscate_moniker_with_secret(self):
        """Moniker with secret returns 8-char hex string."""
        result = message_client.obfuscate_moniker("alice", secret="mysecret")
        self.assertEqual(len(result), 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_obfuscate_moniker_consistency(self):
        """Same moniker + secret always produces same hash."""
        secret = "test_secret_123"
        result1 = message_client.obfuscate_moniker("alice", secret=secret)
        result2 = message_client.obfuscate_moniker("alice", secret=secret)
        self.assertEqual(result1, result2)

    def test_obfuscate_moniker_different_inputs(self):
        """Different monikers produce different hashes."""
        secret = "test_secret"
        hash1 = message_client.obfuscate_moniker("alice", secret=secret)
        hash2 = message_client.obfuscate_moniker("bob", secret=secret)
        self.assertNotEqual(hash1, hash2)

    def test_format_claim_flag_plain(self):
        """Format flag without secret returns plain text flag."""
        result = message_client.format_claim_flag("alice", secret=None)
        self.assertEqual(result, "ClaimedByAlice")

    def test_format_claim_flag_obfuscated(self):
        """Format flag with secret returns ClaimedBy_<8chars>."""
        result = message_client.format_claim_flag("alice", secret="secret123")
        self.assertTrue(result.startswith("ClaimedBy_"))
        self.assertEqual(len(result), len("ClaimedBy_") + 8)

    def test_verify_claim_flag_plain(self):
        """Verify plain text flag matches."""
        flag = message_client.format_claim_flag("alice", secret=None)
        self.assertTrue(message_client.verify_claim_flag(flag, "alice", secret=None))

    def test_verify_claim_flag_obfuscated(self):
        """Verify obfuscated flag matches."""
        secret = "test_secret"
        flag = message_client.format_claim_flag("alice", secret=secret)
        self.assertTrue(message_client.verify_claim_flag(flag, "alice", secret=secret))

    def test_verify_claim_flag_wrong_moniker(self):
        """Verify fails with wrong moniker."""
        secret = "test_secret"
        flag = message_client.format_claim_flag("alice", secret=secret)
        self.assertFalse(message_client.verify_claim_flag(flag, "bob", secret=secret))

    def test_verify_claim_flag_wrong_secret(self):
        """Verify fails with wrong secret."""
        flag = message_client.format_claim_flag("alice", secret="secret1")
        self.assertFalse(
            message_client.verify_claim_flag(flag, "alice", secret="secret2")
        )

    def test_obfuscate_empty_moniker(self):
        """Test obfuscation with empty moniker."""
        result = message_client.obfuscate_moniker("", secret="secret")
        self.assertEqual(len(result), 8)

    def test_obfuscate_special_characters_in_moniker(self):
        """Test obfuscation with special characters in moniker."""
        result = message_client.obfuscate_moniker("alice_smith", secret="secret")
        self.assertEqual(len(result), 8)

    def test_format_claim_flag_preserves_case(self):
        """Test flag formatting preserves moniker case."""
        result_lower = message_client.format_claim_flag("ALICE", secret=None)
        result_upper = message_client.format_claim_flag("alice", secret=None)
        self.assertEqual(result_lower, result_upper)

    def test_obfuscate_moniker_unicode(self):
        """Test obfuscation with unicode characters."""
        result = message_client.obfuscate_moniker("café", secret="secret")
        self.assertEqual(len(result), 8)

    def test_obfuscate_moniker_long_moniker(self):
        """Test obfuscation with long moniker."""
        result = message_client.obfuscate_moniker("very_long_moniker_name", secret="secret")
        self.assertEqual(len(result), 8)

    def test_format_claim_flag_multiple_calls_same_result(self):
        """Test that multiple calls produce same result."""
        flag1 = message_client.format_claim_flag("alice", "secret")
        flag2 = message_client.format_claim_flag("alice", "secret")
        self.assertEqual(flag1, flag2)

    def test_verify_claim_flag_plain_with_obfuscated_expected(self):
        """Test verification fails when flag was obfuscated but checking plain."""
        flag = message_client.format_claim_flag("alice", "secret")
        self.assertFalse(message_client.verify_claim_flag(flag, "alice", None))

    def test_flag_verification_symmetric(self):
        """Test that flag can be verified both ways."""
        moniker = "testuser"
        secret = "symmetric_secret"
        flag = message_client.format_claim_flag(moniker, secret)
        self.assertTrue(message_client.verify_claim_flag(flag, moniker, secret))


class TestGetObfuscateSecret(unittest.TestCase):
    """Test secret retrieval from environment and args."""

    def setUp(self):
        self.original_env = os.environ.get("MCFEELY_OBFUSCATE_SECRET")

    def tearDown(self):
        if self.original_env is not None:
            os.environ["MCFEELY_OBFUSCATE_SECRET"] = self.original_env
        elif "MCFEELY_OBFUSCATE_SECRET" in os.environ:
            del os.environ["MCFEELY_OBFUSCATE_SECRET"]

    def test_get_secret_from_env(self):
        """Get secret from MCFEELY_OBFUSCATE_SECRET env var."""
        os.environ["MCFEELY_OBFUSCATE_SECRET"] = "env_secret"
        args = Mock(databasepassword=None)
        result = message_client.get_obfuscate_secret(args)
        self.assertEqual(result, "env_secret")

    def test_get_secret_from_args(self):
        """Get secret from args.databasepassword if no env var."""
        if "MCFEELY_OBFUSCATE_SECRET" in os.environ:
            del os.environ["MCFEELY_OBFUSCATE_SECRET"]
        args = Mock(databasepassword="db_password")
        result = message_client.get_obfuscate_secret(args)
        self.assertEqual(result, "db_password")

    def test_get_secret_env_takes_priority(self):
        """Env var takes priority over args."""
        os.environ["MCFEELY_OBFUSCATE_SECRET"] = "env_secret"
        args = Mock(databasepassword="db_password")
        result = message_client.get_obfuscate_secret(args)
        self.assertEqual(result, "env_secret")

    def test_get_secret_none_if_neither(self):
        """Return None if no env var or args secret."""
        if "MCFEELY_OBFUSCATE_SECRET" in os.environ:
            del os.environ["MCFEELY_OBFUSCATE_SECRET"]
        args = Mock(databasepassword=None)
        result = message_client.get_obfuscate_secret(args)
        self.assertIsNone(result)

    def test_get_secret_empty_env_var(self):
        """Test with empty string env var - empty string is falsy, so returns args secret."""
        os.environ["MCFEELY_OBFUSCATE_SECRET"] = ""
        args = Mock(databasepassword="db_password")
        result = message_client.get_obfuscate_secret(args)
        self.assertEqual(result, "db_password")

    def test_get_secret_args_has_empty_password(self):
        """Test when args has empty databasepassword - empty string is falsy, returns None."""
        if "MCFEELY_OBFUSCATE_SECRET" in os.environ:
            del os.environ["MCFEELY_OBFUSCATE_SECRET"]
        args = Mock(databasepassword="")
        result = message_client.get_obfuscate_secret(args)
        self.assertIsNone(result)


class TestRenderEventMessage(unittest.TestCase):
    """Test human-readable event message rendering."""

    def test_render_message_claimed(self):
        """Render message for message-claimed event."""
        event_data = {"message_uid": 423}
        result = message_client.render_event_message(
            "message-claimed", "alice", event_data
        )
        self.assertEqual(result, "alice claimed message #423")

    def test_render_message_unclaimed(self):
        """Render message for message-unclaimed event."""
        event_data = {"message_uid": 423}
        result = message_client.render_event_message(
            "message-unclaimed", "alice", event_data
        )
        self.assertEqual(result, "alice unclaimed message #423")

    def test_render_message_new(self):
        """Render message for message-new event."""
        event_data = {
            "from": "user@example.com",
            "subject": "Help needed",
        }
        result = message_client.render_event_message("message-new", None, event_data)
        self.assertIn("user@example.com", result)
        self.assertIn("Help needed", result)

    def test_render_message_flagged(self):
        """Render message for message-flagged event."""
        event_data = {"flag_name": "\\Seen", "added": True}
        result = message_client.render_event_message(
            "message-flagged", "alice", event_data
        )
        self.assertIn("alice", result)
        self.assertIn("set", result)
        self.assertIn("\\Seen", result)

    def test_render_message_flagged_removed(self):
        """Render message for message-flagged event (removed)."""
        event_data = {"flag_name": "\\Seen", "added": False}
        result = message_client.render_event_message(
            "message-flagged", "alice", event_data
        )
        self.assertIn("cleared", result)

    def test_render_message_deleted(self):
        """Render message for message-deleted event."""
        event_data = {"message_uid": 423}
        result = message_client.render_event_message(
            "message-deleted", None, event_data
        )
        self.assertEqual(result, "Message #423 deleted")

    def test_render_message_unknown_type(self):
        """Render generic message for unknown event type."""
        result = message_client.render_event_message("unknown-event", None, {})
        self.assertIn("unknown-event", result)

    def test_render_message_missing_from(self):
        """Test rendering with missing from field."""
        result = message_client.render_event_message(
            "message-new", None, {"subject": "Test"}
        )
        self.assertIn("unknown", result)

    def test_render_message_missing_subject(self):
        """Test rendering with missing subject field."""
        result = message_client.render_event_message(
            "message-new", None, {"from": "user@example.com"}
        )
        self.assertIn("(no subject)", result)

    def test_render_message_missing_flag_name(self):
        """Test rendering with missing flag_name."""
        result = message_client.render_event_message(
            "message-flagged", "alice", {"added": True}
        )
        self.assertIn("?", result)

    def test_render_message_special_characters_in_from(self):
        """Test rendering with special characters in from."""
        result = message_client.render_event_message(
            "message-new", None, {"from": "te+st@example.com", "subject": "Test"}
        )
        self.assertIn("te+st@example.com", result)

    def test_render_message_special_characters_in_subject(self):
        """Test rendering with special characters in subject."""
        result = message_client.render_event_message(
            "message-new", None, {"from": "user@example.com", "subject": "Re: <URGENT> Test"}
        )
        self.assertIn("URGENT", result)

    def test_render_message_with_unicode(self):
        """Test rendering with unicode characters."""
        result = message_client.render_event_message(
            "message-new", None, {"from": "café@example.com", "subject": "Héllo 世界"}
        )
        self.assertIsInstance(result, str)

    def test_render_message_with_empty_data(self):
        """Test rendering with minimal data."""
        result = message_client.render_event_message(
            "message-deleted", None, {}
        )
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


class TestIsEventEnabled(unittest.TestCase):
    """Test event configuration checking."""

    def test_is_enabled_no_config(self):
        """Default to enabled if no config exists."""
        args = Mock(debug=False)
        conn = Mock()

        with patch("postoffice.message_client.database") as mock_db:
            cursor = MagicMock()
            cursor.fetchone.return_value = None
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor

            result = message_client.is_event_enabled(
                args, "shared/support", "message-new", conn=conn
            )
            self.assertTrue(result)

    def test_is_enabled_specific_event(self):
        """Check if specific event type is enabled."""
        args = Mock(debug=False)
        conn = Mock()

        # Config: enable_new_message_events=True
        config_row = (True, False, False, False)

        with patch("postoffice.message_client.database") as mock_db:
            cursor = MagicMock()
            cursor.fetchone.return_value = config_row
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor

            result = message_client.is_event_enabled(
                args, "shared/support", "message-new", conn=conn
            )
            self.assertTrue(result)

    def test_is_disabled_specific_event(self):
        """Check if specific event type is disabled."""
        args = Mock(debug=False)
        conn = Mock()

        # Config: enable_new_message_events=False
        config_row = (False, False, False, False)

        with patch("postoffice.message_client.database") as mock_db:
            cursor = MagicMock()
            cursor.fetchone.return_value = config_row
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor

            result = message_client.is_event_enabled(
                args, "shared/support", "message-new", conn=conn
            )
            self.assertFalse(result)


class TestGetRoutingRules(unittest.TestCase):
    """Test routing rule queries with pattern matching."""

    def test_get_routing_rules_exact_match(self):
        """Query exact mailbox name match."""
        args = Mock(debug=False)
        conn = Mock()

        rule_row = ("recipient1", "mcfeely-message-claimed", "IMPORTANT", "engine")

        with patch("postoffice.message_client.database") as mock_db:
            cursor = MagicMock()
            cursor.fetchall.return_value = [rule_row]
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor

            result = message_client.get_routing_rules(
                args,
                "shared/support@machine1.example.com",
                "message-claimed",
                actor_moniker="alice",
                conn=conn,
            )

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["recipient_moniker"], "recipient1")
            self.assertEqual(result[0]["urgency"], "IMPORTANT")

    def test_get_routing_rules_no_match(self):
        """Return empty list if no rules match."""
        args = Mock(debug=False)
        conn = Mock()

        with patch("postoffice.message_client.database") as mock_db:
            cursor = MagicMock()
            cursor.fetchall.return_value = []
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor

            result = message_client.get_routing_rules(
                args,
                "shared/support@machine1.example.com",
                "message-claimed",
                conn=conn,
            )

            self.assertEqual(len(result), 0)

    def test_get_routing_rules_auto_notification_type(self):
        """Auto-generate notification_type if None in DB."""
        args = Mock(debug=False)
        conn = Mock()

        rule_row = (
            "recipient1",
            None,
            "ROUTINE",
            "engine",
        )  # notification_type is None

        with patch("postoffice.message_client.database") as mock_db:
            cursor = MagicMock()
            cursor.fetchall.return_value = [rule_row]
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor

            result = message_client.get_routing_rules(
                args, "shared/support", "message-claimed", conn=conn
            )

            self.assertEqual(result[0]["notification_type"], "mcfeely-message-claimed")

    def test_get_routing_rules_pattern_actor_moniker_exact(self):
        """Match rule with exact actor_moniker."""
        args = Mock(debug=False)
        conn = Mock()

        rule_row = ("recipient1", "mcfeely-message-claimed", "IMPORTANT", "engine")

        with patch("postoffice.message_client.database") as mock_db:
            cursor = MagicMock()
            cursor.fetchall.return_value = [rule_row]
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor

            message_client.get_routing_rules(
                args,
                "shared/support@machine1.example.com",
                "message-claimed",
                actor_moniker="alice",
                conn=conn,
            )

            # Verify that the query was executed with LIKE pattern
            call_args = cursor.execute.call_args
            self.assertIn("LIKE actor_moniker", call_args[0][0])

    def test_get_routing_rules_pattern_actor_moniker_null_matches_any(self):
        """NULL actor_moniker in rule matches any actual actor."""
        args = Mock(debug=False)
        conn = Mock()

        rule_row = ("admin", "mcfeely-message-claimed", "ROUTINE", "engine")

        with patch("postoffice.message_client.database") as mock_db:
            cursor = MagicMock()
            cursor.fetchall.return_value = [rule_row]
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor

            result = message_client.get_routing_rules(
                args,
                "shared/support@machine1.example.com",
                "message-claimed",
                actor_moniker="alice",
                conn=conn,
            )

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["recipient_moniker"], "admin")


class TestFireEvent(unittest.TestCase):
    """Test event firing via bbsengine6.message.send (post-migration)."""

    def test_fire_event_success(self):
        """Fire event successfully sends via bbsengine6.message.send."""
        args = Mock(debug=False, databasename="postoffice")
        conn = Mock()

        event_data = {
            "event_type": "message-claimed",
            "mailbox_name": "shared/support",
            "message_uid": 423,
            "actor_moniker": "alice",
        }

        with (
            patch("postoffice.message_client.get_routing_rules") as mock_rules,
            patch("postoffice.message_client.is_event_enabled") as mock_enabled,
            patch("postoffice.message_client.render_event_message") as mock_render,
            patch("postoffice.message_client._message_send") as mock_send,
        ):
            mock_enabled.return_value = True
            mock_rules.return_value = [
                {
                    "recipient_moniker": "bob",
                    "notification_type": "mcfeely-message-claimed",
                    "urgency": "IMPORTANT",
                    "delivery_method": "engine",
                }
            ]
            mock_render.return_value = "alice claimed message #423"

            result = message_client.fire_event(
                args,
                "shared/support",
                "message-claimed",
                event_data,
                actor_moniker="alice",
                conn=conn,
            )

            self.assertTrue(result)
            mock_send.assert_called_once()
            kwargs = mock_send.call_args.kwargs
            self.assertEqual(kwargs["notification_type"], "mcfeely-message-claimed")
            self.assertEqual(kwargs["recipients"], ["bob"])
            self.assertEqual(kwargs["sender_moniker"], "alice")
            self.assertEqual(kwargs["urgency"], "IMPORTANT")
            self.assertEqual(kwargs["template"], "alice claimed message #423")
            self.assertIs(kwargs["args"], args)

    def test_fire_event_disabled(self):
        """Fire event returns True if event disabled (not an error)."""
        args = Mock(debug=False)
        conn = Mock()

        with patch("postoffice.message_client.is_event_enabled") as mock_enabled:
            mock_enabled.return_value = False

            result = message_client.fire_event(
                args,
                "shared/support",
                "message-new",
                {"event_type": "message-new"},
                conn=conn,
            )

            self.assertTrue(result)

    def test_fire_event_no_routes(self):
        """Fire event returns True if no routing rules (nothing to deliver)."""
        args = Mock(debug=False)
        conn = Mock()

        with (
            patch("postoffice.message_client.is_event_enabled") as mock_enabled,
            patch("postoffice.message_client.get_routing_rules") as mock_rules,
        ):
            mock_enabled.return_value = True
            mock_rules.return_value = []

            result = message_client.fire_event(
                args,
                "shared/support",
                "message-claimed",
                {"event_type": "message-claimed", "message_uid": 423},
                actor_moniker="alice",
                conn=conn,
            )

            self.assertTrue(result)

    def test_fire_event_multiple_rules(self):
        """Test fire_event with multiple routing rules."""
        args = Mock(debug=False, databasename="postoffice")
        conn = Mock()

        with (
            patch("postoffice.message_client.is_event_enabled") as mock_enabled,
            patch("postoffice.message_client.get_routing_rules") as mock_rules,
            patch("postoffice.message_client.render_event_message") as mock_render,
            patch("postoffice.message_client._message_send") as mock_send,
        ):
            mock_enabled.return_value = True
            mock_rules.return_value = [
                {"recipient_moniker": "alice", "notification_type": "mcfeely-msg", "urgency": "IMPORTANT", "delivery_method": "engine"},
                {"recipient_moniker": "bob", "notification_type": "mcfeely-msg", "urgency": "ROUTINE", "delivery_method": "engine"},
            ]
            mock_render.return_value = "test message"

            result = message_client.fire_event(
                args,
                "shared/support",
                "message-new",
                {"event_type": "message-new", "message_uid": 123},
                conn=conn,
            )

            self.assertTrue(result)
            self.assertEqual(mock_send.call_count, 2)

    def test_fire_event_no_connection(self):
        """Test fire_event returns False when no connection provided."""
        args = Mock(debug=False)

        result = message_client.fire_event(
            args,
            "shared/support",
            "message-claimed",
            {"event_type": "message-claimed"},
        )

        self.assertFalse(result)


class TestEventMessageTemplatesCompleteness(unittest.TestCase):
    """Tests for complete event template coverage."""

    def test_all_event_types_have_templates(self):
        """Test all event types have message templates."""
        event_types = [
            "message-new",
            "message-claimed",
            "message-unclaimed",
            "message-flagged",
            "message-deleted",
        ]

        for event_type in event_types:
            self.assertIn(event_type, message_client.EVENT_MESSAGE_TEMPLATES)

    def test_templates_contain_format_placeholders(self):
        """Test templates contain format placeholders."""
        for event_type, template in message_client.EVENT_MESSAGE_TEMPLATES.items():
            self.assertIn("{", template)

    def test_template_fields_exist_in_template(self):
        """Test that required fields appear in template strings."""
        templates = message_client.EVENT_MESSAGE_TEMPLATES
        self.assertIn("{from}", templates["message-new"])
        self.assertIn("{subject}", templates["message-new"])
        self.assertIn("{actor_moniker}", templates["message-claimed"])
        self.assertIn("{message_uid}", templates["message-claimed"])


class TestEventRoutingPatternMatching(unittest.TestCase):
    """Tests for event routing SQL LIKE pattern matching."""

    def test_routing_query_structure(self):
        """Test that routing query uses LIKE for pattern matching."""
        args = Mock(debug=False)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cursor

        with patch("postoffice.message_client.lib.get_db_connection") as mock_get_conn:
            mock_get_conn.return_value = (conn, False)

            message_client.get_routing_rules(
                args,
                "shared/support@example.com",
                "message-claimed",
                "alice",
            )

            query = cursor.execute.call_args[0][0]
            self.assertIn("%s LIKE", query)
            self.assertIn("mailbox_name", query)

    def test_routing_actor_pattern_matching(self):
        """Test that actor moniker supports pattern matching."""
        args = Mock(debug=False)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cursor

        with patch("postoffice.message_client.lib.get_db_connection") as mock_get_conn:
            mock_get_conn.return_value = (conn, False)

            message_client.get_routing_rules(
                args,
                "shared/support",
                "message-claimed",
                actor_moniker="alice%",
            )

            query = cursor.execute.call_args[0][0]
            params = cursor.execute.call_args[0][1]
            self.assertIn("actor_moniker", query)
            self.assertIn("alice%", params)


class TestNotificationConfigQueries(unittest.TestCase):
    """Tests for notification config query structure."""

    def test_config_query_structure(self):
        """Test that config query uses mailbox_name."""
        args = Mock(debug=False)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value = cursor

        with patch("postoffice.message_client.lib.get_db_connection") as mock_get_conn:
            mock_get_conn.return_value = (conn, False)

            message_client.is_event_enabled(
                args,
                "shared/support@example.com",
                "message-new",
            )

            query = cursor.execute.call_args[0][0]
            self.assertIn("mailbox_name", query)
            self.assertIn("message_config", query)


class TestConnectionCleanup(unittest.TestCase):
    """Tests for connection cleanup in event functions."""

    def setUp(self):
        self.original_env = os.environ.get("MCFEELY_OBFUSCATE_SECRET")

    def tearDown(self):
        if self.original_env is not None:
            os.environ["MCFEELY_OBFUSCATE_SECRET"] = self.original_env
        elif "MCFEELY_OBFUSCATE_SECRET" in os.environ:
            del os.environ["MCFEELY_OBFUSCATE_SECRET"]

    @patch("postoffice.message_client.lib.get_db_connection")
    def test_connection_closed_after_is_event_enabled(self, mock_get_conn):
        """Test that connection is closed when should_close is True."""
        args = Mock(debug=False)
        mock_conn = MagicMock()
        mock_get_conn.return_value = (mock_conn, True)

        cursor = MagicMock()
        cursor.fetchone.return_value = None
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = cursor

        message_client.is_event_enabled(args, "shared/support", "message-new")

        mock_conn.close.assert_called_once()

    @patch("postoffice.message_client.lib.get_db_connection")
    def test_connection_not_closed_when_explicit(self, mock_get_conn):
        """Test that connection is not closed when conn is explicitly provided."""
        args = Mock(debug=False)
        mock_conn = MagicMock()
        mock_get_conn.return_value = (mock_conn, False)

        cursor = MagicMock()
        cursor.fetchone.return_value = None
        cursor.__enter__ = MagicMock(return_value=cursor)
        cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = cursor

        message_client.is_event_enabled(args, "shared/support", "message-new", conn=mock_conn)

        mock_conn.close.assert_not_called()
