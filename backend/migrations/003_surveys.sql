-- Features 03 y 08 (núcleo): metodología, banco de preguntas, encuestas, transcripciones, consentimiento.

-- Helper: políticas estándar por empresa. cons_write = el equipo consultor también puede escribir.
CREATE FUNCTION _rls(tbl text, cons_write boolean, append_only boolean DEFAULT false) RETURNS void LANGUAGE plpgsql AS $$
DECLARE w text := CASE WHEN cons_write THEN ' OR app_is_consultant()' ELSE '' END;
BEGIN
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
  EXECUTE format('CREATE POLICY %I ON %I FOR SELECT USING (app_is_consultant() OR company_id = app_company_id())', tbl||'_r', tbl);
  EXECUTE format('CREATE POLICY %I ON %I FOR INSERT WITH CHECK (company_id = app_company_id()%s)', tbl||'_i', tbl, w);
  IF append_only THEN
    EXECUTE format('GRANT SELECT, INSERT ON %I TO ruta_app', tbl);
  ELSE
    EXECUTE format('CREATE POLICY %I ON %I FOR UPDATE USING (company_id = app_company_id()%s) WITH CHECK (company_id = app_company_id()%s)', tbl||'_u', tbl, w, w);
    EXECUTE format('CREATE POLICY %I ON %I FOR DELETE USING (company_id = app_company_id()%s)', tbl||'_d', tbl, w);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO ruta_app', tbl);
  END IF;
END $$;

