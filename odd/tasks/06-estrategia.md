# Feature 06 — Estrategia guiada

## Objetivo
Chat guiado en 5 etapas que produce ítems estratégicos versionados.

## Supuestos tomados para avanzar (confirmar con el profesor)
- Con `StubLLM` las respuestas son deterministas y simples; la calidad conversacional real no está probada.
- Los usos de IA se registran en `llm_usage`.

## Checklist
- [x] 06-R1 Bloqueada (423) hasta que haya informe publicado
- [x] 06-R2 5 etapas con propuestas que la empresa guarda, edita o descarta
- [x] 06-R3 Ítems con versiones
- [x] 06-R4 Aviso de que el asistente es IA
- [x] 06-R5 Estrategia cerrada habilita casos de uso

## Hecho cuando
- [x] Las pruebas de `tests/test_strategy.py` pasan y el recorrido en navegador (Playwright) llega sin errores de consola.

## Evidencia
`pytest` → 65 passed (todo el backend). Recorrido Playwright: invitación → cuenta → perfil y documento → dos encuestas → diagnóstico → revisión y publicación → informe → estrategia de 5 etapas → casos de uso → «Ver como empresa».

## Pendiente
- Probar `AnthropicLLM` con la API real y datos con NDA.
- Envío real de correos.

## Siguiente paso
Validar supuestos con el profesor y el líder del reto.
