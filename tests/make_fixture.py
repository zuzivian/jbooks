#!/usr/bin/env python3
"""Write tests/fixtures/synthetic_r1.xlsx and synthetic_p1.xlsx.

These are SYNTHETIC files. They copy the column layout of the Comptroller's
R-1 / P-1 "display" spreadsheets so the extractor can be tested, but every
title, line number, PE/BLI code and dollar figure is made up. They are not
budget data. PE/BLI codes start with "TEST" so they can't be mistaken for
real ones.
"""
import pathlib
import zipfile
from xml.sax.saxutils import escape

HERE = pathlib.Path(__file__).resolve().parent / "fixtures"

R1_HEADER = ["Account", "Account Title", "Organization", "Budget Activity", "Budget Activity Title",
             "Line Number", "Program Element/Budget Line Item (BLI)", "Program Element/Budget Line Item (BLI) Title",
             "Classification", "FY 2024 Actuals", "FY 2025 Enacted", "FY 2026 Disc Request",
             "FY 2026 Reconciliation Request", "FY 2026 Total"]
R1_ROWS = [
    ["2040A", "Research, Development, Test & Eval, Army", "A", "04", "Advanced Component Development & Prototypes",
     "1", "TEST0001A", "Synthetic Counter-Small UAS Prototype", "U", 1000, 2000, 3000, 0, 3000],
    ["2040A", "Research, Development, Test & Eval, Army", "A", "05", "System Development & Demonstration",
     "2", "TEST0002A", "Synthetic Tactical Radio", "U", 500, 500, 500, 0, 500],
    ["1319N", "Research, Development, Test & Eval, Navy", "N", "04", "Advanced Component Development & Prototypes",
     "3", "TEST0003N", "Synthetic Unmanned Aircraft Systems", "U", 4000, 4500, 5000, 1000, 6000],
    ["3600F", "Research, Development, Test & Eval, Air Force", "F", "07", "Operational System Development",
     "4", "TEST0004F", "Synthetic Drone Swarm Experiment", "U", 0, 100, "see note", 0, 250],
    ["0400D", "Research, Development, Test & Eval, Defense-Wide", "D", "03", "Advanced Technology Development",
     "5", "TEST0005D", "Synthetic Replicator Initiative", "U", 7000, 8000, 9000, 0, 9000],
    ["0400D", "Research, Development, Test & Eval, Defense-Wide", "D", "03", "Advanced Technology Development",
     "6", "TEST0006D", "Synthetic Pivot Table Study (must NOT match: 'guas', 'casual')", "U", 1, 1, 1, 0, 1],
]
P1_HEADER = ["Account", "Account Title", "Organization", "Budget Activity", "Budget Activity Title",
             "Line Number", "Budget Line Item", "Budget Line Item (BLI) Title", "Classification",
             "FY 2024 Quantity", "FY 2024 Actuals", "FY 2025 Quantity", "FY 2025 Enacted",
             "FY 2026 Disc Request Quantity", "FY 2026 Disc Request", "FY 2026 Total"]
P1_ROWS = [
    ["2035A", "Other Procurement, Army", "A", "02", "Communications and Electronics Equipment",
     "10", "TEST1001A", "Synthetic C-sUAS Interceptors", "U", 10, 1200, 12, 1300, 14, 1400, 1400],
    ["1508N", "Procurement of Ammo, Navy & Marine Corps", "N", "01", "Proc Ammo, Navy",
     "11", "TEST1002N", "Synthetic Loitering Munitions, Marine Corps", "U", None, 300, None, 350, None, 400, 400],
    ["3010F", "Aircraft Procurement, Air Force", "F", "05", "Other Aircraft",
     "12", "TEST1003F", "Synthetic Trainer Aircraft", "U", 2, 9000, 2, 9000, 2, 9000, 9000],
]


def col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, header, rows):
    strings, index = [], {}

    def sid(s):
        if s not in index:
            index[s] = len(strings)
            strings.append(s)
        return index[s]

    xml_rows = []
    # Two banner rows above the header, as the real exhibits have.
    all_rows = [["Department of Defense Budget (SYNTHETIC TEST FIXTURE)"], [], header] + rows
    for r, row in enumerate(all_rows, start=1):
        cells = []
        for c, v in enumerate(row):
            ref = f"{col(c)}{r}"
            if v is None:
                continue
            if isinstance(v, (int, float)):
                cells.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="s"><v>{sid(str(v))}</v></c>')
        xml_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    files = {
        "[Content_Types].xml": '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/data.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>",
        "_rels/.rels": '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>",
        "xl/workbook.xml": f'<?xml version="1.0"?><workbook xmlns="{main}" xmlns:r="{rel}"><sheets>'
        '<sheet name="Exhibit" sheetId="1" r:id="rId7"/></sheets></workbook>',
        # Deliberately not "sheet1.xml" to exercise the rels lookup.
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId7" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/data.xml"/>'
        '<Relationship Id="rId8" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        "</Relationships>",
        "xl/worksheets/data.xml": f'<?xml version="1.0"?><worksheet xmlns="{main}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>',
        "xl/sharedStrings.xml": f'<?xml version="1.0"?><sst xmlns="{main}" count="{len(strings)}" uniqueCount="{len(strings)}">'
        + "".join(f"<si><t>{escape(s)}</t></si>" for s in strings) + "</sst>",
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))  # stable bytes
            z.writestr(info, body)


if __name__ == "__main__":
    HERE.mkdir(parents=True, exist_ok=True)
    write_xlsx(HERE / "synthetic_r1.xlsx", R1_HEADER, R1_ROWS)
    write_xlsx(HERE / "synthetic_p1.xlsx", P1_HEADER, P1_ROWS)
    print("wrote", HERE / "synthetic_r1.xlsx", HERE / "synthetic_p1.xlsx")
