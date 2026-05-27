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
3. Tool matches execution back to individual clients
4. Tool splits broker-level charges proportionally to each client by qty weight
5. Generates **Orbis Allocation File** — uploaded directly to Orbis (portfolio system)

### Multiple Batches in a Day
A second batch is possible. On Part 1, upload the morning's session file as "existing session"
and the tool appends to it (Batch 2). Committed cash from Batch 1 is deducted from available
cash when validating Batch 2 buys.

---

## 3. Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| UI | Streamlit 1.54.0 | Pinned exactly — do not upgrade without testing |
| Processing | Python 3.11+, pandas 2.x | All logic in pure Python functions |
| Excel read | openpyxl (xlsx), xlrd 1.2.0 (xls) | xlrd pinned — v2.x dropped .xls support |
| Excel write | openpyxl directly | For formatting; pandas ExcelWriter for simple outputs |
| Fonts | Google Fonts (Cormorant Garamond + DM Sans) | Loaded via CSS @import |

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
    └── (other test files)
```

**Separate folder (NOT in git):**
```
pms_raw/
└── app_raw.py    # Minimal test instance — same logic, no CSS. Run on port 8502.
```

---

## 5. How to Run

### Main App (port 8501)
```powershell
cd C:\Yatharth\pms_tool
python -m streamlit run app.py --server.port 8501
```

### Raw Test Instance (port 8502) — for logic testing only
```powershell
python -m streamlit run C:\Yatharth\pms_raw\app_raw.py --server.port 8502
```

### Kill a port if busy
```powershell
Get-NetTCPConnection -LocalPort 8502 -State Listen | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

### GitHub repo
`https://github.com/yathnagada1999/pms-tool`

### After pulling new code
Restart the Streamlit server. Code changes to `.py` files only take effect on restart.

---

## 6. Navigation Architecture

The app is a **single-page step-based UI** — no Streamlit pages, no sidebar navigation.
Everything is driven by `st.session_state` keys.

### State keys
```python
st.session_state.section          # "part1" | "part2" | "isin"
st.session_state.p1_step          # 1=Upload, 2=Validate, 3=Export
st.session_state.p2_step          # 1=Upload, 2=Results

# Data state (set after parsing)
st.session_state.research_df
st.session_state.bank_book
st.session_state.scrip_df
st.session_state.existing_session
st.session_state.validation_df
st.session_state.session_df
st.session_state.broker_file_df
st.session_state.allocation_df
st.session_state.p2_not_exec      # list of not-executed ISINs
st.session_state.p2_unexpected    # list of unexpected ISINs in broker reply

# Widget values (persist across steps)
st.session_state.p1_tolerance     # float — tolerance % set in Step 1, read in Step 2
st.session_state.isin_bulk_msg    # tuple (type, text) for bulk update result message
```

### Navigation flow
```
Logo click → Part 1 Step 1 (home)

Top bar: [Part 1] [Part 2] [ISIN Database]

Part 1:
  Step 1 (Upload) → [Validate Orders] button → Step 2
  Step 2 (Validate) → [Generate Files] button → Step 3
  Step 3 (Export) → download session + broker files

Part 2:
  Step 1 (Upload) → [Process Allocation] button → Step 2
  Step 2 (Results) → download allocation file
```

---

## 7. UI Design Language

### Colour palette
| Token | Hex | Usage |
|-------|-----|-------|
| Ink | `#1C1714` | Headings, active stepper fill |
| Gold | `#D9B244` | Primary buttons, accents, borders |
| Gold dark | `#C4A03C` | Button hover |
| Gold muted | `#B8922E` | Scrollbar thumb hover |
| Cream | `#F9F7F4` | Page background feel, card bg |
| Border | `#EAE3D8` | All dividers and card borders |
| Muted text | `#958F87` | Subtitles, labels |
| Label | `#B0A89E` | Section labels (uppercase, tracked) |
| Green | `#16a34a` | Ready/pass states |
| Red | `#dc2626` | Blocked/fail states |
| Amber | `#FEF3C7` | CP Code blank cell highlight in session file |

