"""
Prueba el proveedor de IA configurado para un tenant.

Uso:
    # Prueba de chat (texto):
    uv run python -m scripts.test_llm --tenant green-glamping

    # Prueba de transcripción de audio (STT):
    uv run python -m scripts.test_llm --tenant green-glamping --audio nota_voz.ogg
"""

import argparse
import asyncio
import sys


async def main():
    parser = argparse.ArgumentParser(description="Probar el proveedor LLM de un tenant")
    parser.add_argument("--tenant", default="green-glamping")
    parser.add_argument("--audio", default="", help="Ruta a un archivo de audio para probar STT")
    parser.add_argument("--prompt", default="Responde únicamente: OK", help="Prompt de prueba")
    args = parser.parse_args()

    import sqlalchemy as sa
    from app.db.session import async_session_factory
    from app.llm.base import LLMMessage, LLMRequest, STTRequest
    from app.llm.router import route_llm, route_stt

    schema = f"tenant_{args.tenant}"

    async with async_session_factory() as session:
        tenant_row = (await session.execute(
            sa.text("SELECT id FROM public.tenants WHERE slug=:s"), {"s": args.tenant}
        )).fetchone()
        if not tenant_row:
            print(f"✗ Tenant '{args.tenant}' no existe")
            sys.exit(1)

        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))

        providers = (await session.execute(sa.text(
            "SELECT provider_name, model, base_url, capabilities, priority "
            "FROM llm_providers WHERE is_active=true ORDER BY priority DESC"
        ))).fetchall()

        if not providers:
            print("✗ No hay proveedores activos. Configúralos en /admin/llm")
            sys.exit(1)

        print(f"Proveedores activos ({len(providers)}):")
        for p in providers:
            caps = p.capabilities or {}
            tags = [k for k in ("audio_input", "vision", "tts") if caps.get(k)]
            print(f"  • {p.provider_name} / {p.model} (prioridad {p.priority}) {tags or '[solo texto]'}")
        print()

        # ── Prueba 1: chat ──
        print(f"1️⃣  Chat: enviando '{args.prompt}'...")
        try:
            resp = await route_llm(LLMRequest(
                messages=[LLMMessage(role="user", content=args.prompt)],
                tenant_id=tenant_row.id,
                max_tokens=500,  # los modelos razonadores (M3) gastan tokens en <think>
            ), session)
            print(f"   ✓ [{resp.provider}/{resp.model}] respondió en {resp.latency_ms}ms "
                  f"({resp.tokens_used} tokens):")
            print(f"   → {resp.text.strip()[:200]}")
        except Exception as e:
            print(f"   ✗ Falló: {e}")
            sys.exit(1)

        # ── Prueba 2: STT (opcional) ──
        if args.audio:
            from pathlib import Path
            audio_path = Path(args.audio)
            if not audio_path.exists():
                print(f"\n✗ No existe el archivo: {args.audio}")
                sys.exit(1)

            mime = "audio/ogg" if audio_path.suffix in (".ogg", ".oga") else \
                   "audio/mpeg" if audio_path.suffix == ".mp3" else "audio/wav"
            print(f"\n2️⃣  STT: transcribiendo {audio_path.name} ({audio_path.stat().st_size} bytes)...")
            try:
                stt = await route_stt(STTRequest(
                    audio_bytes=audio_path.read_bytes(),
                    mime_type=mime,
                    language="es",
                    tenant_id=tenant_row.id,
                ), session)
                print(f"   ✓ [{stt.provider}] transcribió en {stt.latency_ms}ms:")
                print(f"   → \"{stt.text.strip()[:300]}\"")
            except Exception as e:
                print(f"   ✗ Falló: {e}")

        print("\n✅ Prueba completa.")


if __name__ == "__main__":
    asyncio.run(main())
