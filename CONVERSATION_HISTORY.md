# PMS Tool — Conversation History & Design Decisions

> This document captures the key discussions, decisions, and evolution of the project
> as it was built. It is written for any LLM picking up this project — read it to
> understand not just what was built, but why, and what was explicitly rejected.

---

## Project Origin

Built from scratch in a single extended Claude Code session. The client is Guardian Capital,
a PMS (Portfolio Management Service) fund. The tool automates their daily equity execution
workflow — previously done manually in Excel.

The original spec was captured in a `CLAUDE.md` planning document before any code was written.
A full architecture plan was discussed and agreed on first, then built phase by phase.

---

## UI Philosophy (Established Early)

The user wanted a **premium, professional feel** — not a generic Streamlit app.

Key decisions made:
- **Font pairing**: Cormorant Garamond (serif, for headings) + DM Sans (sans-serif, for body).
  Cormorant gives a wealth-management / institutional feel. DM Sans keeps it clean.
- **Colour palette**: warm neutrals (cream, beige, ink) with gold (`#D9B244`) as the only accent.
  Gold = premium. No blue Streamlit defaults anywhere.
- **No Streamlit chrome**: menu, footer, header, deploy button all hidden via CSS.
- **Step-based wizard**: not tabs within a page. Linear flow. User always knows where they are.
- **Animations**: subtle fade-in (`fadeSlide`, 0.3s) on every page transition. Not flashy.

The user reviewed every screen and gave iterative feedback. The UI went through multiple
rounds of revision.

---

## Part 1 — Upload Page Evolution

**Original**: Standard Streamlit file uploaders in a grid.

**Problem raised by user**: Upload cards were inconsistent sizes. File icon and name were not
centered inside the card after upload.

**Solution**: Extensive custom CSS to make file uploaders look like fixed-height cards.
- Empty state: dashed gold border, cloud SVG icon via CSS `::before`
- Uploaded state: file info absolutely centered inside card, × delete button pinned top-right
- The uploaded file list overlay was positioned absolute over the dropzone so card height never changed
- Later fix: filename text wrapping — added `white-space: normal`, `word-break: break-word`,
  `flex: 1`, `min-width: 0` on the filename element so long filenames don't overflow the card

**Key constraint discovered**: Streamlit 1.54 has a specific DOM structure for file uploaders.
The CSS selectors are fragile. If Streamlit is upgraded, re-test upload cards first.

---

## Part 1 — Validate Orders Page Evolution

### Status bar
**Original proposal**: Single summary line of text ("X ready, Y blocked").

**User feedback**: Wanted visual blocks, not plain text.

**Built**: Split-badge pattern — two connected boxes: label on left (lighter bg), number on right
(darker bg). Green for Orders Ready, red for Orders Blocked. This pattern was then reused
everywhere in the app (Stocks/Clients in Part 2, download buttons).

### Table structure
**Original approach**: Single `st.dataframe` with all columns.

**Problem**: `st.dataframe` doesn't support row background colouring AND checkbox editing
at the same time.

**Solution decided**: Split into two side-by-side Streamlit columns:
- Narrow column (0.7 ratio): `st.data_editor` with ONLY the Include checkbox column
- Wide column (8.3 ratio): `st.dataframe` with pandas Styler for row colours

Both set to `auto` height so the PAGE scrolls — rows stay naturally in sync without any JS.

### Column order
Evolved through discussion:
- Early version: Status | Reason | Context at the end
- User request: Context (Available/Held) should be immediately to the right of Qty
- Later: "Ref Price" column replaced with "Amount" (Value = Qty × Ref Price, comma-formatted)
- Final order: S.No | Client | Ticker | Direction | Qty | Available/Held | Amount | Status | Reason

### Amount column (replaced Ref Price)
**Decision**: Show Amount (Qty × Ref Price) instead of Ref Price — more meaningful for ops.
- Formatted with comma separators: `1,23,456.78` (pandas Styler lambda format)
- `st.column_config.TextColumn` used instead of NumberColumn because `%,.2f` sprintf format
  is not supported by Streamlit's NumberColumn (caused a "Failed to format" error)
