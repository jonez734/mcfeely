# password/storage.py
# Abstract storage interface for password persistence
# Supports pluggable implementations: PostgreSQL, filesystem, MongoDB, etc.

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class PasswordStorage(ABC):
    """Abstract interface for password storage and retrieval.
    
    Implementations handle:
    - Personal account password storage (in any backend)
    - Shared mailbox per-member password storage
    - Metadata tracking (who set, when)
    
    Examples:
        - PostgreSQLStorage - Stores in PostgreSQL tables
        - FileSystemStorage - Stores in encrypted files (testing)
        - MongoDBStorage - Stores in MongoDB collections
        - VaultStorage - Stores in HashiCorp Vault
    """

    @abstractmethod
    def get_personal_password(
        self, member_moniker: str, password_type: str
    ) -> Optional[str]:
        """Get encrypted personal account password.
        
        Args:
            member_moniker: Member's moniker.
            password_type: 'inbound' or 'outbound'.
        
        Returns:
            Encrypted password (in cipher format), or None if not found.
        """
        pass

    @abstractmethod
    def set_personal_password(
        self, member_moniker: str, password_type: str, encrypted_password: str,
        set_by_moniker: str
    ) -> bool:
        """Store encrypted personal account password.
        
        Args:
            member_moniker: Member's moniker.
            password_type: 'inbound' or 'outbound'.
            encrypted_password: Already-encrypted password from cipher.
            set_by_moniker: Who set this password (for audit).
        
        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def list_personal_passwords(
        self, member_moniker: str
    ) -> Dict[str, Dict[str, Any]]:
        """List personal password metadata (not encrypted).
        
        Args:
            member_moniker: Member's moniker.
        
        Returns:
            Dictionary with password metadata:
            {
                'inbound': {'exists': True, 'encrypted_len': 123, 'set_by': 'jam', 'updated_at': '...'},
                'outbound': {'exists': False}
            }
        """
        pass

    @abstractmethod
    def get_shared_mailbox_password(
        self, mailbox_id: int, member_moniker: str, password_type: str
    ) -> Optional[str]:
        """Get encrypted password for member on shared mailbox.
        
        Args:
            mailbox_id: Shared mailbox ID.
            member_moniker: Member's moniker.
            password_type: 'inbound' or 'outbound'.
        
        Returns:
            Encrypted password (in cipher format), or None if not found.
        """
        pass

    @abstractmethod
    def set_shared_mailbox_password(
        self, mailbox_id: int, member_moniker: str, password_type: str,
        encrypted_password: str, set_by_moniker: str
    ) -> bool:
        """Store encrypted password for member on shared mailbox.
        
        Args:
            mailbox_id: Shared mailbox ID.
            member_moniker: Member's moniker.
            password_type: 'inbound' or 'outbound'.
            encrypted_password: Already-encrypted password from cipher.
            set_by_moniker: Who set this password (for audit).
        
        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def list_shared_mailbox_passwords(
        self, mailbox_id: int, member_moniker: str
    ) -> Dict[str, Dict[str, Any]]:
        """List passwords for member on shared mailbox.
        
        Args:
            mailbox_id: Shared mailbox ID.
            member_moniker: Member's moniker.
        
        Returns:
            Dictionary with password metadata:
            {
                'inbound': {'exists': True, 'encrypted_len': 123, 'set_by': 'jam'},
                'outbound': {'exists': False}
            }
        """
        pass

    @abstractmethod
    def get_member_mailboxes(self, member_moniker: str) -> List[Dict[str, Any]]:
        """Get list of mailboxes member has passwords for.
        
        Args:
            member_moniker: Member's moniker.
        
        Returns:
            List of mailbox info dictionaries.
        """
        pass


__all__ = ["PasswordStorage"]
