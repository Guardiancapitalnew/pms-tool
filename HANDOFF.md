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

The single exception: `data/isin_database.csv` persists on disk (5,324 listed companies).

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
├── requirements.txt          # Pinned dependencies
├── data/
│   └── isin_database.csv     # 5,324 rows: Name | BSE Code | NSE Code | ISIN Code
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
│   └── isin.py               # ISIN DB load/lookup/add
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
`https://github.com/yathnagda1999/pms-tool`

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

### Fonts
- **Cormorant Garamond** (serif, 600) — all headings, section titles, large numbers
- **DM Sans** (sans-serif, 300/400/500) — all body text, labels, buttons

### Component patterns

#### Split badge (used for status + download buttons)
Two-part box: left side = label (lighter bg), right side = value/action (darker bg).
Separated by a 1px border. Used for: Orders Ready/Blocked, Stocks/Clients, file downloads.
```html
<div style="display:flex; border:1px solid ...; border-radius:8px; overflow:hidden; height:38px">
  <div style="padding:0 14px; ... background:rgba(...)">LABEL</div>
  <div style="padding:0 18px; ... border-left:1px solid ...">VALUE</div>
</div>
```

#### Section headers
Centered (Part 1 Validate, Part 2 Upload/Results) or left-aligned (Part 1 Upload).
```python
st.markdown(
    '<div style="margin:0.3rem 0 1.4rem 0; text-align:center">'
    '<div style="font-family:Cormorant Garamond; font-size:2rem; ...">Title</div>'
    '<div style="font-size:0.83rem; color:#958F87; ...">Subtitle</div>'
    '</div>', unsafe_allow_html=True
)
```

#### Upload cards
Custom CSS makes Streamlit's `st.file_uploader` look like cards:
- Empty state: dashed gold border, cloud upload icon (SVG injected via `::before`)
- Uploaded state: solid border, file name centered, × delete button top-right
- `min-height: 140px` on dropzone so all cards are consistent height

#### Row-colour table (validation)
Uses pandas Styler passed to `st.dataframe` — renders as HTML (not canvas), so CSS applies.
Green rows: `rgba(22,163,74,0.07)` bg. Red rows: `rgba(220,38,38,0.06)` bg.
`set_properties(white-space: normal)` added for text wrapping.

#### Split table (validate orders)
Two side-by-side columns: narrow (0.7) for checkboxes only, wide (8.3) for the styled table.
Both auto-height so page scrolls — keeps rows visually in sync without JS.

#### Download via data-URI (Part 1 Export)
`st.download_button` only downloads one file. For "Download Both", used `components.html`
with data-URI `<a download>` anchors + JS to click both with 400ms gap:
```javascript
var badges = document.querySelectorAll('a.dl-badge');
badges[0].click();
setTimeout(function(){ badges[1].click(); }, 400);
```

#### Stepper
Centered horizontal pill stepper. Active step: dark fill + gold text. Done steps: muted.
Connector lines turn gold when done. Built in pure HTML/CSS, rendered via `st.markdown`.

---

## 8. Function Reference

### `utils/isin.py`
| Function | Purpose |
|----------|---------|
| `load_isin_database()` | Reads `data/isin_database.csv`. Decorated with `@st.cache_data` in app.py. |
| `build_isin_index(db)` | Returns `{uppercase_ticker: isin}` dict for O(1) lookups. BSE first, NSE overwrites (NSE priority). |
| `lookup_isin(ticker, db, _index)` | Returns ISIN string or None. Uses index if provided, else DataFrame scan. |
| `add_isin_entry(name, nse, bse, isin)` | Appends row to CSV, re-saves. Call `get_isin_db.clear()` after to reset cache. |

### `utils/reader.py`
| Function | Returns |
|----------|---------|
| `read_research_file(file)` | DataFrame — all research order columns |
| `read_bank_book(file)` | `dict[OFIN str → balance float]` |
| `read_scrip_wise_report(file)` | DataFrame — OFIN, Scrip Name, ISIN, Quantity |
| `read_session_file(file)` | DataFrame — 10 SESSION_COLUMNS |
| `read_broker_reply_ambit(file)` | Raw Ambit DataFrame |
| `read_broker_reply_incred(file)` | Raw InCred DataFrame (numeric casting applied) |