### Fonts
- **Cormorant Garamond** (serif, 600) — all headings, section titles, large numbers
- **DM Sans** (sans-serif, 300/400/500) — all body text, labels, buttons
- **Aptos Narrow** (size 11) — all cells in the generated allocation Excel file

### Component patterns

#### Split badge (used for status + download buttons)
Two-part box: left side = label (lighter bg), right side = value/action (darker bg).
```html
<div style="display:flex; border:1px solid ...; border-radius:8px; overflow:hidden; height:38px">
  <div style="padding:0 14px; ... background:rgba(...)">LABEL</div>
  <div style="padding:0 18px; ... border-left:1px solid ...">VALUE</div>
</div>
```

#### Upload cards
Custom CSS makes Streamlit's `st.file_uploader` look like cards:
- Empty state: dashed gold border, cloud upload icon (SVG injected via `::before`)
- Uploaded state: solid border, file name centered, × delete button top-right
- `min-height: 140px` on dropzone, consistent height across all cards
- Filename text: `white-space: normal; word-break: break-word; flex: 1; min-width: 0`

#### Row-colour table (validation)
Uses pandas Styler passed to `st.dataframe` — renders as HTML (not canvas), so CSS applies.
Green rows: `rgba(22,163,74,0.07)` bg. Red rows: `rgba(220,38,38,0.06)` bg.

#### Split table (validate orders)
Two side-by-side columns: narrow (0.7) for checkboxes only, wide (8.3) for styled table.
Both auto-height so page scrolls — keeps rows in sync without JS.

#### Download via data-URI (Part 1 Export + Part 2)
`st.download_button` only downloads one file. Used `components.html` with data-URI
`<a download>` anchors + JS to click both with 400ms gap:
```javascript
var badges = document.querySelectorAll('a.dl-badge');
badges[0].click();
setTimeout(function(){ badges[1].click(); }, 400);
```

#### Stepper
Centered horizontal pill stepper. Active step: dark fill + gold text. Done steps: muted.
Connector lines turn gold when done. Built in pure HTML/CSS via `st.markdown`.

---

## 8. Function Reference

### `utils/isin.py`
| Function | Purpose |
|----------|---------|
| `load_isin_database()` | Reads `data/isin_database.csv`. Decorated with `@st.cache_data` in app.py. |
| `build_isin_index(db)` | Returns `{uppercase_ticker: isin}` dict for O(1) lookups. BSE first, NSE overwrites (NSE priority). |
| `lookup_isin(ticker, db, _index)` | Returns ISIN string or None. Uses index if provided, else DataFrame scan. |
| `lookup_isin_by_name(company_name, db)` | Fuzzy name match — last resort when ticker is a full company name. Returns ISIN or None. |
| `add_isin_entry(name, nse, bse, isin)` | Appends row to CSV, re-saves. Call `get_isin_db.clear()` after to reset cache. |
| `bulk_update_isin_database(file)` | Reads uploaded CSV, skips existing ISINs, appends new rows. Returns `(added, skipped)`. |

**ISIN lookup priority in validator.py**:
1. Scrip-wise report — exact Scrip Name match (case-insensitive)
2. ISIN database index — NSE Code, then BSE Code fallback
3. `lookup_isin_by_name()` — fuzzy company name match (last resort)

### `utils/reader.py`
| Function | Returns |
|----------|---------|
| `read_research_file(file)` | DataFrame — all research order columns. Client names stripped of trailing dash suffixes (e.g. "-1", "- New"). |
| `read_bank_book(file)` | `dict[OFIN str → balance float]` |
| `read_scrip_wise_report(file)` | DataFrame — OFIN, Scrip Name, ISIN, Quantity |
| `read_session_file(file)` | DataFrame — 10 SESSION_COLUMNS |
| `read_broker_reply_ambit(file)` | Raw Ambit DataFrame |
| `read_broker_reply_incred(file)` | Raw InCred DataFrame (numeric casting applied) |

