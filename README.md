# J-books Explorer

A research tool that pulls drone (UAS) and counter-UAS (C-UAS) budget lines out of the Department of Defense's budget exhibits into one searchable, filterable page. Every row links back to the file it came from.

> **Caveat.** This is a keyword screen of line titles, not an official tally of UAS or C-UAS spending. It misses money buried inside broader lines. It counts a mixed line at its full value. Use it to find lines, then read the J-book.

## Status (slice 1)

- `extract.py` reads the Comptroller's R-1 (RDT&E) and P-1 (Procurement) exhibit spreadsheets and writes `data/lines.json`.
- `index.html` is a static viewer with search, service and category filters, a choice of amount column, and sort by amount.
- **`data/lines.json` has no live rows yet.** The sandbox this was built in couldn't reach the DoD hosts (`comptroller.war.gov` and `comptroller.defense.gov`; the egress proxy answered 403 to CONNECT). The extractor has only been run end to end against synthetic fixtures. To fill the file, run `python3 extract.py --fetch` on a normal machine.
- `data/sample.json` is **synthetic** output from `tests/fixtures/`. Its PE/BLI codes start with `TEST` and its dollar figures are made up. The viewer shows it only behind a red "Synthetic demo data" banner (`index.html?demo=1`).

## Source

For slice 1 the source is the Comptroller's machine-readable exhibit spreadsheets for the FY2026 President's Budget, listed in `sources.json`:

| Exhibit | File | Status |
|---|---|---|
| P-1 Procurement | `https://comptroller.war.gov/Portals/45/Documents/defbudget/FY2026/p1_display.xlsx` | Listed in the FY2026 folder by web search; not downloaded from the sandbox |
| R-1 RDT&E | `https://comptroller.war.gov/Portals/45/Documents/defbudget/FY2026/r1_display.xlsx` | **Unverified**: inferred from the P-1 filename. Confirm it on the index page |

Index page: <https://comptroller.war.gov/Budget-Materials/Budget2026/>. The PDF versions (`FY2026_r1.pdf`, `FY2026_p1.pdf`) and the service J-books sit under the same folder. In 2025 the site moved from `comptroller.defense.gov` to `comptroller.war.gov`.

Why these files: R-1 and P-1 are the department-wide line-item lists that sit on top of the service J-books. Each R-1 line is a program element (PE); each P-1 line is a budget line item (BLI). They come as spreadsheets, so slice 1 needs no PDF scraping. The trade-off is that they carry titles only. The narrative descriptions are in the J-book PDFs.

## Method

1. For each source, read the first worksheet of the `.xlsx`. The reader uses only the standard library (`zipfile` plus `xml.etree`), so there is no dependency to pin.
2. Find the header row: the first row with an `Account` cell and a `…Title` cell. Map the columns by pattern, because the wording drifts from year to year. A column counts as an amount column if its header contains `FY yyyy` and doesn't mention quantity.
3. Keep a line if its PE/BLI title, or its description column where one exists, matches any keyword below.
4. Take the service from the end of the appropriation title, for example "Aircraft Procurement, **Army**". `Procurement of Ammo, Navy & Marine Corps` counts as Navy.
5. Copy amounts exactly as printed, in **thousands of dollars**. A cell that isn't a plain number is left out of the row and logged under `unreadable`.
6. Record each source file's URL and SHA-256 hash, and put the source URL and row number on every line.

### Keyword list

Matching ignores case. A line is tagged **C-UAS** if any counter keyword matches; otherwise it's tagged **UAS**.

| Keyword | Regex | Category |
|---|---|---|
| counter-UAS | `\bcounter[\s-]*(?:small[\s-]*)?(?:s?UAS\|unmanned)` | C-UAS |
| C-UAS | `\bC[\s-]?s?UAS\b` | C-UAS |
| counter-small UAS | `\bcounter[\s-]*small[\s-]*(?:UAS\|unmanned)` | C-UAS |
| UAS | `\bs?UAS\b` | UAS |
| unmanned aircraft | `\bunmanned[\s-]+aircraft` | UAS |
| drone | `\bdrones?\b` | UAS |
| loitering munition | `\bloiter(?:ing)?[\s-]+munitions?\b` | UAS |
| Replicator | `\breplicator\b` | UAS |

### Known misses

- **UAV, "unmanned aerial", RPA, "uncrewed"** don't match. The list was kept to the agreed starting set, and adding these is decision 1 below.
- **Platform-only titles** don't match, for example MQ-9 Reaper, RQ-4, MQ-25, MQ-4C or Gray Eagle. A platform watch list would catch them.
- **Buried money**: UAS work inside a broad line, such as an Army "Aircraft Spares" line or a counter-air-defence PE, is invisible at line level.
- **Classified lines** appear in the exhibits as aggregates or not at all.
- **Abbreviations**: J-book titles are truncated in uppercase, for example "CTR SM UNMAN AIR SYS". Abbreviations like that are missed.
- **Possible false positives**: "UAS" matches as a whole word, so an unrelated acronym spelled UAS would match. Each row shows its matched keywords so you can check.

## Refresh the data

```sh
python3 extract.py --fetch                # downloads into raw/ (gitignored), writes data/lines.json
# or, with files you downloaded in a browser:
python3 extract.py --input ~/Downloads/p1_display.xlsx=fy2026-p1 --input ~/Downloads/r1_display.xlsx=fy2026-r1
```

To add a budget year, add entries to `sources.json` and copy the URLs from the Comptroller index page. After any run, compare the `lines_matched` counts in `data/lines.json` against the totals on the PDF exhibit before trusting them.

## View it

```sh
python3 -m http.server 8000   # then open http://localhost:8000  (add ?demo=1 for the synthetic sample)
```

Browsers block `fetch()` from `file://`, so serve the folder over HTTP. Any static host works, including GitHub Pages and Vercel.

## Tests

```sh
python3 tests/make_fixture.py           # regenerates the synthetic .xlsx fixtures
python3 -m unittest discover -s tests
```

## Data schema (`data/lines.json`)

`status` (`live` | `synthetic` | `not_fetched`), `generated_at`, `units`, `keywords[]`, `sources[]` (`id`, `exhibit`, `fiscal_year`, `url`, `sha256`, `lines_matched`), `unreadable[]`, and `rows[]` with:

`id`, `exhibit`, `fiscal_year`, `line_number`, `pe_or_bli`, `title`, `service`, `organization`, `appropriation`, `budget_activity`, `classification`, `category`, `matched_keywords[]`, `amounts_thousands{column → number}`, `source_url`, `source_row`.
