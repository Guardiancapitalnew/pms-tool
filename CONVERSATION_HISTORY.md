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
InputNetAmount also rounded to 2dp for non-last clients; last client always gets
`broker_total - sum(all_others)` with full precision.

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

### Ops team file comparison
A side-by-side comparison of our generated allocation file vs the Ops team's manually prepared
file was done (45-row file). Result:
- All 45 rows matched exactly on every numeric column
- Every charge column (Brokerage, STT, StampDuty, SEBI, TurnoverTax, OtherCharges, GST,
  NetAmount, InputNetRate) — identical values across all rows
- Only difference found: `Buy/Sell` casing (our tool produced `BUY`/`SELL`; Ops team uses `Buy`/`Sell`)
  → fixed with `.title()` in allocator

**InputNetRate floating-point note**: Tiny 11th-decimal differences visible when comparing
individual cells (e.g. `3377.18078431373` vs `3377.18078431372`) are IEEE 754 floating-point
representation artifacts — not a bug, not meaningful for Orbis.
Both tools perform the same `NetAmount / Qty` division; the final bit of the float representation
can differ depending on intermediate precision and compiler.

### Why `file.seek(0)` matters in broker readers
`openpyxl.load_workbook` is called first to get the sheet list for validation.
This advances the file pointer to end-of-stream.
`pd.read_excel` is then called on the same BytesIO object — if the pointer isn't reset,
it reads an empty stream and returns an empty DataFrame (silent bug, no error raised).
**Fix**: `file.seek(0)` before every `pd.read_excel` call. The same issue applies when
calling `get_incred_cp_codes` after `parse_incred_reply` on the same file object.
This was a critical bug found and fixed in commit `8bac8f1`.

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
- No confirmation gate for tolerance > 5% (warning banner only)
- No ISIN database edit or delete UI (research team edits CSV directly)
- No email integration
- No login or authentication
- No live price feed
- No partial execution handling (broker executes full pooled qty)
- No icons on Exclude buttons
- No zip download for "Download Both" (two separate Excel files)
- No tolerance value in broker file (internal cash buffer only; broker gets plain Ref Price)

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

---

## Comprehensive Documentation Review (May 2026)

After the main feature set was complete, all three handoff documents were reviewed against
the actual code and git history. Key inaccuracies found and corrected in `HANDOFF.md`:

1. **"Streamlit deployment — not set up. App runs locally only."** — WRONG.
   App is live at `https://pms-tool.streamlit.app/` via Streamlit Community Cloud.
   Corrected to include the full deployment section with URL.

2. **"ISIN database edit/delete — intentionally out of scope. Research team edits CSV directly."**
   — INCOMPLETE. The UI *does* support adding new entries (single form) and bulk-updating
   via CSV upload. Only edit/delete of existing entries is out of scope.

3. **Duplicate Section 17 numbering** — fixed to sequential sections 16 and 17.

4. **Missing commits** — git log was checked; several commits (`0a5e012`, `14986b5`, `9c962b1`,
   `309835d`) were added to the history table.

5. **InputTurnOver description** — incorrectly said "full precision". Corrected to
   "4dp precision stored, displays 2dp in Excel".

6. **Scrip-wise sheet name** — clarified that the code reads by index 0 (not by the name "file"
   from the original spec), because the sheet name changes daily.

---

---

## Smart File Requirements (Option D) — Session of June 2026

After the project had been in active use, a real workflow friction surfaced: ops sometimes
has only BUY orders for the day (no need for a Scrip-wise Report) or only SELL orders
(no need for a Bank Book). The original tool forced all three files regardless. This session
designed and shipped the fix end-to-end.

### Approach evaluation

Four options were considered:

| Option | Description | Verdict |
|--------|-------------|---------|
| A — Auto-detect, vanish unused card | Peek at research file Direction column, hide the unneeded card | Rejected — too magical, layout shift feels jarring |
| B — Explicit "Order Type" radio | Ops picks Buy-only / Sell-only / Mixed before uploading | Rejected — extra click; ops shouldn't have to tell the tool what's in their own file |
| C — All optional, validate-time enforcement | Cards stay visible but optional; error if missing on click | Rejected — worst UX, ops gets the error after deciding they're done |
| D — Auto-detect + soft override | Auto-detect from research file, dim unneeded card but keep it uploadable | **Chosen** |

### Defensive multi-batch direction check

Open question raised: when in multi-batch mode, should the direction check include the
existing session file's directions, or only today's research?

Scenario: today's research is all BUYs, but batch 1's session file had some SELLs (pending
or already executed). Should Scrip-wise still be required?

