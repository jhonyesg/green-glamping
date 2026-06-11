# Hallazgos de chats reales — Johana (Green Glamping)

> **Fuente:** 4 conversaciones reales extraídas de WhatsApp Business (`WhatsApp_+57 323 2901133/`, `WhatsApp_Angela Tequia Vuelos/`, `WhatsApp_Estefania Tellez Green/`, `WhatsApp_Lina Villalba Vuelos/`).
>
> **Propósito:** alimentar `system_prompt.txt`, validar `knowledge_base.md` y entrenar el tono del bot. NO es training data formal — es referencia humana para diseño de prompts.
>
> **Total analizado:** ~160 mensajes, 4 clientas distintas, ~5 meses de operación (enero-junio 2026).

---

## 1. Tono y estilo de Johana

- **Voz:** primera persona del plural. Johana habla como "el equipo" (no en singular, no en nombre propio).
- **Registro:** cálido, profesional, comercial. Cercano pero no informal. Tuteo en general, sin diminutivos.
- **Emojis usados (frecuencia alta → baja):** 🏕️ 🪂 ✨ 💚 💳 😊 🙌 💬 🤗 🌿🪂
- **Mayúsculas:** Johana empieza los mensajes importantes con mayúscula ("¡Hola!"), pero el cuerpo del mensaje a veces no tiene mayúsculas consistentes después de cada línea. Es una persona real, no perfecta.
- **Tildes:** Johana a veces olvida tildes ("dias", "numero", "Glamping", "junioom"). El bot debe escribirlos BIEN (es la diferencia entre "persona que escribe rápido" y "bot mal hecho").
- **Puntuación:** usa mucho el asterisco para resaltar (`*texto*` en WhatsApp = negrita), saltos de línea para separar bloques, dos puntos para listas.
- **Cierres típicos:** "Quedo atenta 🤗", "Si señora" (cuando confirma algo breve), "Perfecto" (cuando el cliente confirma), "Vale si señora".
- **Imperativos directos:** "Regálame los datos", "Regálame estos datos", "Quedo atenta". Johana NO usa mucho "por favor" en sus respuestas (sí lo recibe del cliente, no lo da tanto).

## 2. Frases reales que Johana usa (extractos textuales)

### Saludo y bienvenida (versión que ya está en producción)

> "¡Hola! 👋😊 Bienvenido/a a *Green Glamping Chipaque* & *Parapente Volando con Tatan🌿🪂✨* Gracias por contactarnos. Aquí podrás vivir una experiencia única que combina naturaleza, descanso y adrenalina, con nuestros glamping y vuelos en parapente sobre paisajes espectaculares 🌄💚. Será un gusto asesorarte y ayudarte a reservar la experiencia perfecta. Cuéntanos, ¿qué plan te gustaría conocer? 💬✨"

### Cómo reservar (bloque completo que se envía como template)

> "*COMO RESERVAR*
>
> Para confirmar tu reserva debes realizar un abono, el valor restante debe ser cancelado directamente en el sitio a tu llegada
>
> 💚 *Combos cumpleaños/aniversarios/propuestas o solo vuelo en parapente $30.000*
> 💚 *$200.000* *Glamping con parapente*
> 💚 *$160.000* *Demas combos*
> 💚 *$30.000 Combos Spa*
>
> Si deseas reservar con Green Glamping Chipaque:
>
> 1️⃣ Consulta con nuestros asesores disponibilidad del combo y fecha 📆
> 2️⃣ Selecciona el medio de pago por el cual vas a reservar 💸💳
> 3️⃣ Envia foto del comprobante de pago de la reserva junto con los siguientes datos:
> *nombre completo:*
> *Documento de identidad:*
> *número de contacto:*
> *correo electrónico:*
> *Fecha de la reserva:*
> *Especifica el paquete que deseas adquirir*
> 4️⃣ ✅ Todas las transacciones serán verificadas en las diferentes cuentas. Una vez se verifiquen, se realizará el agendamiento de la reserva. Una notificación llegará al correo donde detallará el producto adquirido, recomendación y políticas 💌🗓️
> 5️⃣ Dale click en aceptar y preparate para vivir la mejor experiencia 🤗🎉"

### Medios de pago (template con titular)

> "💳✨ *MEDIOS DE PAGO*✨💳
> 👤 *Titular*: Jonathan Eliécer García
> 🆔 *C.C.:* 80.845.317
> 💚 Llave 🔑 : 3124436880
> 💙 Nequi: 3124436880
> ❤️ Daviplata: 3124436880
> 🏦 Davivienda Ahorros: 488400301062
> 🏦 BBVA Ahorros: 0079209995
> 💳 Pagos con tarjeta débito o crédito. Disponible por datáfono o link de pago (Bold)
> ⚠️ Comisión del 6% sobre el valor de la transacción
> 📲 Elige tu medio de pago favorito y realiza tu reserva fácil y seguro"

