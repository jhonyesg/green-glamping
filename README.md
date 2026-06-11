# Green Glamping Chipaque — Paquete de contexto para proyecto paralelo

**Última actualización**: 2026-06-10
**Propósito**: Replicar el bot de Telegram/n8n en cualquier otra plataforma (LangChain, Rasa, Botpress, custom Python, etc.) con TODO el conocimiento del negocio ya estructurado.

---

## 0. Dónde está cada cosa (mapa rápido)

Los archivos listados en la sección 2 vivían antes sueltos en esta raíz. Ahora
están versionados dentro del proyecto técnico (`multibot/`) bajo una
estructura multi-tenant:

| Antes (raíz) | Ahora |
|---|---|
| `01_knowledge_base.json` | `multibot/data/clients/green-glamping/knowledge_base/knowledge_base.json` |
| `02_intents.json` | `multibot/data/clients/green-glamping/intents/intents.json` |
| `03_handoff_triggers.json` | `multibot/data/clients/green-glamping/intents/handoff_triggers.json` |
| `04_system_prompt.txt` | `multibot/data/clients/green-glamping/prompts/system_prompt.txt` |
| `00_preguntas_frecuentes_pdf_extraido.txt` | `multibot/data/clients/green-glamping/knowledge_base/preguntas_frecuentes.txt` |
| `05_horarios.txt` | `multibot/data/clients/green-glamping/knowledge_base/horarios.txt` |
| `01[a-f]_bienvenida_*.txt` | `multibot/data/clients/green-glamping/knowledge_base/01[a-f]_bienvenida_*.txt` |
| `06_dataset_completo.jsonl` | `multibot/data/clients/green-glamping/datasets/dataset_completo.jsonl` |
| `07_dataset_expandido.jsonl` | `multibot/data/clients/green-glamping/datasets/dataset_expandido.jsonl` |
| `08_hallazgos_chats_reales.md` | `multibot/data/clients/green-glamping/reports/hallazgos_chats_reales.md` |
| `09_imagenes/*.jpg` | `multibot/data/clients/green-glamping/media/images/*.jpg` |
| `10_audios_scripts/*.txt` | `multibot/data/clients/green-glamping/media/audios/*.txt` |
| `saludo de natalia.ogg` (espacio) | `multibot/data/clients/green-glamping/media/voice/saludo_natalia.ogg` (snake_case) |

El proyecto técnico está en `multibot/` — entrá ahí para correr el bot o
hacer cambios al código.

---

## 1. ¿Qué es este proyecto?

Bot comercial 24/7 para **Green Glamping Chipaque y Parapente Volando con Tatán**, un negocio de turismo en Chipaque, Cundinamarca, Colombia. Maneja 2 productos principales:
- **Glamping** (Montaña guadua / Cristal panorámico) con experiencias de cabalgata, cars 4x4, spa, restaurante
- **Parapente** biplaza con piloto certificado

**Canal actual**: Telegram (bot). **Canal planificado**: WhatsApp Business. **Estado**: En desarrollo activo, ya tiene KB completa con 33 intents.

---

## 2. Estructura del paquete

```
proyecto_paralelo/
├── README.md                                  ← Este archivo
├── 00_preguntas_frecuentes_pdf_extraido.txt   ← PDF "preguntas IA.pdf" extraído a texto
├── 01_knowledge_base.json                     ← 33 intents con keywords + response + handoff
├── 02_intents.json                            ← Definición original de intents (15)
├── 03_handoff_triggers.json                   ← 7 triggers H01-H07
├── 04_system_prompt.txt                       ← Prompt del agente IA (personalidad)
├── 05_horarios.txt                            ← Horarios de atención
├── 06_dataset_completo.jsonl                  ← Dataset de entrenamiento (formato JSONL)
├── 07_dataset_expandido.jsonl                 ← Dataset expandido
├── 08_hallazgos_chats_reales.md               ← Notas de chats reales con clientes
├── 09_imagenes/                               ← 10 imágenes (portafolios, medios pago, etc.)
├── 10_audios_scripts/                         ← 13 scripts de audio (textos para TTS)
└── audios_bienvenida_variantes/              ← 6 variantes de bienvenida (mañana/tarde/noche/etc.)
```

