"""Tests for part1/validator.py"""
import pytest
import pandas as pd
from part1.validator import validate_orders


def test_sell_passes_sufficient_units(
    sample_research_df, sample_bank_book, sample_scrip_df, sample_isin_db
):
    result = validate_orders(
        sample_research_df, sample_bank_book, sample_scrip_df, sample_isin_db
    )
    # OF001 sells 500 JIOFIN, holds 600 → GREEN
    row = result[(result["OFIN"] == "OF001") & (result["Ticker"] == "JIOFIN")].iloc[0]
    assert row["Status"] == "GREEN"


def test_sell_fails_insufficient_units(
    sample_bank_book, sample_isin_db
):
    # OF001 holds 600 JIOFIN but tries to sell 700 → RED insufficient units
    research = pd.DataFrame({
        "S.No": [1], "OFIN": ["OF001"], "Client": ["Client A"],
        "Ticker": ["JIOFIN"], "Direction": ["SELL"],
        "Qty": [700], "Ref Price": [230.0], "Value": [161000.0],
        "CP Code": ["ORBIS0000696"],
    })
    scrip = pd.DataFrame({
        "OFIN": ["OF001"], "Scrip Name": ["JIOFIN"],
        "ISIN": ["INE758E01017"], "Quantity": [600.0],
    })
    result = validate_orders(research, sample_bank_book, scrip, sample_isin_db)
    row = result.iloc[0]
    assert row["Status"] == "RED"
    assert "insufficient" in row["Reason"].lower()


def test_sell_fails_client_not_in_scrip_report(
    sample_research_df, sample_bank_book, sample_isin_db
):
    # Scrip report with no OF001 entry
    scrip_df = pd.DataFrame({
        "OFIN": ["OF999"],
        "Scrip Name": ["JIOFIN"],
        "ISIN": ["INE758E01017"],
        "Quantity": [1000.0],
    })
    result = validate_orders(
        sample_research_df, sample_bank_book, scrip_df, sample_isin_db
    )
    row = result[(result["OFIN"] == "OF001") & (result["Ticker"] == "JIOFIN")].iloc[0]
    assert row["Status"] == "RED"
    assert "not found" in row["Reason"].lower()


def test_buy_passes_sufficient_cash(
    sample_research_df, sample_bank_book, sample_scrip_df, sample_isin_db
):
    result = validate_orders(
        sample_research_df, sample_bank_book, sample_scrip_df, sample_isin_db
    )
    # OF001 buys 100 KOTAKBANK @ 400 = 40,000. Balance 500,000 → GREEN
    row = result[(result["OFIN"] == "OF001") & (result["Ticker"] == "KOTAKBANK")].iloc[0]
    assert row["Status"] == "GREEN"


def test_buy_fails_insufficient_cash(
    sample_research_df, sample_bank_book, sample_scrip_df, sample_isin_db
):
    result = validate_orders(
        sample_research_df, sample_bank_book, sample_scrip_df, sample_isin_db
    )
    # OF002 buys 200 KOTAKBANK @ 400 = 80,000. Balance = 100,000 → passes
    # OF003 buys 150 KOTAKBANK @ 400 = 60,000. Balance = -5,000 → RED (negative)
    row = result[(result["OFIN"] == "OF003") & (result["Ticker"] == "KOTAKBANK")].iloc[0]
    assert row["Status"] == "RED"
    assert "negative" in row["Reason"].lower()


def test_buy_fails_client_not_in_bank_book(
    sample_research_df, sample_scrip_df, sample_isin_db
):
    bank_book = {"OF999": 999999.0}  # missing OF001, OF002, OF003
    result = validate_orders(
        sample_research_df, bank_book, sample_scrip_df, sample_isin_db
    )
    row = result[(result["OFIN"] == "OF001") & (result["Ticker"] == "KOTAKBANK")].iloc[0]
    assert row["Status"] == "RED"
    assert "not found" in row["Reason"].lower()


