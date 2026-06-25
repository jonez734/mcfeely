# postoffice/services/__init__.py
# Services package: business-logic layer between the API and the DAL/IMAP
# primitives. One module per cohesive capability.
#
# This __init__ owns the service singleton lifecycle (get_service /
# start_service / stop_service / reset_service) and re-exports the
# public surface used by the rest of the codebase:
#
#     from postoffice.services import (
#         MailboxConfig,
#         MailboxPoller,
#         check_mail,
#         claim_message,
#         unclaim_message,
#         get_service,
#         start_service,
#         stop_service,
#         reset_service,
#         POSTOFFICE_CHANNEL,
#     )

from typing import Any, Dict, Optional

from .config import MailboxConfig, load_mailboxes
from .mailbox_poller import MailboxPoller
from . import check_mail as check_mail_module
from .check_mail import check_mail as run_check_mail
from . import claim as _claim

POSTOFFICE_CHANNEL = "postoffice:check_mail"

claim_message = _claim.claim_message
unclaim_message = _claim.unclaim_message
check_mail = run_check_mail

_service_instance: Optional[MailboxPoller] = None


def get_service(config: Optional[Dict[str, Any]] = None) -> MailboxPoller:
    """Return the singleton MailboxPoller, creating it on first call."""
    global _service_instance
    if _service_instance is None:
        _service_instance = MailboxPoller(config)
    return _service_instance


def start_service(config: Optional[Dict[str, Any]] = None) -> None:
    """Start the singleton poller's background task."""
    get_service(config).start()


def stop_service() -> None:
    """Stop the singleton poller and clear the singleton reference."""
    global _service_instance
    if _service_instance is not None:
        _service_instance.stop()
        _service_instance = None


def reset_service() -> None:
    """Clear the singleton reference without starting/stopping.

    Intended for test setup/teardown so each test gets a fresh instance.
    """
    global _service_instance
    _service_instance = None


__all__ = [
    "MailboxConfig",
    "MailboxPoller",
    "check_mail",
    "check_mail_module",
    "claim_message",
    "unclaim_message",
    "get_service",
    "start_service",
    "stop_service",
    "reset_service",
    "POSTOFFICE_CHANNEL",
    "load_mailboxes",
]
