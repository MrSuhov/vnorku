#!/usr/bin/env python3
"""
Скрипт для обновления Google OAuth токена.
Откроет браузер для авторизации.
"""
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CREDENTIALS_FILE = os.path.join(PROJECT_DIR, 'client_secret_278340352558-ri058tcs20709pd7fvfi88nsotrekr15.apps.googleusercontent.com.json')
TOKEN_FILE = os.path.join(PROJECT_DIR, 'token.json')

# Нужные scopes для перевода через Sheets
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def main():
    print("=" * 50)
    print("Обновление Google OAuth токена")
    print("=" * 50)

    if not os.path.exists(CREDENTIALS_FILE):
        print(f"\n❌ Файл credentials.json не найден: {CREDENTIALS_FILE}")
        return

    print(f"\n📄 Credentials: {CREDENTIALS_FILE}")
    print(f"📄 Token будет сохранён в: {TOKEN_FILE}")
    print("\n🔐 Открываю браузер для авторизации...")
    print("   Разрешите доступ к Google Sheets и Drive\n")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    # Сохраняем токен
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': list(creds.scopes),
        'expiry': creds.expiry.isoformat() if creds.expiry else None
    }

    with open(TOKEN_FILE, 'w') as f:
        json.dump(token_data, f, indent=2)

    print(f"\n✅ Токен успешно обновлён!")
    print(f"   Сохранён в: {TOKEN_FILE}")
    print(f"   Scopes: {', '.join(creds.scopes)}")
    print("\nТеперь можно запустить перевод:")
    print("   python scripts/translate_via_sheets.py")


if __name__ == "__main__":
    main()
