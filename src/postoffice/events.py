# events.py
# Event type definitions for mcfeely notification system.

from enum import Enum


class EventType(str, Enum):
    """Event types fired by mcfeely IMAP monitoring."""

    MESSAGE_NEW = "message-new"
    MESSAGE_CLAIMED = "message-claimed"
    MESSAGE_UNCLAIMED = "message-unclaimed"
    MESSAGE_FLAGGED = "message-flagged"
    MESSAGE_DELETED = "message-deleted"


__all__ = ["EventType"]