**Critical**: `file.seek(0)` is called inside both broker reply readers between the
openpyxl sheet-check and the `pd.read_excel` call. Without this, `pd.read_excel` reads
an empty stream. Do not remove.

### `utils/writer.py`
| Function | Returns |
|----------|---------|
| `to_excel_bytes(df, sheet_name)` | Generic: df → bytes |
| `write_session_file(session_df)` | Session file with bold headers + amber highlight on blank CP Code cells (`#FEF3C7`) |
| `write_allocation_file(allocation_df)` | Blue header row + number format 0.00 on charge cols + date format on TradeDate |

### `part1/validator.py` — `validate_orders()`
Returns research_df enriched with: `ISIN`, `Status` (GREEN/RED), `Reason`, `Context`.

**Sell logic**: merge research rows with scrip_df on (OFIN, Ticker upper). No match → RED.
Zero held → RED. Held < ordered → RED with "Insufficient units - holds X, needs Y". Else GREEN.
Context format: `"X Units"` (e.g. `"200 Units"`).

**Buy logic**: look up OFIN in bank_book. Deduct committed cash from existing session.
`required = qty × ref_price × (1 + tolerance/100)`. Not in bank book → RED.
Negative available → RED. Available < required → RED with cash amounts.
Context format: `"Available: ₹X"`.

**ISIN lookup order**: scrip_df first (by Ticker = Scrip Name, uppercase), then isin_db via index.

**Committed cash** = sum(Qty × Ref Price) for BUY rows in `existing_session_df`, grouped by OFIN.
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

Dual-exchange edge case (same ISIN on NSE+BSE same day): handled separately, allocator
does the per-exchange split.

### `part2/allocator.py` — `allocate_costs()`
For each ISIN+Direction group:
1. `weight = client_qty / total_qty`
2. Verify `sum(weights) ≈ 1.0` via `math.isclose()` — raises `ValueError` if not
3. Each charge col: `client_share = round(weight × broker_total, 2)`
4. Last client: `residual = broker_total - sum(others)` — full precision, no rounding
5. `InputNetRate = InputNetAmount / Input Quantity` — full precision

**19 output columns** (exact order matters for Orbis import):
`S.No | Client Name | CustomerNo | TradeDate | Exchange Type | Settlement No | ISIN No | Buy/ Sell | Input Quantity | InputBrokerage | InputSTT | InputStampDuty | InputSEBIChrg | InputTurnOver | InputOtherCharges | InputGST | InputNetAmount | InputNetRate | CP CODE`

---

## 9. All Screens — What Each Does

### Part 1 — Step 1: Upload & Configure
- 3 mandatory upload cards: Research File (.xlsx), Bank Book (.xlsx), Scrip-wise Report (.xls)
- 1 optional: Existing Session File (.xlsx) — for second batch of day
- Tolerance % input (default 0, warning if > 5%)
- "Validate Orders" primary button (gold) — triggers validation, advances to Step 2
- Title + subtitle centered

### Part 1 — Step 2: Validate Orders
- Centered title "Validate Orders"
- Split-badge status bar: `Orders Ready | N` and `Orders Blocked | N`
- "Exclude All RED" button (red-tinted) + "Exclude Entire Batch" button (dark)
- Split table: narrow checkbox column (0.7) + wide styled table (8.3)
  - Column order: S.No | Client | Ticker | Direction | Qty | Units Held/Cash | Ref Price | Status | Reason
  - Status shows "READY" (green rows) or "BLOCKED" (red rows)
  - Context column renamed "Available / Held" in display
- Sticky bottom bar: "Generate Session File + Broker File" button
  - Disabled if any RED row is still checked OR zero rows included
- JS patches: semantic button colours (red-tinted Exclude All Red, dark Exclude Batch), hide "Press Enter to apply" hint

### Part 1 — Step 3: Export
- Section label "FILES READY"
- 3 split-badge download links (via components.html data-URI):
  - Session File (grey label + gold download)
  - Broker File (grey label + gold download)
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
- Allocation summary table (aggregated by scrip)
- Centered split-badge download: "Orbis Allocation File | Download"

### ISIN Database Tab
- Search input → filters live
- `st.dataframe` showing filtered results (height=400)
- Total entry count
- Add New Entry form: Company Name, NSE Code, BSE Code, ISIN Code
- On add: writes to CSV, clears cache with `get_isin_db.clear()`

