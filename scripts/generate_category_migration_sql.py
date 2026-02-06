#!/usr/bin/env python3
"""Generate SQL migration skeleton from reviewed category mapping CSV.

Inputs:
- data/review/category_mapping_final_v2.csv

Outputs:
- migrations/20260206_category_refactor_v2/postgres_up.sql
- migrations/20260206_category_refactor_v2/postgres_down.sql
- migrations/20260206_category_refactor_v2/mysql_up.sql
- migrations/20260206_category_refactor_v2/mysql_down.sql
- migrations/20260206_category_refactor_v2/validation.sql
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "review" / "category_mapping_final_v2.csv"
OUT_DIR = ROOT / "migrations" / "20260206_category_refactor_v2"
TAG = "20260206"


def esc_sql(value: str) -> str:
    return (value or "").replace("'", "''")


def load_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if (r.get("status") or "").strip().lower() in {"accept", "revise"}]


def mapping_values_pg(rows: List[Dict[str, str]]) -> str:
    lines = []
    for r in rows:
        lines.append(
            "(" + ", ".join(
                [
                    f"'{esc_sql(r.get('old_id', ''))}'",
                    f"'{esc_sql(r.get('old_name', ''))}'",
                    f"'{esc_sql(r.get('final_primary_category', ''))}'",
                    f"'{esc_sql(r.get('final_subcategory', ''))}'",
                    f"'{esc_sql(r.get('alias_of', ''))}'",
                ]
            ) + ")"
        )
    return ",\n    ".join(lines)


def mapping_values_mysql(rows: List[Dict[str, str]]) -> str:
    return mapping_values_pg(rows)


def build_postgres_up(rows: List[Dict[str, str]]) -> str:
    values = mapping_values_pg(rows)
    return f"""-- Category refactor migration (PostgreSQL)
-- Generated from: data/review/category_mapping_final_v2.csv
-- Date tag: {TAG}
--
-- Assumptions (adjust before running):
-- 1) Core dictionary table: case_types(id, name, category, subcategory, updated_at)
-- 2) Historical business table: incident_records(case_type_id, case_type_name, category, subcategory)
--
-- Safety: wrap in transaction + keep backups for rollback.

BEGIN;

CREATE TABLE IF NOT EXISTS category_mapping_v2_{TAG} (
    old_id TEXT PRIMARY KEY,
    old_name TEXT NOT NULL,
    final_primary_category TEXT NOT NULL,
    final_subcategory TEXT NOT NULL,
    alias_of TEXT DEFAULT ''
);

TRUNCATE TABLE category_mapping_v2_{TAG};

INSERT INTO category_mapping_v2_{TAG}
(old_id, old_name, final_primary_category, final_subcategory, alias_of)
VALUES
    {values}
;

CREATE TABLE IF NOT EXISTS backup_case_types_{TAG} AS
SELECT * FROM case_types;

CREATE TABLE IF NOT EXISTS backup_incident_records_{TAG} AS
SELECT * FROM incident_records;

-- 1) Update dictionary table
UPDATE case_types c
SET
    category = m.final_primary_category,
    subcategory = m.final_subcategory,
    updated_at = NOW()
FROM category_mapping_v2_{TAG} m
WHERE c.id = m.old_id;

-- 2) Optional: normalize displayed name to the final subcategory suffix
-- UPDATE case_types c
-- SET name = regexp_replace(m.final_subcategory, '^.*-', '')
-- FROM category_mapping_v2_{TAG} m
-- WHERE c.id = m.old_id;

-- 3) Update historical records by id first
UPDATE incident_records i
SET
    category = m.final_primary_category,
    subcategory = m.final_subcategory,
    case_type_name = m.final_subcategory
FROM category_mapping_v2_{TAG} m
WHERE i.case_type_id = m.old_id;

-- 4) Fallback update by old name (for rows without case_type_id)
UPDATE incident_records i
SET
    category = m.final_primary_category,
    subcategory = m.final_subcategory,
    case_type_name = m.final_subcategory
FROM category_mapping_v2_{TAG} m
WHERE (i.case_type_id IS NULL OR i.case_type_id = '')
  AND i.case_type_name = m.old_name;

COMMIT;
"""


def build_postgres_down() -> str:
    return f"""-- Category refactor rollback (PostgreSQL)
-- Date tag: {TAG}

BEGIN;

TRUNCATE TABLE case_types;
INSERT INTO case_types SELECT * FROM backup_case_types_{TAG};

TRUNCATE TABLE incident_records;
INSERT INTO incident_records SELECT * FROM backup_incident_records_{TAG};

COMMIT;
"""


def build_mysql_up(rows: List[Dict[str, str]]) -> str:
    values = mapping_values_mysql(rows)
    return f"""-- Category refactor migration (MySQL 8+)
-- Generated from: data/review/category_mapping_final_v2.csv
-- Date tag: {TAG}
--
-- Assumptions (adjust before running):
-- 1) Core dictionary table: case_types(id, name, category, subcategory, updated_at)
-- 2) Historical business table: incident_records(case_type_id, case_type_name, category, subcategory)