**All readers accept both `.xls` and `.xlsx`** — format auto-detected from magic bytes.

**Research file**: Handles flexible sheet names (tries "Orders" first, then best-match scan).
Handles flexible column names via alias dict (e.g. "Stock" = "Ticker", "Action" = "Direction").

**Client name normalisation** in `read_research_file`: strips trailing dash suffixes:
```python
.str.replace(r'\s*-\s*\w+\s*$', '', regex=True)
```

**Critical**: `file.seek(0)` is called inside both broker reply readers between the
openpyxl sheet-check and the `pd.read_excel` call. Without this, `pd.read_excel` reads
an empty stream. Do not remove.

### `utils/writer.py`
| Function | Returns |
|----------|---------|
| `to_excel_bytes(df, sheet_name)` | Generic: df → bytes |
| `write_session_file(session_df)` | Session file with bold headers + amber highlight on blank CP Code cells (`#FEF3C7`) |
| `write_allocation_file(allocation_df)` | Formatted allocation file — see below |

**`write_allocation_file` formatting**:
- Font: Aptos Narrow, size 11, all cells (header + data)
- Header: bold, no background fill, center+center alignment, thin border
- Data: center+center alignment (except Client Name: left+center), thin border
- Charge columns: number format `"0.00"` (2dp display)
- InputTurnOver: number format `"0.00"` (displays 2dp; full precision stored in cell)
- TradeDate: number format `"DD-MM-YYYY"`
- Settlement No: always blank (value set to None)

### `part1/validator.py` — `validate_orders()`
Returns research_df enriched with: `ISIN`, `Status` (GREEN/RED), `Reason`, `Context`.

**Sell logic**: Merge on (OFIN, ISIN) — ISIN-based, format-agnostic.
No match → RED. Zero held → RED. Held < ordered → RED "Insufficient units - holds X, needs Y".
Context format: `"X Units"` (e.g. `"200 Units"`).

**Buy logic**: Look up OFIN in bank_book. Deduct committed cash from existing session.
`required = qty × ref_price × (1 + tolerance/100)`. Not in bank book → RED.
Negative available → RED. Available < required → RED with cash amounts.
Context format: `"Available: ₹X"`.

**ISIN lookup order**: scrip_df → isin_db (NSE/BSE code) → `lookup_isin_by_name()` (fuzzy).

**Committed cash** = sum(Qty × Ref Price) for BUY rows in `existing_session_df`, by OFIN.
Sell rows in existing session do NOT reduce available holdings.

### `part1/session.py` — `build_session_file()`
Appends new rows to existing session if provided (Batch increments).
Output columns: `S.No | Batch | OFIN | Client | Ticker | ISIN | Direction | Qty | Ref Price | CP Code`

### `part1/broker_file.py` — `build_broker_file()`
Groups by Ticker+Direction, sums Qty, takes first Ref Price.
Output: `Ticker | Direction | Total Qty | Ref Price`

### `part2/parser.py`
| Function | Purpose |
|----------|---------|
| `parse_ambit_reply(file)` | Parses Ambit, normalises to NORMALISED_COLUMNS |
| `parse_incred_reply(file)` | Parses InCred, uses today's date as TradeDate |
| `get_incred_cp_codes(file)` | Returns `{ISIN_upper: CP_Code}` dict from InCred reply |

**Important**: After calling `parse_incred_reply(file)`, call `file.seek(0)` before calling
`get_incred_cp_codes(file)` — the file pointer is at end after parsing.

Normalised schema: `ISIN | Direction | Exchange | TradeDate | TotalQty | Brokerage | STT | StampDuty | SEBIChrg | TurnoverTax | OtherCharges | GST | NetAmount`

