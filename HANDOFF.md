# PMS Tool — Complete Handoff Document

> **Purpose of this file**: Full context for anyone (or any Claude Code session) picking up this project.
> Read this alongside `CLAUDE.md`. Between the two files you have everything needed to continue.

---

## 1. What This Tool Is

**Guardian Capital PMS Execution Semi-Automation Tool**

A two-part internal Streamlit app for the operations/execution team at Guardian Capital.
Every trading day, the team receives an Excel file from the research team with client-wise
buy/sell orders. This tool validates, processes, and allocates those orders.

**No login. No database. No server state. Files in → processed files out.**

The single exception: `data/isin_database.csv` persists on disk (5,324+ listed companies).

---

## 2. Daily Workflow (Business Context)

### Part 1 — Morning (Pre-Trade)
1. Research team sends `Orders` Excel with client-wise instructions
2. Ops uploads: research file + Orbis bank book + Orbis scrip-wise report
3. Tool validates each order: sells checked against holdings, buys against available cash
4. Ops reviews validation table, excludes any blocked orders
5. Tool generates two files:
   - **Session File** — internal record of all approved orders (used in Part 2)
   - **Broker File** — aggregated order to send to broker (pooled qty per scrip)
6. Broker executes the pooled order

### Part 2 — Afternoon (Post-Trade)
1. Broker replies with execution confirmation (Ambit or InCred format)
2. Ops uploads: session file + broker reply
3. Tool matches execution back to individual clients by ISIN + Direction
4. Tool splits broker-level charges proportionally to each client by qty weight
5. Generates **Orbis Allocation File** — uploaded directly to Orbis (portfolio system)

### Multiple Batches in a Day
A second (or third, fourth...) batch is possible. On Part 1, upload the existing session file
as "Existing Session File" and the tool appends to it (Batch increments by 1).
Committed cash from all prior batches is deducted from available cash when validating new buys.

---

## 3. Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| UI | Streamlit 1.54.0 | Pinned exactly — do not upgrade without re-testing upload card CSS |
| Processing | Python 3.11+, pandas 2.x | All logic in pure Python functions |
| Excel read | openpyxl (xlsx), xlrd 1.2.0 (xls) | xlrd pinned — v2.x dropped .xls support |
| Excel write | openpyxl directly | Required for cell-level formatting |
| Fonts (UI) | Google Fonts (Cormorant Garamond + DM Sans) | Loaded via CSS @import in app.py |
| Font (Excel) | Aptos Narrow | Used in allocation file output |

---

## 4. Project Structure

```
pms_tool/
├── app.py                    # Entire UI — Streamlit entry point
├── CLAUDE.md                 # Rules for Claude Code (git protocol, conventions, specs)
├── HANDOFF.md                # This file
├── CONVERSATION_HISTORY.md   # Design history, decisions, what was tried/rejected
├── HOW_TO_HANDOFF.md         # Guide for starting a new LLM session
├── requirements.txt          # Pinned dependencies
├── data/
│   └── isin_database.csv     # 5,324+ rows: Name | BSE Code | NSE Code | ISIN Code
├── assets/
│   └── logo_transparent.png  # Guardian Capital logo (top-left nav)
├── part1/
│   ├── validator.py          # Core sell/buy validation logic
│   ├── session.py            # Session file builder/appender
│   └── broker_file.py        # Broker file aggregator
├── part2/
│   ├── parser.py             # Ambit + InCred broker reply parsers
│   ├── matcher.py            # Matches session rows to broker reply
│   └── allocator.py          # Weight-based proportional cost allocation
├── utils/
│   ├── reader.py             # All input file readers
│   ├── writer.py             # Excel writers (session file + allocation file)
│   └── isin.py               # ISIN DB load/lookup/add/bulk-update
└── tests/
    ├── conftest.py
    ├── test_validator.py
    ├── test_allocator.py
    └── (other test files — coverage incomplete)
```

**Separate folder (NOT in git):**
```
pms_raw/
└── app_raw.py    # Minimal test instance — same logic, no CSS. Run on port 8502.
```

---

## 5. How to Run

### Live App (production)
**https://pms-tool.streamlit.app/**

Deployed via Streamlit Community Cloud, connected to the GitHub repo (`main` branch).
Code changes pushed to `main` are picked up automatically on next app reboot.

### Run locally (development)
```powershell
cd C:\Yatharth\pms_tool
python -m streamlit run app.py --server.port 8501
```

### Run raw test instance (port 8502) — logic testing only
```powershell
python -m streamlit run C:\Yatharth\pms_raw\app_raw.py --server.port 8502
```

### Kill a port if busy
```powershell
Get-NetTCPConnection -LocalPort 8501 -State Listen | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

### GitHub repo
`https://github.com/yathnagada1999/pms-tool`

### After code changes
Restart the Streamlit server (local) or reboot the app on Streamlit Cloud.
`.py` file changes never take effect until restart.

