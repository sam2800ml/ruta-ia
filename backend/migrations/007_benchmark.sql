-- Comparación de proveedores de IA sobre el mismo caso de referencia (costo, latencia, cobertura, citas verificadas).
CREATE TABLE benchmark_run (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id uuid NOT NULL REFERENCES reference_case(id),
  provider text NOT NULL,
  model text,
  seconds numeric,
  findings_count int NOT NULL DEFAULT 0,
  verified_count int NOT NULL DEFAULT 0,
  findings jsonb NOT NULL DEFAULT '[]',
  error text,
  created_by uuid NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE benchmark_run ENABLE ROW LEVEL SECURITY;
CREATE POLICY benchmark_run_all ON benchmark_run FOR ALL USING (app_is_consultant()) WITH CHECK (app_is_consultant());
GRANT SELECT, INSERT ON benchmark_run TO ruta_app;
