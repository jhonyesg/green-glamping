# Guía de onboarding para nuevos tenants

## Opción A: Wizard visual (recomendado)

1. Abre el panel admin en `https://<host>/admin`
2. Haz clic en **"Nuevo tenant"** en la barra de navegación
3. Sigue los 6 pasos:
   - **Paso 1**: Ingresa el slug (ej. `mi-negocio`) y nombre del negocio
   - **Paso 2**: Elige el modo de operación (autonomous/assisted/hybrid)
   - **Paso 3**: Configura el canal (Telegram: pega el token de @BotFather)
   - **Paso 4**: Define las ventanas de handoff (12h pausa, 48h retoma)
   - **Paso 5**: Escribe el mensaje de bienvenida
   - **Paso 6**: Confirma y crea el tenant

## Opción B: CLI

```bash
# Crear tenant
python -m scripts.create_tenant \
  --slug mi-negocio \
  --name "Mi Negocio SAS" \
  --mode hybrid

# O con el script de onboarding completo
python -m scripts.onboard_tenant \
  --slug mi-negocio \
  --name "Mi Negocio SAS" \
  --mode hybrid \
  --channel telegram \
  --bot-token "123456:ABC..."
```

## Cargar la base de conocimiento

### Desde JSON

```bash
# Formato: data/seeds/mi-negocio_kb.json
python -m scripts.seed_green_glamping  # referencia/ejemplo
```

### Desde el panel admin

1. Ve a **Base de conocimiento** → selecciona el tenant
2. Haz clic en **"+ Nuevo intent"**
3. Completa:
   - **Nombre**: snake_case, descriptivo (ej. `precio_cabana`)
   - **Regex**: patrón Python (ej. `precio|costo|valor|cuanto`)
   - **Respuesta**: texto completo de la respuesta del bot
   - **Prioridad**: 1-10 (mayor = más peso en empates)
   - **Handoff**: marca si este intent requiere humano

## Configurar webhook de Telegram

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<host>/webhook/telegram/<slug>" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

## Probar el bot

1. Abre **Simulador** en el panel admin
2. Escribe mensajes de prueba para verificar que los intents se detectan
3. Usa el **Simulador** → "Export as test" para generar pruebas automáticas

## Configurar handoff (notificación al humano)

1. Asegúrate de tener el `chat_id` de Telegram del operador humano
   (pídele que mande un mensaje a @userinfobot)
2. Actualiza la tabla `handoff_rules` del tenant:
   ```sql
   UPDATE tenant_<slug>.handoff_rules
   SET notify_target = '<chat_id>'
   WHERE notify_channel = 'telegram';
   ```
3. Agrega el token del bot en `.env` como `TELEGRAM_BOT_TOKEN`
