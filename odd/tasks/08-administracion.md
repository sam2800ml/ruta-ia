# Feature 08 — Administración del consultor

## Objetivo
Panel de empresas, banco de preguntas y metodología con versiones.

## Supuestos tomados para avanzar (confirmar con el profesor)
- El consultor es superadmin; no hay roles intermedios.
- Invitación: el token se muestra al consultor, no se envía por correo.

## Checklist
- [x] 08-R1 Dashboard con KPIs calculados de los registros
- [x] 08-R2 Lista de empresas con etapa, madurez y búsqueda
- [x] 08-R3 «Ver como empresa» en solo lectura (transacción read only)
- [x] 08-R4 Banco de preguntas con versiones y retiro
- [x] 08-R5 Metodología editable con versiones

## Hecho cuando
- [x] Las pruebas de `tests/test_admin_eval.py` pasan y el recorrido en navegador (Playwright) llega sin errores de consola.

## Evidencia
`pytest` → 65 passed (todo el backend). Recorrido Playwright: invitación → cuenta → perfil y documento → dos encuestas → diagnóstico → revisión y publicación → informe → estrategia de 5 etapas → casos de uso → «Ver como empresa».

## Pendiente
- Probar `AnthropicLLM` con la API real y datos con NDA.
- Envío real de correos.

## Siguiente paso
Validar supuestos con el profesor y el líder del reto.
