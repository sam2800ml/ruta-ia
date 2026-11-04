# Feature 09 — Analítica y evaluación

## Objetivo
Indicadores del programa y evidencia para la tesis.

## Supuestos tomados para avanzar (confirmar con el profesor)
- Rúbrica: precisión, evidencia, accionabilidad, claridad, completitud (propia).
- No hay datos reales de Banco AV Villas: todo lo medido es sintético.

## Checklist
- [x] 09-R1 Proporciones aceptado/editado/rechazado
- [x] 09-R2 Control humano y cobertura de evidencia
- [x] 09-R3 Línea base, rúbrica de 5 criterios, SUS, casos de referencia
- [x] 09-R4 Corridas de evaluación congeladas con versión del sistema

## Hecho cuando
- [x] Las pruebas de `tests/test_admin_eval.py` pasan y el recorrido en navegador (Playwright) llega sin errores de consola.

## Evidencia
`pytest` → 65 passed (todo el backend). Recorrido Playwright: invitación → cuenta → perfil y documento → dos encuestas → diagnóstico → revisión y publicación → informe → estrategia de 5 etapas → casos de uso → «Ver como empresa».

## Pendiente
- Probar `AnthropicLLM` con la API real y datos con NDA.
- Envío real de correos.

## Siguiente paso
Validar supuestos con el profesor y el líder del reto.
