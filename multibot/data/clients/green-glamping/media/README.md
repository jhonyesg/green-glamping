# Media

Archivos multimedia del cliente. Tres subcarpetas:

| Subcarpeta | Contenido | Versionado |
|---|---|---|
| `images/`  | Fotos del lugar, productos, carta, etc. | sí (suelen ser < 500 KB cada una) |
| `audios/`  | Guiones de audios (texto plano `.txt` listos para TTS) | sí |
| `voice/`   | Audios binarios generados (`.ogg`, `.mp3`, `.wav`) | **no** (ver `.gitignore`) |

## Política de versionado

- **Sí se commitea:** assets pequeños referenciados desde código, prompts,
  textos, logos en SVG.
- **No se commitea:** binarios pesados que se regeneran o se sirven desde
  un CDN/S3. Ver `.gitignore` de esta carpeta.

## Renombrado

- Sin espacios, sin tildes: `saludo_natalia.ogg` (antes `saludo de natalia.ogg`).
- snake_case, todo en minúsculas.
- Si un asset tiene versiones, sufijo `_v2`, `_v3`.
