# tests/test_password_crypto.py
# Unit tests for password encryption/decryption

import os
import pytest
from postoffice import password_crypto


class TestPasswordCrypto:
    """Test AES-256-GCM encryption/decryption."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test encryption key."""
        import base64
        key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = key
    
    def test_get_encryption_key_success(self):
        """Test getting encryption key from environment."""
        key = password_crypto.get_encryption_key()
        assert isinstance(key, bytes)
        assert len(key) == 32
    
    def test_get_encryption_key_missing(self):
        """Test error when key not set."""
        del os.environ["POSTOFFICE_PASSWORD_KEY"]
        with pytest.raises(ValueError, match="not set"):
            password_crypto.get_encryption_key()
    
    def test_get_encryption_key_invalid_base64(self):
        """Test error for invalid base64."""
        os.environ["POSTOFFICE_PASSWORD_KEY"] = "not-valid-base64!!!"
        with pytest.raises(ValueError, match="not valid base64"):
            password_crypto.get_encryption_key()
    
    def test_get_encryption_key_wrong_length(self):
        """Test error for wrong key length."""
        import base64
        os.environ["POSTOFFICE_PASSWORD_KEY"] = base64.b64encode(b"short").decode()
        with pytest.raises(ValueError, match="must be 32 bytes"):
            password_crypto.get_encryption_key()
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test encryption and decryption roundtrip."""
        plaintext = "mysecretpassword123"
        encrypted = password_crypto.encrypt_password(plaintext)
        decrypted = password_crypto.decrypt_password(encrypted)
        assert decrypted == plaintext
    
    def test_encrypt_produces_base64(self):
        """Test that encryption produces valid base64."""
        encrypted = password_crypto.encrypt_password("test")
        # Should be decodable as base64
        import base64
        decoded = base64.b64decode(encrypted)
        assert len(decoded) >= 28  # 12 bytes nonce + 16 bytes tag minimum
    
    def test_encrypt_unique_nonces(self):
        """Test that multiple encryptions use different nonces."""
        plaintext = "testpassword"
        encrypted1 = password_crypto.encrypt_password(plaintext)
        encrypted2 = password_crypto.encrypt_password(plaintext)
        # Different nonces should produce different ciphertexts
        assert encrypted1 != encrypted2
        # But both should decrypt to same plaintext
        assert password_crypto.decrypt_password(encrypted1) == plaintext
        assert password_crypto.decrypt_password(encrypted2) == plaintext
    
    def test_decrypt_invalid_base64(self):
        """Test error for invalid base64 input."""
        with pytest.raises(ValueError, match="Failed to decode"):
            password_crypto.decrypt_password("not-valid-base64!!!")
    
    def test_decrypt_too_short(self):
        """Test error for ciphertext too short."""
        import base64
        too_short = base64.b64encode(b"short").decode()
        with pytest.raises(ValueError, match="too short"):
            password_crypto.decrypt_password(too_short)
    
    def test_decrypt_tampered_ciphertext(self):
        """Test error for tampered ciphertext."""
        plaintext = "testpassword"
        encrypted = password_crypto.encrypt_password(plaintext)
        
        # Tamper with ciphertext
        import base64
        decoded = base64.b64decode(encrypted)
        tampered = decoded[:16] + b'X' * (len(decoded) - 16)
        tampered_b64 = base64.b64encode(tampered).decode()
        
        with pytest.raises(ValueError, match="authentication tag"):
            password_crypto.decrypt_password(tampered_b64)
    
    def test_encrypt_special_characters(self):
        """Test encryption of passwords with special characters."""
        plaintext = "p@ssw0rd!#$%^&*()"
        encrypted = password_crypto.encrypt_password(plaintext)
        decrypted = password_crypto.decrypt_password(encrypted)
        assert decrypted == plaintext
    
    def test_encrypt_unicode(self):
        """Test encryption of unicode passwords."""
        plaintext = "пароль密码🔐"
        encrypted = password_crypto.encrypt_password(plaintext)
        decrypted = password_crypto.decrypt_password(encrypted)
        assert decrypted == plaintext
    
    def test_encrypt_empty_string(self):
        """Test encryption of empty string."""
        plaintext = ""
        encrypted = password_crypto.encrypt_password(plaintext)
        decrypted = password_crypto.decrypt_password(encrypted)
        assert decrypted == plaintext
    
    def test_encrypt_long_password(self):
        """Test encryption of very long password."""
        plaintext = "a" * 10000
        encrypted = password_crypto.encrypt_password(plaintext)
        decrypted = password_crypto.decrypt_password(encrypted)
        assert decrypted == plaintext


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
