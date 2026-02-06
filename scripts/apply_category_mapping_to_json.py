#!/usr/bin/env python3
"""Apply reviewed category mapping to local JSON case-type library (no SQL required)."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
SRC_JSON = ROOT / "data" / "fire_cases_complete.json"
MAPPING_CSV = ROOT / "data" / "review" / "category_mapping_final_v2.csv"
OUT_JSON = ROOT / "data" / "fire_cases_complete_v2.json"
REPORT_MD = ROOT / "data" / "review" / "category_json_update_report.md"


def load_mapping(path: Path) -> Dict[str, Dict[str, str]]:
    rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
    mapping = {}
    for r in rows:
        status = (r.get("status") or "").strip().lower()
        if status not in {"accept", "revise"}:
            continue
        old_id = (r.get("old_id") or "").strip()
        if not old_id:
            continue
        mapping[old_id] = {
            "old_name": (r.get("old_name") or "").strip(),
            "final_primary_category": (r.get("final_primary_category") or "").strip(),
            "final_subcategory": (r.get("final_subcategory") or "").strip(),
            "status": status,
        }
    return mapping


def extract_name(final_subcategory: str, fallback: str) -> str:
    if "-" in final_subcategory:
        tail = final_subcategory.split("-", 1)[1].strip()
        return tail or fallback
    return final_subcategory or fallback


def main() -> None:
    data = json.loads(SRC_JSON.read_text(encoding="utf-8"))
    mapping = load_mapping(MAPPING_CSV)

    changed: List[Dict[str, str]] = []
    missing: List[str] = []

    for case in data.get("case_types", []):
        cid = case.get("id", "")
        m = mapping.get(cid)
        if not m:
            missing.append(cid)
            continue

        old_name = case.get("name", "")
        old_category = case.get("category", "")

        new_category = m["final_primary_category"] or old_category
        new_subcategory = m["final_subcategory"] or f"{new_category}-{old_name}"
        new_name = extract_name(new_subcategory, old_name)

        case["category"] = new_category
        case["subcategory"] = new_subcategory
        case["name"] = new_name

        aliases = case.get("aliases")
        if not isinstance(aliases, list):
            aliases = []
        if old_name and old_name != new_name and old_name not in aliases:
            aliases.append(old_name)
        case["aliases"] = aliases

        if old_name != new_name or old_category != new_category:
            changed.append(
                {
                    "id": cid,
                    "old_name": old_name,
                    "new_name": new_name,
                    "old_category": old_category,
                    "new_category": new_category,
                    "subcategory": new_subcategory,
                    "status": m["status"],
                }
            )

    data["version"] = "v2_refactored_reviewed"
    data["source"] = "fire_cases_complete + category_mapping_final_v2"
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["description"] = "Case type library after reviewed category refactor"
    data["total_cases"] = len(data.get("case_types", []))

    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JSON Category Refactor Report",
        "",
        f"- source_json: `{SRC_JSON}`",
        f"- mapping_csv: `{MAPPING_CSV}`",
        f"- output_json: `{OUT_JSON}`",
        f"- total_cases: {len(data.get('case_types', []))}",
        f"- changed_cases: {len(changed)}",
        f"- mapped_rows: {len(mapping)}",
        "",
        "## Changed Cases",
        "",
        "| id | old_name | new_name | old_category | new_category | subcategory |",
        "|---|---|---|---|---|---|",
    ]

    for c in changed:
        lines.append(
            f"| {c['id']} | {c['old_name']} | {c['new_name']} | {c['old_category']} | {c['new_category']} | {c['subcategory']} |"
        )

    if missing:
        lines.extend([
            "",
            "## Missing IDs (in JSON but not in mapping)",
            "",
            ", ".join(missing),
        ])

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"generated: {OUT_JSON}")
    print(f"generated: {REPORT_MD}")
    print(f"changed_cases={len(changed)} mapped_rows={len(mapping)}")


if __name__ == "__main__":
    main()