---

## 3. Información del negocio (cheat sheet)

| Concepto | Detalle |
|---|---|
| **Ubicación** | Chipaque, Cundinamarca, 30 min de Bogotá por vía al Llano |
| **Horarios** | 24/7 atención. Glamping check-in 3pm / check-out 12m. Parapente 10am-6:30pm |
| **Contacto titular** | Jonathan Eliécer García · CC 80.845.317 |
| **Nequi/Daviplata/Llave** | 3124436880 |
| **Davivienda** | 488400301062 |
| **BBVA** | 0079209995 |
| **Licencia turismo** | No. 219365 |
| **Capacidad glamping** | 2 personas mayores de edad |
| **Capacidad parapente** | 1 pasajero + 1 piloto (tándem), desde 4 años, hasta 100kg |
| **Edad mínima parapente** | 4 años con tutor |
| **Contraindicaciones parapente** | Embarazo, problemas de columna/cardíacos, >100kg |
| **Último vuelo** | 6:30pm |
| **Servicio de transporte** | $60.000 COP por pareja (ida/vuelta desde municipio) |
| **Parqueadero telecable** | Gratis |
| **Parqueadero peatonal** | Moto $5.000 / Carro $8.000 |
| **Pilotos** | Certificados por Aeronáutica Civil, licencia vigente |
| **Convenio** | Parapente Sabana (empresa aliada) |
| **Baño seco** | Disponible en Glamping Montaña (ecológico) |
| **Glamping tipo cabaña** | No hay cabañas separadas; el equivalente rústico es el Glamping Montaña (hecho en guadua) |
| **Telecable** | Servicio de transporte tipo teleférico con vista 360° al aire libre |

### Precios (reserva)
- Solo vuelo / cumple / aniversario: **$30.000**
- Glamping + Parapente: **$200.000**
- Combos 1-7: **$160.000**
- Combo 5 (glamping+parapente+spa): **$290.000**
- Parapente individual: **$220.000**
- Spa pareja: **$130.000**
- NO hay descuentos (regla firme del negocio)

### Reglas de cancelación
- Glamping: cambios con mínimo 15 días
- Parapente: cambios con mínimo 2 días
- Fuera de estos tiempos no se procesan

---

## 4. Lo que el bot hace (funcionalidad)

### 4.1 Preguntas que responde (33 intents pre-hechos, 0 LLM)

Ver `01_knowledge_base.json` para el detalle completo. Resumen:

| Categoría | Ejemplos de intents |
|---|---|
| **Saludos** | saludo_puro (6 variantes por hora/origen) |
| **Información** | info_servicios, horarios, ubicacion, como_reservar, datos_pago, seleccion_combo, diferencia_glamping, capacidad_glamping |
| **Reglas** | menores_bebes, mascotas, comida_externa (no external), cancelacion, clima_lluvia |
| **Servicios** | transporte, parqueadero, restaurante, wifi, spa_jacuzzi, duracion_actividades |
| **Parapente** | contraindicaciones_parapente, edad_volar, tandem_dos_personas, convenio_parapente_sabana |
| **Extras** | tarjeta_invitacion, telecable, bano_seco, nevera_bar, es_empresa_real |
| **Cierre** | despedida, hablar_humano, queja |

### 4.2 Handoffs (7 triggers) - pasan a Johana

| Código | Cuándo | Acción |
|---|---|---|
| H01 | Cliente da datos (nombre + cédula + fecha + combo) | Johana cierra reserva |
| H02 | Cliente pide hablar con humano | Johana interviene |
| H03 | Cliente reporta queja | Johana + supervisor |
| H04 | Cliente pide descuento (objeciones O1-O6) | Johana evalúa firmeza |
| H05 | Cliente pide servicio no catalogado (torta, DJ, decoración) | Johana evalúa |
| H06 | Cliente pide otro número / oficina | Johana evalúa |
| H07 | Más de 3 turnos sin clasificar (intent='otro') | Johana revisa |