---

## 6. Navigation Architecture

The app is a **single-page step-based UI** — no Streamlit pages, no sidebar navigation.
Everything is driven by `st.session_state` keys.

### State keys
```python
st.session_state.section          # "part1" | "part2" | "isin"
st.session_state.p1_step          # 1=Upload, 2=Validate, 3=Export
st.session_state.p2_step          # 1=Upload, 2=Results

# Parsed data (set after file parsing)
st.session_state.research_df      # parsed research orders
st.session_state.bank_book        # dict {OFIN: balance}
st.session_state.scrip_df         # holdings DataFrame
st.session_state.existing_session # optional existing session file for batch 2+
st.session_state.validation_df    # research_df + Status/Reason/ISIN/Context columns
st.session_state.session_df       # built session file DataFrame
st.session_state.broker_file_df   # built broker file DataFrame
st.session_state.allocation_df    # allocation result DataFrame
st.session_state.p2_not_exec      # list[str] — ISINs in session but not in broker reply
st.session_state.p2_unexpected    # list[str] — ISINs in broker reply but not in session

# Widget values (persist across steps via Streamlit key mechanism)
st.session_state.p1_tolerance     # float — tolerance % set in Step 1, read in Step 2
st.session_state.isin_bulk_msg    # tuple ("success"|"info", message_text) for bulk update result
```

### Navigation flow
```
Logo click → Part 1 Step 1 (home/reset)

Top bar: [Part 1] [Part 2] [ISIN Database]

Part 1:
  Step 1 (Upload & Configure)
    → [Validate Orders] button → Step 2

  Step 2 (Validate Orders)
    → [Generate Session File + Broker File] button → Step 3

  Step 3 (Export / Download)
    → Download session file + broker file

Part 2:
  Step 1 (Upload & Configure)
    → [Process Allocation] button → Step 2

  Step 2 (Review & Download)
    → Download allocation file

ISIN Database:
  Always accessible from top bar — no step flow
```

---

## 7. UI Design Language

### Colour palette
| Token | Hex | Usage |
|-------|-----|-------|
| Ink | `#1C1714` | Headings, active stepper fill |
| Gold | `#D9B244` | Primary buttons, accents, upload card borders |
| Gold dark | `#C4A03C` | Button hover, ISIN update button hover |
| Gold muted | `#B8922E` | Scrollbar thumb hover |
| Cream | `#F9F7F4` | Page background feel, card bg |
| Border | `#EAE3D8` | All dividers and card borders |
| Muted text | `#958F87` | Subtitles, labels |
| Label | `#B0A89E` | Section labels (uppercase, tracked) |
| Green | `#16a34a` | Ready/pass states, split-badge (Part 2) |
| Red | `#dc2626` | Blocked/fail states |
| Amber fill | `#FEF3C7` | CP Code blank cell highlight in session file |

### Fonts
- **Cormorant Garamond** (serif, 600) — all headings, section titles, large numbers in UI
- **DM Sans** (sans-serif, 300/400/500) — all body text, labels, buttons in UI
- **Aptos Narrow, size 11** — all cells in the generated allocation Excel file

### Component patterns

#### Split badge
Two-part box: left = label (lighter bg), right = value/action (darker bg), separated by 1px border.
Used for: Orders Ready/Blocked, Stocks/Clients count, download buttons.
```html
<div style="display:flex; border:1px solid ...; border-radius:8px; overflow:hidden; height:38px">
  <div style="padding:0 14px; background:rgba(...)">LABEL</div>
  <div style="padding:0 18px; border-left:1px solid ...">VALUE / ACTION</div>
</div>
```

#### Upload cards
Custom CSS makes Streamlit's `st.file_uploader` look like fixed-height cards:
- Empty state: dashed gold border, cloud SVG icon via CSS `::before`
- Uploaded state: solid border, filename centered, × delete button top-right
- `min-height: 140px` on dropzone — consistent height across all 4 cards
- Filename text: `white-space: normal; word-break: break-word; flex: 1; min-width: 0`
  (prevents long filenames from overflowing the card boundary)

#### Row-colour validation table
Uses pandas Styler passed to `st.dataframe` — renders as HTML (not canvas), so CSS applies.
Green rows: `rgba(22,163,74,0.07)` bg. Red rows: `rgba(220,38,38,0.06)` bg.
`set_properties(white-space: normal)` enables text wrapping in Reason column.

#### Split table (validate orders page)
Two side-by-side Streamlit columns: narrow (0.7 ratio) for checkboxes only, wide (8.3 ratio)
for the styled display table. Both `height="auto"` so the PAGE scrolls — keeps rows in sync
without any JS height-matching.

