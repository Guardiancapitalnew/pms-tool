"""Tests for part2/matcher.py - matches session rows to broker reply rows
by (ISIN, Direction) and surfaces unmatched ISINs in either direction."""
import pytest
import pandas as pd

from part2.matcher import match_session_to_broker


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _session(rows: list[dict]) -> pd.DataFrame:
    """Build a session DataFrame from a list of partial-row dicts. Defaults
    fill in the bookkeeping columns matcher doesn't actually care about."""
    base = {
        "S.No": 1, "Batch": 1, "OFIN": "OF001", "Client": "C",
        "Ticker": "X", "Direction": "BUY", "Qty": 100,
        "Ref Price": 10.0, "CP Code": "X",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def _broker(rows: list[dict]) -> pd.DataFrame:
    """Normalised broker DataFrame matching part2/parser.NORMALISED_COLUMNS."""
    base = {
        "Exchange": "NSE",
        "TradeDate": pd.Timestamp("2026-05-18"),
        "TotalQty": 100,
        "Brokerage": 50.0, "STT": 25.0, "StampDuty": 5.0,
        "SEBIChrg": 0.05, "TurnoverTax": 3.0, "OtherCharges": 0.0,
        "GST": 9.0, "NetAmount": 10000.0,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


# ── Tests ────────────────────────────────────────────────────────────────────

def test_all_session_rows_match_when_broker_has_their_isin():
    session = _session([
        {"S.No": 1, "OFIN": "OF001", "ISIN": "INE001", "Direction": "BUY", "Qty": 100},
        {"S.No": 2, "OFIN": "OF002", "ISIN": "INE001", "Direction": "BUY", "Qty": 200},
    ])
    broker = _broker([{"ISIN": "INE001", "Direction": "BUY"}])
    matched, not_executed, unexpected = match_session_to_broker(session, broker)
    assert len(matched) == 2
    assert not_executed == []
    assert unexpected == []


def test_session_isin_absent_from_broker_goes_to_not_executed():
    session = _session([
        {"S.No": 1, "ISIN": "INE001", "Direction": "BUY"},
        {"S.No": 2, "ISIN": "INE002", "Direction": "BUY"},  # not executed
    ])
    broker = _broker([{"ISIN": "INE001", "Direction": "BUY"}])
    matched, not_executed, unexpected = match_session_to_broker(session, broker)
    assert len(matched) == 1
    assert "INE002" in not_executed
    assert "INE001" not in not_executed


def test_broker_isin_absent_from_session_goes_to_unexpected():
    session = _session([{"S.No": 1, "ISIN": "INE001", "Direction": "BUY"}])
    broker = _broker([
        {"ISIN": "INE001", "Direction": "BUY"},
        {"ISIN": "INE999", "Direction": "BUY"},  # broker executed something we didn't order
    ])
    matched, not_executed, unexpected = match_session_to_broker(session, broker)
    assert "INE999" in unexpected
    assert "INE001" not in unexpected


def test_match_is_case_insensitive_on_isin_and_direction():
    session = _session([
        {"S.No": 1, "ISIN": "ine001", "Direction": "buy"},
    ])
    broker = _broker([{"ISIN": "INE001", "Direction": "BUY"}])
    matched, not_executed, unexpected = match_session_to_broker(session, broker)
    assert len(matched) == 1
    assert not_executed == []


def test_match_strips_whitespace():
    session = _session([{"S.No": 1, "ISIN": "  INE001  ", "Direction": "BUY"}])
    broker = _broker([{"ISIN": "INE001", "Direction": "BUY"}])
    matched, not_executed, unexpected = match_session_to_broker(session, broker)
    assert len(matched) == 1


def test_matched_rows_get_broker_exchange_and_trade_date():
    session = _session([{"S.No": 1, "ISIN": "INE001", "Direction": "BUY"}])
    broker = _broker([{
        "ISIN": "INE001", "Direction": "BUY",
        "Exchange": "BSE", "TradeDate": pd.Timestamp("2026-06-01"),
    }])
    matched, _, _ = match_session_to_broker(session, broker)
    assert matched.iloc[0]["_broker_exchange"] == "BSE"
    assert matched.iloc[0]["_broker_trade_date"] == pd.Timestamp("2026-06-01")


def test_same_isin_buy_and_sell_treated_as_distinct_matches():
    """A BUY and SELL of the same ISIN are independent trades - both must
    appear in broker reply for both to match."""
    session = _session([
        {"S.No": 1, "OFIN": "OF001", "ISIN": "INE001", "Direction": "BUY",  "Qty": 100},
        {"S.No": 2, "OFIN": "OF002", "ISIN": "INE001", "Direction": "SELL", "Qty": 50},
    ])
    broker = _broker([
        {"ISIN": "INE001", "Direction": "BUY"},
        {"ISIN": "INE001", "Direction": "SELL"},
    ])
    matched, not_executed, unexpected = match_session_to_broker(session, broker)
    assert len(matched) == 2
    assert not_executed == []
