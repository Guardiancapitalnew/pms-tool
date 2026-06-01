"""Tests for part2/allocator.py"""
import math
import pytest
import pandas as pd
from part2.allocator import allocate_costs, ALLOCATION_COLUMNS


def _make_session(ofin_list, qty_list, isin, direction="BUY"):
    n = len(ofin_list)
    return pd.DataFrame({
        "S.No": list(range(1, n + 1)),
        "Batch": [1] * n,
        "OFIN": ofin_list,
        "Client": [f"Client {o}" for o in ofin_list],
        "Ticker": ["TEST"] * n,
        "ISIN": [isin] * n,
        "Direction": [direction] * n,
        "Qty": qty_list,
        "Ref Price": [100.0] * n,
        "CP Code": ["ORBIS0000696"] * n,
    })


def _make_broker(isin, direction, total_qty, brokerage=100.0, stt=50.0,
                 stamp=10.0, sebi=0.05, turnover=3.0, other=0.0, gst=14.0,
                 net=10000.0, exchange="NSE"):
    return pd.DataFrame({
        "ISIN": [isin],
        "Direction": [direction],
        "Exchange": [exchange],
        "TradeDate": [pd.Timestamp("2026-05-18")],
        "TotalQty": [total_qty],
        "Brokerage": [brokerage],
        "STT": [stt],
        "StampDuty": [stamp],
        "SEBIChrg": [sebi],
        "TurnoverTax": [turnover],
        "OtherCharges": [other],
        "GST": [gst],
        "NetAmount": [net],
    })


def test_weights_sum_to_one():
    session = _make_session(["A", "B", "C"], [100, 200, 300], "INE001")
    broker = _make_broker("INE001", "BUY", 600)
    result = allocate_costs(session, broker)
    assert not result.empty
    # Weights: 100/600, 200/600, 300/600 - verified via charge sums
    assert math.isclose(
        result["InputBrokerage"].sum(), 100.0, rel_tol=1e-6
    )


def test_charge_columns_split_correctly():
    session = _make_session(["A", "B"], [300, 700], "INE002")
    broker = _make_broker("INE002", "BUY", 1000, brokerage=200.0)
    result = allocate_costs(session, broker)

    row_a = result[result["CustomerNo"] == "A"].iloc[0]
    row_b = result[result["CustomerNo"] == "B"].iloc[0]

    assert math.isclose(row_a["InputBrokerage"], 60.0, rel_tol=1e-4)   # 30%
    assert math.isclose(row_b["InputBrokerage"], 140.0, rel_tol=1e-4)  # 70%


def test_last_client_gets_residual():
    # Use values that cause rounding drift
    session = _make_session(["A", "B", "C"], [1, 1, 1], "INE003")
    broker = _make_broker("INE003", "BUY", 3, brokerage=10.0, net=100.0)
    result = allocate_costs(session, broker)

    # Sum of all brokerage allocations must equal broker total exactly
    assert math.isclose(result["InputBrokerage"].sum(), 10.0, rel_tol=1e-9)
    assert math.isclose(result["InputNetAmount"].sum(), 100.0, rel_tol=1e-9)


def test_input_net_rate_calculation():
    session = _make_session(["A", "B"], [200, 300], "INE004")
    broker = _make_broker("INE004", "SELL", 500, net=50000.0)
    result = allocate_costs(session, broker)

    for _, row in result.iterrows():
        expected_rate = row["InputNetAmount"] / row["Input Quantity"]
        assert math.isclose(row["InputNetRate"], expected_rate, rel_tol=1e-9)


def test_single_client_all_charges_unchanged():
    session = _make_session(["A"], [500], "INE005")
    broker = _make_broker("INE005", "BUY", 500, brokerage=150.0, net=50150.0)
    result = allocate_costs(session, broker)

    assert len(result) == 1
    assert math.isclose(result.iloc[0]["InputBrokerage"], 150.0, rel_tol=1e-9)
    assert math.isclose(result.iloc[0]["InputNetAmount"], 50150.0, rel_tol=1e-9)


def test_sno_renumbered_sequentially():
    session = _make_session(["A", "B", "C"], [100, 200, 300], "INE006")
    broker = _make_broker("INE006", "BUY", 600)
    result = allocate_costs(session, broker)
    assert list(result["S.No"]) == [1, 2, 3]


def test_output_has_all_19_columns():
    session = _make_session(["A"], [100], "INE007")
    broker = _make_broker("INE007", "BUY", 100)
    result = allocate_costs(session, broker)
    assert list(result.columns) == ALLOCATION_COLUMNS


def test_settlement_no_always_blank():
    session = _make_session(["A", "B"], [100, 200], "INE008")
    broker = _make_broker("INE008", "BUY", 300)
    result = allocate_costs(session, broker)
    assert result["Settlement No"].isna().all() or (result["Settlement No"] == "").all()


def test_incred_cp_code_used_when_session_cp_code_blank():
    """When CP Code is blank in the session row and an InCred reply is
    being processed, the allocator should fill it from incred_cp_codes."""
    session = _make_session(["A", "B"], [100, 200], "INE111")
    session["CP Code"] = ""  # blank everywhere
    broker = _make_broker("INE111", "BUY", 300)
    incred_cp = {"INE111": "ORBIS-INCRED-001"}
    result = allocate_costs(session, broker, incred_cp_codes=incred_cp)
    assert set(result["CP CODE"]) == {"ORBIS-INCRED-001"}


def test_session_cp_code_takes_priority_over_incred():
    """If the session file already has a CP Code, the InCred fallback must
    NOT overwrite it - session is the source of truth."""
    session = _make_session(["A", "B"], [100, 200], "INE222")
    session["CP Code"] = "SESSION-CP-VALUE"
    broker = _make_broker("INE222", "BUY", 300)
    incred_cp = {"INE222": "ORBIS-INCRED-999"}
    result = allocate_costs(session, broker, incred_cp_codes=incred_cp)
    assert set(result["CP CODE"]) == {"SESSION-CP-VALUE"}


def test_multibatch_sort_order():
    session = pd.DataFrame({
        "S.No": [1, 2, 1, 2],
        "Batch": [1, 1, 2, 2],
        "OFIN": ["A", "B", "C", "D"],
        "Client": ["CA", "CB", "CC", "CD"],
        "Ticker": ["TEST"] * 4,
        "ISIN": ["INE009"] * 4,
        "Direction": ["BUY"] * 4,
        "Qty": [100, 200, 150, 50],
        "Ref Price": [10.0] * 4,
        "CP Code": ["X"] * 4,
    })
    broker = _make_broker("INE009", "BUY", 500, net=5000.0)
    result = allocate_costs(session, broker)

    # Should be sorted Batch 1 first (A, B), then Batch 2 (C, D)
    assert list(result["CustomerNo"]) == ["A", "B", "C", "D"]
    assert list(result["S.No"]) == [1, 2, 3, 4]
