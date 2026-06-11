# Knowledge base

Texto de referencia del cliente: preguntas frecuentes, horarios y variantes
de bienvenida/saludo.

## Archivos

| Archivo | Propósito |
|---|---|
| `knowledge_base.json` | KB estructurada: pares `(keywords, respuesta)`. Es la fuente que carga el clasificador. |
| `preguntas_frecuentes.txt` | FAQs en lenguaje natural, extraídas del PDF comercial. |
| `horarios.txt` | Horarios de atención al cliente. |
| `01a..01f_bienvenida_*.txt` | 6 variantes de bienvenida según contexto (mañana/tarde/noche/recurrente/anuncio/referido). Las usa el panel admin para elegir el saludo. |

## Cómo se cargan

- `knowledge_base.json` → se importa en el seed del tenant (ver
  `multibot/scripts/seed_green_glamping.py`).
- `preguntas_frecuentes.txt` y `horarios.txt` → referencia humana; el bot
  los consume indirectamente a través de los intents definidos.
- Variantes de bienvenida → renderizadas por `app/bot/welcome.py`
  según la hora y la marca del usuario.