START TRANSACTION;

CREATE TABLE IF NOT EXISTS category_mapping_v2_{TAG} (
    old_id VARCHAR(128) PRIMARY KEY,
    old_name VARCHAR(255) NOT NULL,
    final_primary_category VARCHAR(128) NOT NULL,
    final_subcategory VARCHAR(255) NOT NULL,
    alias_of VARCHAR(128) DEFAULT ''
);

DELETE FROM category_mapping_v2_{TAG};

INSERT INTO category_mapping_v2_{TAG}
(old_id, old_name, final_primary_category, final_subcategory, alias_of)
VALUES
    {values}
;

CREATE TABLE IF NOT EXISTS backup_case_types_{TAG} AS
SELECT * FROM case_types;

CREATE TABLE IF NOT EXISTS backup_incident_records_{TAG} AS
SELECT * FROM incident_records;

-- 1) Update dictionary table
UPDATE case_types c
JOIN category_mapping_v2_{TAG} m ON c.id = m.old_id
SET
    c.category = m.final_primary_category,
    c.subcategory = m.final_subcategory,
    c.updated_at = NOW();

-- 2) Update historical records by id first
UPDATE incident_records i
JOIN category_mapping_v2_{TAG} m ON i.case_type_id = m.old_id
SET
    i.category = m.final_primary_category,
    i.subcategory = m.final_subcategory,
    i.case_type_name = m.final_subcategory;

-- 3) Fallback update by old name
UPDATE incident_records i
JOIN category_mapping_v2_{TAG} m ON i.case_type_name = m.old_name
SET
    i.category = m.final_primary_category,
    i.subcategory = m.final_subcategory,
    i.case_type_name = m.final_subcategory
WHERE (i.case_type_id IS NULL OR i.case_type_id = '');

COMMIT;
"""


def build_mysql_down() -> str:
    return f"""-- Category refactor rollback (MySQL 8+)
-- Date tag: {TAG}

START TRANSACTION;

DELETE FROM case_types;
INSERT INTO case_types SELECT * FROM backup_case_types_{TAG};

DELETE FROM incident_records;
INSERT INTO incident_records SELECT * FROM backup_incident_records_{TAG};

COMMIT;
"""


def build_validation() -> str:
    return f"""-- Validation checks after migration
-- Update table/column names if your schema differs.

-- 1) Count mappings
SELECT COUNT(*) AS mapping_count FROM category_mapping_v2_{TAG};

-- 2) Count case_types rows updated by mapping
SELECT COUNT(*) AS mapped_case_types
FROM case_types c
JOIN category_mapping_v2_{TAG} m ON c.id = m.old_id;

-- 3) Find incident rows that still use old names
SELECT i.case_type_name, COUNT(*) AS cnt
FROM incident_records i
JOIN category_mapping_v2_{TAG} m ON i.case_type_name = m.old_name
GROUP BY i.case_type_name
ORDER BY cnt DESC;

-- 4) Distribution by final primary category
SELECT category, COUNT(*) AS cnt
FROM case_types
GROUP BY category
ORDER BY cnt DESC;
"""


def build_readme(rows: List[Dict[str, str]]) -> str:
    return f"""# Category Refactor Migration v2

Generated from `/Users/vavavoom/Documents/test/data/review/category_mapping_final_v2.csv`.

## Scope
- Reviewed rows included: {len(rows)}
- Status included: `accept`, `revise`
- Rollback strategy: restore from backup tables

## Files
- `postgres_up.sql`
- `postgres_down.sql`
- `mysql_up.sql`
- `mysql_down.sql`
- `validation.sql`

## Run order
1. Pick one dialect (`postgres_*` or `mysql_*`).
2. Edit table/column names if your schema differs.
3. Execute `*_up.sql`.
4. Execute `validation.sql` and verify counts.
5. If needed, execute `*_down.sql` for rollback.

## Notes
- Current repository mainly stores case types in JSON (`data/fire_cases_complete.json`), so this migration is a database deployment skeleton.
- If you want, generate a JSON patch next so local files and DB stay consistent.
"""


def main() -> None:
    rows = load_rows(INPUT)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "postgres_up.sql").write_text(build_postgres_up(rows), encoding="utf-8")
    (OUT_DIR / "postgres_down.sql").write_text(build_postgres_down(), encoding="utf-8")
    (OUT_DIR / "mysql_up.sql").write_text(build_mysql_up(rows), encoding="utf-8")
    (OUT_DIR / "mysql_down.sql").write_text(build_mysql_down(), encoding="utf-8")
    (OUT_DIR / "validation.sql").write_text(build_validation(), encoding="utf-8")
    (OUT_DIR / "README.md").write_text(build_readme(rows), encoding="utf-8")

    print(f"generated migration files in: {OUT_DIR}")
    print(f"rows included: {len(rows)}")


if __name__ == "__main__":
    main()
