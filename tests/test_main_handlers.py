# test_main_handlers.py
# Tests for CLI handlers in postoffice.__main__ that resolve the current user
# from args.loginid with a getcurrentmoniker fallback (handle_tui,
# handle_sasl_password).

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_args(loginid=None, issuperuser=False):
    args = argparse.Namespace()
    args.loginid = loginid
    args.issuperuser = issuperuser
    return args


class TestHandleTui(unittest.TestCase):
    """Tests for postoffice.__main__.handle_tui.

    The handler invokes bbsengine6.screen.init() before the TUI loop,
    which requires a real tty. We patch screen.init so the test never
    touches the terminal.
    """

    def test_uses_loginid_when_provided(self):
        """When args.loginid is set, handle_tui passes it through and
        does not call getcurrentmoniker."""
        args = _make_args(loginid="alice")

        with patch("postoffice.__main__._message_interface_run") as mock_run, \
             patch("postoffice.__main__.startup.get_encryption_key", return_value=b"x" * 32), \
             patch("bbsengine6.screen.init"), \
             patch("postoffice.__main__.echo"), \
             patch("postoffice.__main__.member.getcurrentmoniker") as mock_moniker, \
             patch("postoffice.__main__.database.getpool") as mock_pool:
            mock_run.return_value = 0
            from postoffice.__main__ import handle_tui
            handle_tui(args)

        mock_moniker.assert_not_called()
        mock_pool.assert_not_called()
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        self.assertEqual(call_args[0][1], "alice")

    def test_falls_back_to_getcurrentmoniker_when_loginid_missing(self):
        """When args.loginid is None, handle_tui resolves current user
        via database.getpool + member.getcurrentmoniker."""
        args = _make_args(loginid=None)

        mock_pool_obj = MagicMock()
        with patch("postoffice.__main__._message_interface_run") as mock_run, \
             patch("postoffice.__main__.startup.get_encryption_key", return_value=b"x" * 32), \
             patch("bbsengine6.screen.init"), \
             patch("postoffice.__main__.echo"), \
             patch("postoffice.__main__.member.getcurrentmoniker", return_value="bob") as mock_moniker, \
             patch("postoffice.__main__.database.getpool", return_value=mock_pool_obj) as mock_pool:
            mock_run.return_value = 0
            from postoffice.__main__ import handle_tui
            handle_tui(args)

        mock_pool.assert_called_once_with(args)
        mock_moniker.assert_called_once()
        self.assertEqual(args.loginid, "bob")
        call_args = mock_run.call_args
        self.assertEqual(call_args[0][1], "bob")
        self.assertIs(call_args[1].get("pool"), mock_pool_obj)

    def test_returns_1_when_loginid_missing_and_db_pool_fails(self):
        """When loginid is missing and the database pool cannot be
        acquired, handle_tui returns 1 without entering the TUI."""
        args = _make_args(loginid=None)

        with patch("postoffice.__main__._message_interface_run") as mock_run, \
             patch("postoffice.__main__.startup.get_encryption_key", return_value=b"x" * 32), \
             patch("bbsengine6.screen.init"), \
             patch("postoffice.__main__.echo"), \
             patch("postoffice.__main__.database.getpool", side_effect=Exception("db down")):
            from postoffice.__main__ import handle_tui
            result = handle_tui(args)

        self.assertEqual(result, 1)
        mock_run.assert_not_called()

    def test_returns_1_when_loginid_missing_and_moniker_is_none(self):
        """When getcurrentmoniker returns None (no current user),
        handle_tui returns 1 cleanly."""
        args = _make_args(loginid=None)

        with patch("postoffice.__main__._message_interface_run") as mock_run, \
             patch("postoffice.__main__.startup.get_encryption_key", return_value=b"x" * 32), \
             patch("bbsengine6.screen.init"), \
             patch("postoffice.__main__.echo"), \
             patch("postoffice.__main__.member.getcurrentmoniker", return_value=None), \
             patch("postoffice.__main__.database.getpool", return_value=MagicMock()):
            from postoffice.__main__ import handle_tui
            result = handle_tui(args)

        self.assertEqual(result, 1)
        mock_run.assert_not_called()

    def test_returns_1_when_encryption_key_unavailable(self):
        """When no encryption key can be loaded, handle_tui bails before
        touching the database or TUI."""
        args = _make_args(loginid=None)

        with patch("postoffice.__main__._message_interface_run") as mock_run, \
             patch("postoffice.__main__.startup.get_encryption_key", return_value=None), \
             patch("postoffice.__main__.database.getpool") as mock_pool:
            from postoffice.__main__ import handle_tui
            result = handle_tui(args)

        self.assertEqual(result, 1)
        mock_pool.assert_not_called()
        mock_run.assert_not_called()


