# Troubleshooting común

## Bot no responde en Telegram

1. **Verificar webhook:**
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
   ```
   Debe mostrar `"url": "https://<host>/webhook/telegram/<slug>"` y
   `"pending_update_count": 0`.

2. **Verificar que el servidor está corriendo:**
   ```bash
   curl https://<host>/health
   # {"status":"ok","db":"ok","redis":"ok"}
   ```

3. **Revisar logs:**
   ```bash
   docker compose logs -f web | grep -i error
   ```

## Tenant no encontrado (404)

- Verifica que el slug en la URL coincide exactamente con el slug en `public.tenants`
- Corre: `SELECT slug, status FROM public.tenants;`

## Respuestas incorrectas / no coincide intent

1. Usa el **Simulador** (`/admin/simulate`) para ver el trace de clasificación
2. Revisa la regex del intent: pruébala en [regex101.com](https://regex101.com) con flag `IGNORECASE`
3. Si hay empate entre intents, aumenta la prioridad del intent correcto

## Error de base de datos

- Verificar conexión: `psql $DATABASE_URL -c "SELECT 1"`
- Verificar que el schema del tenant existe:
  ```sql
  SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'tenant_%';
  ```
- Si falta el schema, re-crear el tenant con `scripts/create_tenant.py`

## Redis no disponible

```bash
redis-cli ping  # debe retornar PONG
```

Si no, reiniciar Redis o verificar `REDIS_URL` en `.env`.

## Handoff no notifica a Johana

1. Verificar `notify_target` en `handoff_rules`:
   ```sql
   SELECT rule_code, notify_channel, notify_target FROM tenant_green_glamping.handoff_rules;
   ```
2. Verificar que `TELEGRAM_BOT_TOKEN` está en `.env`
3. Verificar que el `chat_id` de Johana es correcto enviando un mensaje de prueba:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/sendMessage" \
     -d "chat_id=<CHAT_ID>&text=prueba"
   ```

## Migraciones Alembic fallidas

```bash
uv run alembic current   # estado actual
uv run alembic history   # historial
uv run alembic upgrade head  # aplicar pendientes
```

Si hay conflictos, revisar `app/db/migrations/versions/` y resolver manualmente.

## Worker ARQ no procesa tareas

```bash
docker compose logs -f worker
# Verificar que REDIS_URL es accesible desde el contenedor
```

## Importar un dump de n8n KB

Exporta los datos del workflow de n8n como JSON y usa el formato:
```json
{"intents": [{"intent_name": "...", "keywords_regex": "...", "response_text": "..."}]}
```
Luego carga con `scripts/seed_green_glamping.py` (adaptado).
