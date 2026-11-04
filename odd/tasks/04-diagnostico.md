# Feature 04 — Diagnóstico con evidencia

## Objetivo
Se generan puntajes por pilar, nivel de madurez, hallazgos con evidencia verificable y recomendaciones.

## Supuestos tomados para avanzar (confirmar con el profesor)
- Los niveles y cortes de la metodología v1 son propios; el profesor debe validarlos.
- `AnthropicLLM` está escrito pero NUNCA se ejecutó contra la API real; todo lo verificado usa `StubLLM`.
- Se admite diagnóstico parcial y el informe dice cuántos roles lo respaldan.

## Checklist
- [x] 04-R1 Puntaje por pilar determinista (media ponderada 1–5)
- [x] 04-R2 Nivel por umbrales de la metodología (2.3 → nivel 2)
- [x] 04-R3 Hallazgos: brecha, fortaleza, contradicción entre roles
- [x] 04-R4 Cada evidencia se verifica contra su fuente; si no, `insuficiente`
- [x] 04-R5 Máximo 3 recomendaciones ligadas a hallazgos
- [x] 04-R6 Versiones del informe y PDF exportable

## Hecho cuando
- [x] Las pruebas de `tests/test_diagnosis.py` pasan y el recorrido en navegador (Playwright) llega sin errores de consola.

## Evidencia
`pytest` → 65 passed (todo el backend). Recorrido Playwright: invitación → cuenta → perfil y documento → dos encuestas → diagnóstico → revisión y publicación → informe → estrategia de 5 etapas → casos de uso → «Ver como empresa».

## Pendiente
- Probar `AnthropicLLM` con la API real y datos con NDA.
- Envío real de correos.

## Siguiente paso
Validar supuestos con el profesor y el líder del reto.