---

## 10. Key Technical Decisions & Why

| Decision | Why |
|----------|-----|
| Single `app.py`, step-based | No sidebar/multipage complexity. Steps are linear — wizard flow fits best. |
| `components.html` for downloads | `st.download_button` only handles one file. Data-URI anchors + JS enables multi-file download. |
| Pandas Styler for validation table | Need row background colours AND to rename/reorder columns. Styler renders as HTML (not canvas), so CSS like `white-space:normal` works. |
| Split table (checkbox + styled) | `st.data_editor` has limited styling. Narrow checkbox editor + wide styled dataframe in side-by-side columns — page scroll keeps them in sync without JS. |
| `xlrd` for scrip-wise report | Orbis exports `.xls` (Excel 97-2003). `xlrd` 1.2.0 is the last version with `.xls` support. pandas dropped it. |
| `file.seek(0)` in broker readers | `openpyxl.load_workbook` consumes the file stream. Must reset before `pd.read_excel`. |
| `build_isin_index()` | ISIN DB has 5,324 rows. Without the index, every `lookup_isin` call scans the whole DataFrame. With the index, it's O(1). |
| `get_isin_db.clear()` | `@st.cache_data` caches by function. Must clear the specific function's cache, not `st.cache_data.clear()` (which clears everything). |
| Last-client residual (no rounding) | Rounding 2dp on each client leaves a rounding error that accumulates. Last client absorbs the full residual so broker total always equals sum of client totals exactly. |
| `Int64` for Batch/S.No | Pandas nullable integer — handles NaN from `pd.to_numeric` without converting to float64 (which would show `1.0` instead of `1`). |
| No yellow validation state | Ref Price is always present in the research file. Yellow was planned for "market order — no price to validate" but the team always provides prices. |

---

## 11. CSS Architecture

All CSS is in the `CSS` constant at the top of `app.py`, injected via `st.markdown(CSS, unsafe_allow_html=True)`.

**Key CSS blocks and what they do:**
- **Base reset**: DM Sans globally, white background, hide Streamlit chrome (menu/footer/header/deploy button)
- **Block container**: `padding-left/right: 3rem`, `max-width: 100%`
- **Stepper**: `.step-pill`, `.step-pill.active`, `.step-pill.done`, `.step-line`
- **Upload cards**: Complex multi-state CSS — empty (dashed gold), uploaded (solid border, file info centered), delete button top-right
- **File uploader cloud icon**: Injected via `::before` pseudo-element with inline SVG data-URI
- **Buttons**: Primary = gold fill (`#D9B244`), Secondary = gold-outlined gradient, disabled = muted beige
- **Column headers**: `[role="columnheader"]` → `background: #E8E0D2 !important`
- **Hide "Press Enter"**: `[data-testid="InputInstructions"] { display: none !important; }`
- **Scrollbar**: Thin (4px), gold thumb