- Fix: use `TextColumn` + pandas Styler `.format(lambda v: f"{v:,.2f}")` combination

### Tolerance-adjusted Amount
**Discussion**: When tolerance is set (e.g. 2%), the Amount column should show worst-case:
- Buy rows: `Qty × Ref Price × (1 + tolerance/100)` — client may pay more
- Sell rows: `Qty × Ref Price × (1 - tolerance/100)` — client may receive less
- Zero tolerance: plain `Qty × Ref Price` for both (no change)

**Implementation**: Applied in `app.py` when building `editor_df`, after copying from `vdf`.
`tolerance` read from `st.session_state.get("p1_tolerance", 0.0)` — needed because the
tolerance widget is only rendered in Step 1 but the table is rendered in Step 2.

**Bug fixed**: Initial implementation used `tolerance` as a local variable name, but in Step 2
it's out of scope. Fix: read from `st.session_state["p1_tolerance"]` directly.

### S.No and Qty column formatting
- S.No: `NumberColumn(format="%d")` — no decimals, shows as integer
- Qty: `NumberColumn(format="%.2f")` — 2 decimal places
- Both had many decimals showing before (float64 default)

### Context column format
- Sells: `"X Units"` (e.g. `"200 Units"`)
- Buys: `"Available: ₹X"`

### Exclude buttons
**Decision**: No icons. Semantic colours only — Exclude All Red gets red-tinted styling,
Exclude Entire Batch gets dark neutral styling. Implemented via JS MutationObserver.

### Status labels
**Decision**: Don't show GREEN/RED (internal) — show READY/BLOCKED (user-facing).
Done via pandas Styler `.format()`.

---

## Part 1 — Export Page Evolution

**Original**: Two separate `st.download_button` widgets.

**User request**: Make them look like split-badge blocks. Add "Download Both Files".

**Problem**: `st.download_button` can't be styled like a badge AND can't download two files.

**Solution**: `components.html` iframe with data-URI `<a download>` anchors styled as badges.
"Download Both" is a `<button>` that JS-clicks both anchors with a 400ms gap.

### Date-stamped filenames
**Decision**: All downloaded files include today's date in `DD_MM_YYYY` format:
- `session_file_27_05_2026.xlsx`
- `broker_file_27_05_2026.xlsx`
- `orbis_allocation_27_05_2026.xlsx`

`_TODAY = date.today().strftime("%d_%m_%Y")` defined once at module level in `app.py`.

### Batch number in filenames
**Decision**: Session file and broker file also include the batch number:
- `session_file_27_05_2026_batch_1.xlsx`
- `broker_file_27_05_2026_batch_2.xlsx`

Batch number extracted from `session_df["Batch"].max()` at the point of generating download links.
Allocation file does NOT include a batch number (it corresponds to the whole session).

---

## Client Name Suffix Stripping

**Problem discovered**: Research team appends suffixes to client names:
- `"EPSILON HOLDINGS PRIVATE LIMITED-1"`, `"USHA SARVARAYALU- New"`, `"XYZ - Old"`
- Orbis expects clean names: `"EPSILON HOLDINGS PRIVATE LIMITED"`, `"USHA SARVARAYALU"`

**Solution**: Regex in `read_research_file()` strips trailing dash suffixes at read time:
```python
.str.replace(r'\s*-\s*\w+\s*$', '', regex=True)
```
Pattern: optional space + dash + optional space + word characters at end of string.
Runs only on the `Client` column. No other column is touched.

---

## Company Name → ISIN Resolution (3-Step Lookup)

**Problem**: Research team sometimes writes full company names in the Ticker column
(e.g. "AU SMALL FINANCE BANK LTD") instead of NSE tickers (e.g. "AUBANK").

**Solution**: Three-step ISIN lookup in `validator.py`:
1. **Scrip-wise report** — exact match on Scrip Name (case-insensitive)
2. **ISIN database** — NSE Code lookup, then BSE Code fallback (O(1) via index)
3. **Name-based fuzzy lookup** — `lookup_isin_by_name()` in `isin.py`

