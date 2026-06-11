# Runbook de operación diaria

## Checklist matutino (5 min)

```bash
# 1. Verificar salud del sistema
curl https://<host>/health

# 2. Revisar logs de errores de las últimas 8h
docker compose logs --since 8h web | grep -c ERROR

# 3. Verificar webhook activo
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo" | jq '.result.last_error_message'
# Debe ser null

# 4. Ver conversaciones activas en el panel
open https://<host>/admin/conversations
```

## Monitoreo de métricas

Panel: `https://<host>/admin/metrics`

Métricas clave a revisar:
- **Latencia promedio < 2000ms** — si sube, revisar carga del servidor
- **LLM calls = 0** — en modo regex-only, debe ser 0
- **Handoffs pendientes** — revisar si Johana está atendiendo
- **Tickets de feedback abiertos** — revisar y aprobar/rechazar

## Respuesta a incidentes

### Bot caído
```bash
docker compose up -d web
# Si no levanta:
docker compose logs web | tail -50
```

### Alta latencia (>5s)
```bash
# Verificar uso de recursos
docker stats web worker
# Reiniciar si necesario
docker compose restart web
```

### WhatsApp desconectado (Baileys)
```bash
cd /path/to/whatsapp-nooficial
# Ver estado
curl http://localhost:3001/status
# Si status = "disconnected", el proceso intentará reconectar automáticamente
# Si no reconecta en 60s, reiniciar manualmente:
pm2 restart wa-bridge
# o:
node src/index.js &
```

## Operaciones manuales comunes

### Marcar handoff como resuelto (bot retoma)
```sql
UPDATE tenant_green_glamping.conversations
SET in_handoff = false, state = 'active', handoff_expires_at = NULL
WHERE external_thread_id = '<CHAT_ID>';
```

### Silenciar bot para un usuario durante X horas
```sql
UPDATE tenant_green_glamping.conversations
SET in_handoff = true,
    handoff_expires_at = NOW() + INTERVAL '24 hours'
WHERE external_thread_id = '<CHAT_ID>';
```

### Ver historial de conversación de un usuario
```sql
SELECT m.role, m.content_text, m.ts
FROM tenant_green_glamping.messages m
JOIN tenant_green_glamping.conversations c ON c.id = m.conversation_id
WHERE c.external_thread_id = '<CHAT_ID>'
ORDER BY m.ts DESC LIMIT 20;
```

### Backup de KB antes de cambios grandes
```bash
pg_dump $DATABASE_URL \
  --schema=tenant_green_glamping \
  --table=kb_intents \
  -f backup_kb_$(date +%Y%m%d).sql
```

## Media retention

El worker ARQ corre automáticamente a las 3 AM UTC.
Para forzar manualmente:
```bash
docker compose exec worker arq app.workers.arq_worker.WorkerSettings run_media_retention
```

## Rotación de logs

Los logs de Loguru se rotan automáticamente (configurado en `app/core/logging.py`).
Para ver logs históricos:
```bash
ls -lh logs/
cat logs/multibot.log | grep ERROR
```
