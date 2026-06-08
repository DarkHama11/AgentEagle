import requests
import json

BASE = "http://localhost:8000"

print("🦅 AgentEagle API - Validación Completa\n")

# 1. Health Check
print("1️⃣ Health Check:")
h = requests.get(f"{BASE}/health").json()
print(f"   Status: {h['status']} ✅")
print(f"   Version: {h['version']}")
for name, info in h['agents'].items():
    status = "✅" if info.get('ready') else "❌"
    print(f"   ├─ {name}: {status}")

# 2. Chat Tests
print("\n2️⃣ Chat Tests:")
tests = [
    ("hola", "general", "greeting"),
    ("cve aws", "seguridad", "cve"),
    ("excel vlookup", "oficina", "excel"),
]

for query, expected_agent, expected_intent in tests:
    r = requests.post(f"{BASE}/chat", json={"user_input": query})
    if r.ok:
        d = r.json()
        agent_ok = "✅" if d['agent'] == expected_agent else "⚠️"
        print(f"   {agent_ok} '{query}' → {d['agent']} (intent: {d['intent']})")
        if d.get('response'):
            print(f"      └─ {d['response'][:80]}...")
    else:
        print(f"   ❌ '{query}' → Error {r.status_code}")

print("\n✅ Validación completa")
