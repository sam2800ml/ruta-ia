-- Features 08 y 09: evaluación (solo equipo consultor).
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['baseline_measure','reference_case','eval_run','rubric_score','sus_response'] LOOP
    NULL;
  END LOOP;
END $$;

CREATE TABLE baseline_measure (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task text NOT NULL,
  hours numeric NOT NULL CHECK (hours >= 0),
  with_system boolean NOT NULL,
  case_ref text,
  notes text,
  measured_by uuid NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE reference_case (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  system_company_id uuid REFERENCES company(id),
  inputs jsonb NOT NULL DEFAULT '{}',          -- insumos anonimizados
  reference jsonb NOT NULL,                    -- {pillar_scores:{clave:puntaje}, top3:[claves]} del consultor senior
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE eval_run (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  system_version text NOT NULL,
  config jsonb NOT NULL,
  results jsonb NOT NULL,
  created_by uuid NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE rubric_score (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES reference_case(id),
  criterion text NOT NULL,
  value int NOT NULL CHECK (value BETWEEN 1 AND 5),
  evaluator uuid NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sus_response (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  answers int[] NOT NULL CHECK (array_length(answers, 1) = 10),
  score numeric NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['baseline_measure','reference_case','eval_run','rubric_score','sus_response'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY %I ON %I FOR ALL USING (app_is_consultant()) WITH CHECK (app_is_consultant())', t||'_all', t);
    EXECUTE format('GRANT SELECT, INSERT ON %I TO ruta_app', t);     -- los resultados no se reescriben
  END LOOP;
END $$;
DROP FUNCTION _rls(text, boolean, boolean);
