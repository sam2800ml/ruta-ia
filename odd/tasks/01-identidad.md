# Feature 01 — Identidad, roles y aislamiento por empresa

## Objetivo
Cada persona entra solo a lo que le corresponde: la empresa ve lo suyo y el equipo consultor ve todas las empresas.

## Por qué
Es la base de las demás features y una promesa del diseño (aislamiento entre empresas, constitución 6).

## Alcance
Incluye: login por perfil, invitación de empresas, «Ver como empresa», enlaces de encuesta de un solo uso, auditoría.
Fuera: pantallas de ingreso e invitación (decisión 5), envío real de correo (Feature 03).

## Supuestos tomados para avanzar (confirmar con el profesor)
- Decisión 6: dos perfiles, `consultant` (incluye al superadministrador) y `company_user`. Ingreso con correo y contraseña (argon2); la invitación se acepta con un token de un solo uso.
- El token de invitación se devuelve al consultor en la respuesta hasta que exista el envío de correo.

## Restricciones
Constitución 6 (aislamiento) y 9 (trazabilidad). La base de datos hace cumplir el aislamiento (RLS), no solo la aplicación.

## Checklist
- [x] 01-R1 Inicio de sesión con perfiles diferenciados — `test_login_profiles_and_bad_credentials`
- [x] 01-R2 Aislamiento — `test_company_user_gets_not_found_for_other_company`, `test_rls_blocks_cross_company_even_with_raw_sql`
- [x] 01-R3 Invitar empresa (queda «invited» hasta el primer ingreso) — `test_invite_company_flow`. **Pendiente:** envío del correo.
- [x] 01-R4 «Ver como empresa» solo lectura (API y transacción `READ ONLY` en la base) — `test_view_as_company_is_read_only`
- [x] 01-R5 Enlaces de un solo uso, ligados a empresa y rol, con vencimiento — `test_survey_link_single_use_and_expiry`
- [x] 01-R6 Acciones sensibles auditadas con usuario y hora; tabla solo de adición — `test_audit_log_records_and_is_append_only`. **Pendiente:** registrar aprobar, publicar y envío de correo cuando existan (Features 03 y 05).

## Hecho cuando
- [x] Un usuario de la empresa A que pide datos de la B recibe «no encontrado», igual que si no existieran.
- [x] Un enlace de encuesta usado o vencido no abre la encuesta.
- [x] Las acciones registradas aparecen con autor y hora.
- [x] Desde «Ver como empresa» no se puede escribir.

## Evidencia
`cd backend && python migrate.py && pytest` → 8 passed (Postgres 16, rol `ruta_app` sin BYPASSRLS y sin ser dueño).

## Siguiente paso
Feature 02 (empresa y documentos).