**Sell validation change**: Originally merged on (OFIN, Ticker) — broke when Ticker was a
full company name. Changed to merge on (OFIN, ISIN) — format-agnostic, works regardless
of what the research team writes in the Ticker column.

### Fuzzy name matching algorithm
`lookup_isin_by_name()` in `utils/isin.py`:
- Tokenize both names: strip punctuation, uppercase, remove single-char tokens + stop words
- Stop words: LTD, LIMITED, SERVICES, SERVICE, CORP, CORPORATION, INC, CO, THE, AND, OF,
  PVT, PRIVATE, PUBLIC, GROUP, ENTERPRISES, ENTERPRISE, INDIA, INDIAN, HOLDINGS, HOLDING
- `BANK` intentionally NOT a stop word — removing it caused "HDFC BANK" to fail (only 1 token left)
- Require ≥2 tokens OR 1 token of length ≥5 (allows "INFOSYS" to match, blocks "TCS" false positives)
- Every token in shorter list must prefix-match a token in longer list
- Score = matched / max(len(db_tokens), len(research_tokens)); take best score

**Examples that work**:
- `"AU SMALL FINANCE BANK LTD"` → AU Small Finance Bank → AUBANK ISIN
- `"BAJAJ FINANCE LTD"` → Bajaj Finance → BAJFINANCE ISIN
- `"HDFC BANK LTD"` → HDFC Bank → HDFCBANK ISIN
- `"INFOSYS LIMITED"` → 1 token ≥5 chars → INFY ISIN
- `"MOTILAL OSWAL FINANCIAL..."` → prefix matches "Motil.Oswal.Fin." in DB → MOTILALOFS ISIN

**Performance note**: Name lookup scans the full 5,324-row DB. For files with 20-30 orders,
this is acceptable (< 1 second). Not a bottleneck.

---

## ISIN Database — Bulk Update Feature

**Request**: Allow uploading a CSV file to add multiple ISINs at once.
Existing ISINs (by ISIN Code) are skipped to avoid duplicates.

**Implementation**: `bulk_update_isin_database(file)` in `utils/isin.py`.
Reads `Name | BSE Code | NSE Code | ISIN Code` columns, deduplicates against existing,
appends new rows, saves CSV. Returns `(added, skipped)` counts.

**UI placement**: Top-right of ISIN Database page — a compact button (not a full uploader card).

**Technical challenge**: Getting a small button-style uploader required hiding the default
Streamlit dropzone UI. Approach that worked: JS MutationObserver stamps a CSS class
(`isin-uploader-btn`) directly onto the `stFileUploader` DOM element after Streamlit renders.
Then CSS targeting that class collapses the dropzone, shows a custom "Update ISIN Database"
label via `::after`, gold hover effect.

**Why wrapper div approach failed**: `st.markdown('<div class="foo">')` + `st.file_uploader`
renders as siblings in the DOM, not parent-child. So CSS descendant selectors like
`.foo .stFileUploader` never match.

**Result feedback**: After upload, inline coloured div shown:
- Green: `"4 new ISINs added"` 
- Amber: `"All ISINs already present"`
Stored in `st.session_state.isin_bulk_msg`, auto-cleared after display.

---

## Part 2 — Allocation File Evolution

### Buy/Sell casing
**Found by comparing with Ops team file**: Our tool wrote `BUY`/`SELL`, Ops team uses `Buy`/`Sell`.
**Fix**: `row["Direction"].title()` in `allocator.py`. One-character change.

### InputTurnOver precision
**Request**: InputTurnOver should be computed and stored at 4 decimal places.
**Implementation**: `_CHARGE_PRECISION = {"InputTurnOver": 4}` dict in `allocator.py`.
All other charge columns round to 2dp. Last client always gets full-precision residual.

**Later request**: Excel should display InputTurnOver as 2dp (but full value still stored/expandable).
**Fix**: `_COL_NUMBER_FORMAT = {"InputTurnOver": "0.00"}` in `writer.py`.
Excel number format `"0.00"` is display-only — underlying float value unchanged.
User can click "Increase Decimal" in Excel to see more precision.