def test_committed_cash_deducted_in_batch2(
    sample_research_df, sample_bank_book, sample_scrip_df,
    sample_isin_db, sample_session_df
):
    # OF001 balance = 500,000. Committed from session = 160,000. Available = 340,000.
    # Buying 100 KOTAKBANK @ 400 = 40,000 → should still pass
    result = validate_orders(
        sample_research_df, sample_bank_book, sample_scrip_df,
        sample_isin_db, existing_session_df=sample_session_df
    )
    row = result[(result["OFIN"] == "OF001") & (result["Ticker"] == "KOTAKBANK")].iloc[0]
    assert row["Status"] == "GREEN"

    # OF002 balance = 100,000. Committed = 80,000. Available = 20,000.
    # Buying 200 KOTAKBANK @ 400 = 80,000 → RED
    row2 = result[(result["OFIN"] == "OF002") & (result["Ticker"] == "KOTAKBANK")].iloc[0]
    assert row2["Status"] == "RED"
    assert "insufficient" in row2["Reason"].lower()


def test_tolerance_applied_to_required_cash(
    sample_research_df, sample_bank_book, sample_scrip_df, sample_isin_db
):
    # OF002 buys 200 KOTAKBANK @ 400 = 80,000. Balance = 100,000.
    # With 30% tolerance → required = 80,000 * 1.30 = 104,000 > 100,000 → RED
    result = validate_orders(
        sample_research_df, sample_bank_book, sample_scrip_df,
        sample_isin_db, tolerance=30.0
    )
    row = result[(result["OFIN"] == "OF002") & (result["Ticker"] == "KOTAKBANK")].iloc[0]
    assert row["Status"] == "RED"


def test_isin_populated_from_scrip_report(
    sample_research_df, sample_bank_book, sample_scrip_df, sample_isin_db
):
    result = validate_orders(
        sample_research_df, sample_bank_book, sample_scrip_df, sample_isin_db
    )
    jiofin_rows = result[result["Ticker"] == "JIOFIN"]
    assert all(jiofin_rows["ISIN"] == "INE758E01017")


def test_isin_populated_from_database_fallback(
    sample_research_df, sample_bank_book, sample_isin_db
):
    # Empty scrip_df - forces ISIN database lookup for buy-side ISINs.
    # Filter to BUYs only because the validator's new guard rejects sells
    # without a scrip-wise report (that combination is a real UI bug now).
    buys_only = sample_research_df[sample_research_df["Direction"] == "BUY"].copy()
    empty_scrip = pd.DataFrame(columns=["OFIN", "Scrip Name", "ISIN", "Quantity"])
    result = validate_orders(
        buys_only, sample_bank_book, empty_scrip, sample_isin_db
    )
    kotak_rows = result[result["Ticker"] == "KOTAKBANK"]
    assert all(kotak_rows["ISIN"] == "INE237A01036")


# ── Optional file paths and hard guards ──────────────────────────────────────

def _buys_only_research():
    """Three BUY rows for KOTAKBANK across 3 OFINs."""
    return pd.DataFrame({
        "S.No":      [1, 2, 3],
        "OFIN":      ["OF001", "OF002", "OF003"],
        "Client":    ["A", "B", "C"],
        "Ticker":    ["KOTAKBANK", "KOTAKBANK", "KOTAKBANK"],
        "Direction": ["BUY", "BUY", "BUY"],
        "Qty":       [100, 200, 150],
        "Ref Price": [400.0, 400.0, 400.0],
        "Value":     [40000.0, 80000.0, 60000.0],
        "CP Code":   ["X", "X", "X"],
    })


def _sells_only_research():
    """Two SELL rows for JIOFIN across 2 OFINs."""
    return pd.DataFrame({
        "S.No":      [1, 2],
        "OFIN":      ["OF001", "OF002"],
        "Client":    ["A", "B"],
        "Ticker":    ["JIOFIN", "JIOFIN"],
        "Direction": ["SELL", "SELL"],
        "Qty":       [500, 300],
        "Ref Price": [230.0, 230.0],
        "Value":     [115000.0, 69000.0],
        "CP Code":   ["X", "X"],
    })


