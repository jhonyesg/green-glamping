# Proposal: Canales plug-and-play

## Why

La sección de Canales guarda credenciales pero no garantiza que el
canal funcione. La experiencia real del primer tenant lo demostró:

1. Se guardó el **@nombre del bot en lugar del token** y nada lo
   detectó — Telegram devolvía 404 en silencio.
2. Aunque el token fuera correcto, el bot **no respondía**: Telegram
   exige un webhook con URL pública HTTPS, imposible en localhost, y
   nadie lo configura automáticamente.
3. El bot estaba **secuestrado por un webhook ajeno** (un workflow
   muerto de n8n devolviendo 404) y no había forma de verlo desde el
   panel.
4. El dueño del negocio no tiene cómo decidir entre WhatsApp oficial,
   Evolution, Baileys o WAHA: la información es técnica y está
   dispersa.
5. En WhatsApp no oficial, responder en 80ms con bloques largos de
   texto es el patrón que los sistemas anti-bot detectan: falta
   **humanización** del envío (es mitigación de riesgo de bloqueo,
   no estética).

**Objetivo**: que configurar un canal sea "lo agrego y queda
habilitado" — validado, probado y funcionando al instante, con
información clara para elegir la herramienta correcta.

## What Changes

- **Validación al guardar + botón Probar (nivel 1)**: cada canal
  valida sus credenciales contra la API real (Telegram `getMe`,
  Evolution `connectionState`, Baileys `/status`, Meta phone check)
  con mensajes de error en lenguaje claro (ej. "eso parece el
  @nombre del bot, no el token").
- **Diagnóstico de webhook**: para Telegram se consulta
  `getWebhookInfo`; si otro sistema posee el webhook se muestra la
  URL, su último error, y se ofrece tomar el control
  (`deleteWebhook` conservando mensajes pendientes).
- **Prueba end-to-end (nivel 2)**: con un destino de prueba por
  tenant (chat_id / número), un botón envía un mensaje simulado por
  el pipeline completo y la respuesta real llega al
  Telegram/WhatsApp del operador.
- **Modo polling de Telegram**: poller en segundo plano gestionado
  por la app (arranca al guardar el canal, sobrevive reinicios,
  offset persistente). Sin URL pública ni webhook. Selección
  automática: si no hay dominio público configurado → polling.
- **Fichas informativas por opción de canal**: modal no-técnico por
  cada proveedor (qué es, cómo funciona, ventajas, desventajas,
  costo, requisitos, riesgo oficial vs no oficial).
- **Humanización del envío**: nodo 🎭 en el Flujo con configuración
  por tenant — partir respuestas en burbujas, indicador
  "escribiendo…", retardo proporcional al largo del texto con
  aleatoriedad, pausas entre burbujas. Activable por tipo de canal
  (recomendado en WhatsApp, opcional en Telegram).

## Capabilities

- `channel-testing` (nueva): validación, diagnóstico y prueba e2e
- `telegram-polling` (nueva): transporte por polling gestionado
- `channel-info-cards` (nueva): fichas informativas no técnicas
- `humanization` (nueva): envío humanizado configurable

## Impact

- `app/admin/routes/channels.py` y su template (botones, modales)
- `app/channels/telegram.py` (+ getMe/getWebhookInfo helpers)
- `app/channels/evolution.py`, `whatsapp_unofficial.py` (status ya
  existe; se expone en UI)
- Nuevo `app/channels/poller.py` (gestor de pollers por tenant)
- Nuevo `app/bot/humanizer.py` + integración en webhooks/poller al
  enviar
- `app/main.py` (lifespan: arrancar/parar pollers)
- Vista Flujo: nodo 🎭 Humanización con panel
- `bot_config` del tenant: claves de humanización y destino de
  prueba

## Out of scope (futuro change `ia-guias-y-media`)

- Enrutamiento de IA con guías por escenario (fallback → LLM con
  prompt del tenant)
- Biblioteca de medios (audios de respuesta, fotos de catálogo)
  vinculada a intents
