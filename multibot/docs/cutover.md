# Cutover: n8n → Multibot

Migration steps to switch Green Glamping Chipaque from the n8n Telegram bot to Multibot, keeping the n8n bot available as rollback.

## Prerequisites

Before starting:
- [ ] Multibot is deployed and reachable at a public HTTPS URL (e.g. `https://bot.greenglamping.co`)
- [ ] `TELEGRAM_BOT_TOKEN` is set in `.env` (same token as n8n uses)
- [ ] Green Glamping tenant provisioned: `python -m scripts.create_tenant --slug green-glamping --name "Green Glamping Chipaque" --mode autonomous`
- [ ] KB seeded: `python -m scripts.seed_green_glamping`
- [ ] Johana's Telegram `chat_id` added to `.env` as `NOTIFY_TELEGRAM_CHAT_ID` and to the `handoff_rules` seed
- [ ] All Sprint 1 tests pass: `pytest -q`

## Step 1 — Verify Multibot in staging (parallel mode)

While n8n is still live, point the webhook to Multibot on a **test bot** (different token):

```bash
curl "https://api.telegram.org/bot<TEST_TOKEN>/setWebhook" \
  -d "url=https://bot.greenglamping.co/webhook/telegram/green-glamping" \
  -d "secret_token=<SECRET_TOKEN>"
```

Run the acceptance checklist manually on the test bot:
- "Hola" → saludo_puro response
- "Cuánto cuesta combo 5" → info_combos response
- "Quiero reservar, mi nombre es X, cédula Y, fecha Z, combo 5" → handoff triggered, Johana notified
- Bot goes silent for 12h after handoff
- After 48h, bot resumes

## Step 2 — Freeze n8n edits

Notify the team: no edits to n8n workflows during cutover window. n8n stays running as-is.

## Step 3 — Switch production webhook

**This is the moment of cutover.** The same Telegram token is used by both bots; switching the webhook is atomic.

```bash
# Point production token to Multibot
curl "https://api.telegram.org/bot<PRODUCTION_TOKEN>/setWebhook" \
  -d "url=https://bot.greenglamping.co/webhook/telegram/green-glamping" \
  -d "secret_token=<SECRET_TOKEN>"

# Verify webhook is registered
curl "https://api.telegram.org/bot<PRODUCTION_TOKEN>/getWebhookInfo"
```

Expected response shows `url` pointing to Multibot and `pending_update_count: 0`.

## Step 4 — Smoke test in production

Send from a real Telegram account (not Johana's):
1. "Hola" → bot responds within 2s
2. "Cuánto vale el combo 3" → combo info
3. "Necesito ayuda urgente" → handoff + Johana notified

Check logs:
```bash
docker compose logs -f web | grep -E "(matched_via|latency_ms|handoff)"
```

## Step 5 — Monitor for 24h

Watch for errors:
```bash
docker compose logs -f web 2>&1 | grep -i error
```

Key metrics to check (via psql):
```sql
-- Message volume since cutover
SELECT COUNT(*), AVG(latency_ms) FROM tenant_green_glamping.messages
WHERE ts > NOW() - INTERVAL '24 hours';

-- Any LLM calls (should be 0 in regex-only mode)
SELECT COUNT(*) FROM tenant_green_glamping.messages WHERE llm_tokens_used > 0;

-- Handoff rate
SELECT COUNT(*) FROM tenant_green_glamping.conversations WHERE in_handoff = true;
```

## Step 6 — Disable n8n webhook (optional, after 48h)

Once confident, disable the n8n Telegram trigger node to stop n8n from trying to reconnect:

1. Open n8n UI
2. Go to the Telegram bot workflow
3. Deactivate the "Telegram Trigger" node (do NOT delete the workflow — keep as backup)

## Rollback

If anything goes wrong, revert to n8n in under 30 seconds:

```bash
# Point webhook back to n8n
curl "https://api.telegram.org/bot<PRODUCTION_TOKEN>/setWebhook" \
  -d "url=<N8N_WEBHOOK_URL>"
```

Then investigate Multibot logs before retrying.

## Environment variables required in production

| Variable | Description |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://cloud:cloud123@localhost:5432/tcloudstorage` |
| `REDIS_URL` | `redis://localhost:6379` |
| `SECRET_KEY` | 32+ char random string (change from dev default) |
| `TELEGRAM_BOT_TOKEN` | Production bot token from @BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | Random string, set in setWebhook call |
| `NOTIFY_TELEGRAM_CHAT_ID` | Johana's Telegram chat_id for handoff alerts |
| `CORS_ORIGINS` | `https://bot.greenglamping.co` |

## Getting Johana's chat_id

1. Have Johana message the bot (or use @userinfobot)
2. Check the bot updates: `curl "https://api.telegram.org/bot<TOKEN>/getUpdates"`
3. Find `message.from.id` in the response
4. Add to `.env` as `NOTIFY_TELEGRAM_CHAT_ID=<id>`
5. Update the handoff_rules seed or run:
   ```sql
   UPDATE tenant_green_glamping.handoff_rules
   SET notify_target = '<chat_id>'
   WHERE notify_channel = 'telegram';
   ```