#### Download via data-URI
`st.download_button` only downloads one file. Part 1 Export and Part 2 both use
`components.html` with data-URI `<a download>` anchors styled as split-badge buttons.
"Download Both" (Part 1 only) uses a `<button>` that JS-clicks both anchors with 400ms gap:
```javascript
var badges = document.querySelectorAll('a.dl-badge');
badges[0].click();
setTimeout(function(){ badges[1].click(); }, 400);
```

#### Stepper
Centered horizontal pill stepper. Active step: dark fill + gold text. Done steps: muted fill.
Connector lines turn gold when done. Pure HTML/CSS, rendered via `st.markdown`.

---

## 8. Function Reference

### `utils/isin.py`
| Function | Purpose |
|----------|---------|
| `load_isin_database()` | Reads `data/isin_database.csv`. Decorated with `@st.cache_data` in app.py via `get_isin_db()`. |
| `build_isin_index(db)` | Returns `{UPPERCASE_TICKER: ISIN}` dict for O(1) lookups. BSE inserted first, NSE overwrites — NSE always wins. |
| `lookup_isin(ticker, db, _index)` | Returns ISIN string or None. Uses pre-built index if provided; else scans DataFrame. NSE Code priority, BSE fallback. |
| `lookup_isin_by_name(company_name, db)` | Fuzzy company name match — last resort for full names like "AU SMALL FINANCE BANK LTD". Returns ISIN or None. |
| `add_isin_entry(name, nse, bse, isin)` | Appends single row to CSV, re-saves. Call `get_isin_db.clear()` after. |
| `bulk_update_isin_database(file)` | Reads uploaded CSV, skips rows whose ISIN Code already exists, appends new rows. Returns `(added, skipped)` tuple. |

**ISIN lookup priority** (used in `validator.py` for every order row):
1. Scrip-wise report — exact Scrip Name match (case-insensitive uppercase)
2. ISIN database index — NSE Code lookup, then BSE Code fallback (O(1))
3. `lookup_isin_by_name()` — fuzzy prefix-token company name match (last resort)

**Name-based fuzzy matching algorithm** (`lookup_isin_by_name`):
- Tokenize: strip punctuation, uppercase, remove single-char tokens + stop words
- Stop words: LTD, LIMITED, SERVICES, SERVICE, CORP, CORPORATION, INC, CO, THE, AND, OF, PVT, PRIVATE, PUBLIC, GROUP, ENTERPRISES, ENTERPRISE, INDIA, INDIAN, HOLDINGS, HOLDING
- Note: BANK is intentionally NOT a stop word (removing it broke "HDFC BANK" → only 1 token)
- Require ≥2 tokens OR 1 token of length ≥5 (allows "INFOSYS" but blocks "TCS" false positives)
- Every token in shorter list must prefix-match at least one token in longer list
- Best match by score = matched_count / max(len_db_tokens, len_query_tokens)

### `utils/reader.py`
| Function | Returns |
|----------|---------|
| `read_research_file(file)` | DataFrame — all research order columns. Direction uppercase, client names suffix-stripped. |
| `read_bank_book(file)` | `dict[OFIN str → balance float]` |
| `read_scrip_wise_report(file)` | DataFrame — columns: OFIN, Scrip Name, ISIN, Quantity |
| `read_session_file(file)` | DataFrame — 10 SESSION_REQUIRED columns |
| `read_broker_reply_ambit(file)` | Raw Ambit DataFrame |
| `read_broker_reply_incred(file)` | Raw InCred DataFrame (numeric casting applied at read time) |

**All readers accept both `.xls` and `.xlsx`** — format auto-detected from magic bytes
(`content[:4] == b'\xd0\xcf\x11\xe0'` → xls; otherwise xlsx).

**Research file — flexible parsing**:
- Sheet: tries "Orders" first; if not found, scans all sheets and picks the one with the
  most alias matches in first 10 rows
- Columns: mapped via alias dict — e.g. "Stock"→"Ticker", "Action"→"Direction",
  "OFIN Code"→"OFIN", "Quantity"→"Qty", "Amount"→"Value"
- Client name suffix stripping: `r'\s*-\s*\w+\s*$'` removes trailing dash suffixes
  like "-1", "-2", "- New", "- Old" at read time

**Scrip-wise report**: Always reads from the first sheet (index 0) because the sheet name
changes daily (named after the first client in the file). Scans rows for header containing
"Scrip Name". Skips "Scrip Total" rows and blank rows.

**Critical — `file.seek(0)` in broker reply readers**: `openpyxl.load_workbook` consumes
the file stream during sheet validation. `pd.read_excel` is then called after `file.seek(0)`
resets the pointer. Never remove these seek calls.

**Client name normalisation** (applied in `read_research_file`):
```python
.str.replace(r'\s*-\s*\w+\s*$', '', regex=True)
```
Strips: "EPSILON HOLDINGS PRIVATE LIMITED-1" → "EPSILON HOLDINGS PRIVATE LIMITED"
Strips: "USHA SARVARAYALU- New" → "USHA SARVARAYALU"