class TestHandleSaslPasswordUserResolution(unittest.TestCase):
    """Tests the user-resolution block at the top of handle_sasl_password.

    Covers the bug where the handler bailed with 'Could not determine
    current user' even after a successful getcurrentmoniker call. The
    resolution must succeed without raising on a successful resolve, and
    must return 1 only when no user is actually resolvable.

    Note: handle_sasl_password does ``from . import sasl_password``
    inside its body, so the patch target must be the source module
    (``postoffice.sasl_password``), not the parent module attribute.
    """

    def _setup_args(self, loginid=None, issuperuser=False, action=None,
                    target_moniker=None, password=None):
        args = _make_args(loginid=loginid, issuperuser=issuperuser)
        args.target_moniker = target_moniker
        args.sasl_action = action
        args.password = password
        return args

    def test_uses_loginid_when_provided(self):
        args = self._setup_args(loginid="alice", action="list")

        with patch("postoffice.__main__.startup.get_encryption_key", return_value=b"x" * 32), \
             patch("postoffice.__main__.member.getcurrentmoniker") as mock_moniker, \
             patch("postoffice.__main__.database.getpool") as mock_pool, \
             patch("postoffice.sasl_password.list_sasl_passwords", return_value=[]):
            from postoffice.__main__ import handle_sasl_password
            handle_sasl_password(args)

        mock_moniker.assert_not_called()
        mock_pool.assert_not_called()
        self.assertEqual(args.loginid, "alice")

    def test_falls_back_to_getcurrentmoniker_when_loginid_missing(self):
        args = self._setup_args(loginid=None, action="list")

        with patch("postoffice.__main__.startup.get_encryption_key", return_value=b"x" * 32), \
             patch("postoffice.__main__.member.getcurrentmoniker", return_value="bob") as mock_moniker, \
             patch("postoffice.__main__.database.getpool", return_value=MagicMock()) as mock_pool, \
             patch("postoffice.sasl_password.list_sasl_passwords", return_value=[]):
            from postoffice.__main__ import handle_sasl_password
            handle_sasl_password(args)

        mock_pool.assert_called_once_with(args)
        mock_moniker.assert_called_once()
        self.assertEqual(args.loginid, "bob")

    def test_successful_resolve_does_not_print_user_error(self):
        """Regression test: after a successful getcurrentmoniker, the
        handler must not echo 'Could not determine current user' or
        return 1. The action dispatch must proceed."""
        args = self._setup_args(loginid=None, action="list")

        with patch("postoffice.__main__.startup.get_encryption_key", return_value=b"x" * 32), \
             patch("postoffice.__main__.member.getcurrentmoniker", return_value="bob"), \
             patch("postoffice.__main__.database.getpool", return_value=MagicMock()), \
             patch("postoffice.sasl_password.list_sasl_passwords", return_value=[]) as mock_list, \
             patch("postoffice.__main__.echo") as mock_echo:
            from postoffice.__main__ import handle_sasl_password
            handle_sasl_password(args)

        mock_list.assert_called_once()
        for call in mock_echo.call_args_list:
            msg = call.args[0] if call.args else ""
            self.assertNotIn("Could not determine current user", str(msg))

    def test_returns_1_when_loginid_missing_and_db_pool_fails(self):
        args = self._setup_args(loginid=None, action="list")

        with patch("postoffice.__main__.startup.get_encryption_key", return_value=b"x" * 32), \
             patch("postoffice.__main__.database.getpool", side_effect=Exception("db down")):
            from postoffice.__main__ import handle_sasl_password
            result = handle_sasl_password(args)

        self.assertEqual(result, 1)

    def test_returns_1_when_loginid_missing_and_moniker_is_none(self):
        """When loginid is None and getcurrentmoniker also returns None,
        the handler must return 1 with a clear error."""
        args = self._setup_args(loginid=None, action="list")

        with patch("postoffice.__main__.startup.get_encryption_key", return_value=b"x" * 32), \
             patch("postoffice.__main__.member.getcurrentmoniker", return_value=None), \
             patch("postoffice.__main__.database.getpool", return_value=MagicMock()):
            from postoffice.__main__ import handle_sasl_password
            result = handle_sasl_password(args)

        self.assertEqual(result, 1)

    def test_returns_1_when_encryption_key_unavailable(self):
        args = self._setup_args(loginid=None, action="list")

        with patch("postoffice.__main__.startup.get_encryption_key", return_value=None), \
             patch("postoffice.__main__.database.getpool") as mock_pool:
            from postoffice.__main__ import handle_sasl_password
            result = handle_sasl_password(args)

        self.assertEqual(result, 1)
        mock_pool.assert_not_called()


if __name__ == "__main__":
    unittest.main()
