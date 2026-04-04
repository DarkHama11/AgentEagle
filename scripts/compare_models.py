# scripts/compare_models.py
"""Comparar rendimiento de diferentes modelos en AgentEagle++."""
import asyncio
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.model_wrapper import ModelWrapper
from src.agents.seguridad_agent import SeguridadAgent
from src.agents.oficina_agent import OficinaAgent

TEST_PROMPTS = [
    ("seguridad", "hola", "Saludo básico"),
    ("seguridad", "¿Qué es CVE?", "Explicación técnica"),
    ("seguridad", "¿Cómo proteger mi cuenta AWS?", "Consejos prácticos"),
    ("oficina", "hola", "Saludo Office"),
    ("oficina", "¿Cómo sumar en Excel?", "Fórmula Excel"),
]


async def test_model(model_key: str, model_config: dict):
    """Probar un modelo específico con las preguntas de prueba."""
    print(f"\n🧪 Probando modelo: {model_config['ollama_model']} (key: {model_key})")
    print("-" * 60)

    results = []

    try:
        model = ModelWrapper(model_key=model_key).load()
        agents = {
            "seguridad": SeguridadAgent(model_key=model_key).set_model(model),
            "oficina": OficinaAgent(model_key=model_key).set_model(model),
        }

        for agent_name, prompt, description in TEST_PROMPTS:
            if agent_name not in agents:
                continue

            agent = agents[agent_name]
            start = time.time()

            try:
                response_data = await agent.process(prompt)
                elapsed = time.time() - start
                response = response_data.get("response", "")

                passed = bool(response and len(response.strip()) > 20 and response_data.get("success"))

                results.append({
                    "prompt": prompt,
                    "description": description,
                    "passed": passed,
                    "time": round(elapsed, 2),
                    "length": len(response.strip()) if response else 0,
                    "success": response_data.get("success", False),
                    "preview": response[:100] + "..." if response and len(response) > 100 else response
                })

                status = "✅" if passed else "❌"
                print(f"{status} [{description}] {elapsed:.1f}s | {len(response.strip()) if response else 0} chars")
                if not passed and response:
                    print(f"   📝 '{response[:150]}'")

            except Exception as e:
                print(f"❌ [{description}] Error: {e}")
                results.append({"prompt": prompt, "description": description, "passed": False, "error": str(e)})

        passed_count = sum(1 for r in results if r.get("passed", False))
        total_count = len(results)
        avg_time = sum(r.get("time", 0) for r in results if "time" in r) / max(1,
                                                                               len([r for r in results if "time" in r]))

        print(f"\n📊 Resumen {model_config['ollama_model']}:")
        print(f"   ✅ {passed_count}/{total_count} pruebas pasaron")
        print(f"   ⏱️ Tiempo promedio: {avg_time:.1f}s")

        return {"model": model_config["ollama_model"],
                "pass_rate": passed_count / total_count * 100 if total_count > 0 else 0, "avg_time": avg_time,
                "results": results}

    except Exception as e:
        print(f"❌ Error cargando modelo {model_key}: {e}")
        return {"model": model_config["ollama_model"], "error": str(e), "pass_rate": 0}


async def main():
    """Ejecutar comparación de modelos."""
    from src.core.config import Config

    print("🔄 Comparación de Modelos - AgentEagle++")
    print(f"💻 Hardware: RTX 3050 (4GB VRAM) - Optimizado")
    print("=" * 70)

    # Modelos a probar (comenta los que no descargaste)
    models_to_test = [
        ("3b", Config.MODELS.get("3b", {})),  # ✅ Recomendado
        ("7b", Config.MODELS.get("7b", {})),  # Actual
        # ("phi", Config.MODELS.get("phi", {})),    # Ligero
        # ("mistral", Config.MODELS.get("mistral", {})),  # Experimental
    ]

    all_results = []

    for model_key, model_config in models_to_test:
        if not model_config:
            print(f"⚠️ Configuración no encontrada para '{model_key}', saltando")
            continue

        result = await test_model(model_key, model_config)
        all_results.append(result)
        await asyncio.sleep(2)

    # Tabla comparativa final
    print("\n" + "=" * 70)
    print("📈 TABLA COMPARATIVA FINAL")
    print("=" * 70)
    print(f"{'Modelo':<25} {'Pass Rate':<12} {'Tiempo Prom':<12} {'Veredicto'}")
    print("-" * 70)

    for r in all_results:
        if "error" in r:
            print(f"{r['model']:<25} {'ERROR':<12} {'-':<12} ❌ No cargó")
        else:
            verdict = "🎯 RECOMENDADO" if r["pass_rate"] >= 70 else "⚠️ Regular" if r["pass_rate"] >= 40 else "❌ Evitar"
            print(f"{r['model']:<25} {r['pass_rate']:.1f}%{'':<7} {r['avg_time']:.1f}s{'':<7} {verdict}")

    print("=" * 70)

    best = max([r for r in all_results if "error" not in r], key=lambda x: x["pass_rate"], default=None)
    if best and best["pass_rate"] >= 70:
        print(f"\n🎉 RECOMENDACIÓN: Usa '{best['model']}' (pass rate: {best['pass_rate']:.1f}%)")
        print(f"   Para activarlo: cambia DEFAULT_MODEL_KEY en config.py")
    elif best:
        print(f"\n⚠️ Ningún modelo alcanzó 70%. Considera QLoRA fine-tuning.")


if __name__ == "__main__":
    asyncio.run(main())