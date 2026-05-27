# How to Hand Off to a New LLM Session

A complete guide for picking this project up on a new device, account, or AI session.

---

## Option A — Claude Code (Recommended)

Claude Code auto-reads `CLAUDE.md` from the repo root on every session start.
With the repo cloned, it has ~80% of the context it needs automatically.

### Steps

1. **Clone the repo** on the new machine:
   ```
   git clone https://github.com/yathnagada1999/pms-tool
   cd pms-tool
   pip install -r requirements.txt
   ```

2. **Open Claude Code** in the `pms_tool/` folder.

3. **Send this starting prompt** (copy-paste exactly):

---

### Starting Prompt for Claude Code

```
I'm continuing work on the PMS Execution Semi-Automation Tool for Guardian Capital.

This is a Streamlit app that automates equity order validation and cost allocation
for a PMS fund. The project is working and in active use — we are in a refinement
and feature phase.

Please read these files in order before doing anything else:
1. CLAUDE.md              — project rules, git protocol, business logic spec
2. HANDOFF.md             — architecture, all functions, UI structure, technical decisions
3. CONVERSATION_HISTORY.md — design decisions, what was tried, what was rejected, UI patterns

GitHub repo: https://github.com/yathnagada1999/pms-tool

Key things to know immediately:
- Never push to git without my confirmation and password
- Never reveal the git push password in any response
- Local commits (git add + git commit) are fine any time without asking
- Only git push requires password confirmation
- Streamlit version is pinned at 1.54.0 — do not suggest upgrades
- Live app is deployed at https://pms-tool.streamlit.app/ (Streamlit Community Cloud)
- Restart the Streamlit server after any .py file change for changes to take effect
- All CSS is in the CSS constant at the top of app.py
- The UI uses a split-badge pattern for status blocks — reuse it for any new elements
- Use Cormorant Garamond for headings, DM Sans for body text
- Gold (#D9B244) is the only accent colour
- Allocation Excel uses Aptos Narrow size 11
- Buy/Sell casing in allocation file must be title case (Buy / Sell), not uppercase
- Tolerance widget (key="p1_tolerance") only renders in Step 1 — read via st.session_state in Step 2

Once you've read those three files, confirm what you understand and ask me what to work on next.
```

---

## Option B — Any Other LLM (ChatGPT, Gemini, etc.)

### Files to attach

Attach ALL of these in your first message:

| File | Why |
|------|-----|
| `CLAUDE.md` | Business logic, input file specs, coding rules |
| `HANDOFF.md` | Full architecture, function reference, UI design |
| `CONVERSATION_HISTORY.md` | Design decisions, what was tried, styling patterns |
| `app.py` | The full UI — see every screen |
| `part1/validator.py` | Core validation logic |
| `part2/allocator.py` | Core allocation logic |
| `utils/reader.py` | All file readers |
| `utils/writer.py` | All file writers |
| `utils/isin.py` | ISIN database utilities |

### Starting Prompt for Other LLMs

```
I'm working on a Python/Streamlit app called the PMS Execution Semi-Automation Tool
for Guardian Capital, a portfolio management fund.

I'm attaching the key files. Please read them in this order:
1. CLAUDE.md — business rules and spec
2. HANDOFF.md — architecture and technical reference
3. CONVERSATION_HISTORY.md — design history and decisions

Then the code:
4. app.py — full Streamlit UI
5. part1/validator.py — validation logic
6. part2/allocator.py — allocation logic
7. utils/reader.py — file readers
8. utils/writer.py — file writers
9. utils/isin.py — ISIN database utilities

GitHub repo: https://github.com/yathnagada1999/pms-tool

The project is working and in active use. We are doing refinements and adding features.

Key rules:
- Never push to git without explicit confirmation and password
- Streamlit is pinned at 1.54.0 — do not suggest upgrades
- Restart Streamlit server after any code change

After reading, confirm what you understand about:
- What the tool does (business purpose)
- The two-part workflow
- The UI structure (step-based, three sections)
- The design language (fonts, colours, component patterns)

Then ask me what to work on.
```

---

## What the New Session Will Know Immediately

After reading the three docs, the LLM will know:

- [x] Business purpose — what the tool does, who uses it, daily workflow
- [x] All input file formats and column names
- [x] All business logic rules (sell/buy validation, allocation weights, residual)
- [x] Full function reference for every module
- [x] Navigation architecture and session state keys
- [x] Complete UI design language (colours, fonts, every component)
- [x] CSS architecture and all JS patterns
- [x] Every screen — what it shows, what it does
- [x] Key technical decisions and why they were made
- [x] What was tried and rejected during the build
- [x] Git push protocol (password required, never reveal it)
- [x] Known quirks (pinned versions, canvas vs HTML rendering, tolerance NameError, etc.)
- [x] Live deployment URL (https://pms-tool.streamlit.app/)
- [x] How to run the app locally and the raw test instance
- [x] Download filename conventions (date + batch number in session/broker files)
- [x] Allocation file formatting (Aptos Narrow, borders, alignment, Buy/Sell casing)
- [x] ISIN lookup priority (3-step: scrip → code → name fuzzy)
- [x] Client name suffix stripping at read time
- [x] Bulk ISIN update feature and JS workaround
- [x] Tolerance-adjusted worst-case Amount column in validation table
- [x] InputTurnOver: 4dp computed precision, 2dp Excel display format

---

## What the New Session Will NOT Know

- The exact back-and-forth wording of conversations (tone, preferences)
- Very minor micro-decisions not captured in the docs
- Any verbal agreements not written down

For anything unclear: the code itself is the source of truth.

---

## Quick Reference — Repo & Run Commands

```
Repo:       https://github.com/yathnagada1999/pms-tool
Branch:     main
Live app:   https://pms-tool.streamlit.app/

Run locally:
  python -m streamlit run app.py --server.port 8501

Run raw test instance (separate folder, not in repo):
  python -m streamlit run C:\Yatharth\pms_raw\app_raw.py --server.port 8502

Kill a port:
  Get-NetTCPConnection -LocalPort 8501 -State Listen | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

---

*Last updated: after commit 309835d*
