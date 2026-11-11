import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import extract  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


class KeywordTests(unittest.TestCase):
    def cat(self, s):
        return extract.match_keywords(s)[1]

    def tier(self, s):
        return extract.match_keywords(s)[2]

    def test_positive(self):
        for s, c in [
            ("Counter-Small UAS Prototype", "C-UAS"),
            ("C-sUAS Interceptors", "C-UAS"),
            ("COUNTER SMALL UNMANNED AIRCRAFT SYS", "C-UAS"),
            ("Counter-UAS Systems", "C-UAS"),
            ("Unmanned Aircraft Systems", "UAS"),
            ("SMALL UAS", "UAS"),
            ("Drone Swarm", "UAS"),
            ("Loitering Munitions", "UAS"),
            ("Replicator Initiative", "UAS"),
        ]:
            self.assertEqual(self.cat(s), c, s)

    def test_negative(self):
        for s in ["Guasave Study", "Casual Pay", "Tactical Radio", "Unmanned Surface Vessel", "Squadron Ops",
                  "Torque Wrench", "Grasp Program"]:
            self.assertIsNone(self.cat(s), s)

    def test_tiers(self):
        self.assertEqual(self.tier("SMALL UAS"), "core")
        self.assertEqual(self.tier("Counter-UAS and UAV support"), "core")
        for s, c in [("MQ-9 UAV", "UAS"), ("RQ-4 Global Hawk", "UAS"), ("Unmanned Aerial Vehicle", "UAS"),
                     ("CTR SM UNMAN AIR SYS", "C-UAS"), ("Collaborative Combat Aircraft", "CCA"),
                     ("MQ-25 Stingray", "UAS"), ("Uncrewed Aircraft", "UAS"), ("RPA Training", "UAS")]:
            self.assertEqual((self.cat(s), self.tier(s)), (c, "extended"), s)

    def test_service(self):
        self.assertEqual(extract.service_of("Procurement of Ammo, Navy & Marine Corps"), "Navy")
        self.assertEqual(extract.service_of("Procurement, Marine Corps"), "Marine Corps")
        self.assertEqual(extract.service_of("Research, Development, Test & Eval, Defense-Wide"), "Defense-Wide")
        self.assertEqual(extract.service_of("Missile Procurement, Space Force"), "Space Force")


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT / "tests" / "make_fixture.py")], check=True, capture_output=True)

    def run_extract(self):
        out = pathlib.Path(tempfile.mkdtemp()) / "out.json"
        extract.main(["--sources", str(FIX / "sources.json"),
                      "--input", f"{FIX / 'synthetic_r1.xlsx'}=synthetic-r1",
                      "--input", f"{FIX / 'synthetic_p1.xlsx'}=synthetic-p1",
                      "--overrides", str(FIX / "overrides.json"),
                      "--status", "synthetic", "--out", str(out)])
        return json.loads(out.read_text())

    def test_rows(self):
        d = self.run_extract()
        titles = {r["title"] for r in d["rows"]}
        # 7 keyword hits (6 core + 1 extended), minus 1 excluded, plus 1 included = 7
        self.assertEqual(len(d["rows"]), 7, titles)
        self.assertIn("Synthetic Tactical Radio", titles)          # forced in by override
        self.assertNotIn("Synthetic Drone Swarm Experiment", titles)  # dropped by override
        self.assertEqual(d["excluded"][0]["pe_or_bli"], "TEST0004F")
        radio = next(r for r in d["rows"] if r["pe_or_bli"] == "TEST0002A")
        self.assertEqual((radio["match_tier"], radio["category"]), ("override", "C-UAS"))
        self.assertEqual(next(r for r in d["rows"] if r["pe_or_bli"] == "TEST0007F")["match_tier"], "extended")
        self.assertTrue(all(r["source_url"] for r in d["rows"]))

    def test_amounts_and_unreadable(self):
        d = self.run_extract()
        out = pathlib.Path(tempfile.mkdtemp()) / "out.json"
        extract.main(["--sources", str(FIX / "sources.json"), "--overrides", "",
                      "--input", f"{FIX / 'synthetic_r1.xlsx'}=synthetic-r1", "--out", str(out)])
        drone = next(r for r in json.loads(out.read_text())["rows"] if "Drone" in r["title"])
        self.assertNotIn("FY 2026 Disc Request", drone["amounts_thousands"])
        self.assertEqual(drone["amounts_thousands"]["FY 2026 Total"], 250)
        self.assertEqual(json.loads(out.read_text())["unreadable"][0]["raw"], "see note")
        p1 = next(r for r in d["rows"] if "C-sUAS" in r["title"])
        self.assertNotIn("FY 2024 Quantity", p1["amounts_thousands"])
        self.assertEqual(p1["pe_or_bli"], "TEST1001A")
        self.assertEqual(p1["service"], "Army")
        self.assertEqual(p1["exhibit"], "P-1")
        self.assertEqual(p1["source_url"], "tests/fixtures/synthetic_p1.xlsx")


if __name__ == "__main__":
    unittest.main()


class OverrideValidation(unittest.TestCase):
    def test_reason_required(self):
        p = pathlib.Path(tempfile.mkdtemp()) / "o.json"
        p.write_text(json.dumps({"exclude": [{"exhibit": "R-1", "pe_or_bli": "X"}]}))
        with self.assertRaises(ValueError):
            extract.load_overrides(p)


class RealLayout(unittest.TestCase):
    """Header and totals-row shapes seen in the FY2026 Comptroller files."""

    R1_HDR = ["Account", "Account Title", "Organization", "Budget Activity", "Budget Activity Title", "Line Number",
              "PE/BLI", "Program Element/Budget Line Item (BLI) Title", "Include In TOA", "FY 2026 Total", "Classification"]
    P1_HDR = ["Account", "Account Title", "Organization", "Budget Activity", "Budget Activity Title", "Line Number",
              "BSA", "Budget SubActivity (BSA) Title", "Budget Line Item", "Budget Line Item (BLI) Title", "Cost Type",
              "Cost Type Title", "Add/Non-Add", "FY 2026 Total Quantity", "FY 2026 Total Amount", "Classification"]

    def test_header_mapping(self):
        r1 = extract.map_columns(self.R1_HDR)
        self.assertEqual((r1["pe_or_bli"], r1["include_in_toa"]), (6, 8))
        p1 = extract.map_columns(self.P1_HDR)
        self.assertEqual((p1["pe_or_bli"], p1["title"], p1["add_non_add"]), (8, 9, 12))
        self.assertEqual(p1["amounts"], [(14, "FY 2026 Total")])  # quantity dropped, "Amount" normalised

    def test_total_row_check(self):
        cols = extract.map_columns(self.R1_HDR)
        tot = [None] * 6 + ["Total of Displayed Rows", None, None, 30, None]
        data = [["x"] * 9 + [10, "U"], ["x"] * 9 + [20, "U"]]
        self.assertTrue(extract.check_total_row([tot, self.R1_HDR] + data, 1, cols)["checked"])
        tot[9] = 31
        with self.assertRaises(ValueError):
            extract.check_total_row([tot, self.R1_HDR] + data, 1, cols)
