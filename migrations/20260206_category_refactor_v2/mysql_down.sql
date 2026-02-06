-- Category refactor rollback (MySQL 8+)
-- Date tag: 20260206

START TRANSACTION;

DELETE FROM case_types;
INSERT INTO case_types SELECT * FROM backup_case_types_20260206;

DELETE FROM incident_records;
INSERT INTO incident_records SELECT * FROM backup_incident_records_20260206;

COMMIT;
