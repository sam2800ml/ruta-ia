# Feature 02 — Empresa y documentos

## Objetivo
La empresa registra sus datos y sube los documentos que dan contexto al diagnóstico y a la estrategia (paso 1 del diseño).

## Alcance
Incluye: formulario con borrador, carga de PDF/DOCX/TXT (≤25 MB), procesamiento en segundo plano con estados, fragmentos con página, lista de sugeridos, «Continuar».
Fuera: reconocimiento de texto en PDF escaneados (decisión 8).

## Supuestos tomados para avanzar (confirmar con el profesor — decisión 8)
- Datos mínimos: razón social, NIT, sector, tamaño y ciudad. Sitio web opcional.
- Documentos requeridos: plan estratégico, organigrama, mapa de procesos, informe de tecnología y política de datos personales. El inventario de sistemas es opcional.
- Listas de sector y tamaño de ejemplo (`backend/app/company_rules.py`).
- PDF sin texto: se marca «error» con el motivo.
- Los archivos se guardan en disco local (`RUTA_STORAGE_DIR`); el procesamiento corre en un hilo tras confirmar la transacción. Una cola de trabajos real queda para cuando haya más carga.

## Checklist
- [x] 02-R1 Formulario con borrador y listas cerradas — `test_profile_draft_and_closed_lists`
- [x] 02-R2 Carga de PDF, DOCX y TXT de hasta 25 MB — `test_six_sample_documents_reach_processed`, `test_rejects_big_empty_and_wrong_formats`
- [x] 02-R3 Cada documento tiene un tipo — mismas pruebas (tipo desconocido → 422)
- [x] 02-R4 Estado por documento sin bloquear la pantalla — `test_processing_state_survives_and_is_idempotent`; la pantalla consulta el estado cada 2 s mientras haya pendientes (verificado en navegador)
- [x] 02-R5 Sugeridos que se marcan al cumplirse; inventario opcional — `test_readiness_gates_continue`
- [x] 02-R6 «Continuar» se habilita con lo mínimo — `test_readiness_gates_continue` y navegador
- [x] 02-R7 Fragmentos con documento y página — `test_fragments_keep_document_and_page`
- [x] 02-R8 Rechazo con mensaje claro — `test_rejects_big_empty_and_wrong_formats` y navegador («Formato no permitido…»)

## Hecho cuando
- [x] Los seis documentos de ejemplo llegan a «Procesado» sin intervención manual.
- [x] Un archivo de 26 MB se rechaza con su motivo.
- [x] Cada fragmento conserva documento y página.
- [x] El estado correcto se recupera al volver (vive en la base; el procesamiento es idempotente).
- [x] Solo la empresa y el equipo consultor ven los documentos — `test_documents_are_isolated_per_company`.

## Evidencia
`pytest` → 17 passed. Navegador (Playwright): login, borrador, cinco cargas hasta «Procesado», «Continuar» habilitado y rechazo de `virus.exe`.

## Pendiente
- Sin NDA no se suben documentos reales (constitución 7).
- Pantalla del consultor para revisar los documentos de cada empresa (hoy solo hay API con `company_id`).
- Los PDF escaneados quedan rechazados hasta decidir si se aplica OCR.

## Siguiente paso
Feature 08 mínima (banco de preguntas) y Feature 03 (encuestas).