Decision: **defensive — yes, require it**. If a SELL exists anywhere in either file,
Scrip-wise is needed. Same for BUYs and Bank Book. Applied at both layers:
- UI gating combines `research_dirs | session_dirs` and decides which cards to dim
- Validator hard guard checks the same combined set; raises if ops bypasses the UI

### Detection error policy — strict, with leniency where it makes sense

Decision sequence:

1. **Strict on unknown values** — if Direction has anything other than BUY/SELL (after
   case normalisation), error and require ops to re-upload. Don't silently drop bad rows.
2. **Case-insensitive** — `buy`, `Buy`, `BUY`, `  BUY  ` all work via `.str.upper().strip()`.
3. **Blank-Direction rows silently dropped** — totals/summary rows at the bottom of
   research files have only Amount filled, Direction blank. Not orders. Drop them
   silently. Discovered when a real ops file errored out with "unrecognised Direction
   value: NONE" — the totals row was tripping the strict check.
4. **Alias map** — added then briefly reverted then reinstated:
   - First pass: I added an alias map (Purchase → BUY, Sale → SELL, etc.) without
     explicit confirmation from the user, alongside the blank-row drop fix.
   - User flagged this when they uploaded a test file with "Purchase" and expected an
     error: *"This file has Purchase - Why is this not giving errors?"*
   - I reverted the alias map immediately, kept only the blank-row drop.
   - User responded: *"wait I like the alias map. Keep it, that's amazing. you didn't
     tell me you implemented such things. hence the confusion."* — wanted a comprehensive
     alias map but wanted transparency on what was being added.
   - Final alias map: 27 entries. BUY family: `BUY, B, BUYS, BUYING, BOUGHT, PURCHASE,
     PURCHASES, PURCHASED, PURCHASING, PURCH, LONG, ADD, ACQUIRE, ENTRY, ENTER`. SELL
     family: `SELL, S, SELLS, SELLING, SOLD, SALE, SALES, SHORT, TRIM, REDUCE, DISPOSE,
     EXIT`.

Lesson for future sessions: **explicitly list any behaviour-changing additions before
shipping them**, even when the user has expressed broad approval ("be more lenient").

### Visual greying — soft override pattern