### `utils/writer.py`
| Function | Returns |
|----------|---------|
| `to_excel_bytes(df, sheet_name)` | Generic DataFrame → bytes via pandas ExcelWriter |
| `write_session_file(session_df)` | Session file: bold headers + amber (`#FEF3C7`) highlight on blank CP Code cells |
| `write_allocation_file(allocation_df)` | Fully formatted allocation file (see spec below) |

**`write_allocation_file` complete formatting spec**:
- Font: Aptos Narrow, size 11 — every cell, header and data
- Header row: bold, no background fill, center+center alignment, thin border on all sides
- Data rows: thin border on all sides
- Data alignment: center+center for all columns EXCEPT Client Name (left+center)
- Charge columns number format: `"0.00"` (2dp display)
- InputTurnOver number format: `"0.00"` (displays 2dp; underlying value stored at 4dp precision)
- TradeDate number format: `"DD-MM-YYYY"` (e.g. 15-05-2026)
- Settlement No: always blank — `cell.value = None`

### `part1/validator.py` — `validate_orders()`

**Signature**: `validate_orders(research_df, bank_book, scrip_df, isin_db, existing_session_df=None, tolerance=0.0) → pd.DataFrame`

Returns research_df with 4 new columns: `ISIN` (str), `Status` ("GREEN"|"RED"), `Reason` (str), `Context` (str).

**Sell logic** (vectorised merge):
- Merge on (OFIN, ISIN) — ISIN-based, so format-agnostic regardless of what's in Ticker
- No scrip match → RED: "Client not found in holdings report"
- Held == 0 → RED: "Client holds 0 units of {Ticker}"
- Held < qty → RED: "Insufficient units - holds X, needs Y"
- Held >= qty → GREEN
- Context: `"{N:,} Units"` (e.g. "1,500 Units")

**Buy logic** (row-by-row):
- OFIN not in bank_book → RED: "Client not found in bank book"
- `available = bank_balance - committed_cash`
- `required = qty × ref_price × (1 + tolerance/100)`
- available < 0 → RED: "Negative cash balance: −₹X"
- available < required → RED: "Insufficient cash - available ₹X, needs ₹Y"
- available >= required → GREEN
- Context: `"Available: ₹{available:,.2f}"` or `"Available: −₹{abs:,.2f}"`

**Committed cash**: Sum of `Qty × Ref Price` for all BUY rows in `existing_session_df`, grouped by OFIN.
Sell rows in existing session do NOT reduce available holdings (treated as pending/cancelled).

### `part1/session.py` — `build_session_file()`
- If `existing_session_df` is None: Batch = 1 for all rows
- If provided: new rows get Batch = `existing_session_df["Batch"].max() + 1`
- Appends new rows below existing; re-numbers S.No from 1

**Output columns**: `S.No | Batch | OFIN | Client | Ticker | ISIN | Direction | Qty | Ref Price | CP Code`

### `part1/broker_file.py` — `build_broker_file()`
Groups included orders by Ticker + Direction, sums Qty, takes first Ref Price per group.

**Output columns**: `Ticker | Direction | Total Qty | Ref Price`

### `part2/parser.py`
| Function | Purpose |
|----------|---------|
| `parse_ambit_reply(file)` | Reads "Sheet1", normalises to NORMALISED_COLUMNS. TradeDate parsed from "Transaction Date" column. |
| `parse_incred_reply(file)` | Reads "Incred_Capital_Trade_Confirmati", normalises. TradeDate = `date.today()`. |
| `get_incred_cp_codes(file)` | Returns `{ISIN_UPPERCASE: CP_Code}` dict from InCred "CP CODE" column. |

**Important**: `parse_incred_reply(file)` consumes the file pointer. Before calling
`get_incred_cp_codes(file)` on the same file, call `file.seek(0)`.

**Normalised schema** (NORMALISED_COLUMNS):
`ISIN | Direction | Exchange | TradeDate | TotalQty | Brokerage | STT | StampDuty | SEBIChrg | TurnoverTax | OtherCharges | GST | NetAmount`

### `part2/matcher.py` — `match_session_to_broker()`

**Match key**: ISIN + Direction (both uppercased for comparison)

**Returns** `(matched_df, not_executed: list[str], unexpected: list[str])`:
- `matched_df` — session rows that have a corresponding broker row
- `not_executed` — ISINs present in session but absent from broker reply (shown as warning)
- `unexpected` — ISINs in broker reply not found in session (shown as warning)

Dual-exchange edge case (same ISIN on NSE + BSE same day): handled — allocator groups
separately per ISIN+Direction+Exchange.

### `part2/allocator.py` — `allocate_costs()`

**Signature**: `allocate_costs(matched_session_df, broker_df, incred_cp_codes=None) → pd.DataFrame`