### TradeDate format
Changed from `DD-MMM-YYYY` (e.g. `15-May-2026`) to `DD-MM-YYYY` (e.g. `15-05-2026`).
Excel number format string: `"DD-MM-YYYY"`.

### Allocation file formatting (Aptos Narrow)
**Request**: Complete formatting overhaul to match professional standards.

| Element | Before | After |
|---------|--------|-------|
| Font | Default | Aptos Narrow, size 11 (all cells) |
| Header fill | Blue (`#1F4E79`) | No fill |
| Header text | White, bold | Black, bold |
| Data alignment | Default (right for numbers) | center+center for all; left+center for Client Name |
| Cell borders | None | Thin border on all cells (header + data) |

`Border`, `Side` imported from `openpyxl.styles`. `_THIN_SIDE = Side(style="thin")`,
`_CELL_BORDER = Border(left=..., right=..., top=..., bottom=...)`.
Applied to every cell in both header row and data rows.

### InputNetRate floating-point note
When comparing our allocation file vs Ops team file:
- All 45 rows matched exactly on every numeric column
- Only difference: `Buy/Sell` casing (fixed)
- Tiny 11th-decimal differences in InputNetRate (e.g. `3377.18078431373` vs `3377.18078431372`)
  are IEEE 754 floating-point representation — not a bug, not meaningful for Orbis.

---

## Part 2 — Review & Download Page Evolution

**Original**: Title left-aligned, subtitle present, inline pills for stock/client count.

**User changes requested**:
- Center the "Allocation Complete" title
- Remove the subtitle
- Replace inline pills with split-badge blocks (same pattern as Part 1 status bar)
- Both blocks in green

**Final**: Centered title, two green split-badge blocks (Stocks | N, Clients | N), then warnings, then download.

---

## ISIN Database Tab

Straightforward — no major discussions. Simple search + add form.
One subtle decision: `get_isin_db.clear()` (scoped cache clear) instead of
`st.cache_data.clear()` (clears ALL caches globally).

---

## Tolerance Feature

**Price tolerance** is a percentage buffer used in buy validation.

**Buy validation**: `available_cash >= qty × ref_price × (1 + tolerance/100)`

**Sell validation**: tolerance does NOT affect whether a sell is green/red
(only units held vs units ordered matters).

**Amount column display**: Shows worst-case amounts:
- Buy: `Qty × Ref Price × (1 + tolerance/100)`
- Sell: `Qty × Ref Price × (1 - tolerance/100)`
- Zero tolerance: plain `Qty × Ref Price` for both

**Broker file**: Tolerance does NOT appear in the broker file. It is purely an internal
cash buffer check. Broker receives plain Ref Price (Option 4 — explicitly decided).

**Tolerance > 5%**: Shows a warning banner. No confirmation gate (decided: warning only).

---

## Code Quality Fixes (From Audit)

| # | Finding | Decision |
|---|---------|----------|
| 1 | Empty DataFrame edge case in scrip report | No impact — skip |
| 2 | Client holding same stock in multiple scrip rows | Never happens — skip |
| 3 | Tolerance applied to ref price not execution price | No impact — skip |
| 4 | CP Code blank cells flagged | **Implement** — amber highlight in session Excel |
| 5 | Tolerance > 5% confirmation gate | Warning only, no modal |
| 6 | Dual-exchange same-day edge case | Doesn't occur in practice — skip |
| 7 | Normalised broker schema naming | Accepted current approach |
| 8 | Session file CP Code amber highlight | **Implement** — `#FEF3C7` fill on blank cells |
| 9 | ISIN database duplicate check | No duplicates — skip |
| 10 | Cache clear scoping | **Implement** — `get_isin_db.clear()` |
| 11 | O(1) ISIN lookup index | **Implement** — `build_isin_index()` |
| 12 | Int64 for Batch/S.No columns | **Implement** — avoids `1.0` display issue |
| 13 | auto-width default=0 guard in writer | **Implement** — prevents crash on empty DataFrame |

---

## Critical Bug Fixes (Found in Code Audit)

