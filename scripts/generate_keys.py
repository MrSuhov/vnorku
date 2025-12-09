#!/usr/bin/env python3
"""
Утилита для генерации ключей безопасности для Korzinka
"""

import secrets
import string
from cryptography.fernet import Fernet


def generate_secret_key(length: int = 50) -> str:
    """Генерация secret key для JWT и общей безопасности"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_encryption_key() -> str:
    """Генерация ключа для симметричного шифрования"""
    return Fernet.generate_key().decode()


def main():
    print("🔐 Генерация ключей безопасности для Korzinka\n")
    
    secret_key = generate_secret_key()
    encryption_key = generate_encryption_key()
    
    print("Добавьте следующие строки в ваш .env файл:\n")
    print(f"SECRET_KEY={secret_key}")
    print(f"ENCRYPTION_KEY={encryption_key}")
    print()
    print("⚠️  Важно: сохраните эти ключи в безопасном месте!")
    print("   При потере ключей все зашифрованные данные станут недоступны.")


if __name__ == "__main__":
    main()
