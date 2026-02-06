# Category Refactor Migration v2

Generated from `/Users/vavavoom/Documents/test/data/review/category_mapping_final_v2.csv`.

## Scope
- Reviewed rows included: 45
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
