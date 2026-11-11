# J-books Explorer

A research tool that pulls drone (UAS) and counter-UAS (C-UAS) budget lines out of the Department of Defense's budget exhibits into one searchable, filterable page. Every row links back to the file it came from.

> **Caveat.** This is a keyword screen of line titles, not an official tally of UAS or C-UAS spending. It misses money buried inside broader lines. It counts a mixed line at its full value. Use it to find lines, then read the J-book.

## Status (slice 1)

- `extract.py` reads the Comptroller's R-1 (RDT&E) and P-1 (Procurement) exhibit spreadsheets and writes `data/lines.json`.
- `index.html` is a static viewer with search, service, category and keyword-set filters, a choice of amount column, and sort by amount.
- **`data/lines.json` is live FY2026 PB data.** It holds 66 budget lines (71 rows; a P-1 line can span several cost-type rows), screened from the two FY2026 spreadsheets in `sources/fy2026/`. Each match was reviewed by hand from its title (see `overrides.json`). FY2026 total (discretionary plus reconciliation) across the summable rows: **$5,324.1M**. By service: Army $2,291.2M, Navy $1,961.2M, Air Force $1,010.5M, Defense-Wide $34.0M, Marine Corps $27.2M. That splits into UAS $4,343.1M and C-UAS $981.0M. These are sums of matched lines, not an official tally.
- Both files' parsed column sums match the exhibits' own "Total of Displayed Rows" exactly. The check runs on every extraction.
- `data/sample.json` is **synthetic** test output (PE codes `TEST…`, made-up figures). The viewer shows it only behind a red banner (`index.html?demo=1`).

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
- `not_included_mixed_lines` lists lines with a real but unknown UAS/C-UAS share, such as M-SHORAD, MADIS/GBAD, directed energy and DIU. They are left out because the exhibits can't split them. Slice 2 reads their J-book narratives.

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

1. `data/lines.json` has `status: "live"`. It was built with `python3 extract.py --local` from the committed `sources/fy2026/*.xlsx`, and the SHA-256s are pinned in `sources.json`. *(Done.)*
2. Every kept line has been read against the PDF exhibit, and each false hit is recorded in `overrides.json` with a reason. *(Titles reviewed; PDF/J-book check not yet done.)*
3. The `lines_matched` counts and per-service totals are spot-checked against the R-1/P-1 PDFs.
4. The repository has nothing private in it. Then, in Settings → Pages, deploy from branch `main`, folder `/`. The site needs no build step.

The synthetic `data/sample.json` stays in the repo for the demo. The page shows it only behind the "Synthetic demo data" banner.

## Tests

```sh
python3 tests/make_fixture.py           # regenerates the synthetic .xlsx fixtures
python3 -m unittest discover -s tests
```

## Data schema (`data/lines.json`)

`status` (`live` | `synthetic` | `not_fetched`), `generated_at`, `units`, `keywords[]`, `sources[]` (`id`, `exhibit`, `fiscal_year`, `url`, `url_status`, `sha256`, `lines_matched`, `lines_excluded`, `total_row_check`), `overrides_file`, `excluded[]`, `unreadable[]`, and `rows[]` with:

`id`, `exhibit`, `fiscal_year`, `line_number`, `pe_or_bli`, `title`, `service`, `organization`, `appropriation`, `budget_activity`, `classification`, `cost_type`, `add_non_add`, `include_in_toa`, `counts_in_total`, `category`, `match_tier` (`core` | `extended` | `override`), `matched_keywords[]`, `override_reason`, `amounts_thousands{column → number}`, `source_url`, `source_row`.