CREATE TABLE methodology (
  id serial PRIMARY KEY,
  version int NOT NULL UNIQUE,
  pillars jsonb NOT NULL,        -- [{key,label}]
  levels jsonb NOT NULL,         -- [{level,name,description}]
  thresholds jsonb NOT NULL,     -- promedios que separan los niveles
  formula text NOT NULL,
  active boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE methodology ENABLE ROW LEVEL SECURITY;
CREATE POLICY meth_r ON methodology FOR SELECT USING (true);
CREATE POLICY meth_w ON methodology FOR INSERT WITH CHECK (app_is_consultant());
CREATE POLICY meth_u ON methodology FOR UPDATE USING (app_is_consultant()) WITH CHECK (app_is_consultant());
GRANT SELECT, INSERT, UPDATE ON methodology TO ruta_app;
GRANT USAGE ON SEQUENCE methodology_id_seq TO ruta_app;

-- Supuestos (decisión 3): los nombres siguen el modelo de Gartner traducido y los cortes son propios.
INSERT INTO methodology(version, pillars, levels, thresholds, formula, active) VALUES (
  1,
  '[{"key":"strategy","label":"Estrategia"},{"key":"infrastructure","label":"Infraestructura"},{"key":"data","label":"Datos"},{"key":"governance","label":"Gobernanza"},{"key":"talent","label":"Talento"},{"key":"culture","label":"Cultura"}]',
  '[{"level":1,"name":"Consciente","description":"Reconoce la IA pero no ha actuado."},{"level":2,"name":"Activo","description":"Hay pruebas aisladas sin coordinación."},{"level":3,"name":"Operativo","description":"Casos en producción con responsables."},{"level":4,"name":"Sistémico","description":"La IA es parte de los procesos centrales."},{"level":5,"name":"Transformacional","description":"La IA redefine el negocio."}]',
  '[1.8, 2.6, 3.4, 4.2]',
  'Puntaje del pilar = promedio ponderado de las respuestas (escala 1 a 5) de las preguntas de ese pilar. Promedio general = promedio simple de los pilares con respuestas. Nivel = tramo del promedio según los cortes.',
  true);

CREATE TABLE question (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key uuid NOT NULL DEFAULT gen_random_uuid(),   -- identifica la pregunta entre versiones
  version int NOT NULL DEFAULT 1,
  text text NOT NULL,
  pillar text NOT NULL,
  roles text[] NOT NULL DEFAULT '{}',            -- vacío = todos los roles
  weight numeric NOT NULL DEFAULT 1 CHECK (weight > 0),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (key, version)
);
ALTER TABLE question ENABLE ROW LEVEL SECURITY;
CREATE POLICY q_all ON question FOR ALL USING (app_is_consultant()) WITH CHECK (app_is_consultant());
GRANT SELECT, INSERT, UPDATE ON question TO ruta_app;

-- Banco inicial de ejemplo (decisión 9): 3 preguntas por pilar para todos los roles y una por pilar para Tecnología.
INSERT INTO question(text, pillar, roles) VALUES
 ('Existe una estrategia de IA aprobada y conocida en mi área.', 'strategy', '{}'),
 ('La dirección asigna presupuesto específico para iniciativas de IA.', 'strategy', '{}'),
 ('Los objetivos del negocio incluyen metas que dependen de la IA.', 'strategy', '{}'),
 ('Nuestra infraestructura permite probar modelos de IA sin riesgo para la operación.', 'infrastructure', '{}'),
 ('Los sistemas críticos se pueden integrar con servicios externos mediante interfaces.', 'infrastructure', '{}'),
 ('Contamos con capacidad de cómputo o nube disponible para cargas de IA.', 'infrastructure', '{}'),
 ('Los datos que necesito están disponibles, limpios y documentados.', 'data', '{}'),
 ('Hay responsables claros de la calidad de los datos.', 'data', '{}'),
 ('Puedo acceder a los datos de otras áreas cuando los necesito.', 'data', '{}'),
 ('Existen políticas escritas para el uso responsable de la IA.', 'governance', '{}'),
 ('Se evalúan los riesgos legales y éticos antes de usar IA en un proceso.', 'governance', '{}'),
 ('Hay un comité o responsable que aprueba los usos de IA.', 'governance', '{}'),
 ('Mi equipo tiene las habilidades para trabajar con herramientas de IA.', 'talent', '{}'),
 ('La organización ofrece formación en IA a quienes la necesitan.', 'talent', '{}'),
 ('Contamos con perfiles técnicos propios para desarrollar soluciones de IA.', 'talent', '{}'),
 ('Las personas confían en que la IA ayuda a su trabajo y no lo amenaza.', 'culture', '{}'),
 ('Se experimenta con nuevas herramientas y se comparten los aprendizajes.', 'culture', '{}'),
 ('Los líderes dan ejemplo usando IA en su trabajo.', 'culture', '{}'),
 ('Hay un inventario actualizado de los modelos y herramientas de IA en uso.', 'infrastructure', '{Tecnología}'),
 ('Los datos se catalogan y tienen dueño en los sistemas de información.', 'data', '{Tecnología}');

CREATE TABLE survey (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  role_name text NOT NULL,
  responsible text NOT NULL,
  email text NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','complete')),
  deadline date NOT NULL,
  questions jsonb NOT NULL,      -- copia de las preguntas enviadas: editar el banco no cambia esta encuesta
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  UNIQUE (company_id, role_name)
);
SELECT _rls('survey', false);
ALTER TABLE survey_link ADD COLUMN survey_id uuid REFERENCES survey(id);

CREATE TABLE survey_answer (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  survey_id uuid NOT NULL REFERENCES survey(id),
  question_id uuid NOT NULL,
  question_key uuid NOT NULL,
  question_text text NOT NULL,
  pillar text NOT NULL,
  weight numeric NOT NULL DEFAULT 1,
  role_name text NOT NULL,
  value int NOT NULL CHECK (value BETWEEN 1 AND 5),
  UNIQUE (survey_id, question_id)
);
SELECT _rls('survey_answer', false, true);

CREATE TABLE outbox_email (
  id bigserial PRIMARY KEY,
  company_id uuid NOT NULL REFERENCES company(id),
  to_email text NOT NULL,
  subject text NOT NULL,
  body text NOT NULL,
  kind text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz
);
SELECT _rls('outbox_email', false, true);
GRANT USAGE ON SEQUENCE outbox_email_id_seq TO ruta_app;

CREATE TABLE transcript (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  name text NOT NULL,
  meeting_date date,
  duration_min int,
  roles text[] NOT NULL DEFAULT '{}',
  has_timestamps boolean NOT NULL DEFAULT false,
  status text NOT NULL DEFAULT 'analyzing' CHECK (status IN ('analyzing','analyzed','error')),
  consent_id uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);
SELECT _rls('transcript', false);
CREATE TABLE transcript_segment (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  transcript_id uuid NOT NULL REFERENCES transcript(id) ON DELETE CASCADE,
  position int NOT NULL,
  start_sec int,
  end_sec int,
  text text NOT NULL
);
SELECT _rls('transcript_segment', false);

CREATE TABLE consent (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  user_id uuid NOT NULL,
  text text NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);
SELECT _rls('consent', false, true);

-- Encuesta pública: abre por enlace sin cuenta (funciones del dueño).
CREATE FUNCTION auth_survey_open(p_token_hash text)
RETURNS TABLE(survey_id uuid, company_id uuid, role_name text, questions jsonb) LANGUAGE sql SECURITY DEFINER SET search_path = public AS
  $$ SELECT s.id, s.company_id, s.role_name, s.questions FROM survey_link l JOIN survey s ON s.id = l.survey_id
     WHERE l.token_hash = p_token_hash AND l.used_at IS NULL AND l.expires_at > now() AND s.status = 'pending' $$;

CREATE FUNCTION auth_survey_submit(p_token_hash text, p_answers jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE s survey%ROWTYPE; l survey_link%ROWTYPE; q jsonb; a jsonb; v int; expected int; got int;
BEGIN
  SELECT * INTO l FROM survey_link WHERE token_hash = p_token_hash AND used_at IS NULL AND expires_at > now() FOR UPDATE;
  IF NOT FOUND OR l.survey_id IS NULL THEN RETURN false; END IF;
  SELECT * INTO s FROM survey WHERE id = l.survey_id AND status = 'pending' FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;
  expected := jsonb_array_length(s.questions);
  got := jsonb_array_length(p_answers);
  IF got <> expected THEN RETURN false; END IF;
  FOR a IN SELECT * FROM jsonb_array_elements(p_answers) LOOP
    v := (a->>'value')::int;
    IF v IS NULL OR v NOT BETWEEN 1 AND 5 THEN RETURN false; END IF;
    SELECT x INTO q FROM jsonb_array_elements(s.questions) x WHERE x->>'id' = a->>'question_id';
    IF q IS NULL THEN RETURN false; END IF;
    INSERT INTO survey_answer(company_id, survey_id, question_id, question_key, question_text, pillar, weight, role_name, value)
      VALUES (s.company_id, s.id, (q->>'id')::uuid, (q->>'key')::uuid, q->>'text', q->>'pillar', (q->>'weight')::numeric, s.role_name, v);
  END LOOP;
  UPDATE survey SET status = 'complete', completed_at = now() WHERE id = s.id;
  UPDATE survey_link SET used_at = now() WHERE id = l.id;
  INSERT INTO audit_log(company_id, action, entity, entity_id, detail)
    VALUES (s.company_id, 'survey.completed', 'survey', s.id::text, jsonb_build_object('role', s.role_name));
  RETURN true;
END $$;
-- El enlace de encuesta solo puede consumirse por la función anterior.
GRANT UPDATE ON survey_link TO ruta_app;
REVOKE ALL ON FUNCTION auth_survey_open, auth_survey_submit FROM PUBLIC;
GRANT EXECUTE ON FUNCTION auth_survey_open, auth_survey_submit TO ruta_app;

-- Las preguntas se copian al enviar la encuesta; la empresa no lee el banco, la función lo hace por ella.
CREATE FUNCTION survey_questions_for_role(p_role text) RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path = public AS
  $$ SELECT coalesce(jsonb_agg(jsonb_build_object('id', id, 'key', key, 'text', text, 'pillar', pillar, 'weight', weight, 'version', version)
                              ORDER BY pillar, created_at), '[]')
     FROM question WHERE active AND (roles = '{}' OR p_role = ANY(roles)) $$;
REVOKE ALL ON FUNCTION survey_questions_for_role FROM PUBLIC;
GRANT EXECUTE ON FUNCTION survey_questions_for_role TO ruta_app;
