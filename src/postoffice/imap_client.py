# imap_client.py
# IMAP client operations for shared mailboxes.
# Handles message claiming/unclaiming and event firing.

from typing import Optional, Dict, Any

from bbsengine6 import io

from . import notifyd_client


def claim_message(
    args,
    mailbox_name: str,
    message_uid: int,
    actor_moniker: str,
    message_id: str = None,
    message_from: str = None,
    message_subject: str = None,
    imap_conn=None,
    db_conn=None,
) -> bool:
    """
    Claim a message in a shared mailbox.

    Updates Cyrus with claim flag and fires notification event.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name (e.g., 'shared/support@example.com')
        message_uid: IMAP UID of message
        actor_moniker: Moniker of user claiming message
        message_id: RFC 822 Message-ID (optional, for event data)
        message_from: Message From header (optional, for event data)
        message_subject: Message Subject header (optional, for event data)
        imap_conn: IMAP connection (optional, will create if needed)
        db_conn: Database connection (optional, for event firing)

    Returns: True on success, False on error
    """
    try:
        # Format the claim flag with obfuscation
        secret = notifyd_client.get_obfuscate_secret(args)
        claim_flag = notifyd_client.format_claim_flag(actor_moniker, secret)

        if getattr(args, "debug", False):
            io.echo(
                f"imap_client.claim_message: {mailbox_name} / {message_uid} / {claim_flag}",
                level="debug",
            )

        # If IMAP connection provided, set the flag
        if imap_conn:
            try:
                imap_conn.select(mailbox_name)
                imap_conn.store(str(message_uid), "+FLAGS", f"({claim_flag})")
            except Exception as e:
                io.echo(
                    f"imap_client.claim_message.100: IMAP error: {e}", level="error"
                )
                return False

        # Build event data
        event_data: Dict[str, Any] = {
            "event_type": "message-claimed",
            "mailbox_name": mailbox_name,
            "message_uid": message_uid,
            "actor_moniker": actor_moniker,
        }

        if message_id:
            event_data["message_id"] = message_id
        if message_from:
            event_data["from"] = message_from
        if message_subject:
            event_data["subject"] = message_subject

        # Fire notification event
        return notifyd_client.fire_event(
            args,
            mailbox_name,
            "message-claimed",
            event_data,
            actor_moniker=actor_moniker,
            conn=db_conn,
            close_conn=False,
        )

    except Exception as e:
        io.echo(f"imap_client.claim_message.200: {e}", level="error")
        return False


def unclaim_message(
    args,
    mailbox_name: str,
    message_uid: int,
    actor_moniker: str,
    imap_conn=None,
    db_conn=None,
) -> bool:
    """
    Unclaim a message in a shared mailbox (remove claim flag).

    Updates Cyrus and fires notification event.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name
        message_uid: IMAP UID of message
        actor_moniker: Moniker of user unclaiming message
        imap_conn: IMAP connection (optional)
        db_conn: Database connection (optional)

    Returns: True on success, False on error
    """
    try:
        # Format the claim flag with obfuscation
        secret = notifyd_client.get_obfuscate_secret(args)
        claim_flag = notifyd_client.format_claim_flag(actor_moniker, secret)

        if getattr(args, "debug", False):
            io.echo(
                f"imap_client.unclaim_message: {mailbox_name} / {message_uid} / {claim_flag}",
                level="debug",
            )

        # If IMAP connection provided, remove the flag
        if imap_conn:
            try:
                imap_conn.select(mailbox_name)
                imap_conn.store(str(message_uid), "-FLAGS", f"({claim_flag})")
            except Exception as e:
                io.echo(
                    f"imap_client.unclaim_message.100: IMAP error: {e}", level="error"
                )
                return False

        # Build event data
        event_data: Dict[str, Any] = {
            "event_type": "message-unclaimed",
            "mailbox_name": mailbox_name,
            "message_uid": message_uid,
            "actor_moniker": actor_moniker,
        }

        # Fire notification event
        return notifyd_client.fire_event(
            args,
            mailbox_name,
            "message-unclaimed",
            event_data,
            actor_moniker=actor_moniker,
            conn=db_conn,
            close_conn=False,
        )

    except Exception as e:
        io.echo(f"imap_client.unclaim_message.200: {e}", level="error")
        return False


def fire_new_message_event(
    args,
    mailbox_name: str,
    message_uid: int,
    message_id: str,
    message_from: str,
    message_subject: str,
    db_conn=None,
) -> bool:
    """
    Fire notification for newly arrived message.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name
        message_uid: IMAP UID
        message_id: RFC 822 Message-ID
        message_from: From header
        message_subject: Subject header
        db_conn: Database connection (optional)

    Returns: True on success, False on error
    """
    try:
        event_data: Dict[str, Any] = {
            "event_type": "message-new",
            "mailbox_name": mailbox_name,
            "message_uid": message_uid,
            "message_id": message_id,
            "from": message_from,
            "subject": message_subject,
        }

        return notifyd_client.fire_event(
            args,
            mailbox_name,
            "message-new",
            event_data,
            actor_moniker=None,
            conn=db_conn,
            close_conn=False,
        )

    except Exception as e:
        io.echo(f"imap_client.fire_new_message_event: {e}", level="error")
        return False


def fire_flag_changed_event(
    args,
    mailbox_name: str,
    message_uid: int,
    flag_name: str,
    added: bool,
    actor_moniker: Optional[str] = None,
    db_conn=None,
) -> bool:
    """
    Fire notification for flag change on message.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name
        message_uid: IMAP UID
        flag_name: Flag name (e.g., '\\Seen')
        added: True if flag was added, False if removed
        actor_moniker: User who triggered flag change (optional)
        db_conn: Database connection (optional)

    Returns: True on success, False on error
    """
    try:
        event_data: Dict[str, Any] = {
            "event_type": "message-flagged",
            "mailbox_name": mailbox_name,
            "message_uid": message_uid,
            "flag_name": flag_name,
            "added": added,
        }

        return notifyd_client.fire_event(
            args,
            mailbox_name,
            "message-flagged",
            event_data,
            actor_moniker=actor_moniker,
            conn=db_conn,
            close_conn=False,
        )

    except Exception as e:
        io.echo(f"imap_client.fire_flag_changed_event: {e}", level="error")
        return False


def fire_message_deleted_event(
    args, mailbox_name: str, message_uid: int, db_conn=None
) -> bool:
    """
    Fire notification for message deletion/expunge.

    Args:
        args: bbsengine6 args object
        mailbox_name: Mailbox name
        message_uid: IMAP UID
        db_conn: Database connection (optional)

    Returns: True on success, False on error
    """
    try:
        event_data: Dict[str, Any] = {
            "event_type": "message-deleted",
            "mailbox_name": mailbox_name,
            "message_uid": message_uid,
        }

        return notifyd_client.fire_event(
            args,
            mailbox_name,
            "message-deleted",
            event_data,
            actor_moniker=None,
            conn=db_conn,
            close_conn=False,
        )

    except Exception as e:
        io.echo(f"imap_client.fire_message_deleted_event: {e}", level="error")
        return False
