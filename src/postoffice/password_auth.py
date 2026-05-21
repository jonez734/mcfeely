# password_auth.py
# Authentication with fallback from per-member to shared mailbox passwords
# Handles logging of authentication failures

from typing import Optional, Any
from bbsengine6 import database
from bbsengine6.io import echo
from . import password_crypto, member_password, shared_mailbox_password


def validate_password(password_type: str, password: str) -> bool:
    """Validate password (extensible for future strength validation).
    
    Args:
        password_type: 'inbound' or 'outbound'.
        password: Plaintext password to validate.
    
    Returns:
        True if valid, False otherwise.
        
    Note:
        Currently just checks that password exists. Can be extended
        to check password strength, length, complexity, etc.
    """
    if not password or not isinstance(password, str):
        return False
    if password_type not in ("inbound", "outbound"):
        return False
    return len(password) > 0


def get_auth_password(args: Any, mailbox_id: Optional[int], member_moniker: str,
                     password_type: str, requester_moniker: str,
                     log_entry_fn: Optional[Any] = None) -> Optional[str]:
    """Get password for authentication, with fallback logic.
    
    For shared mailboxes (mailbox_id set):
        1. Try per-member password in member_mailbox_password
        2. Fall back to shared mailbox default in mailbox_password
        3. Log failure if both missing
    
    For personal accounts (mailbox_id None):
        1. Get password from engine.__member
        2. Log failure if missing
    
    Args:
        args: bbsengine6 args object with database connection.
        mailbox_id: Mailbox ID (None for personal account).
        member_moniker: Member's moniker.
        password_type: 'inbound' or 'outbound'.
        requester_moniker: Who is requesting (for permission check).
        log_entry_fn: Optional logging function (bbsengine6.logentry).
    
    Returns:
        Decrypted plaintext password, or None if not found.
    """
    if password_type not in ("inbound", "outbound"):
        msg = f"Invalid password_type: {password_type}"
        echo(msg, level="error")
        return None
    
    # Personal account password
    if mailbox_id is None:
        password = member_password.get_personal_password(
            args, member_moniker, password_type, requester_moniker
        )
        if not password:
            msg = f"Auth failed: no {password_type} password for {member_moniker}"
            echo(msg, level="error")
            if log_entry_fn:
                log_entry_fn(msg)
            return None
        return password
    
    # Shared mailbox: try per-member password first
    password = shared_mailbox_password.get_shared_mailbox_password(
        args, mailbox_id, member_moniker, password_type, requester_moniker
    )
    if password:
        return password
    
    # Fall back to shared mailbox default password
    password = _get_shared_mailbox_default_password(
        args, mailbox_id, password_type
    )
    if password:
        return password
    
    # Log failure with both member and mailbox info
    msg = f"Auth failed: no {password_type} password for {member_moniker} on mailbox {mailbox_id}"
    echo(msg, level="error")
    if log_entry_fn:
        log_entry_fn(msg)
    return None


def _get_shared_mailbox_default_password(args: Any, mailbox_id: int,
                                        password_type: str) -> Optional[str]:
    """Get default password for a shared mailbox.
    
    Args:
        args: bbsengine6 args object with database connection.
        mailbox_id: Mailbox ID.
        password_type: 'inbound' or 'outbound'.
    
    Returns:
        Decrypted plaintext password, or None if not found.
    """
    # Password type column in mailbox_password table
    kind_value = f"inbound outbound"  # Both inbound and outbound stored with this kind
    
    sql = """
        SELECT password FROM postoffice.mailbox_password
        WHERE address = (SELECT address FROM postoffice.mailbox WHERE id = %s)
        AND kind = %s
    """
    dat = (mailbox_id, kind_value)
    
    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dat)
                if cur.rowcount == 0:
                    return None
                row = cur.fetchone()
                encrypted = row["password"]
                if not encrypted:
                    return None
                
                # mailbox_password stores crypt() hashes, not AES-256-GCM
                # Return as-is since it's for backwards compatibility
                # Note: This is the old format; new per-member passwords use AES-256-GCM
                return encrypted
    except Exception as e:
        echo(f"password_auth._get_shared_mailbox_default_password: error: {e}",
             level="error")
        return None


__all__ = [
    "validate_password",
    "get_auth_password",
]
