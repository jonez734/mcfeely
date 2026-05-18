# test_notifyd_client.py
# Unit tests for notifyd_client module
# Tests flag obfuscation, event configuration, routing, and event message rendering

import unittest
import json
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from postoffice import notifyd_client


class TestFlagObfuscation(unittest.TestCase):
    """Test Cyrus flag obfuscation with HMAC-SHA256."""

    def test_obfuscate_moniker_without_secret(self):
        """Moniker without secret returns plain moniker (fallback)."""
        result = notifyd_client.obfuscate_moniker("alice", secret=None)
        self.assertEqual(result, "alice")

    def test_obfuscate_moniker_with_secret(self):
        """Moniker with secret returns 8-char hex string."""
        result = notifyd_client.obfuscate_moniker("alice", secret="mysecret")
        self.assertEqual(len(result), 8)
        self.assertTrue(all(c in '0123456789abcdef' for c in result))

    def test_obfuscate_moniker_consistency(self):
        """Same moniker + secret always produces same hash."""
        secret = "test_secret_123"
        result1 = notifyd_client.obfuscate_moniker("alice", secret=secret)
        result2 = notifyd_client.obfuscate_moniker("alice", secret=secret)
        self.assertEqual(result1, result2)

    def test_obfuscate_moniker_different_inputs(self):
        """Different monikers produce different hashes."""
        secret = "test_secret"
        hash1 = notifyd_client.obfuscate_moniker("alice", secret=secret)
        hash2 = notifyd_client.obfuscate_moniker("bob", secret=secret)
        self.assertNotEqual(hash1, hash2)

    def test_format_claim_flag_plain(self):
        """Format flag without secret returns plain text flag."""
        result = notifyd_client.format_claim_flag("alice", secret=None)
        self.assertEqual(result, "ClaimedByAlice")

    def test_format_claim_flag_obfuscated(self):
        """Format flag with secret returns ClaimedBy_<8chars>."""
        result = notifyd_client.format_claim_flag("alice", secret="secret123")
        self.assertTrue(result.startswith("ClaimedBy_"))
        self.assertEqual(len(result), len("ClaimedBy_") + 8)

    def test_verify_claim_flag_plain(self):
        """Verify plain text flag matches."""
        flag = notifyd_client.format_claim_flag("alice", secret=None)
        self.assertTrue(
            notifyd_client.verify_claim_flag(flag, "alice", secret=None)
        )

    def test_verify_claim_flag_obfuscated(self):
        """Verify obfuscated flag matches."""
        secret = "test_secret"
        flag = notifyd_client.format_claim_flag("alice", secret=secret)
        self.assertTrue(
            notifyd_client.verify_claim_flag(flag, "alice", secret=secret)
        )

    def test_verify_claim_flag_wrong_moniker(self):
        """Verify fails with wrong moniker."""
        secret = "test_secret"
        flag = notifyd_client.format_claim_flag("alice", secret=secret)
        self.assertFalse(
            notifyd_client.verify_claim_flag(flag, "bob", secret=secret)
        )

    def test_verify_claim_flag_wrong_secret(self):
        """Verify fails with wrong secret."""
        flag = notifyd_client.format_claim_flag("alice", secret="secret1")
        self.assertFalse(
            notifyd_client.verify_claim_flag(flag, "alice", secret="secret2")
        )


class TestGetObfuscateSecret(unittest.TestCase):
    """Test secret retrieval from environment and args."""

    def test_get_secret_from_env(self):
        """Get secret from MCFEELY_OBFUSCATE_SECRET env var."""
        with patch.dict(os.environ, {"MCFEELY_OBFUSCATE_SECRET": "env_secret"}):
            args = Mock(databasepassword=None)
            result = notifyd_client.get_obfuscate_secret(args)
            self.assertEqual(result, "env_secret")

    def test_get_secret_from_args(self):
        """Get secret from args.databasepassword if no env var."""
        with patch.dict(os.environ, {}, clear=True):
            args = Mock(databasepassword="db_password")
            result = notifyd_client.get_obfuscate_secret(args)
            self.assertEqual(result, "db_password")

    def test_get_secret_env_takes_priority(self):
        """Env var takes priority over args."""
        with patch.dict(os.environ, {"MCFEELY_OBFUSCATE_SECRET": "env_secret"}):
            args = Mock(databasepassword="db_password")
            result = notifyd_client.get_obfuscate_secret(args)
            self.assertEqual(result, "env_secret")

    def test_get_secret_none_if_neither(self):
        """Return None if no env var or args secret."""
        with patch.dict(os.environ, {}, clear=True):
            args = Mock(databasepassword=None)
            result = notifyd_client.get_obfuscate_secret(args)
            self.assertIsNone(result)


