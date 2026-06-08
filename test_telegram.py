import requests

# Tus credenciales
BOT_TOKEN = "8884679745:AAGZVyGTHIw1AtamZIhpphaTdxYQayCqQs0"
CHAT_ID = "1193717225"


def test_telegram():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": "🦅 <b>¡Prueba de AgentEagle 2.0 exitosa!</b>\n\nEl sistema de notificaciones está funcionando correctamente.\n\n🆔 Chat ID: <code>{}</code>\n🕐 {}".format(
            CHAT_ID, __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        "parse_mode": "HTML"
    }

    print("📤 Enviando mensaje de prueba a Telegram...")
    response = requests.post(url, json=payload)

    if response.status_code == 200 and response.json().get("ok"):
        print("✅ ¡Éxito! Revisa tu Telegram. Deberías tener un mensaje nuevo.")
        return True
    else:
        print(f"❌ Error: {response.json()}")
        return False


if __name__ == "__main__":
    test_telegram()