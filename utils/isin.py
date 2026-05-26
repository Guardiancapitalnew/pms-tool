"""
ISIN database read/write/lookup utilities.
Persists to data/isin_database.csv on the server.
"""
import re
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "data" / "isin_database.csv"

# ---------------------------------------------------------------------------
# Load (cached at the Streamlit layer via @st.cache_data)
# ---------------------------------------------------------------------------

def load_isin_database() -> pd.DataFrame:
    """Load the ISIN database CSV.

    Returns:
        pd.DataFrame: columns [Name, BSE Code, NSE Code, ISIN Code]
    """
    df = pd.read_csv(DB_PATH, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    for col in df.columns:
        df[col] = df[col].str.strip()
    return df


# ---------------------------------------------------------------------------
# Lookup index - built once per session for O(1) lookups
# ---------------------------------------------------------------------------

def build_isin_index(db: pd.DataFrame) -> dict[str, str]:
    """Build a flat uppercase ticker → ISIN dict for O(1) lookups.

    NSE Code takes priority; BSE Code is inserted only where NSE Code is blank,
    so NSE always wins when both exist for the same ISIN.

    Args:
        db: DataFrame from load_isin_database()

    Returns:
        dict mapping uppercase ticker → ISIN Code
    """
    index: dict[str, str] = {}
    # BSE first (lower priority) - gets overwritten by NSE below
    for _, row in db.iterrows():
        bse = row["BSE Code"].strip().upper()
        if bse:
            index[bse] = row["ISIN Code"]
    # NSE second (higher priority)
    for _, row in db.iterrows():
        nse = row["NSE Code"].strip().upper()
        if nse:
            index[nse] = row["ISIN Code"]
    return index


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def lookup_isin(ticker: str, db: pd.DataFrame,
                _index: dict[str, str] | None = None) -> str | None:
    """Look up ISIN for a given ticker symbol.

    Uses pre-built O(1) index when provided; falls back to DataFrame scan.
    NSE Code match takes priority over BSE Code.

    Args:
        ticker: NSE/BSE ticker symbol (e.g. 'KOTAKBANK')
        db: ISIN database DataFrame from load_isin_database()
        _index: optional pre-built dict from build_isin_index() for O(1) lookup

    Returns:
        ISIN string if found, None otherwise
    """
    ticker_upper = ticker.strip().upper()

    if _index is not None:
        return _index.get(ticker_upper)

    # Fallback: DataFrame scan (used when index not available)
    nse_match = db[db["NSE Code"].str.upper() == ticker_upper]
    if not nse_match.empty:
        return nse_match.iloc[0]["ISIN Code"]

    bse_match = db[db["BSE Code"].str.upper() == ticker_upper]
    if not bse_match.empty:
        return bse_match.iloc[0]["ISIN Code"]

    return None


# ---------------------------------------------------------------------------
# Name-based fuzzy lookup (fallback for full company names in research file)
# ---------------------------------------------------------------------------

# Common suffixes/words that don't help disambiguate companies
_NAME_STOP_WORDS = {
    "LTD", "LIMITED", "SERVICES", "SERVICE", "CORP", "CORPORATION",
    "INC", "CO", "THE", "AND", "OF", "PVT", "PRIVATE", "PUBLIC", "GROUP",
    "ENTERPRISES", "ENTERPRISE", "INDIA", "INDIAN", "HOLDINGS", "HOLDING",
}


def _name_tokens(s: str) -> list[str]:
    """Tokenize a company name for fuzzy matching.

    Strips punctuation, uppercases, removes single-char tokens and stop words.
    """
    cleaned = re.sub(r"[^A-Z0-9\s]", " ", s.strip().upper())
    return [t for t in cleaned.split() if len(t) >= 2 and t not in _NAME_STOP_WORDS]


def lookup_isin_by_name(company_name: str, db: pd.DataFrame) -> str | None:
    """Find ISIN by fuzzy company name match.

    Used as a last-resort fallback when the ticker is a full company name
    (e.g. 'AU SMALL FINANCE BANK LTD') rather than an NSE/BSE code.

    Algorithm: tokenize both names (strip punctuation, remove stop words),
    then check whether every token in the *shorter* list is a prefix of at
    least one token in the *longer* list. Requires >= 2 tokens to avoid
    false positives on short names.

    Examples that resolve correctly:
      'AU SMALL FINANCE BANK LTD'       -> 'AU Small Finance'    -> AUBANK ISIN
      'BAJAJ FINANCE LTD'               -> 'Bajaj Finance'       -> BAJFINANCE ISIN
      'HDFC BANK LTD'                   -> 'HDFC Bank'           -> HDFCBANK ISIN
      'MOTILAL OSWAL FINANCIAL...'      -> 'Motil.Oswal.Fin.'    -> MOTILALOFS ISIN

    Args:
        company_name: full or abbreviated company name from research file
        db: ISIN database DataFrame from load_isin_database()

    Returns:
        ISIN string if a confident match is found, None if no match or ambiguous
    """
    research_tokens = _name_tokens(company_name)
    if not research_tokens:
        return None

    best_isin: str | None = None
    best_score: float = 0.0

    for _, row in db.iterrows():
        db_tokens = _name_tokens(str(row["Name"]))
        if not db_tokens:
            continue

        # Compare shorter list against longer list (prefix match)
        if len(db_tokens) <= len(research_tokens):
            shorter, longer = db_tokens, research_tokens
        else:
            shorter, longer = research_tokens, db_tokens

        # Need >= 2 tokens, OR exactly 1 token that is >= 5 chars (long enough
        # to be distinctive, e.g. "INFOSYS" but not "TCS" which is an NSE code)
        if not shorter or (len(shorter) == 1 and len(shorter[0]) < 5):
            continue

        # Every token in the shorter list must prefix-match a token in the longer list
        matched = sum(
            1 for st in shorter if any(lt.startswith(st) for lt in longer)
        )
        if matched < len(shorter):
            continue

        score = matched / max(len(db_tokens), len(research_tokens))
        if score > best_score:
            best_score = score
            best_isin = row["ISIN Code"]

    return best_isin


# ---------------------------------------------------------------------------
# Bulk update from uploaded CSV
# ---------------------------------------------------------------------------

def bulk_update_isin_database(file) -> tuple[int, int]:
    """Add new ISIN entries from an uploaded CSV file.

    Reads Name, BSE Code, NSE Code, ISIN Code columns from the file.
    Skips entries where ISIN Code already exists in the database.
    Extra columns in the uploaded file (e.g. financial data) are ignored.

    Args:
        file: BytesIO or Streamlit UploadedFile (.csv)

    Returns:
        (added, skipped) counts
    """
    from io import BytesIO as _BytesIO
    content = file.read() if hasattr(file, "read") else file
    new_df = pd.read_csv(_BytesIO(content), dtype=str, keep_default_na=False)
    new_df.columns = [c.strip() for c in new_df.columns]

    required = ["Name", "BSE Code", "NSE Code", "ISIN Code"]
    missing = [c for c in required if c not in new_df.columns]
    if missing:
        raise ValueError(
            f"Uploaded file is missing column(s): {missing}. "
            f"Expected: Name, BSE Code, NSE Code, ISIN Code."
        )

    new_df = new_df[required].copy()
    for col in new_df.columns:
        new_df[col] = new_df[col].str.strip()

    # Drop rows with blank ISIN
    new_df = new_df[new_df["ISIN Code"].str.len() > 0].reset_index(drop=True)

    existing_db = load_isin_database()
    existing_isins = set(existing_db["ISIN Code"].str.strip().str.upper())

    to_add = new_df[~new_df["ISIN Code"].str.upper().isin(existing_isins)]
    skipped = len(new_df) - len(to_add)

    if not to_add.empty:
        combined = pd.concat([existing_db, to_add], ignore_index=True)
        combined.to_csv(DB_PATH, index=False)

    return len(to_add), skipped


# ---------------------------------------------------------------------------
# Add new entry
# ---------------------------------------------------------------------------

def add_isin_entry(name: str, nse_code: str, bse_code: str, isin_code: str) -> None:
    """Append a new entry to the ISIN database CSV.

    Args:
        name: Company name
        nse_code: NSE ticker symbol (can be blank)
        bse_code: BSE scrip code (can be blank)
        isin_code: ISIN (required)

    Raises:
        ValueError: if isin_code is blank
    """
    if not isin_code.strip():
        raise ValueError("ISIN Code is required.")

    df = load_isin_database()
    new_row = pd.DataFrame([{
        "Name": name.strip(),
        "BSE Code": bse_code.strip(),
        "NSE Code": nse_code.strip(),
        "ISIN Code": isin_code.strip(),
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DB_PATH, index=False)
