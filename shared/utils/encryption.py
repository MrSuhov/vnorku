from cryptography.fernet import Fernet
from config.settings import settings
import json
from typing import Dict, Any


class EncryptionUtils:
    def __init__(self):
        self._fernet = Fernet(settings.encryption_key.encode())
    
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Шифрование словаря в строку"""
        json_str = json.dumps(data)
        encrypted = self._fernet.encrypt(json_str.encode())
        return encrypted.decode()
    
    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """Расшифровка строки в словарь"""
        decrypted = self._fernet.decrypt(encrypted_data.encode())
        return json.loads(decrypted.decode())
    
    def encrypt_string(self, data: str) -> str:
        """Шифрование строки"""
        encrypted = self._fernet.encrypt(data.encode())
        return encrypted.decode()
    
    def decrypt_string(self, encrypted_data: str) -> str:
        """Расшифровка строки"""
        decrypted = self._fernet.decrypt(encrypted_data.encode())
        return decrypted.decode()


# Глобальный экземпляр
encryption = EncryptionUtils()