class TestRenderEventMessage(unittest.TestCase):
    """Test human-readable event message rendering."""

    def test_render_message_claimed(self):
        """Render message for message-claimed event."""
        event_data = {"message_uid": 423}
        result = notifyd_client.render_event_message(
            "message-claimed", "alice", event_data
        )
        self.assertEqual(result, "alice claimed message #423")

    def test_render_message_unclaimed(self):
        """Render message for message-unclaimed event."""
        event_data = {"message_uid": 423}
        result = notifyd_client.render_event_message(
            "message-unclaimed", "alice", event_data
        )
        self.assertEqual(result, "alice unclaimed message #423")

    def test_render_message_new(self):
        """Render message for message-new event."""
        event_data = {
            "from": "user@example.com",
            "subject": "Help needed",
        }
        result = notifyd_client.render_event_message(
            "message-new", None, event_data
        )
        self.assertIn("user@example.com", result)
        self.assertIn("Help needed", result)

    def test_render_message_flagged(self):
        """Render message for message-flagged event."""
        event_data = {"flag_name": "\\Seen", "added": True}
        result = notifyd_client.render_event_message(
            "message-flagged", "alice", event_data
        )
        self.assertIn("alice", result)
        self.assertIn("set", result)
        self.assertIn("\\Seen", result)

    def test_render_message_flagged_removed(self):
        """Render message for message-flagged event (removed)."""
        event_data = {"flag_name": "\\Seen", "added": False}
        result = notifyd_client.render_event_message(
            "message-flagged", "alice", event_data
        )
        self.assertIn("cleared", result)

    def test_render_message_deleted(self):
        """Render message for message-deleted event."""
        event_data = {"message_uid": 423}
        result = notifyd_client.render_event_message(
            "message-deleted", None, event_data
        )
        self.assertEqual(result, "Message #423 deleted")

    def test_render_message_unknown_type(self):
        """Render generic message for unknown event type."""
        result = notifyd_client.render_event_message(
            "unknown-event", None, {}
        )
        self.assertIn("unknown-event", result)


class TestIsEventEnabled(unittest.TestCase):
    """Test event configuration checking."""

    def test_is_enabled_no_config(self):
        """Default to enabled if no config exists."""
        args = Mock(debug=False)
        conn = Mock()
        
        with patch('postoffice.notifyd_client.database') as mock_db:
            cursor = MagicMock()
            cursor.fetchone.return_value = None
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor
            
            result = notifyd_client.is_event_enabled(
                args, "shared/support", "message-new", conn=conn
            )
            self.assertTrue(result)

    def test_is_enabled_specific_event(self):
        """Check if specific event type is enabled."""
        args = Mock(debug=False)
        conn = Mock()
        
        # Config: enable_new_message_events=True
        config_row = (True, False, False, False)
        
        with patch('postoffice.notifyd_client.database') as mock_db:
            cursor = MagicMock()
            cursor.fetchone.return_value = config_row
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor
            
            result = notifyd_client.is_event_enabled(
                args, "shared/support", "message-new", conn=conn
            )
            self.assertTrue(result)

    def test_is_disabled_specific_event(self):
        """Check if specific event type is disabled."""
        args = Mock(debug=False)
        conn = Mock()
        
        # Config: enable_new_message_events=False
        config_row = (False, False, False, False)
        
        with patch('postoffice.notifyd_client.database') as mock_db:
            cursor = MagicMock()
            cursor.fetchone.return_value = config_row
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor
            
            result = notifyd_client.is_event_enabled(
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
        
        with patch('postoffice.notifyd_client.database') as mock_db:
            cursor = MagicMock()
            cursor.fetchall.return_value = [rule_row]
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor
            
            result = notifyd_client.get_routing_rules(
                args,
                "shared/support@machine1.example.com",
                "message-claimed",
                actor_moniker="alice",
                conn=conn
            )
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["recipient_moniker"], "recipient1")
            self.assertEqual(result[0]["urgency"], "IMPORTANT")

    def test_get_routing_rules_no_match(self):
        """Return empty list if no rules match."""
        args = Mock(debug=False)
        conn = Mock()
        
        with patch('postoffice.notifyd_client.database') as mock_db:
            cursor = MagicMock()
            cursor.fetchall.return_value = []
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor
            
            result = notifyd_client.get_routing_rules(
                args,
                "shared/support@machine1.example.com",
                "message-claimed",
                conn=conn
            )
            
            self.assertEqual(len(result), 0)

    def test_get_routing_rules_auto_notification_type(self):
        """Auto-generate notification_type if None in DB."""
        args = Mock(debug=False)
        conn = Mock()
        
        rule_row = ("recipient1", None, "ROUTINE", "engine")  # notification_type is None
        
        with patch('postoffice.notifyd_client.database') as mock_db:
            cursor = MagicMock()
            cursor.fetchall.return_value = [rule_row]
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor
            
            result = notifyd_client.get_routing_rules(
                args,
                "shared/support",
                "message-claimed",
                conn=conn
            )
            
            self.assertEqual(result[0]["notification_type"], "mcfeely-message-claimed")

    def test_get_routing_rules_pattern_actor_moniker_exact(self):
        """Match rule with exact actor_moniker."""
        args = Mock(debug=False)
        conn = Mock()
        
        rule_row = ("recipient1", "mcfeely-message-claimed", "IMPORTANT", "engine")
        
        with patch('postoffice.notifyd_client.database') as mock_db:
            cursor = MagicMock()
            cursor.fetchall.return_value = [rule_row]
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor
            
            result = notifyd_client.get_routing_rules(
                args,
                "shared/support@machine1.example.com",
                "message-claimed",
                actor_moniker="alice",
                conn=conn
            )
            
            # Verify that the query was executed with LIKE pattern
            call_args = cursor.execute.call_args
            self.assertIn("LIKE actor_moniker", call_args[0][0])

    def test_get_routing_rules_pattern_actor_moniker_null_matches_any(self):
        """NULL actor_moniker in rule matches any actual actor."""
        args = Mock(debug=False)
        conn = Mock()
        
        rule_row = ("admin", "mcfeely-message-claimed", "ROUTINE", "engine")
        
        with patch('postoffice.notifyd_client.database') as mock_db:
            cursor = MagicMock()
            cursor.fetchall.return_value = [rule_row]
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor
            
            result = notifyd_client.get_routing_rules(
                args,
                "shared/support@machine1.example.com",
                "message-claimed",
                actor_moniker="alice",
                conn=conn
            )
            
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["recipient_moniker"], "admin")