def test_validator_runs_buy_only_with_no_scrip(
    sample_bank_book, sample_isin_db
):
    """Buy-only research file should validate without requiring scrip_df.
    No SELLs anywhere means the guard does not trigger."""
    research = _buys_only_research()
    result = validate_orders(
        research_df=research,
        bank_book=sample_bank_book,
        scrip_df=None,
        isin_db=sample_isin_db,
    )
    assert len(result) == 3
    # Every row got a verdict
    assert all(s in {"GREEN", "RED"} for s in result["Status"])
    # OF001 (500k balance) buying 40k → GREEN
    of001 = result[result["OFIN"] == "OF001"].iloc[0]
    assert of001["Status"] == "GREEN"
    # OF003 (-5k balance) → RED with negative-balance reason
    of003 = result[result["OFIN"] == "OF003"].iloc[0]
    assert of003["Status"] == "RED"
    assert "negative" in of003["Reason"].lower()


def test_validator_runs_sell_only_with_no_bank(
    sample_scrip_df, sample_isin_db
):
    """Sell-only research file should validate without requiring bank_book."""
    research = _sells_only_research()
    result = validate_orders(
        research_df=research,
        bank_book=None,
        scrip_df=sample_scrip_df,
        isin_db=sample_isin_db,
    )
    assert len(result) == 2
    assert all(s in {"GREEN", "RED"} for s in result["Status"])
    # OF001 holds 600 JIOFIN, selling 500 → GREEN
    of001 = result[result["OFIN"] == "OF001"].iloc[0]
    assert of001["Status"] == "GREEN"


def test_validator_raises_when_sells_present_without_scrip(
    sample_research_df, sample_bank_book, sample_isin_db
):
    """Hard guard: sells in research + scrip_df=None → ValueError."""
    with pytest.raises(ValueError, match=r"[Ss]ell orders.*Scrip-wise"):
        validate_orders(
            research_df=sample_research_df,  # mixed: has SELLs
            bank_book=sample_bank_book,
            scrip_df=None,
            isin_db=sample_isin_db,
        )


def test_validator_raises_when_buys_present_without_bank(
    sample_research_df, sample_scrip_df, sample_isin_db
):
    """Hard guard: buys in research + bank_book=None → ValueError."""
    with pytest.raises(ValueError, match=r"[Bb]uy orders.*Bank Book"):
        validate_orders(
            research_df=sample_research_df,  # mixed: has BUYs
            bank_book=None,
            scrip_df=sample_scrip_df,
            isin_db=sample_isin_db,
        )


def test_validator_defensive_existing_session_sells_force_scrip_requirement(
    sample_bank_book, sample_isin_db
):
    """Defensive multi-batch guard: today's research has no SELLs, but a prior
    batch's session file contains a SELL. Scrip-wise must still be required."""
    research = _buys_only_research()  # no sells today
    existing_session = pd.DataFrame({
        "S.No":      [1],
        "Batch":     [1],
        "OFIN":      ["OF002"],
        "Client":    ["B"],
        "Ticker":    ["JIOFIN"],
        "ISIN":      ["INE758E01017"],
        "Direction": ["SELL"],  # but the existing session does
        "Qty":       [50],
        "Ref Price": [230.0],
        "CP Code":   ["X"],
    })
    with pytest.raises(ValueError, match=r"[Ss]ell orders.*Scrip-wise"):
        validate_orders(
            research_df=research,
            bank_book=sample_bank_book,
            scrip_df=None,
            isin_db=sample_isin_db,
            existing_session_df=existing_session,
        )


def test_validator_defensive_existing_session_buys_force_bank_requirement(
    sample_scrip_df, sample_isin_db
):
    """Mirror of the above: today's research is sell-only but a prior batch
    has BUYs that contribute committed cash - bank book stays required."""
    research = _sells_only_research()  # no buys today
    existing_session = pd.DataFrame({
        "S.No":      [1],
        "Batch":     [1],
        "OFIN":      ["OF001"],
        "Client":    ["A"],
        "Ticker":    ["HDFCBANK"],
        "ISIN":      ["INE040A01034"],
        "Direction": ["BUY"],
        "Qty":       [10],
        "Ref Price": [1600.0],
        "CP Code":   ["X"],
    })
    with pytest.raises(ValueError, match=r"[Bb]uy orders.*Bank Book"):
        validate_orders(
            research_df=research,
            bank_book=None,
            scrip_df=sample_scrip_df,
            isin_db=sample_isin_db,
            existing_session_df=existing_session,
        )
