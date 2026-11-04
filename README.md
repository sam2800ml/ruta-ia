# Ruta IA

Plataforma de diagnóstico y estrategia de adopción de IA. Se desarrolla con ODD: cada feature tiene su documento en `odd/tasks/`.

## Backend
```
docker compose up -d db          # Postgres en el puerto 5433 (usuario postgres)
cd backend
pip install -e ".[dev]"
python migrate.py                # aplica migraciones con el rol dueño
pytest                           # evidencia de cada feature
uvicorn app.main:app --reload
```
Variables: prefijo `RUTA_` (`RUTA_DATABASE_URL`, `RUTA_ADMIN_DATABASE_URL`, `RUTA_JWT_SECRET`).

## Estado
Todas las features están implementadas (backend + pantallas) y verificadas con 65 pruebas y un recorrido en navegador.

| Feature | Estado |
|---|---|
| 01 Identidad | hecha — `odd/tasks/01-*.md` |
| 02 Empresa y documentos | hecha — `odd/tasks/02-*.md` |
| 03 Encuestas y transcripciones | hecha — `odd/tasks/03-*.md` |
| 04 Diagnóstico con evidencia | hecha — `odd/tasks/04-*.md` |
| 05 Revisión y publicación | hecha — `odd/tasks/05-*.md` |
| 06 Estrategia guiada | hecha — `odd/tasks/06-*.md` |
| 07 Casos de uso | hecha — `odd/tasks/07-*.md` |
| 08 Administración | hecha — `odd/tasks/08-*.md` |
| 09 Analítica y evaluación | hecha — `odd/tasks/09-*.md` |

## Límites honestos
- **IA**: por defecto corre `StubLLM` (determinista). `AnthropicLLM` (`RUTA_LLM_PROVIDER=anthropic` + `RUTA_ANTHROPIC_API_KEY`) está escrito pero **no se ha probado contra la API real**.
- **Correo**: no se envía. Invitaciones y encuestas quedan en `outbox_email` / se muestran en pantalla.
- Supuestos pendientes de confirmar con el profesor: niveles y cortes de la metodología, rúbrica, listas de sector/tamaño, documentos requeridos, sin OCR.
- No hay datos reales de Banco AV Villas (falta NDA).

## Demo local
`python backend/seed.py` crea `consultor@example.com` y `empresa@example.com` (clave `demo-clave-1234`). Encuestas: `/?encuesta=TOKEN`; invitaciones: `/?invitacion=TOKEN`.

## Frontend
```
cd frontend && npm install && npm run dev   # http://localhost:5173, el API se consulta por /api
python ../backend/seed.py                    # usuarios de prueba (empresa@example.com, clave demo-clave-1234)
```
