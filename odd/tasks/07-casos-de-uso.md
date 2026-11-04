# Feature 07 — Casos de uso y priorización

## Objetivo
Portafolio de casos con impacto, complejidad y zona en una matriz.

## Supuestos tomados para avanzar (confirmar con el profesor)
- Los casos creados desde oportunidades traen el texto del ítem como nombre; la empresa los completa.
- Las estimaciones propuestas por IA llevan etiqueta.

## Checklist
- [x] 07-R1 Horas/año = casos/mes × minutos ÷ 60 × 12
- [x] 07-R2 Impacto por cortes [200,600,1200,2400]; complejidad = promedio(legal, ético, infra)
- [x] 07-R3 Zonas: victoria rápida, estratégico, mejoras menores, reconsiderar
- [x] 07-R4 Casos desde oportunidades de la estrategia
- [x] 07-R5 Aprobación y piloto solo por el consultor
- [x] 07-R6 Exportación CSV y revisión de sesgo por área

## Hecho cuando
- [x] Las pruebas de `tests/test_strategy.py` pasan y el recorrido en navegador (Playwright) llega sin errores de consola.

## Evidencia
`pytest` → 65 passed (todo el backend). Recorrido Playwright: invitación → cuenta → perfil y documento → dos encuestas → diagnóstico → revisión y publicación → informe → estrategia de 5 etapas → casos de uso → «Ver como empresa».

## Pendiente
- Probar `AnthropicLLM` con la API real y datos con NDA.
- Envío real de correos.

## Siguiente paso
Validar supuestos con el profesor y el líder del reto.
