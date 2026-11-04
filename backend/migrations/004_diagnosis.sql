-- Features 04 y 05: informe de diagnóstico, evidencia y revisión del consultor.
CREATE TABLE report (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  version int NOT NULL,
  status text NOT NULL DEFAULT 'generating' CHECK (status IN ('generating','draft','in_review','published','error')),
  methodology_version int,
  level int,
  average numeric,
  roles_responded int,
  roles_total int,
  sources jsonb NOT NULL DEFAULT '{}',
  error text,
  requested_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz,
  published_by uuid,
  seconds numeric,
  UNIQUE (company_id, version)
);
ALTER TABLE report ENABLE ROW LEVEL SECURITY;
-- La empresa solo ve informes publicados; el equipo consultor ve todos.
CREATE POLICY report_r ON report FOR SELECT USING (app_is_consultant() OR (company_id = app_company_id() AND status = 'published'));
CREATE POLICY report_i ON report FOR INSERT WITH CHECK (app_is_consultant() OR (company_id = app_company_id() AND status = 'generating'));
CREATE POLICY report_u ON report FOR UPDATE USING (app_is_consultant()) WITH CHECK (app_is_consultant());
GRANT SELECT, INSERT, UPDATE ON report TO ruta_app;

CREATE TABLE pillar_score (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  report_id uuid NOT NULL REFERENCES report(id) ON DELETE CASCADE,
  pillar text NOT NULL,
  score numeric NOT NULL,
  answers int NOT NULL,
  review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','accepted','edited','rejected')),
  UNIQUE (report_id, pillar)
);
CREATE TABLE finding (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  report_id uuid NOT NULL REFERENCES report(id) ON DELETE CASCADE,
  position int NOT NULL,
  kind text NOT NULL CHECK (kind IN ('contradiccion','brecha','fortaleza')),
  pillar text NOT NULL,
  title text NOT NULL,
  description text NOT NULL,
  evidence_status text NOT NULL DEFAULT 'verificada' CHECK (evidence_status IN ('verificada','insuficiente','revisada')),
  review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','accepted','edited','rejected'))
);
CREATE TABLE evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  finding_id uuid NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
  source_type text NOT NULL CHECK (source_type IN ('survey','transcript','document')),
  source_id uuid NOT NULL,
  ref jsonb NOT NULL,
  quote text NOT NULL
);
CREATE TABLE recommendation (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  report_id uuid NOT NULL REFERENCES report(id) ON DELETE CASCADE,
  position int NOT NULL,
  text text NOT NULL,
  finding_ids uuid[] NOT NULL,
  review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','accepted','edited','rejected'))
);

-- La empresa lee un bloque solo si su informe está publicado y el consultor lo aceptó o editó.
-- Escribir: únicamente el equipo consultor (revisión) o el trabajo de generación, que corre con ese contexto.
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['pillar_score','finding','recommendation'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format($f$CREATE POLICY %I ON %I FOR SELECT USING (app_is_consultant() OR (company_id = app_company_id()
        AND review_status IN ('accepted','edited') AND EXISTS (SELECT 1 FROM report r WHERE r.id = report_id)))$f$, t||'_r', t);
    EXECUTE format('CREATE POLICY %I ON %I FOR INSERT WITH CHECK (app_is_consultant())', t||'_i', t);
    EXECUTE format('CREATE POLICY %I ON %I FOR UPDATE USING (app_is_consultant()) WITH CHECK (app_is_consultant())', t||'_u', t);
    EXECUTE format('CREATE POLICY %I ON %I FOR DELETE USING (app_is_consultant())', t||'_d', t);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO ruta_app', t);
  END LOOP;
END $$;
ALTER TABLE evidence ENABLE ROW LEVEL SECURITY;
CREATE POLICY evidence_r ON evidence FOR SELECT USING (app_is_consultant() OR (company_id = app_company_id()
  AND EXISTS (SELECT 1 FROM finding f WHERE f.id = finding_id)));
CREATE POLICY evidence_i ON evidence FOR INSERT WITH CHECK (app_is_consultant());
CREATE POLICY evidence_u ON evidence FOR UPDATE USING (app_is_consultant()) WITH CHECK (app_is_consultant());
CREATE POLICY evidence_d ON evidence FOR DELETE USING (app_is_consultant());
GRANT SELECT, INSERT, UPDATE, DELETE ON evidence TO ruta_app;

CREATE TABLE review_decision (
  id bigserial PRIMARY KEY,
  company_id uuid NOT NULL REFERENCES company(id),
  report_id uuid NOT NULL REFERENCES report(id),
  block_type text NOT NULL,
  block_id uuid NOT NULL,
  action text NOT NULL CHECK (action IN ('accept','edit','reject')),
  reason text,
  old_text text,
  new_text text,
  actor_id uuid NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE review_decision ENABLE ROW LEVEL SECURITY;
CREATE POLICY rd_r ON review_decision FOR SELECT USING (app_is_consultant());
CREATE POLICY rd_i ON review_decision FOR INSERT WITH CHECK (app_is_consultant());
GRANT SELECT, INSERT ON review_decision TO ruta_app;     -- solo de adición
GRANT USAGE ON SEQUENCE review_decision_id_seq TO ruta_app;

CREATE TABLE llm_usage (
  id bigserial PRIMARY KEY,
  company_id uuid NOT NULL REFERENCES company(id),
  report_id uuid REFERENCES report(id),
  kind text NOT NULL,
  provider text NOT NULL,
  tokens_in int NOT NULL DEFAULT 0,
  tokens_out int NOT NULL DEFAULT 0,
  cost_usd numeric NOT NULL DEFAULT 0,
  seconds numeric NOT NULL DEFAULT 0,
  at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE llm_usage ENABLE ROW LEVEL SECURITY;
CREATE POLICY lu_r ON llm_usage FOR SELECT USING (app_is_consultant());
CREATE POLICY lu_i ON llm_usage FOR INSERT WITH CHECK (app_is_consultant());
GRANT SELECT, INSERT ON llm_usage TO ruta_app;
GRANT USAGE ON SEQUENCE llm_usage_id_seq TO ruta_app;

-- Estado del informe para la empresa, sin exponer su contenido mientras no esté publicado.
CREATE FUNCTION company_report_state(p_company uuid)
RETURNS TABLE(id uuid, version int, status text) LANGUAGE sql SECURITY DEFINER SET search_path = public AS
  $$ SELECT r.id, r.version, CASE WHEN r.status IN ('in_review','draft') THEN 'in_review' ELSE r.status END
     FROM report r WHERE r.company_id = p_company AND (app_is_consultant() OR p_company = app_company_id())
     ORDER BY r.version DESC LIMIT 1 $$;
REVOKE ALL ON FUNCTION company_report_state FROM PUBLIC;
GRANT EXECUTE ON FUNCTION company_report_state TO ruta_app;