For each ISIN+Direction group:
1. `weight = client_qty / total_qty` per client
2. `sum(weights) ≈ 1.0` verified via `math.isclose(rel_tol=1e-6)` — raises ValueError if not
3. Charge allocation per client (all charge cols + InputNetAmount):
   - Non-last clients: `round(weight × broker_total, precision)`
   - Last client: `broker_total - sum(all_others)` — **full precision residual, no rounding**
4. Rounding precision per column (`_CHARGE_PRECISION` dict):
   - All charges: 2dp
   - InputTurnOver: 4dp (computed at higher precision before the display format applies)
   - InputNetAmount: 2dp for non-last clients; residual for last
5. `InputNetRate = InputNetAmount / Input Quantity` — full precision, no rounding
6. `Buy/ Sell`: `row["Direction"].title()` → `"Buy"` or `"Sell"` (Orbis expects title case)
7. CP Code: session file value first; if blank and InCred, use `incred_cp_codes[ISIN]`

**Output sorted**: Batch → S.No (original session order). S.No re-numbered 1…N.

**19 output columns** (exact order — Orbis import depends on column position):
`S.No | Client Name | CustomerNo | TradeDate | Exchange Type | Settlement No | ISIN No | Buy/ Sell | Input Quantity | InputBrokerage | InputSTT | InputStampDuty | InputSEBIChrg | InputTurnOver | InputOtherCharges | InputGST | InputNetAmount | InputNetRate | CP CODE`

---

## 9. All Screens — What Each Does

### Part 1 — Step 1: Upload & Configure
- 3 mandatory upload cards (gold-bordered): Research File, Bank Book, Scrip-wise Report
- 1 optional upload card: Existing Session File (for 2nd+ batch of day)
- All cards accept both `.xls` and `.xlsx`
- Tolerance % number input (default 0.0, step 0.5; warning banner shown if > 5%)
- Gold "Validate Orders" button — parses all files, runs validation, advances to Step 2
- If any required file is missing, button is disabled

### Part 1 — Step 2: Validate Orders
- Centered title "Validate Orders"
- Split-badge status bar: `Orders Ready | N` (green) and `Orders Blocked | N` (red)
- Two action buttons: "Exclude All RED" (red-tinted) + "Exclude Entire Batch" (dark)
- Split table — two columns side-by-side:
  - Left (0.7): `st.data_editor` with Include checkbox only. Red rows: checkbox disabled.
  - Right (8.3): `st.dataframe` with pandas Styler — row background colours, text wrap
- Table column order: `No. | Client | Ticker | Dir | Qty | Available/Held | Amount | Status | Reason`
  - **Amount** = Qty × Ref Price, tolerance-adjusted worst-case:
    - Buy: `× (1 + tol%)`, Sell: `× (1 - tol%)`
    - Formatted with comma separators (e.g. `1,23,456.78`)
  - **No.** (S.No): integer format, no decimals
  - **Qty**: 2 decimal places
  - **Status**: displays "READY" (green rows) or "BLOCKED" (red rows)
  - **Available/Held** (Context): `"X,XXX Units"` for sells, `"Available: ₹X"` for buys
- Sticky bottom bar: "Generate Session File + Broker File" gold button
  - Disabled if: any RED row is still included OR zero rows included
  - On click: builds session file + broker file, advances to Step 3

### Part 1 — Step 3: Export
- Section label "FILES READY"
- 3 split-badge download elements (via `components.html` data-URI, not `st.download_button`):
  - `Session File | ⬇ Download session_file_DD_MM_YYYY_batch_N.xlsx`
  - `Broker File | ⬇ Download broker_file_DD_MM_YYYY_batch_N.xlsx`
  - `Download Both Files` button (JS clicks both anchors with 400ms gap)
- Batch number = `session_df["Batch"].max()`
- Broker file preview table shown below download buttons

### Part 2 — Step 1: Upload & Configure
- Centered title "Upload & Configure" + subtitle
- Session file uploader
- Radio selector: Ambit / InCred
- Broker reply file uploader
- Gold "Process Allocation" button — parses, matches, allocates, advances to Step 2

### Part 2 — Step 2: Review & Download
- Centered title "Allocation Complete"
- Two green split-badge blocks: `Stocks | N` and `Clients | N`
- Warning banners if present:
  - Amber: not-executed ISINs (in session, not in broker reply)
  - Red: unexpected ISINs (in broker reply, not in session)
- Allocation summary table
- Split-badge download: `Orbis Allocation File | ⬇ Download orbis_allocation_DD_MM_YYYY.xlsx`

### ISIN Database Tab
- Page header + "Update ISIN Database" compact button (top-right)
  - Styled as a grey/gold compact button (not a dropzone card)
  - Clicking opens file browser for CSV upload directly
  - After upload: inline result shown:
    - Green: `"X new ISINs added"`
    - Amber: `"All ISINs already present"`
  - Result stored in `st.session_state.isin_bulk_msg`, cleared after display
