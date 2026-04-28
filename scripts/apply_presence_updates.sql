-- SQL: update empty C1..C4 values to '-'
-- Supports SQLite and Postgres (syntax is generic SQL, adjust if needed).
-- This will set any NULL or empty-string Cx to '-'. It does not change explicit 'Absent' or 'Present' values.

-- For SQLite and Postgres
UPDATE apprenants_apprenant
SET c1 = CASE WHEN TRIM(COALESCE(c1, '')) = '' THEN '-' ELSE c1 END,
    c2 = CASE WHEN TRIM(COALESCE(c2, '')) = '' THEN '-' ELSE c2 END,
    c3 = CASE WHEN TRIM(COALESCE(c3, '')) = '' THEN '-' ELSE c3 END,
    c4 = CASE WHEN TRIM(COALESCE(c4, '')) = '' THEN '-' ELSE c4 END
WHERE TRIM(COALESCE(c1, '')) = ''
   OR TRIM(COALESCE(c2, '')) = ''
   OR TRIM(COALESCE(c3, '')) = ''
   OR TRIM(COALESCE(c4, '')) = '';

-- NOTE: If your production DB is PostgreSQL and uses a schema prefix (e.g. public.apprenants_apprenant),
-- adjust the table name accordingly. If additional integrity checks are required, run this in a transaction.
