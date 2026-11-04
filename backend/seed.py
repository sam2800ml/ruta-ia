"""Datos de desarrollo: un consultor y una empresa activa. Uso: python seed.py"""
from sqlalchemy import create_engine, text
from app.config import settings
from app.security import hash_password

eng = create_engine(settings.admin_database_url, isolation_level="AUTOCOMMIT")
with eng.connect() as c:
    c.execute(text("insert into app_user(email, password_hash, role) values ('consultor@example.com', :p, 'consultant') on conflict do nothing"),
              {"p": hash_password("demo-clave-1234")})
    cid = c.execute(text("insert into company(name, nit, status) values ('Banco AV Villas (demo)', '860035827', 'active') "
                         "on conflict (nit) do update set name = excluded.name returning id")).scalar_one()
    c.execute(text("insert into app_user(company_id, email, password_hash, role) values (:c, 'empresa@example.com', :p, 'company_user') on conflict do nothing"),
              {"c": cid, "p": hash_password("demo-clave-1234")})
print("consultor@example.com / empresa@example.com  (clave: demo-clave-1234)")
