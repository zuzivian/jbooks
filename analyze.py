#!/usr/bin/env python3
"""FY2025 -> FY2026 change view of the screened lines in data/lines.json.

Standard library only. Pure functions over the rows extract.py already wrote, so
every figure here is a sum of numbers copied from the exhibits; nothing is
estimated. extract.py calls build() and writes data/changes.json; run this file
directly to rebuild changes.json from an existing lines.json:

  python3 analyze.py                 # data/lines.json -> data/changes.json
  python3 analyze.py --check         # exit 1 if data/changes.json is stale

Conventions
- Baseline is "FY 2025 Enacted"; the request is "FY 2026 Total" (discretionary
  plus reconciliation). Both columns exist in the P-1 and the R-1.
- A line is (exhibit, PE/BLI, appropriation). P-1 lines can span several
  cost-type rows; only rows with counts_in_total are summed (memo rows are not).
- A blank exhibit cell counts as 0 for that line. extract.py keeps blanks out of
  amounts_thousands, and the exhibits leave a cell blank when a line has no money
  in that year.
- "Matched lines only": the change compares the same screened lines in both
  years. It is not DoD's count of UAS or C-UAS spending.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
BASE_COL = "FY 2025 Enacted"
REQ_COL = "FY 2026 Total"
RECON_COL = "FY 2026 Reconciliation Request"
CATEGORIES = ("UAS", "C-UAS", "CCA")
SERVICES = ("Army", "Navy", "Air Force", "Marine Corps", "Defense-Wide", "Space Force")
CCA_NOTE = ("Collaborative Combat Aircraft (CCA) are uncrewed combat aircraft built to fly with crewed fighters. "
            "A few large CCA lines would dominate the UAS total, so they are reported as their own category.")


def money(k: float) -> str:
    """Thousands of dollars -> '$1,234.5M' (the viewer uses the same format)."""
    sign = "-" if k < 0 else ""
    return f"{sign}${abs(k) / 1000:,.1f}M"


def pct_str(p: float | None) -> str:
    return "n/a" if p is None else f"{p:+.1f}%"


def change(base: float, req: float) -> dict:
    """Delta between two amounts in $K. pct is None when the baseline is not positive."""
    d = req - base
    if base and req:
        status = "continuing"
    elif req:
        status = "new in FY26"
    elif base:
        status = "no FY26 request"
    else:
        status = "neither year"
    return {"change": d, "pct": round(d / base * 100, 1) if base > 0 else None, "status": status}


def line_key(r: dict) -> tuple:
    return (r["exhibit"], r["pe_or_bli"], r["appropriation"])


def aggregate_lines(rows: list[dict]) -> list[dict]:
    """Collapse rows into budget lines with FY25 base, FY26 request and the change."""
    lines: dict[tuple, dict] = {}
    for r in rows:
        k = line_key(r)
        ln = lines.get(k)
        if ln is None:
            ln = lines[k] = {
                "exhibit": r["exhibit"], "pe_or_bli": r["pe_or_bli"], "title": r["title"],
                "service": r["service"], "category": r.get("category"), "appropriation": r["appropriation"],
                "source_url": r["source_url"], "source_rows": [], "fy25": 0, "fy26": 0, "fy26_recon": 0,
            }
            for extra in ("group", "related_reason"):
                if extra in r:
                    ln[extra] = r[extra]
        ln["source_rows"].append(r["source_row"])
        if r.get("counts_in_total") is False:
            continue
        a = r.get("amounts_thousands") or {}
        ln["fy25"] += a.get(BASE_COL, 0)
        ln["fy26"] += a.get(REQ_COL, 0)
        ln["fy26_recon"] += a.get(RECON_COL, 0)
    out = []
    for ln in lines.values():
        ln.update(change(ln["fy25"], ln["fy26"]))
        out.append(ln)
    out.sort(key=lambda x: (-x["fy26"], x["exhibit"], x["pe_or_bli"]))
    return out


def totals(lines: list[dict]) -> dict:
    fy25 = sum(x["fy25"] for x in lines)
    fy26 = sum(x["fy26"] for x in lines)
    return {"fy25": fy25, "fy26": fy26, "fy26_recon": sum(x["fy26_recon"] for x in lines),
            "lines": len(lines), **{k: v for k, v in change(fy25, fy26).items() if k != "status"}}


def group_totals(lines: list[dict], field: str, order: tuple = ()) -> list[dict]:
    names = list(order) + sorted({x[field] for x in lines} - set(order))
    out = []
    for n in names:
        sub = [x for x in lines if x[field] == n]
        if sub:
            out.append({"name": n, **totals(sub)})
    return out


def movers(lines: list[dict], n: int = 10) -> dict:
    up = sorted((x for x in lines if x["change"] > 0), key=lambda x: (-x["change"], x["pe_or_bli"]))[:n]
    down = sorted((x for x in lines if x["change"] < 0), key=lambda x: (x["change"], x["pe_or_bli"]))[:n]
    return {"up": up, "down": down}


def findings(t_all: dict, t_ex: dict, by_cat: list[dict], lines: list[dict]) -> list[str]:
    """Plain-English findings. Every number is one shown in the change view."""
    cat = {c["name"]: c for c in by_cat}
    out = [
        f"On the {t_all['lines']} matched lines, the FY2026 request totals {money(t_all['fy26'])}, "
        f"up {money(t_all['change'])} ({pct_str(t_all['pct'])}) from {money(t_all['fy25'])} enacted in FY2025."
    ]
    if "CCA" in cat:
        c = cat["CCA"]
        out.append(
            f"Collaborative Combat Aircraft account for {money(c['fy26'])} of the FY2026 request across "
            f"{c['lines']} lines. Without CCA the matched total is {money(t_ex['fy26'])}, "
            f"up {money(t_ex['change'])} ({pct_str(t_ex['pct'])}).")
    if "C-UAS" in cat:
        c = cat["C-UAS"]
        out.append(
            f"Counter-drone (C-UAS) lines total {money(c['fy26'])} in FY2026 against {money(c['fy25'])} in FY2025 "
            f"({pct_str(c['pct'])}), before counting any share of mixed air-defence lines such as M-SHORAD.")
    if t_all["fy26"]:
        share = t_all["fy26_recon"] / t_all["fy26"] * 100
        out.append(
            f"{money(t_all['fy26_recon'])} of the FY2026 figure ({share:.1f}%) is in the separate reconciliation "
            f"request rather than the base discretionary request.")
    new = [x for x in lines if x["status"] == "new in FY26"]
    ended = [x for x in lines if x["status"] == "no FY26 request"]
    if new:
        top = max(new, key=lambda x: x["fy26"])
        out.append(
            f"{len(new)} lines are new in FY2026 ({money(sum(x['fy26'] for x in new))}) and {len(ended)} lines "
            f"with FY2025 money have no FY2026 request ({money(sum(x['fy25'] for x in ended))}); the largest new one is "
            f"{top['service']} {top['title'].title()} ({top['exhibit']} {top['pe_or_bli']}, {money(top['fy26'])}). "
            f"Some titles appear in both groups under different codes, so read single-line changes with care; the totals do not "
            f"depend on codes.")
    return out


def build(doc: dict) -> dict:
    lines = aggregate_lines(doc.get("rows", []))
    related = aggregate_lines(doc.get("related_not_counted", []))
    ex_cca = [x for x in lines if x["category"] != "CCA"]
    t_all, t_ex = totals(lines), totals(ex_cca)
    by_cat = group_totals(lines, "category", CATEGORIES)

    # Totals check: the line sums must equal the row-level sums of the same columns.
    for col, key in ((BASE_COL, "fy25"), (REQ_COL, "fy26")):
        rows_sum = sum((r.get("amounts_thousands") or {}).get(col, 0)
                       for r in doc.get("rows", []) if r.get("counts_in_total") is not False)
        if abs(rows_sum - t_all[key]) > 0.5:
            raise ValueError(f"line sum of {col} is {t_all[key]}, row sum is {rows_sum}")
    if abs(sum(x["change"] for x in lines) - t_all["change"]) > 0.5:
        raise ValueError("per-line changes do not add up to the total change")

    return {
        "status": doc.get("status"),
        "built_from": "data/lines.json",
        "lines_generated_at": doc.get("generated_at"),
        "units": "thousands of US dollars",
        "base_column": BASE_COL,
        "request_column": REQ_COL,
        "label": "Matched lines only: the same screened lines in both years. Not an official tally.",
        "cca_note": CCA_NOTE,
        "totals": {"all": t_all, "excluding_cca": t_ex},
        "by_service": group_totals(lines, "service", SERVICES),
        "by_service_excluding_cca": group_totals(ex_cca, "service", SERVICES),
        "by_category": by_cat,
        "movers": movers(lines),
        "findings": findings(t_all, t_ex, by_cat, lines),
        "lines": lines,
        "related_not_counted": related,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lines", default=str(ROOT / "data" / "lines.json"))
    ap.add_argument("--out", default=str(ROOT / "data" / "changes.json"))
    ap.add_argument("--check", action="store_true", help="fail if --out differs from a fresh build")
    a = ap.parse_args(argv)
    text = json.dumps(build(json.loads(pathlib.Path(a.lines).read_text())), indent=1) + "\n"
    out = pathlib.Path(a.out)
    if a.check:
        if not out.exists() or out.read_text() != text:
            print(f"{out} is stale: run python3 analyze.py", file=sys.stderr)
            return 1
        return 0
    out.write_text(text)
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
