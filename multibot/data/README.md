# data/

Datos y archivos no-código del proyecto Multibot.

## Estructura

```
data/
├── media/                   # Archivos multimedia
│   ├── received/            # Lo que llega de clientes (entrada)
│   ├── sent/                # Lo que envía el bot (salida)
│   │   ├── portfolio/       # Imágenes de catálogo (∞)
│   │   ├── pregenerated/    # Audios pre-grabados (∞)
│   │   ├── kb_assets/       # Assets asociados a intents (∞)
│   │   ├── tts/             # Audios TTS generados (rotación)
│   │   └── temp/            # Temporales (24h)
│   ├── thumbnails/          # Previews (regenerables)
│   └── quarantine/          # Borrado lógico (7d antes de hard delete)
├── exports/                 # Reportes, dumps, logs
│   ├── db_dumps/            # pg_dump (rotación 30d)
│   ├── conversation_logs/   # Logs de conversaciones (90d)
│   └── reports/             # Reportes generados (365d)
├── seeds/                   # Datos iniciales versionados
│   ├── system_prompts/      # Plantillas de system prompt
│   └── welcome_variants/    # Variantes de bienvenida
└── uploads/                 # Lo que sube el admin
    └── tenants/             # Por tenant_id
```

## Política de retención

Ver `design.md` sección 16 (política de eliminación).

Resumen:
- `received/*` → 90 días (configurable por tenant)
- `sent/portfolio, pregenerated, kb_assets` → ∞ (es KB)
- `sent/tts/*` → 30 días si use_count <3, 60 días en cualquier caso
- `sent/temp/*` → 24 horas
- `quarantine/*` → 7 días antes de hard delete
- `exports/db_dumps/*` → 30 días
- `exports/conversation_logs/*` → 90 días
- `exports/reports/*` → 365 días

## Versionado

Ver `.gitignore` raíz. Se versiona:
- `seeds/`
- `media/sent/portfolio/` (assets iniciales)
- `media/sent/pregenerated/` (audios iniciales)
- `media/sent/kb_assets/` (assets de KB iniciales)

NO se versiona:
- Todo lo demás (runtime, recibidos, TTS, exports, uploads runtime)
