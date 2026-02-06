-- Validation checks after migration
-- Update table/column names if your schema differs.

-- 1) Count mappings
SELECT COUNT(*) AS mapping_count FROM category_mapping_v2_20260206;

-- 2) Count case_types rows updated by mapping
SELECT COUNT(*) AS mapped_case_types
FROM case_types c
JOIN category_mapping_v2_20260206 m ON c.id = m.old_id;

-- 3) Find incident rows that still use old names
SELECT i.case_type_name, COUNT(*) AS cnt
FROM incident_records i
JOIN category_mapping_v2_20260206 m ON i.case_type_name = m.old_name
GROUP BY i.case_type_name
ORDER BY cnt DESC;

-- 4) Distribution by final primary category
SELECT category, COUNT(*) AS cnt
FROM case_types
GROUP BY category
ORDER BY cnt DESC;