### `part2/matcher.py` — `match_session_to_broker()`
Match key: `ISIN + Direction` (uppercase). Returns:
- `matched_df` — session rows that have a broker match
- `not_executed` — ISINs in session but not in broker reply
- `unexpected` — ISINs in broker reply but not in session

### `part2/allocator.py` — `allocate_costs()`
For each ISIN+Direction group:
1. `weight = client_qty / total_qty`
2. Verify `sum(weights) ≈ 1.0` via `math.isclose()` — raises `ValueError` if not
3. Each charge col: `client_share = round(weight × broker_total, precision)`
   - Default precision: 2dp. InputTurnOver: 4dp (`_CHARGE_PRECISION` dict)
4. Last client: `residual = broker_total - sum(others)` — full precision, no rounding
5. `InputNetRate = InputNetAmount / Input Quantity` — full precision
6. `Buy/ Sell` value: `row["Direction"].title()` → `"Buy"` or `"Sell"`

**19 output columns** (exact order matters for Orbis import):
`S.No | Client Name | CustomerNo | TradeDate | Exchange Type | Settlement No | ISIN No | Buy/ Sell | Input Quantity | InputBrokerage | InputSTT | InputStampDuty | InputSEBIChrg | InputTurnOver | InputOtherCharges | InputGST | InputNetAmount | InputNetRate | CP CODE`

---

## 9. All Screens — What Each Does

### Part 1 — Step 1: Upload & Configure
- 3 mandatory upload cards: Research File (.xlsx/.xls), Bank Book (.xlsx/.xls), Scrip-wise Report (.xls/.xlsx)
- 1 optional: Existing Session File (.xlsx) — for second batch of day
- Tolerance % input (default 0, warning banner if > 5%)
- "Validate Orders" primary button (gold) — triggers validation, advances to Step 2

### Part 1 — Step 2: Validate Orders
- Centered title "Validate Orders"
- Split-badge status bar: `Orders Ready | N` and `Orders Blocked | N`
- "Exclude All RED" button (red-tinted) + "Exclude Entire Batch" button (dark)
- Split table: narrow checkbox column (0.7) + wide styled table (8.3)
  - Column order: S.No | Client | Ticker | Direction | Qty | Units Held/Cash | **Amount** | Status | Reason
  - Amount = Qty × Ref Price, with worst-case tolerance applied (buy +tol%, sell -tol%)
  - Amount displayed with comma formatting (e.g. `1,23,456.78`)
  - S.No shown as integer; Qty shown to 2dp
  - Status shows "READY" (green rows) or "BLOCKED" (red rows)
  - Context column renamed "Available / Held" in display
- Sticky bottom bar: "Generate Session File + Broker File" button
  - Disabled if any RED row is still checked OR zero rows included

### Part 1 — Step 3: Export
- Section label "FILES READY"
- 3 split-badge download links (via components.html data-URI):
  - Session File — `session_file_DD_MM_YYYY_batch_N.xlsx`
  - Broker File — `broker_file_DD_MM_YYYY_batch_N.xlsx`
  - "Download Both Files" button (triggers both with 400ms JS gap)
- Broker file summary table shown below

### Part 2 — Step 1: Upload & Configure
- Centered title "Upload & Configure" + subtitle
- Session file uploader
- Radio: Ambit / InCred broker selection
- Broker reply uploader
- "Process Allocation" primary button

### Part 2 — Step 2: Review & Download
- Centered title "Allocation Complete"
- Two green split-badge blocks: `Stocks | N` and `Clients | N`
- Warning banners (if any): not-executed ISINs (amber), unexpected ISINs (red)
- Allocation summary table
- Centered split-badge download: `orbis_allocation_DD_MM_YYYY.xlsx`

