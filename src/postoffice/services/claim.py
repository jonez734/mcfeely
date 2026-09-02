# postoffice/services/claim.py
# Message claim / unclaim service.
#
# Thin wrapper over the low-level postoffice_client.claim_message /
# postoffice_client.unclaim_message functions, exposing an intention-revealing
# surface so callers don't import the IMAP client directly.
# Future business rules (sysop override, session-bound claims, etc.)
# should land here.

from typing import Any

from . import postoffice_client


def claim_message(
    args: Any,
    mailbox_name: str,
    message_uid: int,
    actor_moniker: str,
    message_id: str = "",
    message_from: str = "",
    message_subject: str = "",
    **kwargs: Any,
) -> bool:
    """Claim a message in a shared mailbox on behalf of `actor_moniker`."""
    return postoffice_client.claim_message(
        args,
        mailbox_name,
        message_uid,
        actor_moniker,
        message_id=message_id,
        message_from=message_from,
        message_subject=message_subject,
        **kwargs,
    )


def unclaim_message(
    args: Any,
    mailbox_name: str,
    message_uid: int,
    actor_moniker: str,
    **kwargs: Any,
) -> bool:
    """Remove `actor_moniker`'s claim from a message in a shared mailbox."""
    return postoffice_client.unclaim_message(
        args,
        mailbox_name,
        message_uid,
        actor_moniker,
        **kwargs,
    )
