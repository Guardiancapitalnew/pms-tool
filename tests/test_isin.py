"""Tests for utils/isin.py lookup logic."""
import pytest
import pandas as pd
from utils.isin import (
    lookup_isin, lookup_isin_by_name,
    build_name_token_index, build_reverse_isin_index,
)


@pytest.fixture
def db():
    return pd.DataFrame({
        "Name": ["Kotak Bank", "Jio Financial", "BSE Only Co"],
        "BSE Code": ["500247", "543940", "999001"],
        "NSE Code": ["KOTAKBANK", "JIOFIN", ""],
        "ISIN Code": ["INE237A01036", "INE758E01017", "INE999X01011"],
    })


def test_nse_code_lookup(db):
    assert lookup_isin("KOTAKBANK", db) == "INE237A01036"


def test_nse_code_case_insensitive(db):
    assert lookup_isin("kotakbank", db) == "INE237A01036"
    assert lookup_isin("KotakBank", db) == "INE237A01036"


def test_bse_code_fallback(db):
    # BSE Only Co has no NSE code
    assert lookup_isin("999001", db) == "INE999X01011"


def test_unknown_ticker_returns_none(db):
    assert lookup_isin("UNKNOWN", db) is None


def test_strips_whitespace(db):
    assert lookup_isin("  JIOFIN  ", db) == "INE758E01017"


# ── Name-based fuzzy lookup ────────────────────────────────────────────────────

@pytest.fixture
def name_db():
    """A few realistic company names to exercise the fuzzy matcher."""
    return pd.DataFrame({
        "Name": [
            "Kotak Mahindra Bank Ltd",
            "Jio Financial Services Ltd",
            "Bajaj Finance Ltd",
            "AU Small Finance Bank Ltd",
            "Infosys Ltd",
        ],
        "BSE Code": ["500247", "543940", "500034", "540611", "500209"],
        "NSE Code": ["KOTAKBANK", "JIOFIN", "BAJFINANCE", "AUBANK", "INFY"],
        "ISIN Code": [
            "INE237A01036", "INE758E01017", "INE296A01024",
            "INE949L01017", "INE009A01021",
        ],
    })


def test_name_lookup_full_company_name(name_db):
    assert lookup_isin_by_name("AU SMALL FINANCE BANK LTD", name_db) == "INE949L01017"
    assert lookup_isin_by_name("BAJAJ FINANCE LTD", name_db) == "INE296A01024"


def test_name_lookup_single_long_token(name_db):
    # 1-token-but-long rule: "INFOSYS" (>=5 chars) should match
    assert lookup_isin_by_name("INFOSYS LIMITED", name_db) == "INE009A01021"


def test_name_lookup_returns_none_on_unknown(name_db):
    assert lookup_isin_by_name("RANDOM UNLISTED PRIVATE LTD", name_db) is None


def test_reverse_isin_index_prefers_nse_code(db):
    """ISIN → Ticker reverse lookup: NSE Code wins when present."""
    idx = build_reverse_isin_index(db)
    assert idx["INE237A01036"] == "KOTAKBANK"
    assert idx["INE758E01017"] == "JIOFIN"


def test_reverse_isin_index_falls_back_to_bse(db):
    """When NSE Code is blank, the reverse map should use BSE Code."""
    idx = build_reverse_isin_index(db)
    # "BSE Only Co" has NSE Code "" and BSE Code "999001"
    assert idx["INE999X01011"] == "999001"


def test_reverse_isin_index_normalises_isin_keys_to_upper(db):
    """Lookups happen with uppercased ISINs; the index keys must match."""
    idx = build_reverse_isin_index(db)
    # Every key is uppercased
    for k in idx.keys():
        assert k == k.upper()


def test_name_lookup_precomputed_index_matches_fallback(name_db):
    """The precomputed-index path must return identical results to the
    on-the-fly fallback path. Guards against the perf optimisation
    silently changing behaviour."""
    token_index = build_name_token_index(name_db)
    queries = [
        "KOTAK MAHINDRA BANK LTD",
        "BAJAJ FINANCE LTD",
        "INFOSYS LIMITED",
        "AU SMALL FINANCE BANK LTD",
        "RANDOM UNLISTED PRIVATE LTD",
    ]
    for q in queries:
        without = lookup_isin_by_name(q, name_db)
        with_idx = lookup_isin_by_name(q, name_db, _token_index=token_index)
        assert without == with_idx, f"Mismatch for {q!r}: {without!r} vs {with_idx!r}"
