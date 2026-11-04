-- Feature 02: datos de la empresa y documentos.
ALTER TABLE company
  ADD COLUMN sector text,
  ADD COLUMN size_range text,
  ADD COLUMN city text,
  ADD COLUMN website text;

CREATE TABLE document (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  name text NOT NULL,
  doc_type text NOT NULL,
  size_bytes bigint NOT NULL CHECK (size_bytes > 0),
  storage_path text NOT NULL,
  status text NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded','processing','processed','error')),
  error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz
);

-- Fragmentos citables: recuerdan su documento y su página (02-R7).
CREATE TABLE fragment (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES company(id),
  document_id uuid NOT NULL REFERENCES document(id) ON DELETE CASCADE,
  page int,
  position int NOT NULL,
  text text NOT NULL
);
CREATE INDEX fragment_doc ON fragment(document_id, position);

ALTER TABLE document ENABLE ROW LEVEL SECURITY;
ALTER TABLE fragment ENABLE ROW LEVEL SECURITY;

CREATE POLICY doc_read ON document FOR SELECT USING (app_is_consultant() OR company_id = app_company_id());
CREATE POLICY doc_insert ON document FOR INSERT WITH CHECK (company_id = app_company_id());
CREATE POLICY doc_update ON document FOR UPDATE
  USING (company_id = app_company_id()) WITH CHECK (company_id = app_company_id());
CREATE POLICY frag_read ON fragment FOR SELECT USING (app_is_consultant() OR company_id = app_company_id());
CREATE POLICY frag_insert ON fragment FOR INSERT WITH CHECK (company_id = app_company_id());
CREATE POLICY frag_delete ON fragment FOR DELETE USING (company_id = app_company_id());

GRANT SELECT, INSERT, UPDATE ON document TO ruta_app;
GRANT SELECT, INSERT, DELETE ON fragment TO ruta_app;
