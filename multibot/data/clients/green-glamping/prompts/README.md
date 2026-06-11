# Prompts

Prompts del sistema que se envían al LLM cuando se usa (fallback,
audio transcrito, visión de imagen).

- `system_prompt.txt` → prompt principal. Se concatena con la KB y
  la configuración del tenant antes de cada llamada al LLM.

Mantener archivos individuales por escenario, no uno monolítico. Si
necesitás un prompt específico (ej. para audio), creá
`audio_prompt.txt`, etc.
