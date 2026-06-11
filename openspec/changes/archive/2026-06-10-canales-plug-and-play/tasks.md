# Tasks: Canales plug-and-play

## 1. Validación y prueba de canales (channel-testing)

- [x] 1.1 Helpers de verificación en los adapters:
  `TelegramAdapter.get_me()`, `get_webhook_info()`;
  exponer `get_status()` de Evolution/Baileys en un
  método uniforme `check(creds) -> CheckResult`
- [x] 1.2 Detección de token con forma inválida
  (empieza con `@`, no cumple `digitos:letras`) con
  mensaje pedagógico
- [x] 1.3 Endpoint `POST /admin/channels/test/{type}`
  (nivel 1) que retorna JSON con ok/detalle
- [x] 1.4 Validación automática al guardar cada canal
  (no bloquea el guardado; muestra resultado)
- [x] 1.5 Diagnóstico de webhook Telegram: mostrar URL
  ajena + último error; endpoint
  `POST /admin/channels/takeover/telegram`
  (deleteWebhook conservando pendientes)
- [x] 1.6 Campo `test_destination` en bot_config +
  formulario inline (con ayuda para obtener chat_id)
- [x] 1.7 Endpoint `POST /admin/channels/test-e2e/{type}`:
  inyecta "hola" simulado al pipeline y envía la
  respuesta real al destino de prueba
- [x] 1.8 UI: botones "Probar conexión" y "Prueba
  completa" por canal con resultados en vivo
- [x] 1.9 GATE: guardar token inválido → mensaje claro;
  token válido → @nombre mostrado; prueba e2e →
  respuesta llega al Telegram del operador

## 2. Polling de Telegram (telegram-polling)

- [x] 2.1 Crear `app/channels/poller.py` con
  `PollerManager` (start/stop/status por tenant,
  asyncio.Task, backoff, offset persistente en
  bot_config)
- [x] 2.2 Reusar el handler del webhook como función
  compartida `handle_telegram_update(tenant, update)`
  (webhook y poller llaman lo mismo)
- [x] 2.3 Campo `transport` (auto/polling/webhook) en
  credenciales del canal Telegram + selector en UI
- [x] 2.4 Lógica `auto`: con `PUBLIC_BASE_URL` global →
  webhook (setWebhook automático); sin ella → polling
- [x] 2.5 Exclusión mutua: activar polling borra
  webhook; activar webhook detiene poller; manejar 409
  marcando el canal en conflicto
- [x] 2.6 Lifespan: arrancar pollers de canales activos
  al inicio; detenerlos en shutdown
- [x] 2.7 (Re)iniciar el poller del tenant al guardar el
  canal — "lo agrego y queda habilitado"
- [x] 2.8 Estado del poller visible en Canales y en
  Estado (running/stopped/conflicted/error)
- [x] 2.9 GATE: guardar canal con token válido en
  localhost → escribir al bot → respuesta llega sin
  configurar nada más; reiniciar servidor → sigue
  funcionando

## 3. Fichas informativas (channel-info-cards)

- [x] 3.1 Contenido en `app/admin/channel_info.py`:
  fichas de Telegram, WhatsApp oficial, Evolution,
  Baileys propio y WAHA (qué es, cómo funciona,
  ventajas, desventajas, costo, requisitos, riesgo)
- [x] 3.2 Modal HTML/CSS reutilizable + botón ⓘ junto a
  cada opción en Canales
- [x] 3.3 Comparación explícita oficial vs no oficial y
  divulgación de riesgo de bloqueo con referencia a
  Humanización
- [x] 3.4 GATE: revisión de contenido con el usuario
  (lenguaje no técnico, completo)

## 4. Humanización (humanization)

- [x] 4.1 Crear `app/bot/humanizer.py`:
  `plan(text, cfg) -> list[Burbuja]` (partición por
  párrafos, typing_ms por wpm con jitter, pausas
  aleatorias acotadas) — funciones puras testeables
- [x] 4.2 `send_humanized(adapter, thread_id, text,
  cfg)`: typing → sleep → send por burbuja; envío
  directo si está desactivada o el canal no aplica
- [x] 4.3 Integrar en todos los puntos de envío
  (webhooks telegram/evolution/unofficial y poller)
- [x] 4.4 Config en bot_config (`humanization{...}`) con
  defaults seguros; aplicar sin reiniciar
- [x] 4.5 Nodo 🎭 en la vista Flujo con panel de
  configuración (mismo patrón de los nodos actuales)
- [x] 4.6 `latency_ms` registrado excluye los retardos
  de entrega
- [x] 4.7 Simulador/Flujo: previsualizar el plan de
  burbujas con sus tiempos, sin esperar los delays
- [x] 4.8 `tests/test_humanizer.py`: partición,
  tiempos acotados, jitter dentro de rango,
  desactivado → una sola burbuja inmediata
- [x] 4.9 GATE: con humanización activa en Telegram de
  prueba, una respuesta larga llega como 2-4 burbujas
  con "escribiendo…" visible entre ellas

## 5. Verificación final

- [x] 5.1 Flujo completo de novato: tenant nuevo →
  Canales → pegar token → validación lo corrige →
  guardar → escribirle al bot → responde humanizado →
  prueba e2e verde
- [x] 5.2 pytest completo en verde (105 tests passing)
- [x] 5.3 Documentar en `docs/canales.md` (transporte,
  pruebas, humanización)