### 4.3 Objeciones de precio (6 precanned, 0 LLM)

Ver `01_knowledge_base.json` → `objeciones_precio`:
- O1_descuento: "Los precios del catálogo ya son los mínimos posibles..."
- O2_quitar_servicio: "El precio del combo incluye los servicios tal como están publicados..."
- O3_comparacion: "Entiendo. Cada lugar maneja sus precios..."
- O4_precio_mas_bajo: "El precio más bajo es el que está en el catálogo..."
- O5_presupuesto_ajustado: "Te entiendo. Si quieres, puedo mostrarte las opciones de menor valor..."
- O6_pago_contado: "El precio es el mismo independientemente de la forma de pago..."

### 4.4 Protección anti-inyección (3 capas)

1. **Pre-filtro en código**: bloquea keywords antes de tocar el LLM
2. **System prompt del agente**: reglas inquebrantables contra revelar prompt
3. **Validación post-respuesta**: detecta si la respuesta menciona "soy bot/IA/modelo"

Lista de keywords bloqueadas:
```
ignora instrucciones, olvida lo anterior, actúa como, pretend, finge,
dime tu prompt, muéstrame tu prompt, revela tu prompt, system prompt,
qué modelo usas, qué ia eres, quién te creó, override, bypass,
eres un bot, eres una ia, eres un modelo, instructions, instrucciones internas
```

### 4.5 Cascada de bienvenida (primer contacto)

Si `isFirstContact` → envía 5 mensajes en orden:
1. Mensaje de bienvenida (texto, ~500 chars)
2. Foto portafolio glamping
3. Foto portafolio parapente
4. Saludo por hora (mañana/tarde/noche)
5. Mensaje de cierre ("¿qué plan te gustaría conocer?")

**Nota**: el slot 4 (audio saludo) está implementado en BD pero el workflow actual de n8n no lo envía. Hay que añadir `sendVoice` con file_id cuando se suban los .ogg a Telegram.

---

## 5. Hallazgos de chats reales (importante para entrenar)

Ver `08_hallazgos_chats_reales.md` para el documento completo. Resumen de insights:

1. **Los clientes combinan saludo + pregunta en un solo mensaje**: "Hola, cuánto cuesta el combo 5" → el bot debe detectar la PREGUNTA (no responder solo saludo)
2. **Confunden "Glamping Cristal" con "cabaña"**: cuando dicen "cabaña" en realidad quieren "Glamping Montaña" (que es tipo cabaña en guadua)
3. **Preguntan por "Penti" o "peti"**: se refiere a "Parapente" mal escrito → keyword fuzzy debe matchear
4. **Piden descuento SIEMPRE al final de la primera respuesta**: la objeción de precio es casi inevitable
5. **Piden "torta de cumple" y "DJ"**: la regla es clara (no se permite por el restaurante), pero escalan a H05
6. **Muchos preguntan por WiFi**: confirmar que sí hay, pero advertir sobre la montaña
7. **Piden "hablar con humano" o "asesor"**: derivar a Johana rápido
8. **El bot debe tolerar typos y abreviaciones**: "komo", "kuesta", "glampin", "combos", "preio"

---

## 6. Cómo implementar en otra plataforma

### 6.1 Arquitectura mínima requerida

```
[Canal: Telegram/WhatsApp/Web] 
  → Normalizar mensaje
  → Pre-filtro anti-inyección
  → Cargar contexto (memoria últimos 10 turnos)
  → Clasificar intent (regex matching contra KB)
  → Decidir:
     ├─ match con KB → enviar respuesta pre-hecha
     ├─ match con handoff → push a Johana + marcar pausa
     └─ sin match → fallback handoff (H07)
  → Guardar turno en memoria
  → Enviar respuesta al cliente
```

### 6.2 Stack sugerido para proyecto paralelo

**Opción A: LangChain + Python + Telegram Bot**
- Cargar `01_knowledge_base.json` con `json.load()`
- Usar `ConversationBufferWindowMemory(k=10)` para memoria
- LLM: GPT-4o-mini o Claude 3.5 Sonnet (MiniMax NO está disponible públicamente, requiere API especial)
- Vector store opcional para fuzzy matching