**JS patterns (via `components.html` iframes and inline `<script>` in `st.markdown`):**
- Logo click → navigate to Part 1 home (sets `st.session_state` via Streamlit's component bridge)
- Sticky bottom bar in validate step: `position: sticky; bottom: 0`
- Semantic button colours: MutationObserver + setInterval to stamp `.exclude-red` and `.exclude-batch` classes on buttons, then CSS colours them
- Download Both: JS queries `a.dl-badge` anchors, clicks first, setTimeout 400ms, clicks second

---

## 12. Input File Specs (Quick Reference)

| File | Sheet | Key Columns | Notes |
|------|-------|-------------|-------|
| Research File | `Orders` | S.No, OFIN, Client, Ticker, Direction, Qty, Ref Price, Value, CP Code | Value = informational only |
| Bank Book | `Bank Balance Summary` | OFIN Code, Balance | Dynamic header scan. Skip "Total" rows. |
| Scrip-wise Report | `file` | Scrip Name, Item No (=ISIN), Client Code (=OFIN), Quantity | `.xls` format. Skip "Scrip Total" rows. |
| Session File | `Session` | S.No, Batch, OFIN, Client, Ticker, ISIN, Direction, Qty, Ref Price, CP Code | Output of Part 1, input of Part 2 |
| Ambit Reply | `Sheet1` | Transaction Date, Exchange, ISIN No., Transaction Type, quantity, + charge cols | TradeDate from file |
| InCred Reply | `Incred_Capital_Trade_Confirmati` | Exchange, ISIN No., Transaction Type, Quantity, + charge cols, CP CODE | TradeDate = today |

---

## 13. Git History

| Commit | What it did |
|--------|-------------|
| `bce0f62` | Initial commit — full working codebase (all logic + UI) |
| `488ebfd` | Pin streamlit to 1.54.0 |
| `e3537c4` | Pin all dependencies to exact versions |
| `c0271ad` | Redesign Part 1 upload layout |
| `56d6442` | Polish upload cards (consistent box sizes, centered file info) |
| `884db0b` | Polish Validate Orders UI (badges, row colours, sticky bar, table tweaks) |
| `84e7669` | Redesign Part 1 Download (split-badge downloads, spacing, icons) |
| `6dfebb5` | Redesign Part 2 Download (centered split-badge) |
| `c0161cd` | UX: hide "Press Enter" hint, logo click → home |
| `8bac8f1` | Fix 3 critical bugs: file.seek(0), assert→ValueError, InCred ISIN .upper() |
| `8cf265e` | Quality fixes + em dash cleanup + Part 2 UI polish (Stocks/Clients badges, centered headers) |
| `d2545ff` | Validate table: Context column next to Qty, "X Units" format |

---

## 14. Known Quirks

- **Streamlit 1.54.0 is pinned** — newer versions changed upload card DOM structure. Do not upgrade without re-testing all upload card CSS.
- **components.html iframes** — download badges live inside iframes. JS uses `document` (not `window.parent.document`) since the anchor clicks are within the iframe. Height must be set correctly or buttons clip.
- **Canvas vs HTML rendering** — `st.dataframe` with a raw DataFrame uses canvas (glide-data-grid). `st.dataframe` with a pandas Styler uses HTML. Only HTML tables respect CSS from `set_properties`. This is why all styled tables use a Styler.
- **InCred CP Code** — stored as `CP CODE` (all caps) in the InCred reply. The reader looks for this column. `get_incred_cp_codes` normalises ISIN keys to uppercase for consistent lookup.
- **xlrd 1.2.0 must be pinned** — `pip install xlrd` gets 2.x which only reads `.xlsx`. The scrip-wise report is `.xls`. Always `xlrd==1.2.0`.
- **ISIN lookup for buys** — scrip-wise report only has current holdings (sell stocks). For buys, the ISIN will typically not be in the scrip report and falls through to the isin_database.

---

## 15. What Is Not Yet Done (from original plan)

- **Full test suite** — `tests/` folder has structure but coverage is not complete. The `conftest.py` and some test files exist.
- **Streamlit deployment** — not set up. App runs locally only.
- **ISIN database edit/delete** — intentionally out of scope. Research team edits CSV directly.
- **Email integration** — out of scope.
- **Tolerance > 5% confirmation gate** — decided to keep as warning-only (no modal gate).

---

## 16. The Raw Test Instance (`pms_raw/`)

Located at `C:\Yatharth\pms_raw\app_raw.py`. **Not in git.**

Purpose: test the processing logic with real files without any UI styling.
Uses `sys.path.insert(0, r"C:\Yatharth\pms_tool")` to import directly from the main project.
Zero code duplication — same functions, same logic.

Extra features vs main app:
- Shows every intermediate DataFrame (parsed research, bank book, scrip report, etc.)
- Weight check table per ISIN+Direction (confirms weights sum to 1.0)
- Charge totals verification table (allocated total vs broker total per charge column)
- Download buttons for session file and broker file

Run: `python -m streamlit run C:\Yatharth\pms_raw\app_raw.py --server.port 8502`

---

## 17. Continuing from a New Session

If picking this up fresh (new device, new Claude Code account, etc.):

1. Clone repo: `git clone https://github.com/yathnagada1999/pms-tool`
2. Install: `pip install -r requirements.txt`
3. Run: `python -m streamlit run app.py`
4. Claude Code will auto-read `CLAUDE.md` — read this file (`HANDOFF.md`) too for full context

The `CLAUDE.md` has the git push protocol (password required before every push).
The `HANDOFF.md` (this file) has everything else.

---

*Last updated: after commit d2545ff*
