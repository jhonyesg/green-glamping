# Evolution API para Multibot

Gateway de WhatsApp no oficial (open source, basado en Baileys).

## Arranque

```bash
cp .env.example .env
nano .env   # cambia AUTHENTICATION_API_KEY
docker compose up -d
```

## Crear instancia y vincular el número

```bash
# 1. Crear la instancia
curl -X POST http://localhost:8080/instance/create \
  -H "apikey: TU_KEY" -H "Content-Type: application/json" \
  -d '{"instanceName": "multibot", "qrcode": true, "integration": "WHATSAPP-BAILEYS"}'

# 2. Obtener el QR (también lo devuelve el paso 1)
curl http://localhost:8080/instance/connect/multibot -H "apikey: TU_KEY"
# Escanear con el WhatsApp del negocio: Dispositivos vinculados → Vincular dispositivo

# 3. Verificar conexión
curl http://localhost:8080/instance/connectionState/multibot -H "apikey: TU_KEY"
# {"instance":{"state":"open"}}  ← conectado
```

## Conectar con Multibot

1. Panel → **Canales** → WhatsApp (no oficial) → proveedor **Evolution API**
2. URL: `http://localhost:8080` · API Key: la de tu `.env` · Instancia: `multibot`
3. El webhook ya queda configurado en `.env` (WEBHOOK_GLOBAL_URL) apuntando a
   `/webhook/whatsapp_evolution/<tenant>`

## Alternativas soportadas por Multibot

| Proveedor | Carpeta/Imagen | Cuándo usarla |
|---|---|---|
| **Evolution API** | esta carpeta | Recomendada: multi-instancia, API completa, comunidad grande |
| **Puente Baileys propio** | `../whatsapp-nooficial/` | Mínima, sin dependencias, una sesión |
| **WAHA** | `devlikeapro/waha` (docker) | Si ya la usas o prefieres su API |
