-- Features 06 y 07: estrategia conversacional y casos de uso.
CREATE TABLE strategy (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL UNIQUE REFERENCES company(id),
  status text NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress','closed')),
  current_stage text NOT NULL,
  closed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
SELECT _rls('strategy', false);
CREATE TABLE strategy_stage (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  stage text NOT NULL,
  position int NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','current','complete')),
  UNIQUE (company_id, stage)
);
SELECT _rls('strategy_stage', false);
CREATE TABLE strategy_message (
  id bigserial PRIMARY KEY,
  company_id uuid NOT NULL REFERENCES company(id),
  stage text NOT NULL,
  author text NOT NULL CHECK (author IN ('user','assistant')),
  text text NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);
SELECT _rls('strategy_message', false, true);
GRANT USAGE ON SEQUENCE strategy_message_id_seq TO ruta_app;
CREATE TABLE strategy_proposal (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  stage text NOT NULL,
  kind text NOT NULL,
  text text NOT NULL,
  basis text,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','saved','discarded')),
  created_at timestamptz NOT NULL DEFAULT now()
);
SELECT _rls('strategy_proposal', false);
CREATE TABLE strategy_item (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  key uuid NOT NULL,
  version int NOT NULL DEFAULT 1,
  stage text NOT NULL,
  kind text NOT NULL,
  text text NOT NULL,
  basis text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (key, version)
);
SELECT _rls('strategy_item', false);

CREATE TABLE use_case (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  name text NOT NULL,
  area text NOT NULL,
  status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','approved','pilot')),
  risk text NOT NULL DEFAULT 'limitado' CHECK (risk IN ('minimo','limitado','alto')),
  indicator text,
  baseline text,
  target text,
  tech text,
  personal_data boolean NOT NULL DEFAULT false,
  ai_proposed boolean NOT NULL DEFAULT true,
  legal int NOT NULL CHECK (legal BETWEEN 1 AND 5),
  ethic int NOT NULL CHECK (ethic BETWEEN 1 AND 5),
  infra int NOT NULL CHECK (infra BETWEEN 1 AND 5),
  legal_note text NOT NULL,
  ethic_note text NOT NULL,
  infra_note text NOT NULL,
  volume_per_month numeric,
  minutes_saved numeric,
  source text NOT NULL DEFAULT 'manual',
  source_item_key uuid,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  approved_by uuid,
  approved_at timestamptz
);
ALTER TABLE use_case ENABLE ROW LEVEL SECURITY;
CREATE POLICY uc_r ON use_case FOR SELECT USING (app_is_consultant() OR company_id = app_company_id());
CREATE POLICY uc_i ON use_case FOR INSERT WITH CHECK (company_id = app_company_id() AND status = 'proposed' OR app_is_consultant());
-- La empresa solo edita casos «propuestos»; aprobar o pasar a piloto es del equipo consultor.
CREATE POLICY uc_u ON use_case FOR UPDATE USING (app_is_consultant() OR (company_id = app_company_id() AND status = 'proposed'))
  WITH CHECK (app_is_consultant() OR (company_id = app_company_id() AND status = 'proposed'));
GRANT SELECT, INSERT, UPDATE ON use_case TO ruta_app;
