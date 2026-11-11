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
        for s in ["Guasave Study", "Casual Pay", "Tactical Radio", "Unmanned Surface Vessel", "MQ-9 UAV"]:
            self.assertIsNone(self.cat(s), s)

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
                      "--status", "synthetic", "--out", str(out)])
        return json.loads(out.read_text())

    def test_rows(self):
        d = self.run_extract()
        titles = {r["title"] for r in d["rows"]}
        self.assertEqual(len(d["rows"]), 6, titles)
        self.assertNotIn("Synthetic Tactical Radio", titles)
        self.assertTrue(all(r["source_url"] for r in d["rows"]))

    def test_amounts_and_unreadable(self):
        d = self.run_extract()
        drone = next(r for r in d["rows"] if "Drone" in r["title"])
        self.assertNotIn("FY 2026 Disc Request", drone["amounts_thousands"])
        self.assertEqual(drone["amounts_thousands"]["FY 2026 Total"], 250)
        self.assertEqual(d["unreadable"][0]["raw"], "see note")
        p1 = next(r for r in d["rows"] if "C-sUAS" in r["title"])
        self.assertNotIn("FY 2024 Quantity", p1["amounts_thousands"])
        self.assertEqual(p1["pe_or_bli"], "TEST1001A")
        self.assertEqual(p1["service"], "Army")
        self.assertEqual(p1["exhibit"], "P-1")
        self.assertEqual(p1["source_url"], "tests/fixtures/synthetic_p1.xlsx")


if __name__ == "__main__":
    unittest.main()