1. **`file.seek(0)` missing** — in Ambit and InCred broker reply readers.
   `openpyxl.load_workbook` consumed the file stream. `pd.read_excel` then read an empty stream.

2. **`assert` instead of `raise ValueError`** — in allocator weight check.
   `assert` is disabled in optimised mode (`python -O`).

3. **InCred CP Code ISIN key not uppercased** — `get_incred_cp_codes()`.
   Session file ISINs were upper, InCred dict keys were mixed case. Lookup always failed.

---

## Em Dash Decision

**Decision**: Replace every em dash (`—`) with a plain hyphen (`-`). No em dashes anywhere.

---

## Git Push Protocol

- Always ask before pushing
- Require a password confirmation
- If the user includes the password in their message (`git push pcom`), push immediately
- If not, ask for the password and wait
- **STRICTLY FORBIDDEN**: Never reveal, repeat, hint at, or display the password

Local commits (`git add` + `git commit`) are fine any time without asking.
Only `git push` requires the password.

---

## Things Explicitly Decided NOT To Do

- No yellow/amber validation rows (ref price always present)
- No confirmation gate for tolerance > 5% (warning only)
- No ISIN database edit or delete UI
- No email integration
- No deployment/cloud setup
- No login or authentication
- No live price feed
- No partial execution handling
- No icons on Exclude buttons
- No zip download for "Download Both" (both excels separately)
- No tolerance value in broker file (internal buffer only)

---

## Styling Patterns Established — Use These For Any New Screens

### New page title (centered)
```python
st.markdown(
    '<div style="margin:0.3rem 0 1.4rem 0;text-align:center">'
    '<div style="font-family:\'Cormorant Garamond\',Georgia,serif;'
    'font-size:2rem;font-weight:600;color:#1C1714;line-height:1;margin-bottom:5px">'
    'Page Title</div>'
    '<div style="font-size:0.83rem;color:#958F87;font-family:\'DM Sans\',sans-serif;'
    'font-weight:300">Subtitle text here.</div>'
    '</div>', unsafe_allow_html=True
)
```

### Split badge block (green)
```python
f'<div style="display:flex;border:1px solid rgba(22,163,74,0.28);'
f'border-radius:8px;overflow:hidden;height:38px">'
f'<div style="padding:0 14px;display:flex;align-items:center;'
f'background:rgba(22,163,74,0.05);font-size:0.67rem;color:#16a34a;'
f'letter-spacing:0.65px;text-transform:uppercase;font-weight:400;'
f'font-family:\'DM Sans\',sans-serif;white-space:nowrap">LABEL</div>'
f'<div style="padding:0 18px;display:flex;align-items:center;'
f'background:rgba(22,163,74,0.1);font-size:1rem;font-weight:600;'
f'color:#16a34a;font-family:\'DM Sans\',sans-serif;'
f'border-left:1px solid rgba(22,163,74,0.2)">{value}</div>'
f'</div>'
```

### Warning banner
```python
st.markdown(
    '<div style="background:#FBF5E3;border:1px solid rgba(217,178,68,0.3);'
    'border-left:3px solid #D9B244;border-radius:6px;padding:0.75rem 1rem;'
    'font-size:0.82rem;color:#6B5718;margin-bottom:0.6rem;'
    'font-family:\'DM Sans\',sans-serif;font-weight:400">'
    'Warning text here</div>', unsafe_allow_html=True
)
```

### Section label (uppercase muted)
```python
st.markdown(
    '<div style="font-size:0.67rem;color:#B0A89E;font-family:\'DM Sans\',sans-serif;'
    'font-weight:400;letter-spacing:0.65px;text-transform:uppercase;margin-bottom:8px">'
    'SECTION LABEL</div>', unsafe_allow_html=True
)
```

### Styled dataframe (with row colours + wrap)
```python
styled = (
    df.style
    .apply(row_style_fn, axis=1)
    .set_properties(**{"white-space": "normal"})
)
st.dataframe(styled, use_container_width=True, hide_index=True)
```

---

*Last updated: after commit 6d3ab85 (tolerance NameError fix)*
