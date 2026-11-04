"""Aplica las migraciones SQL en orden con el rol dueño. Uso: python migrate.py"""
import pathlib
from sqlalchemy import create_engine, text
from app.config import settings

eng = create_engine(settings.admin_database_url, isolation_level="AUTOCOMMIT")
with eng.connect() as c:
    c.execute(text("create table if not exists schema_migration(name text primary key, at timestamptz default now())"))
    done = {r[0] for r in c.execute(text("select name from schema_migration"))}
    for f in sorted(pathlib.Path(__file__).parent.joinpath("migrations").glob("*.sql")):
        if f.name not in done:
            c.connection.driver_connection.execute(f.read_text())  # SQL crudo: sin interpretar :nombres como parámetros
            c.execute(text("insert into schema_migration(name) values (:n)"), {"n": f.name})
            print("aplicada", f.name)