- Search text input → filters ISIN database live as user types
- `st.dataframe` of filtered results (height=400, ~10 visible rows)
- Total entry count shown below table
- **Add New Entry** form: Company Name, NSE Code, BSE Code, ISIN Code
  - On submit: appends to CSV, calls `get_isin_db.clear()` to reset cache, shows success message

---

## 10. Download Filename Convention

| File | Pattern | Example |
|------|---------|---------|
| Session File | `session_file_DD_MM_YYYY_batch_N.xlsx` | `session_file_27_05_2026_batch_1.xlsx` |
| Broker File | `broker_file_DD_MM_YYYY_batch_N.xlsx` | `broker_file_27_05_2026_batch_2.xlsx` |
| Allocation File | `orbis_allocation_DD_MM_YYYY.xlsx` | `orbis_allocation_27_05_2026.xlsx` |

`_TODAY = date.today().strftime("%d_%m_%Y")` defined once at module level in `app.py`.
Batch number: `int(session_df["Batch"].max())` extracted at the point of generating download links.
Allocation file has no batch number — it corresponds to the full session, not a single batch.

---

## 11. Key Technical Decisions & Why

| Decision | Why |
|----------|-----|
| Single `app.py`, step-based wizard | No sidebar/multipage complexity. Steps are linear — wizard flow maps to the workflow exactly. |
| `components.html` for downloads | `st.download_button` only handles one file at a time. Data-URI `<a download>` anchors + JS enables multi-file and styled buttons. |
| Pandas Styler for validation table | Need row background colours AND column renaming. Styler renders as HTML (not canvas), so `white-space:normal` and row colour CSS apply. |
| Split table (checkbox + styled display) | `st.data_editor` has limited styling support. Narrow checkbox-only editor + wide styled dataframe in side-by-side columns — page scroll keeps them visually in sync without JS. |
| `xlrd 1.2.0` pinned | Orbis exports `.xls` (Excel 97-2003 format). `xlrd` v2.x dropped `.xls` support entirely. Must stay on `1.2.0`. |
| Auto-detect `.xls` vs `.xlsx` | Magic bytes check (`content[:4]`) allows all readers to accept both formats without requiring users to know which format they have. |
| `file.seek(0)` in broker readers | `openpyxl.load_workbook` for sheet validation consumes the stream. Must reset before `pd.read_excel`. |
| `build_isin_index()` | ISIN DB has 5,324+ rows. Without index, each `lookup_isin` call scans the entire DataFrame. With index, O(1) dict lookup. |
| `get_isin_db.clear()` (not `st.cache_data.clear()`) | `@st.cache_data` caches per function. `st.cache_data.clear()` would wipe all caches globally. Must clear only the ISIN function's cache. |
| Last-client residual (full precision) | Rounding each client to 2dp accumulates error. Last client gets `broker_total - sum(others)` so the sum always reconciles exactly with broker total. |
| `Int64` for Batch/S.No columns | Pandas nullable integer — handles NaN from `pd.to_numeric` without promoting to float64 (which would show `1.0` instead of `1`). |
| ISIN-based sell merge | Research file Ticker column may contain full company names. Merging on ISIN (not Ticker text) is format-agnostic. |
| `tolerance` from `st.session_state` in Step 2 | Tolerance widget only renders in Step 1. Step 2 must read `st.session_state.get("p1_tolerance", 0.0)` — bare variable would cause NameError. |
| `Buy`/`Sell` title case (not `BUY`/`SELL`) | Verified against Ops team's manually prepared allocation files — Orbis expects title case. |
| Aptos Narrow in allocation Excel | Matches the Ops team's manually prepared allocation format exactly. |
| Tolerance not in broker file | Tolerance is purely an internal cash buffer check. Broker receives plain Ref Price. (Option 4 — explicitly decided.) |
| JS MutationObserver for ISIN button | `st.markdown('<div class="x">')` + `st.file_uploader` renders as DOM siblings, not parent-child. CSS descendant selectors fail. JS stamps the class directly onto the `stFileUploader` DOM element after render. |
| `TextColumn` for Amount (not `NumberColumn`) | `%,.2f` sprintf format with comma is not supported by Streamlit's column_config. Comma formatting done via pandas Styler lambda `f"{v:,.2f}"` + `TextColumn` to display the string. |

---

## 12. CSS Architecture

All CSS is in the `CSS` constant near the top of `app.py`, injected once via:
```python
st.markdown(CSS, unsafe_allow_html=True)
```

**Key CSS blocks and what they do:**