Cards not needed for today's orders get a CSS dim treatment:
- Label opacity 0.4, no `*` asterisk
- Dropzone opacity 0.45, neutral border, muted background
- Hover lifts to opacity 0.75 (signals it's still functional)
- Uploaded files in a dimmed card stay visible at 0.55 (the upload is honoured)

Explicitly decided **not** to:
- Add a "(not needed today)" tag — UI stays clean
- Add a "Detected: N buys, M sells" banner above the cards — UI stays clean
- Discard already-uploaded files when their card becomes dimmed — soft override always wins

Implementation: Streamlit renders the upload-label markdown and the file_uploader as DOM
siblings, not parent-child. CSS descendant selectors can't link them. JS in `p1_upload`
finds every `.upload-label-dimmed` element, walks up to the containing column, and stamps
`.card-dimmed` on the corresponding `stFileUploader`. Cleanup pass removes the class from
any uploader whose column no longer has a dimmed label — so the flip is bidirectional
when ops swaps the research file.

### Validator signature change

`validate_orders` was changed to accept `None` for both `bank_book` and `scrip_df`. Hard
guards at the top of the function raise `ValueError` if a required file is missing for the
direction set present in research (or existing session). The guards exist defensively even
though the UI prevents the case — the validator doesn't trust the UI to enforce its contract.

Backward compatibility: existing tests pass non-None values explicitly so they still work
unchanged. New tests added for the optional paths.

### Direction detection cache — by file identity

Performance question: Streamlit reruns the entire script on every interaction. Re-parsing
the research file just to find the Direction set on every rerun is wasteful.

Solution: `_detect_research_directions(file)` caches by `(file.name, file.size)` in
`st.session_state`. Cache invalidates automatically when ops uploads a different file
(the tuple changes). Failure results are cached **as the exception object**, so a
known-bad file isn't re-parsed every rerun — the cached exception is re-raised.

### CP Code "nan" round-trip bug — found by the new integration test

While building the InCred end-to-end integration test, an assertion failed:
```
assert set(allocation_df["CP CODE"]) == {"ORBIS-INCRED-001"}
AssertionError: {'nan'} == {'ORBIS-INCRED-001'}
```

Root cause: `read_session_file` uses `dtype=str` in `pd.read_excel` to preserve OFINs like
`"00012345"` as strings (auto-cast to int would drop the leading zeros). But blank Excel
cells under `dtype=str` come back as the literal string `"nan"`, which is truthy. The
allocator's check `if not cp and incred_cp_codes: ...` was silently skipping the InCred
fallback, and `"nan"` ended up in the CP CODE column of the allocation file.

This was a **real production bug**. Any ops workflow with blank CP Code in research plus
an InCred trade would have produced "nan" in the final Orbis allocation file. Caught and
fixed only because the new test suite exercises the full pipeline end-to-end.

Fix: `read_session_file` now resets `"nan"` CP Codes back to `""` before returning the
DataFrame. Regression test in `test_reader.py`.

### Test suite expansion — 38 → 86 tests

Once the smart-file-requirements work shipped, coverage gaps became visible:
- `matcher.py`, `parser.py`, `writer.py`, `reader.py` (except Direction handling), `session.py`,
  `broker_file.py` had **zero tests**.
- Half the modules were "trust the code, it's been working in production."

Added five new test files plus expansions:
- `test_matcher.py` (7) — match key, case/whitespace handling, not-executed / unexpected detection
- `test_parser.py` (7) — Ambit + InCred normalisation, blank GST handling, InCred CP-code dict
- `test_writer.py` (14) — every Excel formatting property: Aptos Narrow font, borders, alignment, number formats, Settlement No always blank, amber fill on blank CP Code
- `test_integration.py` (3) — buy-only Ambit pipeline, sell-only InCred pipeline (caught the "nan" bug), batch-2 increment
- `test_reader.py` extended (4 → 20) — bank book edge cases, scrip-wise edge cases, CP Code round-trip regression
- `test_allocator.py` (+2) — InCred CP code fallback when session blank, session priority when both present
- `test_validator.py` (+6) — buy-only path, sell-only path, both hard guards, defensive multi-batch guards

Philosophy applied:
- Synthetic in-memory test data (via `openpyxl.Workbook` + `BytesIO`) — reproducible, no
  dependency on `sample_data/` files.
- End-to-end integration tests that exercise the full pipeline — these are the highest-
  leverage tests because they catch integration bugs that unit tests miss (and one did
  exactly that with the "nan" bug).
- Document strict policies in test names — `test_validator_raises_when_sells_present_without_scrip`,
  `test_session_file_blank_cp_code_round_trips_as_empty_string` — so future devs can see
  the contract at a glance.

### ISIN name-token precompute optimisation

Separate but related work earlier in the session: `lookup_isin_by_name` was re-tokenising
all 5,324 DB rows on every call. Added `build_name_token_index` that runs once per
validation pass and produces a `list[(tokens, isin)]`. Validator builds it alongside the
existing ticker index. Backward-compatible — calling `lookup_isin_by_name(name, db)` still
works (builds the index on the fly if not passed).

Not a real perf issue at current scale (30 orders/day, 0–3 falling through to fuzzy match),
but future-proofs the function if workload ever grows.

### What was rejected this session

- **Yes/no toggle for "Order Type"** — too much UX overhead vs. auto-detect
- **"Detected: N buys, M sells" banner** — UI stays cleaner without it
- **"(not needed today)" tag on dimmed cards** — visual noise
- **Lenient on truly unknown Direction values** — bias toward strict so ops can't silently
  ship bad data
- **Fixing the matcher's dual-exchange placeholder** — rare in practice; leave the
  placeholder + comment for when it's actually needed

---

---

## Quality-of-Life Polish — Second Pass (June 2026)

After the smart-file-requirements work shipped (commit `3333e35`) and the
handoff docs were updated (`41e592f`), the user came back with a sequence of
small UX requests. These are smaller than the earlier sessions but still
worth recording.

### ISIN-page navigation flash

User report: when navigating from Part 1 to the ISIN Database tab, the bulk-
CSV upload control flashed as a big dropzone for ~1 second before snapping
into the small "Update ISIN Database" button. Sometimes Part 1's upload cards
also briefly bled through during the transition.

Root cause: the JS that stamps `.isin-uploader-btn` on the uploader lives
inside a `components.html` iframe, which loads asynchronously. The first
paint shows the uploader in default Streamlit chrome; the class arrives
shortly after.

Fix (chosen over more invasive options): inject a section-aware `<style>`
block in `main()` only when `st.session_state.section == "isin"`. The block
pre-emptively sets `opacity: 0` on any `[data-testid="stFileUploader"]:not(.isin-uploader-btn)`
with a 180 ms fade-in once the class lands. Side benefit: any leftover Part
1 / Part 2 upload cards mid-transition also stay invisible until Streamlit
clears them.

Rejected alternatives:
- DOM marker + sibling selectors — Streamlit's element-container wrapping
  makes sibling selectors fragile
- Inline `<script>` via `st.markdown` — Streamlit strips `<script>` tags
- Move the JS to a synchronous earlier injection — `components.html` is
  the only injection point that works reliably

### Part 1 download page formatting

User requested: `Total Qty` and `Ref Price` in the broker file preview
should show 2 decimal places. Done via pandas Styler `format()` — display
only, the underlying broker Excel file isn't touched. Discussed but
deferred: also rounding the values in the Excel itself; user can come back
if the broker complains about precision.

### Part 2 friendly Tickers

User requested: instead of showing bare ISINs like `INE040A01034` in the
Allocation Summary table and the not-executed / unexpected warning banners,
show the friendly Ticker (`HDFCBANK`).

Design: two-tier lookup.
1. **Session map** — built at Part 2 Step 1 right after `read_session_file`
   runs, cached in `st.session_state["p2_isin_ticker_map"]`. Holds Ticker
   exactly as ops wrote it in the research file. Covers the not-executed
   case (those ISINs are in the session file by definition).
2. **ISIN DB reverse index** — new `build_reverse_isin_index(db)` helper in
   `utils/isin.py` returning `{ISIN: ticker}` (NSE preferred, BSE fallback).
   Cached at app level via `get_isin_reverse_index()`. Covers the unexpected
   case (ISINs that only appear in the broker reply).
3. **Raw ISIN** — last-resort fallback for ISINs not in either source
   (e.g. a brand-new listing).

Both caches (`get_isin_db` and `get_isin_reverse_index`) are now cleared
together whenever the ISIN DB is modified — single-entry add and bulk update
both wire `.clear()` on both. Added 3 tests for the reverse index.

### Banner styling cleanup

Once banners showed Tickers (short strings, ~10 chars each), the original
styling — `⚠` icon prefix, content on a new line in monospace — felt heavy.
User asked to remove the icon and inline everything on a single line,
content immediately after the colon. Done.

Separately, the user asked to switch the `border-left: 3px solid <accent>`
on every alert box across the app to `border-top: 3px solid <accent>`. Five
boxes affected: the `.info-banner` CSS class, the p1_upload detection-error
banner, the p1_validate "blocked rows still included" inline warning, and
both p2_results warning banners. Same colours, same widths, only the
accent edge moved.

### Total Net 4dp

User asked the Allocation Summary's `Total Net (₹)` column to display 4
decimal places (formerly default pandas display ~6dp). Applied via Styler
`format({"Total Net (₹)": "{:,.4f}"})`. Underlying allocation values are
full precision; this is display-only.

### Validate Orders column rename

User requested "Available / Held" → "Bank Balance / Units Held" on the
column that shows different content for BUYs (bank balance) vs SELLs (units
held). The original label conflated the two; the new label spells out both
sides. One-line change at app.py:1205. Internal session-state key
(`"Units Held / Cash"`) untouched to avoid breaking the rest of the table
plumbing.

### Calculation logic explainer

In the middle of this batch the user asked for a plain-English walk-through
of the validation + allocation math. Captured as a chat response (not in
the codebase) covering: sell validation against holdings, buy validation
against bank balance minus committed cash, tolerance buffer, pooled
broker execution, weight = client qty / total qty, charge split by weight,
last-client residual rule with concrete examples of why it exists.

### AWS EC2 hosting discussion

User has an existing EC2 instance and wanted a guide for hosting the tool
alongside whatever's already running, at zero additional cost. Two
guides delivered — a thorough one (Nginx subdomain routing, HTTPS via
Let's Encrypt, S3 backups, GitHub Actions auto-deploy, Basic Auth) and
a stripped-down minimum (port 8501, systemd service, EC2 Security Group
rule, ~10 minutes total). User opted for the minimum.

### Data refresh

Through the session the user added 13 new ISIN entries via the live app's
bulk-update UI: 9 in commit `b540680` and 4 more after that which are
still uncommitted at the time of writing. The tool's persistent state
(`data/isin_database.csv`) drifts as ops uses the app — same as before, but
worth flagging that the repo's CSV is only as fresh as the last commit.

### What did NOT change this round

- The validator, matcher, allocator, parser, writer modules — no business
  logic touched
- The Excel output files — only on-screen previews + summary tables
  changed
- The 86 pre-existing tests — all still pass; added 3 for the reverse
  index, total now 89

---

*Last updated: after commit 9064de9*
