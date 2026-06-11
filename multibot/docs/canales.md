# Canales — Guía de operación

> Change: `canales-plug-and-play`. Estado: implementado.

## Resumen

Cada canal (Telegram, WhatsApp oficial, WhatsApp no oficial) ofrece tres
niveles de garantía de funcionamiento:

| Nivel | Cómo se dispara | Qué hace |
|---|---|---|
| 0 | Automático al guardar | Valida credenciales (forma del token, URL alcanzable) sin bloquear el guardado. |
| 1 | Botón **🔌 Probar conexión** | Llama a la API real (`getMe`, `connectionState`, etc.) y devuelve el estado en lenguaje claro. |
| 2 | Botón **🧪 Prueba completa** | Inyecta un "hola" simulado al pipeline completo y envía la respuesta real al destino de prueba del tenant. |

Adicionalmente Telegram soporta **dos modos de transporte** (`webhook` y
`polling`) que se gestionan automáticamente.

---

## Transporte de Telegram

Campo `transport` en las credenciales del canal:

- `auto` (recomendado): si hay `PUBLIC_BASE_URL` global con HTTPS → webhook;
  en cualquier otro caso → polling.
- `polling`: la aplicación abre `getUpdates` en background. No requiere URL
  pública, ideal para desarrollo y `localhost`.
- `webhook`: la aplicación registra el webhook en Telegram. Requiere HTTPS
  público accesible desde internet.

### Exclusión mutua

- Activar **polling** llama a `deleteWebhook` (conservando updates pendientes).
- Activar **webhook** detiene el poller del tenant.
- Si durante el polling Telegram responde **HTTP 409** (ya hay un webhook
  activo), el poller se detiene y el canal queda en estado `conflicted` —
  la UI muestra el botón **⚠ Tomar el control**.

### Persistencia y reinicio

- El offset de polling se guarda en `bot_config.tg_poll_offset` después de
  cada batch procesado.
- Al arrancar el servidor (lifespan), se levantan pollers para todos los
  canales Telegram activos con `transport ∈ {auto, polling}`.
- Al guardar el canal desde el panel, el poller se (re)inicia en el acto.

### Estados visibles

| Estado | Significado |
|---|---|
| `running`    | Poller activo, esperando updates |
| `stopped`    | Sin poller (canal inactivo o sin token) |
| `conflicted` | Webhook ajeno detectado — requiere tomar el control |
| `error:<msg>` | Error de red/API; backoff exponencial, cap 60s |

Visibles en:
- `/admin/channels?tenant=...` (badge al lado del título)
- `/admin/status` (columna "Poller Telegram" en la tabla de tenants)

---

## Destino de prueba (Prueba completa)

Para Telegram: pegar tu `chat_id` (lo entrega `@userinfobot`).
Para WhatsApp: el número donde querés recibir el mensaje de prueba.

El destino se guarda en `bot_config.test_destination` y se aplica
por tenant. Sin destino configurado, el botón **Prueba completa**
devuelve un error claro pidiendo configurarlo.

---

## Humanización 🎭

Mitigación del riesgo de bloqueo en WhatsApp no oficial: parte
respuestas largas en burbujas, muestra "escribiendo…" y agrega
retardos aleatorios proporcionales al largo del texto.

### Configuración (`bot_config.humanization`)

```json
{
  "enabled": true,
  "channels": ["whatsapp_unofficial"],
  "split_bubbles": true,
  "max_bubbles": 4,
  "wpm": 40,
  "typing_min_ms": 800,
  "typing_max_ms": 6000,
  "pause_min_ms": 600,
  "pause_max_ms": 2200
}
```

### Defaults seguros

Al cargar cualquier vista de Flujo, si `bot_config.humanization` no
existe, se inicializa con los defaults (con `enabled=false` para no
humanizar de entrada por accidente).

### Aplicación sin reiniciar

`send_humanized(adapter, thread_id, text, tenant_id, channel, session)`
lee la config desde la BD **en cada envío**, así que cualquier
cambio en el panel Flujo se aplica al próximo mensaje.

### Latencia de pipeline intacta

`messages.latency_ms` se persiste **antes** de invocar
`send_humanized` (en `app/bot/pipeline.py`), por lo que mide solo el
procesamiento del pipeline, no los retardos de entrega.

### Simulador

El simulador (`/admin/simulate/`) calcula el plan de burbujas y lo
muestra al instante (sin esperar los delays) para que el operador
vea cómo quedaría la respuesta.

### Previsualización de plan

```python
from app.bot.humanizer import plan
bubbles = plan("Párrafo uno.\n\nPárrafo dos largo.", {"enabled": True, "channels": ["whatsapp_unofficial"]})
for b in bubbles:
    print(b.typing_ms, b.pause_before_ms, b.text)
```

---

## Fichas informativas (ⓘ)

Cada opción de canal (Telegram, WhatsApp oficial, Evolution, Baileys
propio, WAHA) tiene un botón ⓘ que abre un modal con:

- Qué es (lenguaje de negocio, sin jerga).
- Cómo funciona.
- Ventajas y desventajas.
- Costo aproximado.
- Requisitos.
- Nivel de riesgo (con etiqueta OFICIAL / NO OFICIAL).

Las opciones **no oficiales** mencionan explícitamente la mitigación
disponible: activar 🎭 Humanización reduce los patrones detectables
como bot.

Definidas en `app/admin/channel_info.py` — editables en código,
versionadas con el repo.

---

## Endpoints admin

| Método | Ruta | Propósito |
|---|---|---|
| GET    | `/admin/channels`                      | Listar/editar canales del tenant |
| POST   | `/admin/channels/telegram`             | Guardar token + transporte |
| POST   | `/admin/channels/whatsapp`             | Guardar credenciales WhatsApp no oficial |
| POST   | `/admin/channels/whatsapp_official`    | Guardar credenciales WhatsApp oficial |
| POST   | `/admin/channels/test/{type}`          | Nivel 1: prueba de credenciales |
| POST   | `/admin/channels/test-e2e/{type}`      | Nivel 2: pipeline completo end-to-end |
| POST   | `/admin/channels/takeover/telegram`    | Borrar webhook ajeno + activar transporte |
| POST   | `/admin/channels/test-destination`     | Guardar destino de prueba |

`type` ∈ `telegram | whatsapp | whatsapp_official`.

---

## Smoke test manual (GATE)

1. **Tenant nuevo** → `Canales` → pegar token de Telegram.
2. Al guardar, `token_shape_problem()` valida la forma. Si es buena, el
   poller arranca (`sync_tenant_poller`).
3. Click **🔌 Probar conexión** → resuelve `@usuario` del bot.
4. Escribirle al bot desde el celular → la respuesta llega (polling
   activo, estado `running`).
5. Click **🧪 Prueba completa** → simula "hola" por el pipeline y la
   respuesta llega al destino configurado.
6. Activar 🎭 Humanización → respuestas largas se parten en 2-4
   burbujas con "escribiendo…" visible.
