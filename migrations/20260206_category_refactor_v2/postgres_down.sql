-- Category refactor rollback (PostgreSQL)
-- Date tag: 20260206

BEGIN;

TRUNCATE TABLE case_types;
INSERT INTO case_types SELECT * FROM backup_case_types_20260206;

TRUNCATE TABLE incident_records;
INSERT INTO incident_records SELECT * FROM backup_incident_records_20260206;

COMMIT;
