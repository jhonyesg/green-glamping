# Deploy con Docker Compose

## Requisitos previos

- Docker + Docker Compose v2
- PostgreSQL 14+ (contenedor externo `tcloud_postgres` o instancia dedicada)
- Redis 7 (local o contenedor)
- Dominio con HTTPS (Nginx + Certbot recomendado)

## Configuración inicial

```bash
# 1. Clonar y copiar variables de entorno
git clone <repo> multibot && cd multibot
cp .env.example .env

# 2. Editar .env con valores reales
nano .env
# - DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
# - REDIS_URL=redis://localhost:6379
# - SECRET_KEY=<32 chars aleatorios>
# - TELEGRAM_BOT_TOKEN=<token de @BotFather>
# - TELEGRAM_WEBHOOK_SECRET=<string aleatorio>

# 3. Instalar dependencias (para desarrollo local)
uv sync

# 4. Aplicar migraciones de base de datos
uv run alembic upgrade head

# 5. Crear el primer tenant
python -m scripts.create_tenant --slug green-glamping \
  --name "Green Glamping Chipaque" --mode autonomous

# 6. Cargar KB de Green Glamping
python -m scripts.seed_green_glamping
```

## Levantar en producción

```bash
docker compose up -d web worker

# Verificar
curl http://localhost:8000/health
```

## Registro del webhook de Telegram

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<tu-dominio>/webhook/telegram/green-glamping" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"

# Verificar
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

## Variables de entorno requeridas

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | URL asyncpg de PostgreSQL |
| `REDIS_URL` | URL de Redis |
| `SECRET_KEY` | Clave maestra para encriptación de credenciales |
| `TELEGRAM_BOT_TOKEN` | Token del bot de producción |
| `TELEGRAM_WEBHOOK_SECRET` | Token secreto para validar webhooks |
| `LOG_LEVEL` | `INFO` (producción) o `DEBUG` (desarrollo) |
| `ENVIRONMENT` | `production` o `development` |
| `CORS_ORIGINS` | CSV de dominios permitidos |

## Actualización

```bash
git pull
docker compose build web worker
docker compose up -d web worker
uv run alembic upgrade head  # si hay nuevas migraciones
```