| Block | Purpose |
|-------|---------|
| Base reset | DM Sans globally, white background, remove Streamlit chrome (menu/footer/header/deploy button) |
| Block container | `padding-left/right: 3rem`, `max-width: 100%` |
| Stepper | `.step-pill`, `.step-pill.active`, `.step-pill.done`, `.step-line` |
| Upload cards | Multi-state: empty (dashed gold border + cloud icon), uploaded (solid + file info + × button) |
| Cloud icon | Injected via `::before` pseudo-element with inline SVG data-URI |
| Filename wrap | `white-space: normal; word-break: break-word; flex: 1; min-width: 0` on filename element |
| Buttons | Primary = gold fill (`#D9B244`), Secondary = gold-outlined, Disabled = muted beige |
| Column headers | `[role="columnheader"]` → `background: #E8E0D2 !important` |
| Hide "Press Enter" hint | `[data-testid="InputInstructions"] { display: none !important; }` |
| Scrollbar | Thin (4px), gold thumb (`#D9B244`), gold-dark hover |
| ISIN update button | `.isin-uploader-btn` class stamped by JS — collapses dropzone to 42px button, grey default, gold hover |

**JS patterns used in the app:**

| Pattern | Where | How |
|---------|-------|-----|
| Logo click → home | Top nav | `window.parent.postMessage` to set session state |
| Sticky bottom bar | Validate step | `position: sticky; bottom: 0` in `components.html` |
| Exclude button colours | Validate step | MutationObserver + setInterval stamps `.exclude-red` / `.exclude-batch` classes |
| Download Both | Export step | JS queries `a.dl-badge`, clicks [0], setTimeout 400ms, clicks [1] |
| ISIN update button | ISIN Database tab | MutationObserver stamps `isin-uploader-btn` class on `stFileUploader` DOM element |

---

## 13. Input File Specs (Quick Reference)

| File | Sheet | Key Columns | Notes |
|------|-------|-------------|-------|
| Research File | `Orders` (flexible — scans all sheets if not found) | S.No, OFIN, Client, Ticker, Direction, Qty, Ref Price, Value, CP Code | Flexible column aliases. Client names suffix-stripped. |
| Bank Book | `Bank Balance Summary` | OFIN Code, Balance | Dynamic header scan. Skip rows with "total" anywhere. |
| Scrip-wise Report | First sheet (name changes daily) | Scrip Name, Item No (=ISIN), Client Code (=OFIN), Quantity | Skip "Scrip Total" rows and blank rows. |
| Session File | Sheet index 0 | S.No, Batch, OFIN, Client, Ticker, ISIN, Direction, Qty, Ref Price, CP Code | Output of Part 1, input of Part 2. |
| Ambit Reply | `Sheet1` | Transaction Date, Exchange, ISIN No., Transaction Type, quantity, Brokerage, stt, Stamp Duty, SEBI Charges, Turnover Tax, Other Charges, GST Amount, Net Amount | TradeDate from file. |
| InCred Reply | `Incred_Capital_Trade_Confirmati` | Exchange, ISIN No., Transaction Type, Quantity, Amount, Brokerage, STT, Stamp Duty, SEBI Charges, Turnover Tax, Other Charges, GST Amount, Net Amount, CP CODE | TradeDate = today. String numeric cols cast to float at read time. |

---

## 14. Git History

| Commit | What it did |
|--------|-------------|
| `bce0f62` | Initial commit — full working codebase (all logic + UI) |
| `488ebfd` | Pin streamlit to 1.54.0 |
| `e3537c4` | Pin all dependency versions to exact builds |
| `c0271ad` | Redesign Part 1 upload page layout |
| `56d6442` | Polish upload cards (consistent sizes, centred file info) |
| `884db0b` | Polish Validate Orders UI (split-badges, row colours, sticky bar) |
| `84e7669` | Redesign Part 1 Download page (split-badge buttons, icons) |
| `6dfebb5` | Redesign Part 2 Download page (centered split-badge) |
| `c0161cd` | UX: hide "Press Enter" hint, logo click → home |
| `8bac8f1` | Fix 3 critical bugs: file.seek(0), assert→ValueError, InCred ISIN .upper() |
| `8cf265e` | Quality fixes, em dash cleanup, Part 2 UI polish (Stocks/Clients badges) |
| `d2545ff` | Validate table: Context column next to Qty, "X Units" format for sells |
| `c149e32` | Add HANDOFF.md, apply wrap-text to all tables |
| `e708fa0` | Add CONVERSATION_HISTORY.md and HOW_TO_HANDOFF.md |
| `9e03725` | Fix sell validation for full company names; universal xls/xlsx support; 3-step ISIN lookup |
| `49ff2aa` | Bulk ISIN update feature, InputTurnOver 4dp, filename wrap fix, upload card fixes |
| `131d13e` | Increase Update ISIN Database button height |
| `fda111c` | Inline result message after bulk ISIN update |
| `88ec162` | Amount column with commas in validation table; client name suffix stripping in reader |
| `6337d82` | Date-stamped filenames (DD_MM_YYYY) on all downloads |
| `41efbeb` | Buy/Sell title case in allocation file (Orbis format match) |
| `0a5e012` | Center-align all allocation file data cells; Client Name left-align |
| `14986b5` | Allocation file: Aptos Narrow 11pt, no header fill, thin borders on all cells |
| `742b288` | InputTurnOver display as 2dp in Excel (value stored at 4dp precision) |
| `7a3a7af` | TradeDate format changed from DD-MMM-YYYY to DD-MM-YYYY |
| `6bdfc1f` | Batch number appended to session and broker file download names |
| `2ab4ba1` | Worst-case tolerance-adjusted Amount column in validation table |
| `6d3ab85` | Fix NameError: read tolerance from st.session_state in Step 2 |
| `9c962b1` | Update all three handoff docs to reflect current state |
| `309835d` | Fix two inaccuracies in handoff docs (deployment URL, ISIN UI) |

