-- Feature 01: identidad, roles y aislamiento por empresa.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE company (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  nit text UNIQUE,
  status text NOT NULL DEFAULT 'invited' CHECK (status IN ('invited','active')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app_user (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid REFERENCES company(id),
  email text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  role text NOT NULL CHECK (role IN ('company_user','consultant')),
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((role = 'consultant') = (company_id IS NULL))
);

CREATE TABLE invitation (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  email text NOT NULL,
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  accepted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE survey_link (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  role_name text NOT NULL,
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
  id bigserial PRIMARY KEY,
  company_id uuid REFERENCES company(id),
  actor_id uuid,
  action text NOT NULL,
  entity text,
  entity_id text,
  detail jsonb NOT NULL DEFAULT '{}',
  at timestamptz NOT NULL DEFAULT now()
);

-- Contexto de la petición, fijado por la aplicación solo dentro de la transacción.
CREATE FUNCTION app_company_id() RETURNS uuid LANGUAGE sql STABLE AS
  $$ SELECT nullif(current_setting('app.company_id', true), '')::uuid $$;
CREATE FUNCTION app_is_consultant() RETURNS boolean LANGUAGE sql STABLE AS
  $$ SELECT coalesce(current_setting('app.is_consultant', true), '') = 'on' $$;

ALTER TABLE company ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitation ENABLE ROW LEVEL SECURITY;
ALTER TABLE survey_link ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY company_read ON company FOR SELECT USING (app_is_consultant() OR id = app_company_id());
CREATE POLICY company_insert ON company FOR INSERT WITH CHECK (app_is_consultant());
CREATE POLICY company_update ON company FOR UPDATE
  USING (app_is_consultant() OR id = app_company_id())
  WITH CHECK (app_is_consultant() OR id = app_company_id());

CREATE POLICY user_read ON app_user FOR SELECT USING (app_is_consultant() OR company_id = app_company_id());
CREATE POLICY user_insert ON app_user FOR INSERT WITH CHECK (app_is_consultant());

CREATE POLICY inv_all ON invitation FOR ALL
  USING (app_is_consultant()) WITH CHECK (app_is_consultant());

CREATE POLICY link_read ON survey_link FOR SELECT USING (app_is_consultant() OR company_id = app_company_id());
CREATE POLICY link_insert ON survey_link FOR INSERT
  WITH CHECK (app_is_consultant() OR company_id = app_company_id());

CREATE POLICY audit_read ON audit_log FOR SELECT USING (app_is_consultant() OR company_id = app_company_id());
CREATE POLICY audit_insert ON audit_log FOR INSERT
  WITH CHECK (app_is_consultant() OR company_id = app_company_id());

-- Rol de la aplicación: sin BYPASSRLS, sin ser dueño de las tablas.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ruta_app') THEN
    CREATE ROLE ruta_app LOGIN PASSWORD 'ruta_app' NOBYPASSRLS NOSUPERUSER;
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO ruta_app;
GRANT SELECT, INSERT, UPDATE ON company TO ruta_app;
GRANT SELECT, INSERT ON app_user, invitation, survey_link, audit_log TO ruta_app;
GRANT USAGE ON SEQUENCE audit_log_id_seq TO ruta_app;
-- El registro de auditoría es solo de adición: ruta_app no tiene UPDATE ni DELETE.

-- Operaciones que ocurren antes de saber la empresa: corren como el dueño (SECURITY DEFINER).
CREATE FUNCTION auth_get_user(p_email text)
RETURNS TABLE(id uuid, company_id uuid, email text, password_hash text, role text)
LANGUAGE sql SECURITY DEFINER SET search_path = public AS
  $$ SELECT id, company_id, email, password_hash, role FROM app_user WHERE email = lower(p_email) $$;

CREATE FUNCTION auth_accept_invitation(p_token_hash text, p_password_hash text)
RETURNS TABLE(user_id uuid, company_id uuid) LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE inv invitation%ROWTYPE; uid uuid;
BEGIN
  SELECT * INTO inv FROM invitation WHERE token_hash = p_token_hash FOR UPDATE;
  IF NOT FOUND OR inv.accepted_at IS NOT NULL OR inv.expires_at < now() THEN RETURN; END IF;
  INSERT INTO app_user(company_id, email, password_hash, role)
    VALUES (inv.company_id, lower(inv.email), p_password_hash, 'company_user') RETURNING id INTO uid;
  UPDATE invitation SET accepted_at = now() WHERE id = inv.id;
  UPDATE company SET status = 'active' WHERE id = inv.company_id;
  INSERT INTO audit_log(company_id, actor_id, action, entity, entity_id)
    VALUES (inv.company_id, uid, 'invitation.accepted', 'invitation', inv.id::text);
  RETURN QUERY SELECT uid, inv.company_id;
END $$;

-- Abre un enlace de encuesta: válido solo si no se usó ni venció. Devuelve empresa y rol.
CREATE FUNCTION auth_check_survey_link(p_token_hash text)
RETURNS TABLE(link_id uuid, company_id uuid, role_name text) LANGUAGE sql SECURITY DEFINER SET search_path = public AS
  $$ SELECT id, company_id, role_name FROM survey_link
     WHERE token_hash = p_token_hash AND used_at IS NULL AND expires_at > now() $$;

CREATE FUNCTION auth_consume_survey_link(p_token_hash text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE n int;
BEGIN
  UPDATE survey_link SET used_at = now()
   WHERE token_hash = p_token_hash AND used_at IS NULL AND expires_at > now();
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n = 1;
END $$;

REVOKE ALL ON FUNCTION auth_get_user, auth_accept_invitation, auth_check_survey_link, auth_consume_survey_link FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth_get_user, auth_accept_invitation, auth_check_survey_link, auth_consume_survey_link TO ruta_app;
