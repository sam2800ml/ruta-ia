# Feature 03 — Encuestas y transcripciones

## Objetivo
Se recoge la visión de cada rol por encuesta con enlace único y se cargan transcripciones de reuniones con consentimiento.

## Supuestos tomados para avanzar (confirmar con el profesor)
- Los correos NO se envían de verdad: quedan en la tabla `outbox_email` y se ven en la bandeja de prueba.
- Banco de 20 preguntas y preguntas por rol sembrados (editable en Feature 08).
- Sin consentimiento, la transcripción se guarda pero no se usa.

## Checklist
- [x] 03-R1 Encuesta por rol (1–5) con enlace único, de un solo uso y con vencimiento
- [x] 03-R2 Seguimiento de respondidas y recordatorios (cola `outbox_email`)
- [x] 03-R3 Respuestas inmutables (append-only)
- [x] 03-R4 Consentimiento registrado antes de usar transcripciones
- [x] 03-R5 Transcripciones TXT/VTT/SRT/DOCX con roles y marcas de tiempo

## Hecho cuando
- [x] Las pruebas de `tests/test_surveys.py` pasan y el recorrido en navegador (Playwright) llega sin errores de consola.

## Evidencia
`pytest` → 65 passed (todo el backend). Recorrido Playwright: invitación → cuenta → perfil y documento → dos encuestas → diagnóstico → revisión y publicación → informe → estrategia de 5 etapas → casos de uso → «Ver como empresa».

## Pendiente
- Probar `AnthropicLLM` con la API real y datos con NDA.
- Envío real de correos.

## Siguiente paso
Validar supuestos con el profesor y el líder del reto.
