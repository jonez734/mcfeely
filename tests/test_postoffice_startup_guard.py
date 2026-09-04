# tests/test_postoffice_startup_guard.py
# Tests for the bbsengine6 startup guard at the top of
# postoffice.__main__.main and the postoffice module's startup hook.
#
# Mirrors the casino pattern: bin/casino calls runmodule(args, "startup",
# package="bbsengine6") at the top of its direct-mode branch. We do
# the same in postoffice.__main__.main so that every invocation of
# bin/postoffice (or `python -m postoffice`) runs the full bbsengine6
# startup chain, which transitively runs postoffice.startup.startup_main
# via the postoffice module's `startup` hook.

import argparse
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_parsed_args(command="menu", **overrides):
    args = argparse.Namespace()
    args.command = command
    args.version = False
    args.verbose = False
    args.debug = False
    args.loginid = None
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


class TestPostofficeMainRunsStartupGuard(unittest.TestCase):
    """postoffice.__main__.main must invoke
    runmodule(args, "startup", package="bbsengine6") before any
    subcommand handler runs."""

    def test_startup_guard_runs_before_subcommand(self):
        from postoffice import __main__ as postoffice_main

        with patch(
            "bbsengine6.module.runmodule", return_value=True
        ) as mock_runmodule, \
             patch.object(postoffice_main, "handle_menu", return_value=True) as mock_handler:
            parsed = _make_parsed_args(command="menu")
            postoffice_main.main(parsed)

        # Startup guard was called.
        self.assertTrue(mock_runmodule.called)
        # First positional call args: (parsed, "startup").
        first_call = mock_runmodule.call_args_list[0]
        self.assertEqual(first_call[0][0], parsed)
        self.assertEqual(first_call[0][1], "startup")
        self.assertEqual(first_call[1].get("package"), "bbsengine6")
        # Subcommand handler ran AFTER the startup guard.
        self.assertTrue(mock_handler.called)

    def test_startup_failure_aborts_subcommand(self):
        from postoffice import __main__ as postoffice_main

        with patch(
            "bbsengine6.module.runmodule", return_value=False
        ) as mock_runmodule, \
             patch.object(postoffice_main, "handle_menu", return_value=True) as mock_handler, \
             patch("postoffice.__main__.echo"):
            parsed = _make_parsed_args(command="menu")
            result = postoffice_main.main(parsed)

        # Startup guard was called.
        self.assertTrue(mock_runmodule.called)
        # Subcommand handler did NOT run.
        self.assertFalse(mock_handler.called)
        # main() returned False (failure).
        self.assertFalse(result)

    def test_version_skips_startup_guard(self):
        """--version should not run the startup chain (no DB needed)."""
        from postoffice import __main__ as postoffice_main

        with patch(
            "bbsengine6.module.runmodule", return_value=True
        ) as mock_runmodule, \
             patch("postoffice.__main__.echo"):
            parsed = _make_parsed_args(command="menu", version=True)
            result = postoffice_main.main(parsed)

        # No startup guard for --version.
        self.assertFalse(mock_runmodule.called)
        self.assertTrue(result)


class TestPostofficeStartupHook(unittest.TestCase):
    """postoffice (the package) exposes ``init`` as its bbsengine6
    module-conventional hook, matching casino's pattern. It delegates
    to startup.startup_main when given a pool."""

    def test_package_has_init_hook(self):
        import postoffice
        self.assertTrue(hasattr(postoffice, "init"))
        self.assertTrue(callable(postoffice.init))

    def test_package_init_with_no_pool_returns_true(self):
        """When no pool is supplied, init returns True (nothing to do)."""
        import postoffice
        result = postoffice.init(MagicMock(), pool=None)
        self.assertTrue(result)

    def test_package_init_delegates_to_startup_main(self):
        """When a pool is supplied, init delegates to startup.startup_main."""
        import postoffice
        postoffice_startup_mod = sys.modules["postoffice.startup"]

        mock_args = MagicMock()
        mock_pool = MagicMock()

        with patch.object(
            postoffice_startup_mod, "startup_main", return_value=True
        ) as mock_startup_main:
            result = postoffice.init(mock_args, pool=mock_pool)

        mock_startup_main.assert_called_once_with(mock_args, pool=mock_pool)
        self.assertTrue(result)

    def test_package_init_returns_false_on_delegate_failure(self):
        import postoffice
        postoffice_startup_mod = sys.modules["postoffice.startup"]

        mock_args = MagicMock()
        mock_pool = MagicMock()

        with patch.object(
            postoffice_startup_mod, "startup_main", return_value=False
        ):
            result = postoffice.init(mock_args, pool=mock_pool)

        self.assertFalse(result)


class TestPostofficeStartupMainDelegate(unittest.TestCase):
    """postoffice.startup.main() is a thin delegate that calls
    startup_main(). Required so bbsengine6.startup.main can dispatch
    into postoffice.startup via runmodule(args, "startup",
    package="postoffice") -- same shape as casino.startup.main."""

    def test_main_delegates_to_startup_main(self):
        postoffice_startup_mod = sys.modules["postoffice.startup"]

        mock_args = MagicMock()
        with patch.object(
            postoffice_startup_mod, "startup_main", return_value=True
        ) as mock_startup_main:
            result = postoffice_startup_mod.main(mock_args, conn="fake-conn")

        mock_startup_main.assert_called_once_with(
            mock_args, conn="fake-conn"
        )
        self.assertTrue(result)

    def test_main_returns_false_on_delegate_failure(self):
        postoffice_startup_mod = sys.modules["postoffice.startup"]

        mock_args = MagicMock()
        with patch.object(
            postoffice_startup_mod, "startup_main", return_value=False
        ):
            result = postoffice_startup_mod.main(mock_args)

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
