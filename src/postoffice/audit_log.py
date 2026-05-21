# audit_log.py
# Password operation logging via bbsengine6.logentry()

from typing import Optional, Any
from bbsengine6.io import echo


def log_password_operation(action: str, target_type: str, target_moniker: str,
                          password_type: str, performed_by: str,
                          mailbox_id: Optional[int] = None,
                          reason: Optional[str] = None,
                          log_entry_fn: Optional[Any] = None) -> bool:
    """Log a password operation via bbsengine6.logentry().
    
    Args:
        action: 'set', 'delete', 'access', 'auth_fail', etc.
        target_type: 'personal' or 'shared_mailbox'.
        target_moniker: Member's moniker being affected.
        password_type: 'inbound' or 'outbound'.
        performed_by: Moniker of who performed the action.
        mailbox_id: Mailbox ID (None for personal passwords).
        reason: Optional reason/details of the operation.
        log_entry_fn: bbsengine6's logentry function.
    
    Returns:
        True if logging succeeded, False otherwise.
    """
    if not log_entry_fn:
        # If no logger provided, just skip (don't error)
        return True
    
    # Build structured message
    msg_parts = [
        f"[PASSWORD] {action.upper()}",
        f"type={target_type}",
        f"member={target_moniker}",
        f"pwd_type={password_type}",
        f"by={performed_by}",
    ]
    
    if mailbox_id:
        msg_parts.append(f"mailbox_id={mailbox_id}")
    
    if reason:
        msg_parts.append(f"reason={reason}")
    
    message = " | ".join(msg_parts)
    
    try:
        log_entry_fn(message)
        return True
    except Exception as e:
        echo(f"audit_log.log_password_operation: logging failed: {e}",
             level="error")
        return False


def log_auth_failure(member_moniker: str, password_type: str, reason: str,
                    mailbox_id: Optional[int] = None,
                    log_entry_fn: Optional[Any] = None) -> bool:
    """Log authentication failure.
    
    Args:
        member_moniker: Member who failed authentication.
        password_type: 'inbound' or 'outbound'.
        reason: Why authentication failed.
        mailbox_id: Mailbox ID (None for personal account).
        log_entry_fn: bbsengine6's logentry function.
    
    Returns:
        True if logging succeeded, False otherwise.
    """
    return log_password_operation(
        action="auth_fail",
        target_type="shared_mailbox" if mailbox_id else "personal",
        target_moniker=member_moniker,
        password_type=password_type,
        performed_by="system",
        mailbox_id=mailbox_id,
        reason=reason,
        log_entry_fn=log_entry_fn
    )


__all__ = [
    "log_password_operation",
    "log_auth_failure",
]
