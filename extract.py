#!/usr/bin/env python3
"""Keyword screen of DoD R-1 / P-1 budget exhibit spreadsheets for UAS and C-UAS lines.

Standard library only. Reads .xlsx files directly (they are zip archives of XML),
so there is no parsing dependency to pin.

Usage:
  # Fetch every source in sources.json to its local path, then screen it:
  python3 extract.py --fetch

  # Screen the committed copies under sources/ (checks pinned sha256 if set):
  python3 extract.py --local

  # Screen files you already downloaded (by hand, from a browser):
  python3 extract.py --input ~/Downloads/p1_display.xlsx=fy2026-p1 --input ~/Downloads/r1_display.xlsx=fy2026-r1

  # Screen an arbitrary file and say where it came from:
  python3 extract.py --input path.xlsx --source-url https://... --exhibit P-1 --out data/lines.json

Output: data/lines.json (see README for the schema). Amounts are copied exactly
as they appear in the exhibit (thousands of dollars). A cell that is not a plain
number is left out of the row and listed under "unreadable".
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

import analyze

ROOT = pathlib.Path(__file__).resolve().parent
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# ---------------------------------------------------------------------------
# Keyword list. Matching is case-insensitive against the line title (and any
# description column, if the exhibit has one). Each keyword has a category
# ("C-UAS" wins over "CCA", which wins over "UAS", when several match) and a tier.
# CCA (Collaborative Combat Aircraft) is a UAS program reported separately
# because a few large lines would otherwise dominate the UAS total:
#   core     - the agreed starting list
#   extended - wider terms and a platform watch list, added to catch titles the
#              core list misses (UAV, RPA, MQ-9...). Higher recall, more noise;
#              review these rows and use overrides.json to drop false hits.
# ---------------------------------------------------------------------------
KEYWORDS = [
    # (label, regex, category, tier)
    ("counter-UAS", r"\bcounter[\s-]*(?:small[\s-]*)?(?:s?UAS|unmanned)", "C-UAS", "core"),
    ("C-UAS", r"\bC[\s-]?s?UAS\b", "C-UAS", "core"),
    ("counter-small UAS", r"\bcounter[\s-]*small[\s-]*(?:UAS|unmanned)", "C-UAS", "core"),
    ("UAS", r"\bs?UAS\b", "UAS", "core"),
    ("unmanned aircraft", r"\bunmanned[\s-]+aircraft", "UAS", "core"),
    ("drone", r"\bdrones?\b", "UAS", "core"),
    ("loitering munition", r"\bloiter(?:ing)?[\s-]+munitions?\b", "UAS", "core"),
    ("Replicator", r"\breplicator\b", "UAS", "core"),
    # extended
    ("counter (abbrev.)", r"\b(?:ctr|cntr|counter)[\s-]*(?:sm(?:all)?[\s-]*)?(?:s?UAVs?\b|unman)", "C-UAS", "extended"),
    ("UAV", r"\bs?UAVs?\b", "UAS", "extended"),
    ("unmanned aerial", r"\bunmanned[\s-]+aerial", "UAS", "extended"),
    ("unmanned air (abbrev.)", r"\bunman(?:ned)?[\s-]+air\b", "UAS", "extended"),
    ("uncrewed", r"\buncrewed[\s-]+(?:aircraft|aerial|air)\b", "UAS", "extended"),
    ("RPA", r"\bRPAs?\b", "UAS", "extended"),
    ("collaborative combat aircraft", r"\bcollaborative[\s-]+combat[\s-]+aircraft", "CCA", "extended"),
    ("MQ-/RQ- designation", r"\b[MR]Q[\s-]?\d{1,2}[A-Z]?\b", "UAS", "extended"),
    ("platform name", r"\b(?:gr[ae]y[\s-]+eagle|global[\s-]+hawk|triton|reaper|stingray|switchblade)\b", "UAS", "extended"),
]
CATEGORY_PRECEDENCE = ("C-UAS", "CCA", "UAS")
_COMPILED = [(label, re.compile(rx, re.I), cat, tier) for label, rx, cat, tier in KEYWORDS]


def match_keywords(text: str) -> tuple[list[str], str | None, str | None]:
    """Return (matched labels, category, tier). tier is "core" if any core keyword hit."""
    hits, cats, tiers = [], set(), set()
    for label, rx, cat, tier in _COMPILED:
        if rx.search(text or ""):
            hits.append(label)
            cats.add(cat)
            tiers.add(tier)
    if not hits:
        return [], None, None
    category = next(c for c in CATEGORY_PRECEDENCE if c in cats)
    return hits, category, ("core" if "core" in tiers else "extended")


# ---------------------------------------------------------------------------
# Minimal xlsx reader (first worksheet, values only).
# ---------------------------------------------------------------------------
def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_xlsx_rows(path: pathlib.Path) -> list[list[object]]:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        # Resolve the first sheet through workbook.xml + rels (don't assume sheet1.xml).
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        first = wb.find("m:sheets/m:sheet", NS)
        rid = first.get(f"{{{REL_NS}}}id")
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == rid)
        target = target.lstrip("/")
        sheet_path = target if target.startswith("xl/") else "xl/" + target
        sheet = ET.fromstring(z.read(sheet_path))

    rows: list[list[object]] = []
    for r in sheet.iter(f"{{{NS['m']}}}row"):
        row: list[object] = []
        for c in r.findall("m:c", NS):
            idx = _col_index(c.get("r"))
            while len(row) < idx:
                row.append(None)
            t = c.get("t")
            v = c.find("m:v", NS)
            if t == "s" and v is not None:
                val: object = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
            elif t == "str":
                val = v.text if v is not None else None
            elif t == "b":
                val = v.text == "1" if v is not None else None
            elif v is not None and v.text is not None:
                try:
                    f = float(v.text)
                    val = int(f) if f.is_integer() else f
                except ValueError:
                    val = v.text
            else:
                val = None
            row.append(val)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Header detection. The R-1/P-1 "display" spreadsheets have one header row;
# its exact wording drifts year to year, so columns are found by pattern.
# ---------------------------------------------------------------------------
def _norm(s: object) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def find_header(rows: list[list[object]]) -> int:
    for i, row in enumerate(rows[:40]):
        cells = [_norm(c).lower() for c in row]
        if any(c == "account" or c.startswith("account ") for c in cells) and any("title" in c for c in cells):
            return i
    raise ValueError("could not find a header row containing 'Account' and a 'Title' column")


def map_columns(header: list[object]) -> dict:
    h = [_norm(c) for c in header]
    low = [c.lower() for c in h]

    def first(pred):
        for i, c in enumerate(low):
            if pred(c):
                return i
        return None

    cols = {
        "account": first(lambda c: c == "account"),
        "account_title": first(lambda c: c.startswith("account title")),
        "organization": first(lambda c: c.startswith("organization")),
        "budget_activity": first(lambda c: c == "budget activity"),
        "budget_activity_title": first(lambda c: c.startswith("budget activity title")),
        "line_number": first(lambda c: c.startswith("line number") or c == "line no" or c == "line"),
        # R-1: "Program Element/Budget Line Item (BLI)"; P-1: "Budget Line Item"
        "pe_or_bli": first(lambda c: c in ("pe/bli", "pe", "bli")
                           or (("program element" in c or "budget line item" in c) and "title" not in c)),
        "title": first(lambda c: ("program element" in c or "budget line item" in c) and "title" in c),
        "description": first(lambda c: "description" in c),
        "classification": first(lambda c: c.startswith("classification")),
        # P-1: one row per cost type; "Non-Add" rows are memo entries (e.g. multiyear EOQ) not in the line total.
        "cost_type_title": first(lambda c: c.startswith("cost type title")),
        "add_non_add": first(lambda c: c.replace(" ", "") == "add/non-add"),
        # R-1: "Include In TOA" = N marks lines outside DoD total obligational authority.
        "include_in_toa": first(lambda c: c.startswith("include in toa")),
    }
    amounts = []
    for i, c in enumerate(h):
        if re.search(r"\bFY\s?\d{4}\b", c, re.I) and not re.search(r"quantit|qty", c, re.I):
            # P-1 says "FY 2026 Total Amount", R-1 says "FY 2026 Total": use one label for both.
            amounts.append((i, re.sub(r"\s+Amount$", "", c, flags=re.I)))
    cols["amounts"] = amounts
    if cols["title"] is None:
        raise ValueError(f"no title column found in header: {h}")
    return cols


SERVICE_PATTERNS = [
    ("Space Force", r"space force"),
    ("Air Force", r"air force"),
    ("Navy", r"\bnavy\b"),  # before Marine Corps: "Procurement of Ammo, Navy & Marine Corps" is a Navy account
    ("Marine Corps", r"marine corps"),
    ("Army", r"\barmy\b"),
    ("Defense-Wide", r"defense[\s-]*wide|\bdefense\b|test\s*&\s*eval"),
]


def service_of(account_title: str) -> str:
    # Account titles end in the component, e.g. "Aircraft Procurement, Army".
    tail = account_title.rsplit(",", 1)[-1] if "," in account_title else account_title
    for name, rx in SERVICE_PATTERNS:
        if re.search(rx, tail, re.I):
            return name
    for name, rx in SERVICE_PATTERNS:
        if re.search(rx, account_title, re.I):
            return name
    return "Unknown"


def load_overrides(path: pathlib.Path | None) -> dict:
    """overrides.json: hand-reviewed decisions applied after the keyword screen.

    {"exclude": [{"exhibit": "R-1", "pe_or_bli": "0604123A", "account": "2040A", "reason": "..."}],
     "include": [{"exhibit": "P-1", "pe_or_bli": "1234", "category": "C-UAS", "reason": "..."}],
     "related_not_counted": {"lines": [{"exhibit": "R-1", "pe_or_bli": "0604117A", "group": "M-SHORAD", "reason": "..."}]}}
    "account" is optional; when given, the rule only applies to that appropriation code.
    "related_not_counted" lines are read with their amounts but kept out of rows[] and every total.
    """
    if not path or not path.exists():
        return {"exclude": [], "include": [], "related": []}
    d = json.loads(path.read_text())
    d["related"] = d.get("related_not_counted", {}).get("lines", [])
    for k in ("exclude", "include", "related"):
        d.setdefault(k, [])
        for r in d[k]:
            if not r.get("exhibit") or not r.get("pe_or_bli") or not r.get("reason"):
                raise ValueError(f"override needs exhibit, pe_or_bli and reason: {r}")
            if k == "include" and r.get("category", "UAS") not in CATEGORY_PRECEDENCE:
                raise ValueError(f"include category must be one of {CATEGORY_PRECEDENCE}: {r}")
            if k == "related" and not r.get("group"):
                raise ValueError(f"related_not_counted line needs a group: {r}")
    return d


def _rule_for(rules: list[dict], exhibit: str, pe: str, account: str) -> dict | None:
    for r in rules:
        if r["exhibit"] == exhibit and r["pe_or_bli"] == pe and (not r.get("account") or r["account"] == account):
            return r
    return None


def check_total_row(rows: list[list[object]], hi: int, cols: dict) -> dict:
    """Reconcile the exhibit's own "Total of Displayed Rows" against what we parsed.

    The Comptroller display sheets put a totals row above the header. If our cell
    reader dropped or misread anything, the column sums won't match. Raises on a
    mismatch; returns a summary if there's no totals row to check against.
    """
    total_row = next((r for r in rows[:hi] if any(_norm(c).lower() == "total of displayed rows" for c in r)), None)
    if total_row is None:
        return {"checked": False, "reason": "no 'Total of Displayed Rows' row found"}
    checked = []
    for i, label in cols["amounts"]:
        want = total_row[i] if i < len(total_row) else None
        if not isinstance(want, (int, float)):
            continue
        got = sum(r[i] for r in rows[hi + 1:] if i < len(r) and isinstance(r[i], (int, float)) and not isinstance(r[i], bool))
        if abs(got - want) > 0.5:
            raise ValueError(f"parsed sum of {label!r} is {got}, exhibit total row says {want}")
        checked.append({"column": label, "total_thousands": want})
    return {"checked": True, "columns": checked}


def screen(path: pathlib.Path, source: dict, overrides: dict | None = None):
    """Return (rows, unreadable, excluded, total_check, related) for one exhibit file."""
    overrides = overrides or {"exclude": [], "include": [], "related": []}
    overrides.setdefault("related", [])
    rows = read_xlsx_rows(path)
    hi = find_header(rows)
    cols = map_columns(rows[hi])
    total_check = check_total_row(rows, hi, cols)
    out, unreadable, excluded, related = [], [], [], []
    exhibit = source.get("exhibit", "")

    def get(row, key):
        i = cols.get(key)
        return _norm(row[i]) if i is not None and i < len(row) and row[i] is not None else ""

    for n, row in enumerate(rows[hi + 1:], start=hi + 2):
        title = get(row, "title")
        if not title:
            continue
        pe, account = get(row, "pe_or_bli"), get(row, "account")
        hits, category, tier = match_keywords(title + " " + get(row, "description"))
        inc = _rule_for(overrides["include"], exhibit, pe, account)
        rel = _rule_for(overrides["related"], exhibit, pe, account)
        if rel and (hits or inc):
            raise ValueError(f"{exhibit} {pe} is both a counted line and related_not_counted: {rel}")
        if not hits and not inc and not rel:
            continue
        exc = _rule_for(overrides["exclude"], exhibit, pe, account)
        rid = f"{source['id']}:r{n}"
        if exc:
            excluded.append({"id": rid, "exhibit": exhibit, "pe_or_bli": pe, "title": title, "matched_keywords": hits,
                             "reason": exc["reason"]})
            continue
        if inc and not hits:
            category, tier = inc.get("category", "UAS"), "override"
        amounts, bad = {}, []
        for i, label in cols["amounts"]:
            v = row[i] if i < len(row) else None
            if v is None or v == "":
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                amounts[label] = v
            else:
                bad.append({"column": label, "raw": str(v)})
        account_title = get(row, "account_title")
        add_flag, toa = get(row, "add_non_add"), get(row, "include_in_toa")
        rec = {
            "id": rid,
            "exhibit": exhibit,
            "fiscal_year": source.get("fiscal_year"),
            "line_number": get(row, "line_number"),
            "pe_or_bli": pe,
            "title": title,
            "service": service_of(account_title),
            "organization": get(row, "organization"),
            "appropriation": " ".join(x for x in [account, account_title] if x),
            "budget_activity": " ".join(x for x in [get(row, "budget_activity"), get(row, "budget_activity_title")] if x),
            "classification": get(row, "classification"),
            "cost_type": get(row, "cost_type_title"),
            "add_non_add": add_flag,
            "include_in_toa": toa,
            "counts_in_total": add_flag.lower() != "non-add" and toa.upper() != "N",
            "category": category,
            "match_tier": tier,
            "matched_keywords": hits,
            "override_reason": inc["reason"] if inc and not hits else None,
            "amounts_thousands": amounts,
            "source_url": source["url"],
            "source_row": n,
        }
        for b in bad:
            unreadable.append({"id": rid, **b})
        if rel:
            rec.update(category=None, match_tier="related", group=rel["group"], related_reason=rel["reason"])
            related.append(rec)
            continue
        out.append(rec)
    return out, unreadable, excluded, total_check, related


def check_sha256sums(path: pathlib.Path) -> None:
    """If the file's folder has a SHA256SUMS ("<sha>  <file>  [url]", '#' comments), verify it."""
    sums = path.parent / "SHA256SUMS"
    if not sums.exists():
        return
    for line in sums.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and pathlib.Path(parts[1]).name == path.name:
            if sha256(path) != parts[0]:
                raise ValueError(f"{path} does not match {sums}")
            return


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(url: str, dest: pathlib.Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "jbooks-explorer/0.1 (research script)"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", default=str(ROOT / "sources.json"))
    ap.add_argument("--fetch", action="store_true",
                    help="download every source in sources.json to its 'local' path, then screen it")
    ap.add_argument("--local", action="store_true",
                    help="screen the already-downloaded files at each source's 'local' path")
    ap.add_argument("--input", action="append", default=[],
                    help="local .xlsx, optionally as PATH=SOURCE_ID to borrow that source's URL/exhibit")
    ap.add_argument("--source-url", help="source URL for a bare --input (required if no SOURCE_ID)")
    ap.add_argument("--exhibit", default="", help="exhibit label for a bare --input, e.g. R-1 or P-1")
    ap.add_argument("--fiscal-year", type=int)
    ap.add_argument("--status", default="live", help="dataset status written to the output (live|synthetic)")
    ap.add_argument("--overrides", default=str(ROOT / "overrides.json"),
                    help="hand-reviewed include/exclude rules (default: overrides.json)")
    ap.add_argument("--out", default=str(ROOT / "data" / "lines.json"))
    ap.add_argument("--changes", help="where to write the FY25->FY26 change view "
                    "(default: changes.json next to --out, for live data)")
    a = ap.parse_args(argv)

    cfg = json.loads(pathlib.Path(a.sources).read_text())
    by_id = {s["id"]: s for s in cfg["sources"]}
    jobs: list[tuple[pathlib.Path, dict]] = []

    if a.fetch or a.local:
        for s in cfg["sources"]:
            dest = ROOT / s["local"]
            if a.fetch:
                print(f"fetching {s['url']}", file=sys.stderr)
                fetch(s["url"], dest)
            elif not dest.exists():
                ap.error(f"{dest} is missing: run with --fetch, or download {s['url']} there")
            if s.get("sha256") and sha256(dest) != s["sha256"]:
                ap.error(f"{dest} does not match the sha256 pinned in sources.json")
            check_sha256sums(dest)
            jobs.append((dest, s))
    for spec in a.input:
        path, _, sid = spec.partition("=")
        if sid:
            if sid not in by_id:
                ap.error(f"unknown source id {sid!r}")
            jobs.append((pathlib.Path(path), by_id[sid]))
        else:
            if not a.source_url:
                ap.error("--source-url is required for an --input without =SOURCE_ID")
            jobs.append((pathlib.Path(path), {"id": pathlib.Path(path).stem, "exhibit": a.exhibit,
                                              "fiscal_year": a.fiscal_year, "url": a.source_url}))
    if not jobs:
        ap.error("nothing to do: pass --fetch or --input")

    ov_path = pathlib.Path(a.overrides) if a.overrides else None
    overrides = load_overrides(ov_path)
    rows, unreadable, excluded, used, related = [], [], [], [], []
    for path, s in jobs:
        r, u, x, tc, rel = screen(path, s, overrides)
        related += rel
        rows += r
        unreadable += u
        excluded += x
        used.append({"id": s["id"], "exhibit": s.get("exhibit"), "fiscal_year": s.get("fiscal_year"),
                     "url": s["url"], "url_status": s.get("url_status"), "sha256": sha256(path), "lines_matched": len(r),
                     "lines_excluded": len(x), "total_row_check": tc})
        print(f"{s['id']}: {len(r)} lines kept, {len(x)} excluded by overrides", file=sys.stderr)

    # A rule that matches nothing is almost always a typo (wrong code or account): fail loudly.
    exhibits_run = {s.get("exhibit") for _, s in jobs}
    hit = {(r["exhibit"], r["pe_or_bli"]) for r in rows} | {(x["exhibit"], x["pe_or_bli"]) for x in excluded}
    for kind in ("include", "exclude"):
        for rule in overrides[kind]:
            if rule["exhibit"] in exhibits_run and (rule["exhibit"], rule["pe_or_bli"]) not in hit:
                ap.error(f"{kind} rule matched no line: {rule}")
            if kind == "exclude" and rule["exhibit"] in exhibits_run and not any(
                    x["exhibit"] == rule["exhibit"] and x["pe_or_bli"] == rule["pe_or_bli"] for x in excluded):
                ap.error(f"exclude rule matched no line: {rule}")

    rel_hit = {(r["exhibit"], r["pe_or_bli"]) for r in related}
    for rule in overrides["related"]:
        if rule["exhibit"] in exhibits_run and (rule["exhibit"], rule["pe_or_bli"]) not in rel_hit:
            ap.error(f"related_not_counted line matched nothing: {rule}")

    doc = {
        "status": a.status,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "units": "thousands of US dollars, as printed in the exhibit",
        "method": "case-insensitive keyword screen of line titles, then hand-reviewed overrides; see README",
        "keywords": [{"label": l, "regex": rx, "category": c, "tier": t} for l, rx, c, t in KEYWORDS],
        "overrides_file": str(ov_path.relative_to(ROOT)) if ov_path and ov_path.exists() and ov_path.is_relative_to(ROOT) else None,
        "excluded": excluded,
        "sources": used,
        "unreadable": unreadable,
        "rows": rows,
        "related_not_counted": related,
    }
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"wrote {len(rows)} rows to {out}", file=sys.stderr)
    if a.status == "live" or a.changes:
        changes_out = pathlib.Path(a.changes) if a.changes else out.with_name("changes.json")
        changes_out.write_text(json.dumps(analyze.build(doc), indent=1) + "\n")
        print(f"wrote FY25->FY26 change view to {changes_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
