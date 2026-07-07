# conftest.py
# pytest configuration for jam mailbox integration tests
# Reads passwords from environment variables so getpass doesn't block pytest.
#
# Usage:
#   CYRUS_ADMIN_PASSWORD=... JAM_IMAP_PASSWORD=... python -m pytest tests/test_jam_mailbox_integration.py -v
#
# To skip interactive prompts entirely, ensure both env vars are set.
# Checks for a running venv at /home/opencode/.venv to avoid nested activation.

import os

os.environ.setdefault("JAM_IMAP_PASSWORD", "")
os.environ.setdefault("CYRUS_ADMIN_PASSWORD", "")


def pytest_configure(config):
    venv_path = "/home/opencode/.venv"
    active = os.environ.get("VIRTUAL_ENV", "")
    if active and active != venv_path:
        import warnings

        warnings.warn(
            f"Non-standard venv active ({active}). Tests expect {venv_path}.",
            UserWarning,
        )