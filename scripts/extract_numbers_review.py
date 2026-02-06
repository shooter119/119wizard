#!/usr/bin/env python3
import csv
from pathlib import Path
from numbers_parser import Document

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "review" / "category_review_full.csv"
OUT_REVIEW = ROOT / "data" / "review" / "category_review_full_extracted.csv"
OUT_FINAL = ROOT / "data" / "review" / "category_mapping_final_v2.csv"


def read_numbers_rows(path: Path):
    # numbers_parser expects .numbers extension for this package type
    tmp = Path("/tmp/category_review_full.numbers")
    tmp.write_bytes(path.read_bytes())
    doc = Document(tmp)
    for sheet in doc.sheets:
        for table in sheet.tables:
            rows = table.rows(values_only=True)
            if rows and len(rows) > 1:
                header = [str(h).strip() if h is not None else "" for h in rows[0]]
                data_rows = rows[1:]
                result = []
                for r in data_rows:
                    d = {}
                    for i, h in enumerate(header):
                        if not h:
                            continue
                        v = r[i] if i < len(r) else ""
                        d[h] = "" if v is None else str(v).strip()
                    result.append(d)
                return result
    return []


def write_csv(path: Path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def normalize_subcategory(old_primary: str, old_sub: str, review_comment: str, status: str):
    status_l = (status or "").lower()
    if status_l == "revise" and review_comment:
        return review_comment.strip()
    return old_sub.strip()


def extract_primary(subcategory: str, fallback: str):
    if "-" in subcategory:
        return subcategory.split("-", 1)[0].strip() or fallback
    return fallback


def main():
    rows = read_numbers_rows(SRC)
    review_fields = [
        "review_id",
        "old_id",
        "old_name",
        "old_category",
        "problem_type",
        "suggested_new_primary_category",
        "suggested_new_subcategory",
        "alias_of",
        "status",
        "review_comment",
        "decision_reason",
    ]
    write_csv(OUT_REVIEW, rows, review_fields)

    final_rows = []
    for r in rows:
        final_sub = normalize_subcategory(
            r.get("suggested_new_primary_category", ""),
            r.get("suggested_new_subcategory", ""),
            r.get("review_comment", ""),
            r.get("status", ""),
        )
        final_primary = extract_primary(final_sub, r.get("suggested_new_primary_category", ""))
        final_rows.append(
            {
                "review_id": r.get("review_id", ""),
                "old_id": r.get("old_id", ""),
                "old_name": r.get("old_name", ""),
                "status": r.get("status", ""),
                "alias_of": r.get("alias_of", ""),
                "final_primary_category": final_primary,
                "final_subcategory": final_sub,
                "review_comment": r.get("review_comment", ""),
            }
        )

    final_fields = [
        "review_id",
        "old_id",
        "old_name",
        "status",
        "alias_of",
        "final_primary_category",
        "final_subcategory",
        "review_comment",
    ]
    write_csv(OUT_FINAL, final_rows, final_fields)

    accept = sum(1 for r in rows if (r.get("status", "").lower() == "accept"))
    revise = sum(1 for r in rows if (r.get("status", "").lower() == "revise"))
    reject = sum(1 for r in rows if (r.get("status", "").lower() == "reject"))
    pending = sum(1 for r in rows if (r.get("status", "").lower() in ("", "pending")))
    print(f"rows={len(rows)} accept={accept} revise={revise} reject={reject} pending={pending}")
    print(f"generated: {OUT_REVIEW}")
    print(f"generated: {OUT_FINAL}")


if __name__ == "__main__":
    main()