**Opción B: Rasa**
- Cargar intents de `02_intents.json` y `01_knowledge_base.json`
- Definir stories (no son necesarias, son pre-hechas)
- Actions custom para los handoffs (push a Johana)

**Opción C: Botpress**
- Crear Q&A pairs desde `01_knowledge_base.json`
- Webhooks para handoffs
- Tablas para memoria (últimos turnos por chat_id)

**Opción D: Custom Python puro (sin LLM para 90% de casos)**
- Clasificador regex contra keywords de `01_knowledge_base.json`
- Solo LLM (GPT-4o) para casos no cubiertos (H07 fallback)
- Memoria: SQLite o archivo JSON por chat_id
- Webhook receiver para Telegram/WhatsApp

### 6.3 Datos que necesitas en BD

```sql
-- Messages (memoria)
CREATE TABLE messages (
  id SERIAL PRIMARY KEY,
  chat_id VARCHAR(100) NOT NULL,
  role VARCHAR(20) NOT NULL,  -- 'user' | 'bot'
  body TEXT,
  intent VARCHAR(50),
  ts TIMESTAMPTZ DEFAULT NOW()
);

-- Conversation state (control de handoff + pausa)
CREATE TABLE conversation_state (
  chat_id VARCHAR(100) PRIMARY KEY,
  in_handoff BOOLEAN DEFAULT FALSE,
  handoff_at TIMESTAMPTZ,
  handoff_rule VARCHAR(10),
  handoff_expires_at TIMESTAMPTZ,  -- NOW() + 7 hours
  push_name VARCHAR(100),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Knowledge base (intents)
CREATE TABLE knowledge_base (
  intent VARCHAR(50) PRIMARY KEY,
  keywords_regex TEXT NOT NULL,
  response TEXT NOT NULL,
  handoff BOOLEAN DEFAULT FALSE,
  handoff_rule VARCHAR(10),
  description TEXT
);
```

### 6.4 Sistema de handoff con pausa 7h

Cuando `mark_handoff(rule, reason)` se llama:
1. Actualizar `conversation_state` con `in_handoff=TRUE, handoff_expires_at=NOW() + 7 hours`
2. Responder al cliente: "Te paso con mi compañera. Ella te escribe en un momento 🙌"
3. Push a Johana con todo el contexto

Mientras `handoff_expires_at > NOW()`:
- Cualquier mensaje del cliente → **NO responder**
- Solo reenviar el mensaje a Johana

Después de 7h:
- Bot retoma automáticamente
- Resetea `in_handoff=FALSE`

---

## 7. Tareas pendientes (futuro)

Estas son features que NO están implementadas y serían valiosas:

1. **STT (Speech-to-Text)**: transcribir notas de voz del cliente con Whisper
2. **TTS (Text-to-Speech)**: generar y enviar audios pre-grabados (los scripts en `10_audios_scripts/` están listos, falta convertirlos a .ogg y subirlos)
3. **Imagen adjunta del cliente**: si manda comprobante de pago, validar con Vision API
4. **Multi-canal (WhatsApp Business)**: actualmente solo Telegram
5. **Dashboard de Johana**: que vea todos los chats activos y métricas
6. **Análisis de sentimiento**: detectar frustración temprana
7. **A/B testing de respuestas**: probar versiones de O1-O6 para ver cuál convierte más
8. **Persistencia de carritos**: si el cliente elige combo pero no completa reserva, recordarle después
9. **Generador de tarjetas de invitación personalizadas**: los datos (De:/Para:) ya están en la respuesta, falta el flujo completo

---

## 8. Contactos clave del proyecto

- **Johana** (la persona que toma el control): `+57 317 806 7766` (chat_id Telegram: `573178067766`)
- **Negocios** (titular Jonathan): Nequi `3124436880`
- **Bot actual** (Telegram): @Databgbot (Alertas data)
- **Bot token**: NO incluir en este documento. Guardar en `.env` o variable de entorno.

---

