# password/manager.py
# Password manager combining cipher and storage strategies

from typing import Optional, Dict, Any, List

from bbsengine6.io import echo

from .cipher import PasswordCipher
from .storage import PasswordStorage


class PasswordManager:
    """Unified password manager with pluggable cipher and storage.
    
    Combines:
    - Cipher: Handles encryption/decryption (AES-256-GCM, etc.)
    - Storage: Handles persistence (PostgreSQL, filesystem, etc.)
    
    Provides high-level interface for password operations without
    needing to worry about encryption or storage details.
    """

    def __init__(self, cipher: PasswordCipher, storage: PasswordStorage):
        """Initialize password manager.
        
        Args:
            cipher: PasswordCipher implementation (e.g., AES256GCMCipher)
            storage: PasswordStorage implementation (e.g., PostgreSQLStorage)
        """
        self.cipher = cipher
        self.storage = storage

    # Personal password operations

    def set_personal_password(
        self,
        member_moniker: str,
        password_type: str,
        plaintext_password: str,
        set_by_moniker: str,
    ) -> bool:
        """Set and encrypt personal account password.
        
        Args:
            member_moniker: Member's moniker.
            password_type: 'inbound' or 'outbound'.
            plaintext_password: Plaintext password to encrypt and store.
            set_by_moniker: Who is setting this password (for audit).
        
        Returns:
            True if successful, False otherwise.
        """
        if password_type not in ("inbound", "outbound"):
            echo("Invalid password_type", level="error")
            return False

        try:
            encrypted = self.cipher.encrypt(plaintext_password)
            return self.storage.set_personal_password(
                member_moniker, password_type, encrypted, set_by_moniker
            )
        except Exception as e:
            echo(f"Failed to set personal password: {e}", level="error")
            return False

    def get_personal_password(
        self, member_moniker: str, password_type: str
    ) -> Optional[str]:
        """Get and decrypt personal account password.
        
        Args:
            member_moniker: Member's moniker.
            password_type: 'inbound' or 'outbound'.
        
        Returns:
            Plaintext password, or None if not found/error.
        """
        if password_type not in ("inbound", "outbound"):
            return None

        try:
            encrypted = self.storage.get_personal_password(
                member_moniker, password_type
            )
            if not encrypted:
                return None
            return self.cipher.decrypt(encrypted)
        except Exception as e:
            echo(f"Failed to get personal password: {e}", level="error")
            return None

    def delete_personal_password(
        self, member_moniker: str, password_type: str
    ) -> bool:
        """Delete personal account password.
        
        Args:
            member_moniker: Member's moniker.
            password_type: 'inbound' or 'outbound'.
        
        Returns:
            True if successful, False otherwise.
        """
        if password_type not in ("inbound", "outbound"):
            return False

        return self.storage.delete_personal_password(
            member_moniker, password_type
        )

    def list_personal_passwords(
        self, member_moniker: str
    ) -> Dict[str, Dict[str, Any]]:
        """List personal password metadata (not decrypted).
        
        Args:
            member_moniker: Member's moniker.
        
        Returns:
            Dictionary with password metadata.
        """
        return self.storage.list_personal_passwords(member_moniker)

    # Shared mailbox password operations

    def set_shared_mailbox_password(
        self,
        mailbox_id: int,
        member_moniker: str,
        password_type: str,
        plaintext_password: str,
        set_by_moniker: str,
    ) -> bool:
        """Set and encrypt password for member on shared mailbox.
        
        Args:
            mailbox_id: Shared mailbox ID.
            member_moniker: Member's moniker.
            password_type: 'inbound' or 'outbound'.
            plaintext_password: Plaintext password to encrypt and store.
            set_by_moniker: Who is setting this password (for audit).
        
        Returns:
            True if successful, False otherwise.
        """
        if password_type not in ("inbound", "outbound"):
            echo("Invalid password_type", level="error")
            return False

        try:
            encrypted = self.cipher.encrypt(plaintext_password)
            return self.storage.set_shared_mailbox_password(
                mailbox_id,
                member_moniker,
                password_type,
                encrypted,
                set_by_moniker,
            )
        except Exception as e:
            echo(f"Failed to set shared mailbox password: {e}", level="error")
            return False

    def get_shared_mailbox_password(
        self, mailbox_id: int, member_moniker: str, password_type: str
    ) -> Optional[str]:
        """Get and decrypt password for member on shared mailbox.
        
        Args:
            mailbox_id: Shared mailbox ID.
            member_moniker: Member's moniker.
            password_type: 'inbound' or 'outbound'.
        
        Returns:
            Plaintext password, or None if not found/error.
        """
        if password_type not in ("inbound", "outbound"):
            return None

        try:
            encrypted = self.storage.get_shared_mailbox_password(
                mailbox_id, member_moniker, password_type
            )
            if not encrypted:
                return None
            return self.cipher.decrypt(encrypted)
        except Exception as e:
            echo(f"Failed to get shared mailbox password: {e}", level="error")
            return None

    def delete_shared_mailbox_password(
        self, mailbox_id: int, member_moniker: str, password_type: str
    ) -> bool:
        """Delete password for member on shared mailbox.
        
        Args:
            mailbox_id: Shared mailbox ID.
            member_moniker: Member's moniker.
            password_type: 'inbound' or 'outbound'.
        
        Returns:
            True if successful, False otherwise.
        """
        if password_type not in ("inbound", "outbound"):
            return False

        return self.storage.delete_shared_mailbox_password(
            mailbox_id, member_moniker, password_type
        )

    def list_shared_mailbox_passwords(
        self, mailbox_id: int, member_moniker: str
    ) -> Dict[str, Dict[str, Any]]:
        """List passwords for member on shared mailbox.
        
        Args:
            mailbox_id: Shared mailbox ID.
            member_moniker: Member's moniker.
        
        Returns:
            Dictionary with password metadata.
        """
        return self.storage.list_shared_mailbox_passwords(
            mailbox_id, member_moniker
        )

    def get_member_mailboxes(self, member_moniker: str) -> List[Dict[str, Any]]:
        """Get list of mailboxes member has passwords for.
        
        Args:
            member_moniker: Member's moniker.
        
        Returns:
            List of mailbox info.
        """
        return self.storage.get_member_mailboxes(member_moniker)


__all__ = ["PasswordManager"]
