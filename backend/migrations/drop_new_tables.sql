-- Drop the new tables created during refactoring
-- This will NOT drop merchant_document or psc_document

BEGIN;

-- Drop tables in reverse order of dependencies (child tables first)
DROP TABLE IF EXISTS director_verification_documents CASCADE;
DROP TABLE IF EXISTS vat_registration_documents CASCADE;
DROP TABLE IF EXISTS company_registration_documents CASCADE;
DROP TABLE IF EXISTS companies_house_documents CASCADE;
DROP TABLE IF EXISTS documents CASCADE;

-- Note: document_verifications is the old table - you may want to keep it or drop it
-- Uncomment the line below if you want to drop the old table too
-- DROP TABLE IF EXISTS document_verifications CASCADE;

COMMIT;