## 9. Cómo probar

### 9.1 Con el bot en n8n (Telegram)
- Escríbele al bot desde Telegram como si fueras un cliente
- El bot responde según los intents
- Las respuestas que terminan en handoff generan push a Johana

### 9.2 Con el simulador HTML (sin Telegram)
- Abre `chatbot/simulador.html` en el navegador
- Escribe mensajes como cliente
- El HTML hace polling al bot vía webhook
- Funciona aunque Telegram no esté configurado

### 9.3 Test manual con curl
```bash
# Mandar mensaje al bot
curl -X POST https://automatizaciones.mediaserver.com.co/webhook/bot-entrada \
  -H "Content-Type: application/json" \
  -d '{"chatId":"test_001","body":"Cuánto cuesta combo 5?","pushName":"Test","type":"text"}'

# Leer respuestas
curl "https://automatizaciones.mediaserver.com.co/webhook/sim-get-replies?chatId=test_001"
```

---

## 10. Workflows de n8n desplegados (referencia)

| Workflow ID | Nombre | Estado |
|---|---|---|
| `hubpAhcxkfyhEImk` | Bot Green Glamping 24/7 | Activo (Telegram entrada + clasificación + handoff) |
| `IojAthIBXnDVb3XM` | Simulador Cliente | Activo (webhook para testing) |
| `78Xg5A5jsYWWhDSm` | Admin: Setup BD Bot | Activo (setup tablas + seed KB) |

Para usar la API de n8n necesitas:
- `N8N_API_URL`: `https://automatizaciones.mediaserver.com.co/`
- `N8N_API_KEY`: en `.env` del proyecto

---

## 11. Conversación de ejemplo (test de extremo a extremo)

```
👤 Cliente: Hola, buenos días
🤖 Bot: ¡Hola! 👋 Bienvenido/a a *Green Glamping Chipaque* y *Parapente Volando con Tatán* 🌿🪂
        ¿En qué te podemos ayudar?

👤 Cliente: Quiero info del combo 5
🤖 Bot: ¡Excelente elección! 🙌
        Tenemos dos Glamping:
        🏕️ *Montaña* — guadua con chimenea, cálido y natural
        💎 *Cristal* — 100% transparente, vista 360°
        Ambos tienen capacidad para 2 personas mayores de edad, baño seco (ecológico) y vista espectacular.
        *Si buscas sensación de cabaña rústica*: el Glamping Montaña (hecho en guadua) es tu opción.
        ¿Para qué fecha te gustaría? 📅

👤 Cliente: Cabaña, no glamping cristal
🤖 Bot: [misma respuesta del turno anterior, con memoria del contexto]
       "Si buscas sensación de cabaña rústica, el Glamping Montaña..."

👤 Cliente: Para el 14 de junio
🤖 Bot: ¿Para cuántas personas?
[Continúa pidiendo datos hasta handoff H01]

👤 Cliente: Juan Pérez, CC 1234567890
🤖 Bot: Recibido ✅. Te paso con mi compañera para finalizar los datos y la reserva. 
        Ella te escribe en un momento 🙌

🔔 H01: Push a Johana
   👤 jhon (sim_client_001)
   🎯 Intent: datos_cliente
   📝 "Juan Pérez, CC 1234567890, combo 5, 14 de junio"

[Bot en pausa 7h, no responde más]
```

---

## 12. Resumen ejecutivo para arrancar en 1 frase

> Bot de Telegram para Green Glamping que combina clasificación regex (33 intents pre-hechos, 0 LLM en 90% de casos) + LLM para fallback (MiniMax) + handoff a Johana con pausa 7h + memoria de últimos 10 turnos.

**Stack actual**: n8n (Telegram) + PostgreSQL + MiniMax + audio .ogg (pendiente subir)

**Para replicar**: cargar `01_knowledge_base.json` + `04_system_prompt.txt` + implementar los 7 handoffs + clasificador regex

---

**¿Listo para empezar tu proyecto paralelo?** Si necesitas ayuda con alguna parte específica (clasificación, handoff, memoria, LLM integration), pregúntame.
