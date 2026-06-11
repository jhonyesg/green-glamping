# Design: Canales plug-and-play

## 1. Validación y prueba (channel-testing)

### Niveles

```
Nivel 0 — al guardar (automático, sin riesgo)
  Telegram:  GET /getMe          → @usuario real o error claro
  Evolution: GET /connectionState → open / connecting / close
  Baileys:   GET /status
  Meta:      GET /{phone_number_id}

Nivel 1 — botón "Probar conexión" (mismo check, bajo demanda,
  con detalle: nombre del bot, estado de instancia, QR si falta)

Nivel 2 — botón "Prueba completa" (end-to-end)
  destino de prueba del tenant (chat_id / número)
        │
        ▼
  inyectar mensaje simulado "hola" al pipeline (mismo código
  que el webhook) → respuesta real enviada por el canal
        │
        ▼
  el operador la ve llegar a su teléfono
```

### Detección de errores en lenguaje claro

| Síntoma | Mensaje |
|---|---|
| token empieza con `@` | "Eso es el nombre del bot, no el token. El token te lo dio @BotFather y se ve como `123456:ABC...`" |
| getMe 404/401 | "Telegram no reconoce este token. Revísalo en @BotFather" |
| webhook ajeno con error | "⚠ Este bot está conectado a otra plataforma: `<url>` (último error: <msg>). ¿Tomar el control?" |
| Evolution `close` | "La instancia existe pero el número no está vinculado — escanea el QR" + botón Ver QR |
| Evolution unreachable | "No se pudo conectar a `<base_url>`. ¿Está corriendo el docker?" |

### Endpoints admin

- `POST /admin/channels/test/{type}` → JSON con resultado nivel 1
- `POST /admin/channels/test-e2e/{type}` → ejecuta nivel 2
- `POST /admin/channels/takeover/telegram` → deleteWebhook + activar
  polling
- Campo nuevo por tenant en `bot_config`: `test_destination`
  (`{"telegram_chat_id": "...", "whatsapp_number": "..."}`)

## 2. Polling de Telegram (telegram-polling)

### PollerManager

```
app/channels/poller.py
┌──────────────────────────────────────────────┐
│ PollerManager (singleton en app.state)       │
│  start(tenant_slug, token)                   │
│  stop(tenant_slug)                           │
│  status() → {tenant: running/stopped/error}  │
│                                              │
│  por tenant: asyncio.Task con loop           │
│   getUpdates(timeout=25, offset)             │
│   → mismo handler que el webhook             │
│   offset persistido en bot_config            │
│   backoff exponencial en errores             │
│   409 (webhook activo) → parar y reportar    │
└──────────────────────────────────────────────┘
```

- **Arranque**: lifespan de FastAPI lee canales telegram activos con
  `transport=polling` y arranca sus pollers. Al guardar el canal se
  (re)inicia el poller del tenant.
- **Selección de transporte**: campo `transport` en credenciales del
  canal: `auto` (default) | `polling` | `webhook`. En `auto`: si hay
  `PUBLIC_BASE_URL` global configurada → webhook (setWebhook
  automático); si no → polling.
- **Exclusión mutua**: activar polling borra el webhook; activar
  webhook detiene el poller.
- **Un solo proceso**: los pollers viven en el proceso web (uvicorn
  single worker hoy). Si se escala a múltiples workers, mover a un
  worker ARQ dedicado (nota para entonces, no ahora).

## 3. Fichas informativas (channel-info-cards)

Contenido estático en `app/admin/channel_info.py` (dict por
proveedor) renderizado en modal HTML/CSS (sin librerías). Campos:
`que_es`, `como_funciona`, `ventajas[]`, `desventajas[]`, `costo`,
`requisitos`, `riesgo`. Tono no técnico, comparación
oficial-vs-no-oficial explícita. Botón ⓘ junto a cada opción.

## 4. Humanización (humanization)

### Pipeline de salida

```
texto de respuesta
   │
   ▼ humanizer.plan(text, cfg) → [Burbuja]
   Burbuja = {texto, delay_antes_ms, typing_ms}

   reglas:
   - partir por párrafos (doble salto); máx N burbujas (cfg)
   - typing_ms = len(palabras)/velocidad_wpm ± jitter,
     acotado [min_ms, max_ms]
   - delay entre burbujas: uniforme [pausa_min, pausa_max]
   │
   ▼ por cada burbuja:
   adapter.send_typing() → sleep(typing_ms) → adapter.send()
```

### Configuración (bot_config del tenant)

```json
"humanization": {
  "enabled": true,
  "channels": ["whatsapp_unofficial"],   // dónde aplica
  "split_bubbles": true,
  "max_bubbles": 4,
  "wpm": 40,                // velocidad de "tipeo"
  "typing_min_ms": 800,
  "typing_max_ms": 6000,
  "pause_min_ms": 600,
  "pause_max_ms": 2200
}
```

- Punto de integración: función `send_humanized(adapter, thread_id,
  text, cfg)` usada por todos los webhooks y el poller (un solo
  lugar). Si `enabled=false` o el canal no está en `channels`:
  envío directo como hoy.
- Nodo 🎭 en el Flujo con panel de configuración (mismo patrón que
  los nodos existentes).
- El simulador muestra el plan de burbujas (sin esperar los delays).

## Decisiones

1. **Polling en el proceso web** (no ARQ) — simple, suficiente con
   un worker; revisar si se escala.
2. **Humanización a nivel de envío** (no en el pipeline de
   clasificación) — no afecta latencia medida del pipeline; el
   `latency_ms` registrado sigue siendo el de procesamiento.
3. **Fichas como contenido estático en código** — versionado con el
   repo; editor visual no se justifica aún.
4. **`test_destination` en bot_config** (no tabla nueva).
