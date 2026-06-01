"""Tests for part2/parser.py - Ambit and InCred broker reply parsing.

Both parsers normalise to the same internal schema (NORMALISED_COLUMNS) so
the matcher and allocator don't care which broker the reply came from."""
from datetime import date
from io import BytesIO

import pandas as pd
from openpyxl import Workbook

from part2.parser import (
    parse_ambit_reply, parse_incred_reply,
    get_incred_cp_codes, NORMALISED_COLUMNS,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

_AMBIT_COLS = [
    "Transaction Date", "Exchange", "NSE Symbol", "BSE Scrip Code",
    "ISIN No.", "Transaction Type", "quantity",
    "Brokerage", "stt", "Stamp Duty", "SEBI Charges",
    "Turnover Tax", "Other Charges", "GST Amount", "Net Amount",
]
_INCRED_COLS = [
    "Exchange", "ISIN No.", "Transaction Type", "Quantity",
    "Amount", "Brokerage", "STT", "Stamp Duty", "SEBI Charges",
    "Turnover Tax", "Other Charges", "GST Amount", "Net Amount",
    "CP CODE",
]


def _ambit_xlsx(rows: list[dict]) -> BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(_AMBIT_COLS)
    for r in rows:
        ws.append([r.get(c, "") for c in _AMBIT_COLS])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _incred_xlsx(rows: list[dict]) -> BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Incred_Capital_Trade_Confirmati"
    ws.append(_INCRED_COLS)
    for r in rows:
        ws.append([r.get(c, "") for c in _INCRED_COLS])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ── Ambit parser ─────────────────────────────────────────────────────────────

def test_ambit_parser_returns_normalised_schema():
    f = _ambit_xlsx([{
        "Transaction Date": "2026-05-18", "Exchange": "NSE",
        "NSE Symbol": "HDFCBANK", "BSE Scrip Code": "500180",
        "ISIN No.": "INE040A01034", "Transaction Type": "BUY", "quantity": 100,
        "Brokerage": 50.0, "stt": 25.0, "Stamp Duty": 5.0,
        "SEBI Charges": 0.05, "Turnover Tax": 3.0, "Other Charges": 0.0,
        "GST Amount": 9.0, "Net Amount": 10000.0,
    }])
    df = parse_ambit_reply(f)
    assert list(df.columns) == NORMALISED_COLUMNS
    row = df.iloc[0]
    assert row["ISIN"] == "INE040A01034"
    assert row["Direction"] == "BUY"
    assert row["Exchange"] == "NSE"
    assert row["TotalQty"] == 100
    assert row["NetAmount"] == 10000.0
    assert row["TradeDate"] == pd.Timestamp("2026-05-18")


def test_ambit_parser_uppercases_direction_and_exchange():
    """Lowercase direction/exchange from broker file should be normalised."""
    f = _ambit_xlsx([{
        "Transaction Date": "2026-05-18", "Exchange": "nse",
        "NSE Symbol": "X", "BSE Scrip Code": "1",
        "ISIN No.": "INE001", "Transaction Type": "buy", "quantity": 50,
        "Brokerage": 0, "stt": 0, "Stamp Duty": 0, "SEBI Charges": 0,
        "Turnover Tax": 0, "Other Charges": 0, "GST Amount": 0, "Net Amount": 1000,
    }])
    df = parse_ambit_reply(f)
    assert df.iloc[0]["Direction"] == "BUY"
    assert df.iloc[0]["Exchange"] == "NSE"


def test_ambit_parser_fills_missing_numeric_charges_with_zero():
    """Empty/blank charge cells should become 0.0, not NaN."""
    f = _ambit_xlsx([{
        "Transaction Date": "2026-05-18", "Exchange": "NSE",
        "NSE Symbol": "X", "BSE Scrip Code": "1",
        "ISIN No.": "INE001", "Transaction Type": "BUY", "quantity": 100,
        "Brokerage": "", "stt": "", "Stamp Duty": "", "SEBI Charges": "",
        "Turnover Tax": "", "Other Charges": "", "GST Amount": "",
        "Net Amount": 1000,
    }])
    df = parse_ambit_reply(f)
    row = df.iloc[0]
    for col in ["Brokerage", "STT", "StampDuty", "SEBIChrg",
                "TurnoverTax", "OtherCharges", "GST"]:
        assert row[col] == 0.0, f"{col} should default to 0.0, got {row[col]!r}"


# ── InCred parser ────────────────────────────────────────────────────────────

def test_incred_parser_returns_normalised_schema_and_today_tradedate():
    """InCred reply has no Trade Date column - parser stamps today's date."""
    f = _incred_xlsx([{
        "Exchange": "NSE", "ISIN No.": "INE001", "Transaction Type": "BUY",
        "Quantity": "100", "Amount": "10000", "Brokerage": "50", "STT": "25",
        "Stamp Duty": "5", "SEBI Charges": "0.05", "Turnover Tax": "3",
        "Other Charges": "0", "GST Amount": "9", "Net Amount": "10000",
        "CP CODE": "ORBIS001",
    }])
    df = parse_incred_reply(f)
    assert list(df.columns) == NORMALISED_COLUMNS
    assert df.iloc[0]["TradeDate"] == pd.Timestamp(date.today())


def test_incred_parser_casts_string_numeric_columns_to_float():
    """InCred amounts arrive as strings; parser must coerce."""
    f = _incred_xlsx([{
        "Exchange": "NSE", "ISIN No.": "INE001", "Transaction Type": "BUY",
        "Quantity": "100", "Amount": "12345.67", "Brokerage": "50.5",
        "STT": "25", "Stamp Duty": "5.5", "SEBI Charges": "0.05",
        "Turnover Tax": "3.7", "Other Charges": "1.25",
        "GST Amount": "9", "Net Amount": "12345.67", "CP CODE": "X",
    }])
    df = parse_incred_reply(f)
    row = df.iloc[0]
    assert row["StampDuty"] == 5.5
    assert row["SEBIChrg"] == 0.05
    assert row["TurnoverTax"] == 3.7
    assert row["OtherCharges"] == 1.25


def test_incred_parser_blank_gst_becomes_zero():
    """Blank GST cells in InCred replies (empty string) should default to 0.0."""
    f = _incred_xlsx([{
        "Exchange": "NSE", "ISIN No.": "INE001", "Transaction Type": "BUY",
        "Quantity": "100", "Amount": "1000", "Brokerage": "10",
        "STT": "5", "Stamp Duty": "1", "SEBI Charges": "0.05",
        "Turnover Tax": "0.5", "Other Charges": "0",
        "GST Amount": "", "Net Amount": "1000", "CP CODE": "X",
    }])
    df = parse_incred_reply(f)
    assert df.iloc[0]["GST"] == 0.0


# ── InCred CP-code helper ────────────────────────────────────────────────────

def test_get_incred_cp_codes_returns_isin_to_cp_mapping():
    f = _incred_xlsx([
        {"Exchange": "NSE", "ISIN No.": "INE001", "Transaction Type": "BUY",
         "Quantity": "100", "Amount": "1000", "Brokerage": "10", "STT": "5",
         "Stamp Duty": "1", "SEBI Charges": "0.05", "Turnover Tax": "0.5",
         "Other Charges": "0", "GST Amount": "0.5", "Net Amount": "1000",
         "CP CODE": "ORBIS001"},
        {"Exchange": "NSE", "ISIN No.": "INE002", "Transaction Type": "BUY",
         "Quantity": "100", "Amount": "1000", "Brokerage": "10", "STT": "5",
         "Stamp Duty": "1", "SEBI Charges": "0.05", "Turnover Tax": "0.5",
         "Other Charges": "0", "GST Amount": "0.5", "Net Amount": "1000",
         "CP CODE": "ORBIS002"},
    ])
    cp = get_incred_cp_codes(f)
    assert cp == {"INE001": "ORBIS001", "INE002": "ORBIS002"}


def test_get_incred_cp_codes_uppercases_isin_keys():
    """Session-file ISINs come in upper; the dict must match that case."""
    f = _incred_xlsx([{
        "Exchange": "NSE", "ISIN No.": "ine001", "Transaction Type": "BUY",
        "Quantity": "100", "Amount": "1000", "Brokerage": "10", "STT": "5",
        "Stamp Duty": "1", "SEBI Charges": "0.05", "Turnover Tax": "0.5",
        "Other Charges": "0", "GST Amount": "0.5", "Net Amount": "1000",
        "CP CODE": "ORBIS001",
    }])
    cp = get_incred_cp_codes(f)
    assert "INE001" in cp
    assert cp["INE001"] == "ORBIS001"
