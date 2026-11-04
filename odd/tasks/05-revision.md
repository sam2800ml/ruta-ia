# Feature 05 — Revisión del consultor y publicación

## Objetivo
Un consultor acepta, edita o rechaza cada bloque; la empresa solo ve lo publicado y aceptado.

## Supuestos tomados para avanzar (confirmar con el profesor)
- Un bloque rechazado cuenta como decidido y se oculta a la empresa.
- Los puntajes por pilar no se editan, solo se aceptan o rechazan.

## Checklist
- [x] 05-R1 Cola de revisión con contadores
- [x] 05-R2 Decisión por bloque con historial inmutable
- [x] 05-R3 Evidencia insuficiente no se acepta tal cual (editar o rechazar)
- [x] 05-R4 Publicar exige todos los bloques decididos
- [x] 05-R5 Filtrado en la base (RLS): la empresa no ve borradores ni rechazados

## Hecho cuando
- [x] Las pruebas de `tests/test_diagnosis.py` pasan y el recorrido en navegador (Playwright) llega sin errores de consola.

## Evidencia
`pytest` → 65 passed (todo el backend). Recorrido Playwright: invitación → cuenta → perfil y documento → dos encuestas → diagnóstico → revisión y publicación → informe → estrategia de 5 etapas → casos de uso → «Ver como empresa».

## Pendiente
- Probar `AnthropicLLM` con la API real y datos con NDA.
- Envío real de correos.

## Siguiente paso
Validar supuestos con el profesor y el líder del reto.
