import yaml
import os

config_path = "config/notifications.yaml"

print("=" * 70)
print("🔍 DIAGNÓSTICO DE CONFIGURACIÓN")
print("=" * 70)

if not os.path.exists(config_path):
    print(f"❌ Archivo no encontrado: {config_path}")
    exit(1)

print(f"\n📄 Leyendo: {config_path}\n")

try:
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print("📝 Contenido del archivo:")
    print("-" * 70)
    print(content)
    print("-" * 70)

    # Parsear YAML
    config = yaml.safe_load(content)

    if not config:
        print("\n❌ ERROR: El archivo YAML está vacío o mal formado")
        exit(1)

    # Verificar estructura
    telegram = config.get('telegram', {})

    if not telegram:
        print("\n❌ ERROR: No se encontró la sección 'telegram:'")
        exit(1)

    bot_token = telegram.get('bot_token', '')
    chat_id = telegram.get('chat_id', '')
    approval_ids = telegram.get('approval_chat_ids', [])

    print(f"\n🔑 bot_token: '{bot_token}'")
    print(f"📏 Longitud: {len(bot_token)} caracteres")
    print(f"👤 chat_id: '{chat_id}'")
    print(f"👥 approval_chat_ids: {approval_ids}")

    if not bot_token:
        print("\n❌ ERROR CRÍTICO: bot_token está VACÍO")
        print("\n💡 SOLUCIÓN:")
        print("   1. Abre config/notifications.yaml")
        print("   2. Asegúrate de que la línea bot_token tenga tu token entre comillas:")
        print('      bot_token: "8884679745:AAGZVyGTHIw1AtamZIhpphaTdxYQayCqQs0"')
        print("   3. Verifica que la indentación sea correcta (2 espacios)")
        exit(1)

    # Probar conexión
    print("\n🌐 Probando conexión con Telegram...")
    import requests

    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                bot_info = result['result']
                print(f"✅ Conexión exitosa con @{bot_info.get('username')}")
            else:
                print(f"❌ Error de Telegram: {result.get('description')}")
        else:
            print(f"❌ Error HTTP: {response.status_code}")
    except Exception as e:
        print(f"❌ Error de red: {e}")

    print("\n" + "=" * 70)
    print("✅ DIAGNÓSTICO COMPLETADO")
    print("=" * 70)

except yaml.YAMLError as e:
    print(f"\n❌ ERROR DE SINTAXIS YAML: {e}")
    print("\n💡 El archivo tiene errores de formato. Revisa:")
    print("   - Indentación (usa espacios, no tabs)")
    print("   - Comillas en strings con caracteres especiales (como el token)")
    print("   - Dos puntos (:) al final de las claves")
except Exception as e:
    print(f"\n❌ ERROR INESPERADO: {e}")
    import traceback

    traceback.print_exc()