---

## 15. Known Quirks

- **Streamlit 1.54.0 pinned** — newer versions changed the upload card DOM structure. Do not upgrade without re-testing all upload card CSS selectors.
- **`components.html` iframes** — download badges live inside iframes. The JS uses `document` (not `window.parent.document`) because clicks happen within the iframe. Height must be set exactly or buttons clip.
- **Canvas vs HTML rendering** — `st.dataframe` with a raw DataFrame uses canvas (glide-data-grid). `st.dataframe` with a pandas Styler uses HTML. Only HTML tables respect CSS from `set_properties`. Always use Styler for styled tables.
- **`TextColumn` for Amount** — Streamlit's `NumberColumn` sprintf does not support comma formatting (`%,.2f`). Use `TextColumn` + pandas Styler `.format(lambda v: f"{v:,.2f}")` instead.
- **InCred CP Code column** — named `CP CODE` (all caps, space). `get_incred_cp_codes` normalises ISIN keys to uppercase before building the dict.
- **`xlrd 1.2.0` must be pinned** — `pip install xlrd` gives 2.x which only reads `.xlsx`. The scrip-wise report from Orbis is `.xls`. Always `xlrd==1.2.0`.
- **ISIN lookup for buy orders** — scrip-wise report only contains current holdings (sell stocks). For buy orders, ISIN falls through to isin_database or name-based lookup.
- **JS class-stamping for ISIN button** — `st.markdown('<div class="x">')` + `st.file_uploader` renders as DOM siblings, not parent-child. CSS descendant selectors `.x .stFileUploader` never match. Class must be stamped directly on the element via MutationObserver.
- **`tolerance` in Step 2** — widget `key="p1_tolerance"` only renders in Step 1. Step 2 reads `st.session_state.get("p1_tolerance", 0.0)`. Never use `tolerance` as a bare local variable in Step 2 code.
- **InputTurnOver precision** — computed at 4dp and stored at full float64 precision in the cell. Excel number format `"0.00"` shows 2dp by default; user can click "Increase Decimal" to see more.
- **Scrip-wise sheet name** — changes daily (named after the first client). Code always reads by index 0, not by name. CLAUDE.md spec says `Sheet: file` — this was the original spec but the code handles any sheet name.

---

## 16. What Is Not Yet Done / Out of Scope

- **Full test suite** — `tests/` folder has structure but coverage is not complete.
- **ISIN database edit/delete** — intentionally out of scope. Adding new ISINs is available via UI (single entry form + bulk CSV upload). Editing or deleting existing entries: research team does this directly in `data/isin_database.csv`.
- **Email integration** — out of scope.
- **Tolerance in broker file** — decided to keep out. Tolerance is an internal cash buffer check only. Broker file always shows plain Ref Price.

---

## 17. The Raw Test Instance (`pms_raw/`)

Located at `C:\Yatharth\pms_raw\app_raw.py`. **Not in git.**

Purpose: test the processing logic with real files without any UI styling getting in the way.
Uses `sys.path.insert(0, r"C:\Yatharth\pms_tool")` to import directly from the main project.
Zero code duplication — same functions, same logic.

Extra features vs main app:
- Shows every intermediate DataFrame (parsed research, bank book, scrip report, etc.)
- Weight check table per ISIN+Direction (confirms all weights sum to 1.0)
- Charge totals verification table (sum of allocated per charge vs broker total)
- Download buttons for session file and broker file

Run: `python -m streamlit run C:\Yatharth\pms_raw\app_raw.py --server.port 8502`

---

## 18. Continuing from a New Session

If picking this up fresh (new device, new Claude Code account, etc.):

1. Clone repo: `git clone https://github.com/yathnagada1999/pms-tool`
2. Install: `pip install -r requirements.txt`
3. Run locally: `python -m streamlit run app.py` OR access live at `https://pms-tool.streamlit.app/`
4. Read `CLAUDE.md` first (git protocol, business rules), then this file

The `CLAUDE.md` has the git push protocol (password required before every push; local commits are fine without asking).
See `HOW_TO_HANDOFF.md` for the exact starting prompt to use in a new LLM session.

---

*Last updated: after commit 309835d*