### ISIN Database Tab
- Search input → filters live
- `st.dataframe` showing filtered results (height=400)
- Total entry count
- Add New Entry form: Company Name, NSE Code, BSE Code, ISIN Code
- On add: writes to CSV, clears cache with `get_isin_db.clear()`
- **Update ISIN Database** button (top-right, compact gold button):
  - Acts as a file browser — opens CSV upload dialog directly
  - After upload: inline result shows "X new ISINs added" or "All ISINs already present"
  - Implemented via JS MutationObserver stamping CSS class on the stFileUploader element

---

## 10. Download Filename Convention

| File | Pattern | Example |
|------|---------|---------|
| Session File | `session_file_DD_MM_YYYY_batch_N.xlsx` | `session_file_27_05_2026_batch_1.xlsx` |
| Broker File | `broker_file_DD_MM_YYYY_batch_N.xlsx` | `broker_file_27_05_2026_batch_1.xlsx` |
| Allocation File | `orbis_allocation_DD_MM_YYYY.xlsx` | `orbis_allocation_27_05_2026.xlsx` |

`_TODAY` is defined once at module level: `date.today().strftime("%d_%m_%Y")`.
Batch number extracted from `session_df["Batch"].max()` at download time.

---

## 11. Key Technical Decisions & Why

| Decision | Why |
|----------|-----|
| Single `app.py`, step-based | No sidebar/multipage complexity. Steps are linear — wizard flow fits best. |
| `components.html` for downloads | `st.download_button` only handles one file. Data-URI anchors + JS enables multi-file download. |
| Pandas Styler for validation table | Need row background colours AND rename/reorder columns. Styler renders as HTML (not canvas), so CSS like `white-space:normal` works. |
| Split table (checkbox + styled) | `st.data_editor` has limited styling. Narrow checkbox editor + wide styled dataframe in side-by-side columns — page scroll keeps them in sync without JS. |
| `xlrd` for scrip-wise report | Orbis exports `.xls` (Excel 97-2003). `xlrd` 1.2.0 is the last version with `.xls` support. |
| `file.seek(0)` in broker readers | `openpyxl.load_workbook` consumes the file stream. Must reset before `pd.read_excel`. |
| `build_isin_index()` | ISIN DB has 5,324+ rows. Without the index, every `lookup_isin` call scans the whole DataFrame. With the index, it's O(1). |
| `get_isin_db.clear()` | `@st.cache_data` caches by function. Must clear the specific function's cache, not `st.cache_data.clear()` (which clears everything). |
| Last-client residual (no rounding) | Rounding 2dp on each client leaves accumulated error. Last client absorbs the full residual so broker total always equals sum of client totals exactly. |
| `Int64` for Batch/S.No | Pandas nullable integer — handles NaN without converting to float64 (avoids `1.0` display issue). |
| ISIN-based sell merge | Research file may use full company names in Ticker. Merging on ISIN is format-agnostic. |
| `tolerance` from session_state in Step 2 | Widget only renders in Step 1. Step 2 reads `st.session_state.get("p1_tolerance", 0.0)` to avoid NameError. |
| `Buy`/`Sell` title case in allocator | Orbis expects title case. Our internal Direction is always uppercase. Apply `.title()` at output time. |
| Aptos Narrow in allocation Excel | Matches the format used by the Ops team in their manually prepared allocation files. |
| Tolerance not in broker file | Tolerance is purely an internal cash validation buffer. Broker receives plain Ref Price. |

---

## 12. CSS Architecture

All CSS is in the `CSS` constant at the top of `app.py`, injected via `st.markdown(CSS, unsafe_allow_html=True)`.