### Confirmación de reserva en curso

> "Ok . Ya te agendo"

### Cierre cálido

> "Quedo atenta 🤗"
> "En el transcurso del día te llega el correo con la información"

### Confirmación corta

> "Si señora"
> "Si tenemos disponibilidad"
> "Perfecto"

### Cuando pide datos

> "Regálame estos datos"
> "Regálame los datos del paso 3 de cómo reservar por favor"
> "Regálame el De Para En una sola palabra para tarjeta de invitación"

### Sobre el almuerzo (cuando el combo lo incluye)

> "Si tu combo incluye almuerzo, 🍽️puedes escoger libremente *platos de nuestra carta hasta $20.000*. Si deseas un plato diferente o de mayor valor, *solo pagas el valor excedente 😊*"

### Sobre bebidas

> "Esta es nuestra carta de bebidas. *NO SE PERMITE EL INGRESO DE BEBIDAS O ALIMENTOS A RESTAURANTE*"

## 3. Estructura típica de respuesta de Johana

Johana NO escribe párrafos largos. Estructura típica:

1. **Saludo breve** (cuando arranca chat nuevo): "¡Hola! Buenos días" + bloque de bienvenida.
2. **Bloque de texto principal** con saltos de línea, asteriscos para resaltar, emojis como bullets (💚 1️⃣ ✅).
3. **Adjuntos** (imágenes o audios) inmediatamente después del texto que los referencia.
4. **Cierre** con pregunta o siguiente paso: "Cuéntanos qué te gustaría", "Regálame los datos", "Quedo atenta".
5. **Confirmación corta** cuando el cliente responde: "Si señora", "Perfecto", "Ok. Ya te agendo".

## 4. Casos típicos observados

| Caso | Frecuencia | Cómo lo maneja Johana |
|------|-----------|------------------------|
| Cumpleaños | Alta (4/4 chats mencionan) | Ofrece decoración feliz cumpleaños, tarjeta personalizada, torta → H05 |
| Aniversario | Media (2/4) | Ofrece decoración feliz aniversario / romántica |
| Spa pareja | Media (2/4) | Adjunta imagen spa-pareja.jpg cuando preguntan por relajación |
| Combo 5 / 6 / 7 | Alta | Confirma, adjunta imagen del combo específico, manda medios de pago |
| Glamping + Parapente | Media | Manda portafolio de ambos |
| Cambio de fecha | Media | "Si tenemos disponibilidad" + reagenda, recalcula precio |
| Datos + comprobante | Alta | "Regálame estos datos" + "En el transcurso del día te llega el correo" |
| Tarjeta personalizada | Media (1/4) | Pide "De Para" en una sola línea |
| "Tiene piscina/jacuzzi?" | Ocasional | Responde con imagen de spa pareja (lo que sí tienen) |
| "Descorche de vino" | Ocasional | Johana respondió con audio (probablemente derivó a handoff) |
| "Tienen disponibilidad para X fecha?" | Alta | "Si tenemos disponibilidad" o "Esos cupos los confirma..." (en v2 derivar a handoff) |

## 5. Objeciones reales observadas y cómo las manejó

### O1. "¿Hay descuento?" — Estefanía (31/05/26)

> **Cliente:** "Hay descuento si uno decide hacer parapente, spa y hospedaje?"
> **Johana (real):** No respondió directamente al descuento. Siguió con "PORTAFOLIO GLAMPING" y dejó que el cliente eligiera combo.
>
> **Problema:** en producción NO aplicó la regla de no-negociar. Simplemente ignoró la pregunta.
>
> **Lo que el bot DEBE hacer:** activar regla P1 → respuesta O5 ("te entiendo, puedo mostrarte opciones de menor valor o separar la fecha") + audio 06 si insiste.

### O2. "Quitar un servicio para abaratar" — no observado en estos 4 chats

> El HTML `objeciones` lo cubre. No visto en data real, pero Johana lo manejaría con objeción O2 fija.

### O3. "Comparación con otro lugar" — no observado

> No visto en data real.

### O4. "Precio más bajo" — no observado explícitamente

> Johana suele confirmar precio fijo sin negociación ("$160", "Combo 5 $290.000", etc.). El bot debe hacer lo mismo.

### O5. "Ajustado de presupuesto" — Lina (01/06/26)

> **Cliente:** "Quisiera saber que precio tiene el almuerzo por persona, ya que vamos a ir en familia, y que Menú tienen."
> **Johana (real):** Adjuntó imagen "si-tu-combo-incluye-almuerzo-puedes-escoger-librem.jpg" explicando que hasta $20.000.
>
> **Lo que el bot debe hacer:** ofrecer alternativas de combos de menor valor publicados o separar la fecha, sin reducir precio.

