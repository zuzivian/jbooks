# J-books Explorer

A research tool that pulls drone (UAS) and counter-UAS (C-UAS) budget lines out of the Department of Defense's budget exhibits into one searchable, filterable page. Every row links back to the file it came from.

> **Caveat.** This is a keyword screen of line titles, not an official tally of UAS or C-UAS spending. It misses money buried inside broader lines. It counts a mixed line at its full value. Use it to find lines, then read the J-book.

## Status (slice 2)

- `extract.py` reads the Comptroller's R-1 (RDT&E) and P-1 (Procurement) exhibit spreadsheets and writes `data/lines.json`. It then calls `analyze.py`, which writes the FY2025 → FY2026 change view to `data/changes.json`.
- `index.html` is a static viewer. From the top: a key-findings box, the change view (totals with and without CCA, service and category tables with SVG charts, top 10 movers each way, every line's change), a "Related, not counted" table, and the row explorer with search and filters.
- **`data/lines.json` is live FY2026 PB data.** It holds 66 budget lines (71 rows; a P-1 line can span several cost-type rows), screened from the two FY2026 spreadsheets in `sources/fy2026/`. Each match was reviewed by hand from its title (see `overrides.json`). FY2026 total (discretionary plus reconciliation) across the summable rows: **$5,324.1M**, against **$4,310.3M** FY2025 enacted on the same lines (+$1,013.8M, +23.5%). By service: Army $2,291.2M, Navy $1,961.2M, Air Force $1,010.5M, Defense-Wide $34.0M, Marine Corps $27.2M. By category: UAS $3,480.6M, C-UAS $981.0M, CCA $862.4M. Without CCA the total is $4,461.7M (+24.0% on FY2025). These are sums of matched lines, not an official tally.
- Both files' parsed column sums match the exhibits' own "Total of Displayed Rows" exactly. The check runs on every extraction. `analyze.py` also checks that its line totals equal the row sums.
- `data/sample.json` is **synthetic** test output (PE codes `TEST…`, made-up figures). The viewer shows it only behind a red banner (`index.html?demo=1`), and hides the change view there.

### Categories

Each counted line has one `category`:

| Category | Lines | Rule |
|---|---|---|
| `C-UAS` | 9 | A counter keyword matches the title. Wins over the others. |
| `CCA` | 3 | "Collaborative Combat Aircraft" matches the title: Air Force R-1 0207147F ($789.4M FY26), Navy/USMC R-1 0207147M ($58.0M), Air Force P-1 CCA00M Mods ($15.0M). |
| `UAS` | 54 | Any other drone keyword, or a hand-added line. |

CCA is reported on its own because the Air Force CCA line alone ($789.4M) is 15% of the matched FY2026 total and would swamp the drone figures. Autonomous Collaborative Platforms (R-1 0207179F, $62.0M) stays in `UAS`, because its title doesn't say CCA.

### FY2025 → FY2026 change view (`analyze.py`)

- Baseline is the `FY 2025 Enacted` column. The request is `FY 2026 Total` (discretionary plus reconciliation). Both columns exist in both exhibits.
- A line is (exhibit, PE/BLI, appropriation). Its cost-type rows are summed, and memo (Non-Add) rows are left out, just as in the viewer totals. A blank exhibit cell counts as 0.
- `pct` is the change over FY2025. It is blank when FY2025 is zero. A line is `new in FY26` with no FY2025 figure, and `no FY26 request` with no FY2026 figure.
- **Matched lines only.** The view compares the same screened lines in both years. It is not DoD's count, and it doesn't see money outside the screen.
- **Code changes.** In FY2026 the Army moved several drone and counter-drone procurement lines into a new P-1 budget activity, "06 Agile Portfolio Management", with new codes. For example, C-sUAS was Other Procurement 0219AD0500 and Missile Procurement 9216C82200 in FY2025, and is Other Procurement 0010I24000 in FY2026; Small UAS was 9678A12500 and is now 7000I47000. The exhibits don't link old and new codes, so these show as one line ending and another starting. That's why 15 lines are "new" and 15 "ended". Service and category totals aren't affected. A crosswalk needs the P-40s (see "PDFs needed").
- The key findings are generated in `analyze.findings()`. A test checks that every dollar figure in them is also shown in the change view.

### Related, not counted

`overrides.json` → `related_not_counted.lines` lists 16 lines with a real but unknown drone or counter-drone share: M-SHORAD, Marine Corps GBAD (which buys MADIS), ABADS, Army Future Interceptor, directed-energy and high-energy-laser lines, DIU, and two "unmanned" lines with no domain. `extract.py` reads them with their amounts into `data/lines.json` → `related_not_counted`, and the viewer lists each with a reason. None of their money is in any total. Their combined FY2026 amount isn't shown, because it would read as a counter-drone figure and it isn't one. HEL basic and applied research (R-1 0601108D8Z, 0602890D8Z) and Air Force Directed Energy Prototyping (0604032F, no FY2025 or FY2026 money) were left off as further from fielded air defence.

### PDFs needed (slice 3)

These J-book justification documents would show how much of each mixed line is counter-drone work, and would link the Army's old and new codes. The Comptroller site blocks cloud servers, so download them in a browser from <https://comptroller.war.gov/Budget-Materials/Budget2026/> (service J-books are linked from there) and commit them under `sources/fy2026/jbooks/`. In each PDF, the exhibit is the R-2 (RDT&E) or P-40 (procurement) page for the code listed.

**Mixed air-defence lines (C-UAS share):**

| # | Service | Book (appropriation) | Budget activity | Exhibit | PE / BLI | Line | FY26 $M |
|---|---|---|---|---|---|---|---|
| 1 | Army | Missile Procurement, Army (2032A) | 02 Other missiles | P-40 | 8082C14300 | M-SHORAD - Procurement | 729.1 |
| 2 | Army | RDT&E, Army (2040A) | 04 Advanced Component Development and Prototypes | R-2 | 0604117A | M-SHORAD | 298.4 |
| 3 | Army | RDT&E, Army (2040A) | 04 Advanced Component Development and Prototypes | R-2 | 0604403A | Future Interceptor | 152.0 |
| 4 | Marine Corps | Procurement, Marine Corps (1109N) | 03 Guided missiles and equipment | P-40 | 3006 | Ground Based Air Defense (MADIS) | 620.2 |
| 5 | Marine Corps | RDT&E, Navy (1319N) | 07 Operational system development | R-2 | 0605520M | Marine Corps Air Defense Weapons Systems | 90.3 |
| 6 | Air Force | RDT&E, Air Force (3600F) | 04 Advanced component development and prototypes | R-2 | 0207522F | Airbase Air Defense Systems (ABADS) | 30.8 |
| 7 | Navy | RDT&E, Navy (1319N) | 04 Advanced Component Development and Prototypes | R-2 | 0603925N | Directed Energy and Electric Weapon Systems | 61.0 |
| 8 | Navy | Other Procurement, Navy (1810N) | 04 Ordnance support equipment | P-40 | 5510 | Directed Energy Systems | 3.0 |
| 9 | Defense-Wide (OSD) | RDT&E, Defense-Wide (0400D) | 03 Advanced technology development | R-2 | 0603924D8Z | High Energy Laser Advanced Technology Program | 130.6 |
| 10 | Defense-Wide (OSD) | RDT&E, Defense-Wide (0400D) | 04 Advanced Component Development and Prototypes | R-2 | 0604924D8Z | High Energy Laser Advanced Component Development & Prototype | 27.6 |
| 11 | Air Force | RDT&E, Air Force (3600F) | 02 Applied Research | R-2 | 0602605F | Directed Energy Technology | 92.3 |
| 12 | Defense-Wide (DIU) | RDT&E, Defense-Wide (0400D) | 03 Advanced technology development | R-2 | 0603342D8Z | Defense Innovation Unit (DIU) | 661.2 |
| 13 | Defense-Wide (DIU) | RDT&E, Defense-Wide (0400D) | 08 Software and digital technology pilot programs | R-2 | 0608776D8Z | Defense Innovation Unit Fielding | 281.4 |
| 14 | Defense-Wide (OSD) | RDT&E, Defense-Wide (0400D) | 04 Advanced Component Development and Prototypes | R-2 | 0604400D8Z | DoD Unmanned System Common Development | 2.1 |

If time is short, rows 1, 2, 4 and 12 cover $2,308.9M of the $3,180.1M FY26 in this table.

**Army code crosswalk (old FY2025 code → new FY2026 code):**

| # | Book (appropriation) | Budget activity | Exhibit | BLI | Line |
|---|---|---|---|---|---|
| 15 | Other Procurement, Army (2035A) | 06 Agile Portfolio Management | P-40 | 0010I24000 | Counter-Small Unmanned Aerial System (C-sUAS). Check whether it continues 0219AD0500 (OPA BA 02) and 9216C82200 (MPA BA 02). |
| 16 | Aircraft Procurement, Army (2031A) | 06 Agile Portfolio Management | P-40 | 7000I47000 | Small Unmanned Aerial Systems. Check whether it continues 9678A12500 (APA BA 01). |
| 17 | Aircraft Procurement, Army (2031A) | 06 Agile Portfolio Management | P-40 | 8000I48000 | Future UAS Family. Check whether it continues 9672A00510 (APA BA 01). |

## Source

For slice 1 the source is the Comptroller's machine-readable exhibit spreadsheets for the FY2026 President's Budget, listed in `sources.json`:

| Exhibit | File | Status |
|---|---|---|
| P-1 Procurement | `https://comptroller.war.gov/Portals/45/Documents/defbudget/FY2026/p1_display.xlsx` | Expected Comptroller path. Committed copy at `sources/fy2026/p1_display.xlsx`, SHA-256 `4d965906…a9c0` |
| R-1 RDT&E | `https://comptroller.war.gov/Portals/45/Documents/defbudget/FY2026/r1_display.xlsx` | **Path inferred** from the P-1 filename. Committed copy at `sources/fy2026/r1_display.xlsx`, SHA-256 `671c8e81…cc2e` |

The committed copies were downloaded by hand in a browser on 2026-11-11, because cloud runners get a 403 from the Comptroller site. They are byte-for-byte unmodified, and `sources/fy2026/SHA256SUMS` lists their hashes. The exact click-through URLs weren't captured, so the URLs above are the expected paths. `extract.py --local` checks both the hashes pinned in `sources.json` and `SHA256SUMS`.

Index page: <https://comptroller.war.gov/Budget-Materials/Budget2026/>. The PDF versions (`FY2026_r1.pdf`, `FY2026_p1.pdf`) and the service J-books sit under the same folder. In 2025 the site moved from `comptroller.defense.gov` to `comptroller.war.gov`.

Why these files: R-1 and P-1 are the department-wide line-item lists that sit on top of the service J-books. Each R-1 line is a program element (PE); each P-1 line is a budget line item (BLI). They come as spreadsheets, so slice 1 needs no PDF scraping. The trade-off is that they carry titles only. The narrative descriptions are in the J-book PDFs.

## Method

1. For each source, read the first worksheet of the `.xlsx`. The reader uses only the standard library (`zipfile` plus `xml.etree`), so there is no dependency to pin.
2. Find the header row: the first row with an `Account` cell and a `…Title` cell. Map the columns by pattern, because the wording drifts from year to year. A column counts as an amount column if its header contains `FY yyyy` and doesn't mention quantity.
3. Keep a line if its PE/BLI title, or its description column where one exists, matches any keyword below.
4. Take the service from the end of the appropriation title, for example "Aircraft Procurement, **Army**". `Procurement of Ammo, Navy & Marine Corps` counts as Navy.
5. Copy amounts exactly as printed, in **thousands of dollars**. A cell that isn't a plain number is left out of the row and logged under `unreadable`. Before any line is kept, the parsed column sums are reconciled against the exhibit's own "Total of Displayed Rows", and the run aborts on any mismatch.
   - **P-1 cost types.** A budget line item can appear on several rows: weapon system cost, advance procurement (CY), "Less: advance procurement (PY)", and so on. Rows marked **Non-Add** are memo entries, such as multiyear economic-order-quantity amounts. They are kept and shown, but `counts_in_total` is false and the viewer doesn't sum them.
   - **R-1 TOA.** Lines with "Include In TOA" = N are also marked `counts_in_total: false`. None of the FY2026 matches are affected.
6. Record each source file's URL and SHA-256 hash, and put the source URL and row number on every line.

### Keyword list

Matching ignores case. A line is tagged **C-UAS** if any counter keyword matches; otherwise it's tagged **UAS**. Each keyword is in one of two tiers:

- **core** is the agreed starting list.
- **extended** adds wider terms and a platform watch list. It catches more lines and more noise, so review those rows. The viewer's "Keyword set" filter shows each tier separately.

| Keyword | Regex | Category | Tier |
|---|---|---|---|
| counter-UAS | `\bcounter[\s-]*(?:small[\s-]*)?(?:s?UAS\|unmanned)` | C-UAS | core |
| C-UAS | `\bC[\s-]?s?UAS\b` | C-UAS | core |
| counter-small UAS | `\bcounter[\s-]*small[\s-]*(?:UAS\|unmanned)` | C-UAS | core |
| UAS | `\bs?UAS\b` | UAS | core |
| unmanned aircraft | `\bunmanned[\s-]+aircraft` | UAS | core |
| drone | `\bdrones?\b` | UAS | core |
| loitering munition | `\bloiter(?:ing)?[\s-]+munitions?\b` | UAS | core |
| Replicator | `\breplicator\b` | UAS | core |
| counter (abbrev.) | `\b(?:ctr\|cntr\|counter)[\s-]*(?:sm(?:all)?[\s-]*)?(?:s?UAVs?\b\|unman)` | C-UAS | extended |
| UAV | `\bs?UAVs?\b` | UAS | extended |
| unmanned aerial | `\bunmanned[\s-]+aerial` | UAS | extended |
| unmanned air (abbrev.) | `\bunman(?:ned)?[\s-]+air\b` | UAS | extended |
| uncrewed | `\buncrewed[\s-]+(?:aircraft\|aerial\|air)\b` | UAS | extended |
| RPA | `\bRPAs?\b` | UAS | extended |
| collaborative combat aircraft | `\bcollaborative[\s-]+combat[\s-]+aircraft` | UAS | extended |
| MQ-/RQ- designation | `\b[MR]Q[\s-]?\d{1,2}[A-Z]?\b` | UAS | extended |
| platform name | `\b(?:gr[ae]y[\s-]+eagle\|global[\s-]+hawk\|triton\|reaper\|stingray\|switchblade)\b` | UAS | extended |

The authoritative list is `KEYWORDS` in `extract.py`. A copy is written into every `data/lines.json`.

### Hand-reviewed overrides (`overrides.json`)

After the screen, each kept line is checked by hand. Record every decision with a reason:

```json
{
  "exclude": [{"exhibit": "R-1", "pe_or_bli": "0604123A", "account": "2040A", "reason": "Triton here is a radar program, not the MQ-4C"}],
  "include": [{"exhibit": "P-1", "pe_or_bli": "1234", "category": "C-UAS", "reason": "J-book P-40 says this line buys C-sUAS interceptors"}]
}
```

- `exclude` drops a false hit. The dropped line is still listed under `excluded` in `data/lines.json`.
- `include` adds a line no keyword caught. It shows in the viewer as "hand-added", with its reason.
- `account` is optional and narrows a rule to one appropriation. A rule without a `reason` is rejected, and so is a rule that matches no line (usually a typo).
- `related_not_counted.lines` lists lines with a real but unknown UAS/C-UAS share (see "Related, not counted"). Each needs `exhibit`, `pe_or_bli`, `group` and `reason`. A line can't be both counted and related; that, or a related rule that matches nothing, stops the run.
- `include` takes `category` `UAS`, `C-UAS` or `CCA` (default `UAS`).

The FY2026 review so far is from **titles only**. It adds 6 lines (launched effects, low-altitude unmanned systems, Unmanned Carrier Aviation, Autonomous Collaborative Platforms, and SOCOM Unmanned ISR in both P-1 and R-1) and drops 1 (Air Force "Target Drones", which are aerial targets).

### Known misses

- **Platforms not on the watch list** are missed, and so are titles that name only a program office or contract name.
- **Buried money**: UAS work inside a broad line, such as an Army "Aircraft Spares" line or a counter-air-defence PE, is invisible at line level. The fix is an `include` override backed by the J-book narrative.
- **Classified lines** appear in the exhibits as aggregates or not at all.
- **Unusual abbreviations**: J-book titles are truncated in uppercase. The extended tier catches common forms like "CTR SM UNMAN AIR SYS", but not every variant.
- **False positives (extended tier)**: "Triton", "Reaper" and "RPA" can mean other things, and an MQ-/RQ- designation can sit on a sustainment or ground-station line. Each row shows its matched keywords; drop false hits with `exclude`.

## Refresh the data

```sh
python3 extract.py --fetch    # downloads each source to its "local" path (sources/fy2026/...), writes data/lines.json
python3 extract.py --local    # re-screens the committed copies; checks the sha256 pinned in sources.json, if set
python3 analyze.py            # rebuilds data/changes.json from data/lines.json (extract.py already does this)
# or, with files you downloaded in a browser:
python3 extract.py --input ~/Downloads/p1_display.xlsx=fy2026-p1 --input ~/Downloads/r1_display.xlsx=fy2026-r1
```

To add a budget year, add entries to `sources.json` and copy the URLs from the Comptroller index page. After any run, compare the `lines_matched` counts in `data/lines.json` against the totals on the PDF exhibit before trusting them.

## View it

```sh
python3 -m http.server 8000   # then open http://localhost:8000  (add ?demo=1 for the synthetic sample)
```

Browsers block `fetch()` from `file://`, so serve the folder over HTTP. Any static host works, including GitHub Pages and Vercel.

## Publish (not yet)

The plan is to publish the viewer publicly, for example on GitHub Pages from `main`, once the real FY2026 data has been reviewed. **It is not public yet.** Before turning Pages on:

1. `data/lines.json` has `status: "live"`. It was built with `python3 extract.py --local` from the committed `sources/fy2026/*.xlsx`, and the SHA-256s are pinned in `sources.json`. *(Done. CI re-runs the extraction and fails if the committed data differs.)*
2. Every kept line has been read against the PDF exhibit, and each false hit is recorded in `overrides.json` with a reason. *(Titles reviewed; PDF/J-book check not yet done. Needs the PDFs above.)*
3. The `lines_matched` counts and per-service totals are spot-checked against the R-1/P-1 PDFs (`FY2026_r1.pdf`, `FY2026_p1.pdf`). *(Not done: the PDFs aren't in the repo and can't be fetched from the cloud.)*
4. The change view and key findings have been read by a person, and the "matched lines only" label is on the page. *(Label is on the page; human read not yet done.)*
5. The repository has nothing private in it. The downloader is recorded only as "the maintainer" (anonymised 2026-11-12). Then, in Settings → Pages, deploy from branch `main`, folder `/`. The site needs no build step.

The synthetic `data/sample.json` stays in the repo for the demo. The page shows it only behind the "Synthetic demo data" banner.

## Tests

```sh
python3 tests/make_fixture.py           # regenerates the synthetic .xlsx fixtures
python3 -m unittest discover -s tests
python3 -m http.server 8000 & node tests/browser_check.js http://localhost:8000   # Playwright: 1280px and 390px, no console errors, no horizontal scroll
```

CI (`.github/workflows/ci.yml`) runs the unit tests, re-runs `extract.py --local` and compares the result with the committed `data/` files, and runs the browser check.

## Data schema (`data/lines.json`)

`status` (`live` | `synthetic` | `not_fetched`), `generated_at`, `units`, `keywords[]`, `sources[]` (`id`, `exhibit`, `fiscal_year`, `url`, `url_status`, `sha256`, `lines_matched`, `lines_excluded`, `total_row_check`), `overrides_file`, `excluded[]`, `unreadable[]`, and `rows[]` with:

`id`, `exhibit`, `fiscal_year`, `line_number`, `pe_or_bli`, `title`, `service`, `organization`, `appropriation`, `budget_activity`, `classification`, `cost_type`, `add_non_add`, `include_in_toa`, `counts_in_total`, `category` (`UAS` | `C-UAS` | `CCA`), `match_tier` (`core` | `extended` | `override`), `matched_keywords[]`, `override_reason`, `amounts_thousands{column → number}`, `source_url`, `source_row`.

`related_not_counted[]` has the same fields, with `category: null`, `match_tier: "related"`, `group` and `related_reason`.

## Change schema (`data/changes.json`)

`status`, `lines_generated_at` (must equal `generated_at` in `lines.json`), `base_column`, `request_column`, `label`, `cca_note`, `totals.all` / `totals.excluding_cca`, `by_service[]`, `by_service_excluding_cca[]`, `by_category[]`, `movers.up[]` / `movers.down[]` (10 each), `findings[]`, `lines[]` and `related_not_counted[]`. A total has `fy25`, `fy26`, `fy26_recon`, `change`, `pct`, `lines`; a line adds `exhibit`, `pe_or_bli`, `title`, `service`, `category`, `appropriation`, `status`, `source_url`, `source_rows[]`. All amounts are in thousands of dollars.
