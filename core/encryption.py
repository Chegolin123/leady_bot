import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.config import settings


class TokenEncryption:
    """AES-256-GCM шифрование/дешифрование токенов ботов."""

    def __init__(self):
        self._key: bytes | None = None

    @property
    def key(self) -> bytes:
        if self._key is None:
            self._key = settings.load_aes_key()
        return self._key

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return (nonce + ciphertext).hex()

    def decrypt(self, encrypted_hex: str) -> str:
        raw = bytes.fromhex(encrypted_hex)
        nonce = raw[:12]
        ciphertext = raw[12:]
        aesgcm = AESGCM(self.key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")


encryption = TokenEncryption()
