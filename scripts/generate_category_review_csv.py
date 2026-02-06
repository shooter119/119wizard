#!/usr/bin/env python3
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "fire_cases_complete.json"
OUT_DIR = ROOT / "data" / "review"
FULL_CSV = OUT_DIR / "category_review_full.csv"
SAMPLE_CSV = OUT_DIR / "category_review_first30.csv"

AMBIGUOUS_TERMS = ["其他", "综合", "一般", "相关", "事故处置", "灾害事故"]
SPLIT_HINTS = ["和", "及", "、", "/", "与"]


def load_cases(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("case_types", [])


def normalize_name(name: str) -> str:
    s = name.strip()
    for token in ["事故处置", "火灾", "事故", "处置"]:
        s = s.replace(token, "")
    return "".join(s.split())


def guess_problem_type(name: str, duplicate_count: int) -> str:
    if duplicate_count > 1:
        return "重复"
    if any(term in name for term in AMBIGUOUS_TERMS):
        return "模糊"
    if len(name) >= 14:
        return "啰唆"
    if any(hint in name for hint in SPLIT_HINTS):
        return "可拆分"
    return ""


def suggest_subcategory(old_category: str, name: str) -> str:
    base = name.replace("事故处置", "").replace("事故", "").strip()
    if not base:
        return "待人工判定"
    return f"{old_category}-{base}"


def build_rows(cases):
    normalized = [normalize_name(c.get("name", "")) for c in cases]
    dup_counter = {}
    for n in normalized:
        dup_counter[n] = dup_counter.get(n, 0) + 1

    rows = []
    for idx, case in enumerate(cases, start=1):
        name = case.get("name", "").strip()
        old_category = case.get("category", "").strip()
        norm = normalize_name(name)
        problem_type = guess_problem_type(name, dup_counter.get(norm, 0))
        rows.append({
            "review_id": f"R{idx:03d}",
            "old_id": case.get("id", ""),
            "old_name": name,
            "old_category": old_category,
            "problem_type": problem_type,
            "suggested_new_primary_category": old_category,
            "suggested_new_subcategory": suggest_subcategory(old_category, name),
            "alias_of": "",
            "status": "pending",
            "review_comment": "",
            "decision_reason": "",
        })
    return rows


def write_csv(path: Path, rows):
    fieldnames = [
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
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = load_cases(INPUT_FILE)
    rows = build_rows(cases)
    write_csv(FULL_CSV, rows)
    write_csv(SAMPLE_CSV, rows[:30])
    print(f"generated: {FULL_CSV}")
    print(f"generated: {SAMPLE_CSV}")
    print(f"rows(full)={len(rows)}, rows(sample)={min(30, len(rows))}")


if __name__ == "__main__":
    main()
