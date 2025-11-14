"""Tests for encryption utilities."""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.encryption import decrypt_data, encrypt_data


@pytest.fixture
def valid_encryption_key():
    """Generate a valid encryption key for testing."""
    return Fernet.generate_key().decode()


def test_encrypt_data_success(valid_encryption_key):
    """Test successful data encryption."""
    plaintext = "my-secret-api-key"

    encrypted = encrypt_data(plaintext, valid_encryption_key)

    assert encrypted != plaintext
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0


def test_decrypt_data_success(valid_encryption_key):
    """Test successful data decryption."""
    plaintext = "my-secret-api-key"

    encrypted = encrypt_data(plaintext, valid_encryption_key)
    decrypted = decrypt_data(encrypted, valid_encryption_key)

    assert decrypted == plaintext


def test_encrypt_decrypt_roundtrip(valid_encryption_key):
    """Test that encryption and decryption are reversible."""
    original_data = "sensitive-information-12345"

    encrypted = encrypt_data(original_data, valid_encryption_key)
    decrypted = decrypt_data(encrypted, valid_encryption_key)

    assert decrypted == original_data
    assert encrypted != original_data


def test_encrypt_data_empty_key():
    """Test encryption with empty key raises ValueError."""
    with pytest.raises(ValueError, match="Encryption key is required"):
        encrypt_data("some data", "")


def test_decrypt_data_empty_key():
    """Test decryption with empty key raises ValueError."""
    with pytest.raises(ValueError, match="Encryption key is required"):
        decrypt_data("some encrypted data", "")


def test_encrypt_data_invalid_key():
    """Test encryption with invalid key raises exception."""
    invalid_key = "not-a-valid-fernet-key"

    with pytest.raises(Exception):  # Fernet raises ValueError for invalid key format
        encrypt_data("some data", invalid_key)


def test_decrypt_data_invalid_key():
    """Test decryption with invalid key raises exception."""
    invalid_key = "not-a-valid-fernet-key"

    with pytest.raises(Exception):  # Fernet raises ValueError for invalid key format
        decrypt_data("some encrypted data", invalid_key)


def test_decrypt_data_wrong_key(valid_encryption_key):
    """Test decryption with wrong key raises InvalidToken."""
    plaintext = "my-secret-data"
    encrypted = encrypt_data(plaintext, valid_encryption_key)

    # Generate a different key
    wrong_key = Fernet.generate_key().decode()

    with pytest.raises(InvalidToken):
        decrypt_data(encrypted, wrong_key)


def test_decrypt_data_corrupted_data(valid_encryption_key):
    """Test decryption of corrupted data raises InvalidToken."""
    corrupted_data = "this-is-not-encrypted-data"

    with pytest.raises(InvalidToken):
        decrypt_data(corrupted_data, valid_encryption_key)


def test_encrypt_data_special_characters(valid_encryption_key):
    """Test encryption of data with special characters."""
    plaintext = "key-with-special!@#$%^&*()_+-={}[]|:;<>?,./~`"

    encrypted = encrypt_data(plaintext, valid_encryption_key)
    decrypted = decrypt_data(encrypted, valid_encryption_key)

    assert decrypted == plaintext


def test_encrypt_data_unicode(valid_encryption_key):
    """Test encryption of unicode data."""
    plaintext = "unicode-data-日本語-emojis-🔐🔑"

    encrypted = encrypt_data(plaintext, valid_encryption_key)
    decrypted = decrypt_data(encrypted, valid_encryption_key)

    assert decrypted == plaintext


def test_encrypt_data_json_string(valid_encryption_key):
    """Test encryption of JSON string data."""
    import json

    json_data = json.dumps({"api_key": "secret123", "github_token": "ghp_token456"})

    encrypted = encrypt_data(json_data, valid_encryption_key)
    decrypted = decrypt_data(encrypted, valid_encryption_key)

    assert decrypted == json_data
    # Verify it's valid JSON
    parsed = json.loads(decrypted)
    assert parsed["api_key"] == "secret123"
    assert parsed["github_token"] == "ghp_token456"


def test_encrypt_data_empty_string(valid_encryption_key):
    """Test encryption of empty string."""
    plaintext = ""

    encrypted = encrypt_data(plaintext, valid_encryption_key)
    decrypted = decrypt_data(encrypted, valid_encryption_key)

    assert decrypted == plaintext


def test_encrypt_data_long_string(valid_encryption_key):
    """Test encryption of very long string."""
    plaintext = "a" * 10000  # 10KB of data

    encrypted = encrypt_data(plaintext, valid_encryption_key)
    decrypted = decrypt_data(encrypted, valid_encryption_key)

    assert decrypted == plaintext
    assert len(encrypted) > len(plaintext)  # Encrypted data is larger