### O6. "Descuento por pago contado" — no observado

### Fuera de horario (mensaje automático viejo)

> El chat de Ángela y Estefanía muestra que cuando el cliente escribe FUERA del horario 8-17, el bot (versión vieja) responde con un mensaje automático de "no podemos atenderte, te respondemos lo antes posible".
>
> **PROBLEMA:** en producción actual, ese mensaje de "fuera de horario" NO debería existir — el bot es 24/7. Este mensaje es LEGACY y debe ser eliminado del flujo.

## 6. Lo que el bot DEBE imitar

- ✅ Voz de "equipo comercial", no persona individual
- ✅ Tuteo siempre
- ✅ Respuestas divididas en bloques cortos con saltos de línea (no párrafos)
- ✅ Asteriscos para resaltar `*texto*` (formato WhatsApp)
- ✅ Emojis moderados: 🏕️ 🪂 ✨ 💚 💳 😊 🙌 💬 🤗
- ✅ Saludo = bloque de bienvenida completo (cuando cliente nuevo)
- ✅ "Regálame estos datos" cuando necesita info
- ✅ "Quedo atenta 🤗" como cierre
- ✅ "Si señora" / "Perfecto" como confirmación corta
- ✅ Adjuntar portafolios + medios de pago como IMAGEN (filename descriptivo)
- ✅ NUNCA decir "soy bot" / "soy asistente virtual"
- ✅ Derivar a "mi compañera" cuando el caso lo requiere

## 7. Lo que el bot NO debe imitar (errores de Johana que el bot debe corregir)

- ❌ **"Demas combos" sin tilde** → escribir "Demás combos" (con tilde)
- ❌ **"junioom"** → escribir "junio" (typo)
- ❌ **"Ok . Ya te agendo"** con espacio antes del punto → escribir "Ok. Ya te agendo"
- ❌ **"La diferencia es el tipo de Glamping"** (respuesta vaga) → el bot debe explicar: Montaña (guadua + chimenea) vs Cristal (transparente 360°)
- ❌ **Mensaje automático de "fuera de horario"** → eliminar (bot 24/7)
- ❌ **Ignorar pregunta de descuento** → aplicar regla P1 (respuesta O1-O6)
- ❌ **"Esos cupos los confirma..."** sin ofrecer handoff claro → el bot debe escalar a handoff con audio 06 cuando hay combo+fecha elegidos

## 8. Patrones de audio (observación de los 4 chats)

Johana responde con AUDIO en situaciones específicas:
- Después de varias idas y vueltas (resume lo conversado)
- Confirmaciones largas (decoración, logística, instrucciones)
- Casos que requieren énfasis (handoff, condiciones)
- "Quedo atenta 🤗" muchas veces va como audio
- Cuando el cliente pregunta algo abierto (diferencia entre glamping, política)

El bot puede imitar esto: para respuestas > 80 chars Y no cubiertas por audio pre-grabado, usar TTS.

## 9. Patrones de imagen (observación de los 4 chats)

Johana adjunta imágenes en este orden aproximado cuando un cliente pregunta por primera vez:
1. Portafolio Glamping (o Portafolio Parapente si vino por vuelo)
2. Glamping específico (si eligió)
3. Decoración (si es cumpleaños/aniversario)
4. Carta de bebidas (si menciona almuerzo/familia)
5. Medios de pago con titular
6. Spa pareja (si pregunta por relajación)

El bot debe imitar esta cascada visual de assets fijos, sin regenerar.

## 10. Recomendaciones para el system prompt

Basado en los hallazgos:

1. **El system prompt DEBE incluir:**
   - El bloque completo de bienvenida (ya está)
   - La plantilla de "cómo reservar" (ya está parcialmente en `knowledge_base.md`)
   - La plantilla de medios de pago (ya está)
   - Las frases de cierre ("Quedo atenta 🤗", "Perfecto", "Si señora")
   - La regla de "regálame los datos" como imperativo natural

2. **El system prompt DEBE evitar:**
   - Lenguaje técnico de chatbot
   - Tildes incorrectas
   - Mensaje automático de "fuera de horario"
   - Respuestas vagas sin información útil
   - "Hola soy un asistente virtual"

3. **El knowledge_base.md DEBE:**
   - Cubrir todos los combos que Johana ha mencionado (cumple, aniversario, propuesta, parapente solo, glamping+parapente, spa, combo 5, combo 6, combo 7)
   - Incluir el caso especial de la "tarjeta personalizada" (De / Para)
   - Confirmar que NO tienen piscina ni jacuzzi, pero sí spa pareja
   - Documentar la política de descorche (NO se permite ingreso de bebidas, consultar política actual)
   - Confirmar almuerzo incluido hasta $20.000 en combos que lo incluyen
