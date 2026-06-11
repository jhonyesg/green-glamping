# Cliente piloto: Green Glamping Chipaque + Parapente Volando con Tatán

Datos de este tenant versionados dentro del repo.

## Estructura

```
green-glamping/
├── knowledge_base/         # Texto de referencia (KB, FAQs, bienvenidas, horarios)
│   ├── knowledge_base.json         # KB estructurada con keywords/respuestas
│   ├── preguntas_frecuentes.txt    # FAQs extraídas del PDF comercial
│   ├── horarios.txt                # Horarios de atención
│   └── 01[abcdef]_bienvenida_*.txt # Variantes de bienvenida (mañana/tarde/etc.)
├── intents/                # Definiciones de intents y disparadores de handoff
│   ├── intents.json
│   └── handoff_triggers.json
├── prompts/                # Prompts del sistema (LLM)
│   └── system_prompt.txt
├── datasets/               # Datasets de entrenamiento / evaluación
│   ├── dataset_completo.jsonl
│   └── dataset_expandido.jsonl
├── reports/                # Análisis e informes (chats reales, hallazgos)
│   └── hallazgos_chats_reales.md
└── media/                  # Archivos multimedia
    ├── images/             # Fotos del lugar y servicios
    ├── audios/             # Guiones de audios (.txt)
    └── voice/              # Audios binarios (.ogg, .mp3) — ver .gitignore
```

## Convención de nombres

- `snake_case`, sin tildes, sin espacios.
- Versiones se numeran con sufijo `_vN` (ej: `system_prompt_v2.txt`).
- Los assets multimedia se referencian por ruta relativa desde
  `multibot/data/clients/<cliente>/...` usando el helper de carga del proyecto.
