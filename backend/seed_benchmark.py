"""Caso de referencia de ejemplo para poder correr el benchmark entre proveedores sin datos reales.
Uso: python seed_benchmark.py
"""
import json

from sqlalchemy import create_engine, text

from app.config import settings

FRAGMENTS = [
    {"id": "frag-1", "document": "Plan estratégico 2025-2028.pdf", "page": 3,
     "text": "La empresa no cuenta con un presupuesto asignado para proyectos de inteligencia artificial en los próximos dos años."},
    {"id": "frag-2", "document": "Informe de TI 2026.pdf", "page": 7,
     "text": "Contamos con una nube híbrida ya integrada con el core bancario, lista para cargas de analítica avanzada."},
    {"id": "frag-3", "document": "Política de tratamiento de datos.pdf", "page": 1,
     "text": "No existe una política de uso responsable de inteligencia artificial ni un comité que autorice nuevos casos de uso."},
]
SEGMENTS = [
    {"id": "seg-1", "transcript": "Reunión de dirección", "start_sec": 180,
     "text": "El equipo técnico tiene buena formación en la nube, pero carece de experiencia en modelos de lenguaje."},
    {"id": "seg-2", "transcript": "Mesa de trabajo de operaciones", "start_sec": 900,
     "text": "Existe resistencia al cambio en el área comercial frente a cualquier herramienta de IA nueva."},
]
REFERENCE = {"pillar_scores": {"strategy": 2.0, "infrastructure": 3.5, "governance": 1.0}, "top3": ["governance", "strategy", "talent"]}

eng = create_engine(settings.admin_database_url, isolation_level="AUTOCOMMIT")
with eng.connect() as c:
    exists = c.execute(text("select 1 from reference_case where name = 'Caso de ejemplo (benchmark)'")).first()
    if exists:
        print("Ya existe 'Caso de ejemplo (benchmark)'.")
    else:
        c.execute(text("insert into reference_case(name, inputs, reference) values (:n, cast(:i as jsonb), cast(:r as jsonb))"),
                  {"n": "Caso de ejemplo (benchmark)",
                   "i": json.dumps({"fragments": FRAGMENTS, "segments": SEGMENTS}), "r": json.dumps(REFERENCE)})
        print("Creado 'Caso de ejemplo (benchmark)'.")