**Key CSS blocks:**
- **Base reset**: DM Sans globally, white background, hide Streamlit chrome
- **Block container**: `padding-left/right: 3rem`, `max-width: 100%`
- **Stepper**: `.step-pill`, `.step-pill.active`, `.step-pill.done`, `.step-line`
- **Upload cards**: Complex multi-state CSS — empty (dashed gold), uploaded (solid border), delete button top-right
- **File uploader cloud icon**: Injected via `::before` pseudo-element with inline SVG data-URI
- **Filename wrap**: `white-space: normal; word-break: break-word; flex: 1; min-width: 0`
- **Buttons**: Primary = gold fill, Secondary = gold-outlined, disabled = muted beige
- **Column headers**: `[role="columnheader"]` → `background: #E8E0D2 !important`
- **Hide "Press Enter"**: `[data-testid="InputInstructions"] { display: none !important; }`
- **Scrollbar**: Thin (4px), gold thumb
- **ISIN update button**: `.isin-uploader-btn` class stamped by JS — collapses dropzone to 42px button

**JS patterns:**
- Logo click → navigate to Part 1 home
- Sticky bottom bar in validate step: `position: sticky; bottom: 0`
- Semantic button colours: MutationObserver stamps `.exclude-red` and `.exclude-batch` classes
- Download Both: JS queries `a.dl-badge` anchors, clicks first, setTimeout 400ms, clicks second
- ISIN update button: MutationObserver stamps `isin-uploader-btn` class on `stFileUploader` element

---

## 13. Input File Specs (Quick Reference)

| File | Sheet | Key Columns | Notes |
|------|-------|-------------|-------|
| Research File | `Orders` (flexible) | S.No, OFIN, Client, Ticker, Direction, Qty, Ref Price, Value, CP Code | Flexible sheet/column names via alias dict |
| Bank Book | `Bank Balance Summary` | OFIN Code, Balance | Dynamic header scan. Skip "Total" rows. |
| Scrip-wise Report | First sheet | Scrip Name, Item No (=ISIN), Client Code (=OFIN), Quantity | `.xls` or `.xlsx`. Skip "Scrip Total" rows. |
| Session File | `Session` | S.No, Batch, OFIN, Client, Ticker, ISIN, Direction, Qty, Ref Price, CP Code | Output of Part 1, input of Part 2 |
| Ambit Reply | `Sheet1` | Transaction Date, Exchange, ISIN No., Transaction Type, quantity, + charge cols | TradeDate from file |
| InCred Reply | `Incred_Capital_Trade_Confirmati` | Exchange, ISIN No., Transaction Type, Quantity, + charge cols, CP CODE | TradeDate = today |

---

## 14. Git History

| Commit | What it did |
|--------|-------------|
| `bce0f62` | Initial commit — full working codebase |
| `488ebfd` | Pin streamlit to 1.54.0 |
| `c0271ad` | Redesign Part 1 upload layout |
| `56d6442` | Polish upload cards |
| `884db0b` | Polish Validate Orders UI (badges, row colours, sticky bar) |
| `84e7669` | Redesign Part 1 Download (split-badge downloads) |
| `6dfebb5` | Redesign Part 2 Download (centered split-badge) |
| `c0161cd` | UX: hide "Press Enter" hint, logo click → home |
| `8bac8f1` | Fix 3 critical bugs: file.seek(0), assert→ValueError, InCred ISIN .upper() |
| `8cf265e` | Quality fixes + em dash cleanup + Part 2 UI polish |
| `d2545ff` | Validate table: Context column next to Qty, "X Units" format |
| `c149e32` | Add HANDOFF.md, wrap-text on all tables |
| `e708fa0` | Add CONVERSATION_HISTORY.md and HOW_TO_HANDOFF.md |
| `9e03725` | Fix sell validation for full company names; universal xls/xlsx support; 3-step ISIN lookup |
| `49ff2aa` | Bulk ISIN update, InputTurnOver 4dp, filename wrap fix, upload card fixes |
| `131d13e` | Increase Update ISIN Database button height |
| `fda111c` | Add inline result message after bulk ISIN update |
| `88ec162` | Amount column with commas in validation table; client name suffix stripping |
| `6337d82` | Date-stamped filenames (DD_MM_YYYY) on all downloads |
| `41efbeb` | Buy/Sell title case in allocation file |
| `14986b5` | Allocation file: Aptos Narrow 11pt, no header fill, thin borders, alignment |
| `742b288` | InputTurnOver display as 2dp in Excel |
| `7a3a7af` | TradeDate format DD-MM-YYYY |
| `6bdfc1f` | Batch number in session and broker file download names |
| `2ab4ba1` | Worst-case tolerance-adjusted Amount in validation table |
| `6d3ab85` | Fix NameError: tolerance read from session_state in step 2 |

