"""Encryption utilities for sensitive data."""

from cryptography.fernet import Fernet


def encrypt_data(data: str, key: str) -> str:
    """Encrypt data using Fernet symmetric encryption.

    Args:
        data: The plaintext string to encrypt
        key: Base64-encoded 32-byte encryption key

    Returns:
        Base64-encoded encrypted string

    Raises:
        ValueError: If the key is invalid
    """
    if not key:
        raise ValueError("Encryption key is required")

    fernet = Fernet(key.encode())
    encrypted_bytes = fernet.encrypt(data.encode())
    return encrypted_bytes.decode()


def decrypt_data(encrypted_data: str, key: str) -> str:
    """Decrypt data using Fernet symmetric encryption.

    Args:
        encrypted_data: Base64-encoded encrypted string
        key: Base64-encoded 32-byte encryption key

    Returns:
        Decrypted plaintext string

    Raises:
        ValueError: If the key is invalid
        cryptography.fernet.InvalidToken: If decryption fails
    """
    if not key:
        raise ValueError("Encryption key is required")

    fernet = Fernet(key.encode())
    decrypted_bytes = fernet.decrypt(encrypted_data.encode())
    return decrypted_bytes.decode()