class TestFireEvent(unittest.TestCase):
    """Test event firing to engine.__notify."""

    def test_fire_event_success(self):
        """Fire event successfully inserts into engine.__notify."""
        args = Mock(debug=False, databasename="zoid6")
        conn = Mock()
        
        event_data = {
            "event_type": "message-claimed",
            "mailbox_name": "shared/support",
            "message_uid": 423,
            "actor_moniker": "alice",
        }
        
        with patch('postoffice.notifyd_client.database') as mock_db, \
             patch('postoffice.notifyd_client.get_routing_rules') as mock_rules, \
             patch('postoffice.notifyd_client.is_event_enabled') as mock_enabled, \
             patch('postoffice.notifyd_client.render_event_message') as mock_render:
            
            mock_enabled.return_value = True
            mock_rules.return_value = [
                {
                    "recipient_moniker": "bob",
                    "notification_type": "mcfeely-message-claimed",
                    "urgency": "IMPORTANT",
                    "delivery_method": "engine"
                }
            ]
            mock_render.return_value = "alice claimed message #423"
            
            cursor = MagicMock()
            cursor.__enter__.return_value = cursor
            mock_db.cursor.return_value = cursor
            
            result = notifyd_client.fire_event(
                args,
                "shared/support",
                "message-claimed",
                event_data,
                actor_moniker="alice",
                conn=conn,
            )
            
            self.assertTrue(result)
            mock_db.cursor.assert_called()
            cursor.execute.assert_called()
            conn.commit.assert_called()

    def test_fire_event_disabled(self):
        """Fire event returns True if event disabled (not an error)."""
        args = Mock(debug=False)
        conn = Mock()
        
        with patch('postoffice.notifyd_client.is_event_enabled') as mock_enabled:
            mock_enabled.return_value = False
            
            result = notifyd_client.fire_event(
                args,
                "shared/support",
                "message-new",
                {"event_type": "message-new"},
                conn=conn
            )
            
            self.assertTrue(result)

    def test_fire_event_no_routes(self):
        """Fire event returns True if no routing rules (nothing to deliver)."""
        args = Mock(debug=False)
        conn = Mock()
        
        with patch('postoffice.notifyd_client.is_event_enabled') as mock_enabled, \
             patch('postoffice.notifyd_client.get_routing_rules') as mock_rules:
            
            mock_enabled.return_value = True
            mock_rules.return_value = []
            
            result = notifyd_client.fire_event(
                args,
                "shared/support",
                "message-claimed",
                {"event_type": "message-claimed", "message_uid": 423},
                actor_moniker="alice",
                conn=conn
            )
            
            self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