---

## 15. Known Quirks

- **Streamlit 1.54.0 is pinned** — newer versions changed upload card DOM structure. Do not upgrade without re-testing all upload card CSS.
- **components.html iframes** — download badges live inside iframes. JS uses `document` (not `window.parent.document`) since anchor clicks are within the iframe. Height must be set correctly or buttons clip.
- **Canvas vs HTML rendering** — `st.dataframe` with a raw DataFrame uses canvas (glide-data-grid). `st.dataframe` with a pandas Styler uses HTML. Only HTML tables respect CSS from `set_properties`. This is why all styled tables use a Styler.
- **TextColumn for Amount** — Amount uses `st.column_config.TextColumn` (not NumberColumn) because `%,.2f` with comma formatting is not supported by Streamlit's sprintf formatter. Comma formatting is done via pandas Styler lambda instead.
- **InCred CP Code** — stored as `CP CODE` (all caps) in the InCred reply. `get_incred_cp_codes` normalises ISIN keys to uppercase.
- **xlrd 1.2.0 must be pinned** — `pip install xlrd` gets 2.x which only reads `.xlsx`. Always `xlrd==1.2.0`.
- **ISIN lookup for buys** — scrip-wise report only has current holdings (sell stocks). For buys, ISIN falls through to isin_database or name lookup.
- **JS class-stamping for ISIN button** — `st.markdown('<div class="foo">')` + `st.file_uploader` renders as siblings (not parent-child). CSS descendant selectors don't match. Must stamp class directly on the element via JS MutationObserver.
- **Tolerance in Step 2** — `tolerance` widget only renders in Step 1. Step 2 must read `st.session_state.get("p1_tolerance", 0.0)`. Do not use `tolerance` as a bare variable in Step 2.

---

## 16. What Is Not Yet Done

- **Full test suite** — `tests/` folder has structure but coverage is not complete.
- **Streamlit deployment** — not set up. App runs locally only.
- **ISIN database edit/delete** — intentionally out of scope. Research team edits CSV directly.
- **Email integration** — out of scope.
- **Tolerance in broker file** — decided: tolerance is internal only, broker gets plain Ref Price.

---

## 17. The Raw Test Instance (`pms_raw/`)

Located at `C:\Yatharth\pms_raw\app_raw.py`. **Not in git.**

Purpose: test the processing logic with real files without any UI styling.
Uses `sys.path.insert(0, r"C:\Yatharth\pms_tool")` to import directly from the main project.
Zero code duplication — same functions, same logic.

Extra features vs main app:
- Shows every intermediate DataFrame
- Weight check table per ISIN+Direction (confirms weights sum to 1.0)
- Charge totals verification table
- Download buttons for session file and broker file

Run: `python -m streamlit run C:\Yatharth\pms_raw\app_raw.py --server.port 8502`

---

## 18. Continuing from a New Session

If picking this up fresh (new device, new Claude Code account, etc.):

1. Clone repo: `git clone https://github.com/yathnagada1999/pms-tool`
2. Install: `pip install -r requirements.txt`
3. Run: `python -m streamlit run app.py`
4. Read `CLAUDE.md` first (git protocol, business rules), then this file

The `CLAUDE.md` has the git push protocol (password required before every push).
This file (`HANDOFF.md`) has everything else.
See `HOW_TO_HANDOFF.md` for the exact starting prompt to use in a new LLM session.

---

*Last updated: after commit 6d3ab85*
