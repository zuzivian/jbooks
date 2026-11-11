import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import analyze  # noqa: E402
import extract  # noqa: E402


def row(pe, fy25=None, fy26=None, recon=None, cat="UAS", svc="Army", exhibit="R-1", counts=True, n=1, approp="2040A X"):
    a = {}
    if fy25 is not None:
        a["FY 2025 Enacted"] = fy25
    if fy26 is not None:
        a["FY 2026 Total"] = fy26
    if recon is not None:
        a["FY 2026 Reconciliation Request"] = recon
    return {"exhibit": exhibit, "pe_or_bli": pe, "title": "T " + pe, "service": svc, "category": cat,
            "appropriation": approp, "source_url": "x.xlsx", "source_row": n, "counts_in_total": counts,
            "amounts_thousands": a}


class DeltaMath(unittest.TestCase):
    def test_change(self):
        self.assertEqual(analyze.change(100, 150), {"change": 50, "pct": 50.0, "status": "continuing"})
        self.assertEqual(analyze.change(200, 50), {"change": -150, "pct": -75.0, "status": "continuing"})
        self.assertEqual(analyze.change(0, 80), {"change": 80, "pct": None, "status": "new in FY26"})
        self.assertEqual(analyze.change(80, 0), {"change": -80, "pct": -100.0, "status": "no FY26 request"})
        self.assertEqual(analyze.change(0, 0), {"change": 0, "pct": None, "status": "neither year"})
        self.assertEqual(analyze.change(3, 4)["pct"], 33.3)  # rounded to one decimal

    def test_aggregate_sums_cost_types_and_skips_memo_rows(self):
        rows = [row("0449", 61979, 507046, exhibit="P-1", n=1),
                row("0449", -11979, None, exhibit="P-1", n=2),           # less: advance procurement (PY)
                row("0449", None, 52191, exhibit="P-1", n=3),            # advance procurement (CY)
                row("0449", None, 52191, exhibit="P-1", n=4, counts=False)]  # non-add memo row
        [ln] = analyze.aggregate_lines(rows)
        self.assertEqual((ln["fy25"], ln["fy26"], ln["change"]), (50000, 559237, 509237))
        self.assertEqual(ln["source_rows"], [1, 2, 3, 4])

    def test_lines_keyed_by_exhibit_code_and_appropriation(self):
        rows = [row("A", 10, 20), row("A", 5, 5, exhibit="P-1"), row("A", 1, 1, approp="3600F Y")]
        self.assertEqual(len(analyze.aggregate_lines(rows)), 3)

    def test_totals_and_cca_split(self):
        rows = [row("U", 100, 150), row("C", 50, 60, cat="C-UAS", svc="Navy"),
                row("K", 0, 300, recon=200, cat="CCA", svc="Air Force")]
        doc = {"rows": rows, "generated_at": "t"}
        ch = analyze.build(doc)
        self.assertEqual(ch["totals"]["all"], {"fy25": 150, "fy26": 510, "fy26_recon": 200, "lines": 3,
                                               "change": 360, "pct": 240.0})
        self.assertEqual(ch["totals"]["excluding_cca"]["fy26"], 210)
        self.assertEqual([c["name"] for c in ch["by_category"]], ["UAS", "C-UAS", "CCA"])
        self.assertEqual([s["name"] for s in ch["by_service"]], ["Army", "Navy", "Air Force"])
        self.assertEqual(sum(s["change"] for s in ch["by_service"]), ch["totals"]["all"]["change"])

    def test_movers(self):
        lines = analyze.aggregate_lines([row(str(i), 100, 100 + d) for i, d in enumerate(range(-15, 16))])
        m = analyze.movers(lines, n=10)
        self.assertEqual([x["change"] for x in m["up"]], list(range(15, 5, -1)))
        self.assertEqual([x["change"] for x in m["down"]], list(range(-15, -5)))
        self.assertTrue(all(x["change"] != 0 for x in m["up"] + m["down"]))

    def test_related_lines_never_counted(self):
        doc = {"rows": [row("U", 10, 20)], "related_not_counted": [dict(row("M", 1000, 2000), group="g", related_reason="r")]}
        ch = analyze.build(doc)
        self.assertEqual(ch["totals"]["all"]["fy26"], 20)
        self.assertEqual(ch["related_not_counted"][0]["fy26"], 2000)
        self.assertEqual(ch["related_not_counted"][0]["group"], "g")

    def test_money(self):
        self.assertEqual(analyze.money(5324096), "$5,324.1M")
        self.assertEqual(analyze.money(-35595), "-$35.6M")


class LiveData(unittest.TestCase):
    """The committed FY2026 data: figures in the README and the change view must agree."""

    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((ROOT / "data" / "lines.json").read_text())
        cls.ch = json.loads((ROOT / "data" / "changes.json").read_text())

    def test_changes_json_is_fresh(self):
        self.assertEqual(analyze.main(["--check"]), 0)
        self.assertEqual(self.ch["lines_generated_at"], self.doc["generated_at"])

    def test_headline_totals(self):
        t = self.ch["totals"]["all"]
        self.assertEqual((t["lines"], t["fy25"], t["fy26"]), (66, 4310277, 5324096))
        cat = {c["name"]: c for c in self.ch["by_category"]}
        self.assertEqual(sum(c["fy26"] for c in cat.values()), t["fy26"])
        self.assertEqual(self.ch["totals"]["excluding_cca"]["fy26"], t["fy26"] - cat["CCA"]["fy26"])

    def test_cca_lines(self):
        cca = sorted(x["pe_or_bli"] for x in self.ch["lines"] if x["category"] == "CCA")
        self.assertEqual(cca, ["0207147F", "0207147M", "CCA00M"])

    def test_related_lines_disjoint_from_counted(self):
        counted = {analyze.line_key(r) for r in self.doc["rows"]}
        rel = self.ch["related_not_counted"]
        self.assertGreaterEqual(len(rel), 10)
        self.assertFalse(counted & {(x["exhibit"], x["pe_or_bli"], x["appropriation"]) for x in rel})
        self.assertTrue(all(x["related_reason"] and x["group"] for x in rel))

    def test_every_finding_figure_is_on_the_page(self):
        ch = self.ch
        shown = set()
        groups = [ch["totals"]["all"], ch["totals"]["excluding_cca"]] + ch["by_service"] + ch["by_category"] + ch["lines"]
        for g in groups:
            for k in ("fy25", "fy26", "change", "fy26_recon"):
                shown.add(analyze.money(abs(g[k])))
        new = [x for x in ch["lines"] if x["status"] == "new in FY26"]
        ended = [x for x in ch["lines"] if x["status"] == "no FY26 request"]
        shown.add(analyze.money(sum(x["fy26"] for x in new)))
        shown.add(analyze.money(sum(x["fy25"] for x in ended)))
        self.assertTrue(3 <= len(ch["findings"]) <= 5)
        for f in ch["findings"]:
            for m in re.findall(r"\$[\d,]+\.\dM", f):
                self.assertIn(m, shown, f)

    def test_keyword_category(self):
        self.assertEqual(extract.match_keywords("Collaborative Combat Aircraft Mods")[1], "CCA")
        self.assertEqual(extract.match_keywords("Counter-UAS for Collaborative Combat Aircraft")[1], "C-UAS")


if __name__ == "__main__":
    unittest.main()
