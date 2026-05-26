"""
Weight calculation and proportional cost allocation for Part 2.
Produces the 19-column Orbis allocation DataFrame.
"""
import math

import pandas as pd

CHARGE_COLS = [
    "Brokerage", "STT", "StampDuty", "SEBIChrg",
    "TurnoverTax", "OtherCharges", "GST",
]

# Rounding precision per output column (last client always gets full precision residual)
_CHARGE_PRECISION = {
    "InputBrokerage":    2,
    "InputSTT":          2,
    "InputStampDuty":    2,
    "InputSEBIChrg":     2,
    "InputTurnOver":     4,
    "InputOtherCharges": 2,
    "InputGST":          2,
}

ALLOCATION_COLUMNS = [
    "S.No", "Client Name", "CustomerNo", "TradeDate", "Exchange Type",
    "Settlement No", "ISIN No", "Buy/ Sell", "Input Quantity",
    "InputBrokerage", "InputSTT", "InputStampDuty", "InputSEBIChrg",
    "InputTurnOver", "InputOtherCharges", "InputGST",
    "InputNetAmount", "InputNetRate", "CP CODE",
]


def allocate_costs(
    matched_session_df: pd.DataFrame,
    broker_df: pd.DataFrame,
    incred_cp_codes: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Allocate broker execution costs proportionally to individual clients.

    Weight = client_qty / total_qty per ISIN+Direction group.
    Last client per group receives residual (broker_total - sum of others)
    for every charge column independently - full precision, no rounding.
    All other clients rounded to 2 decimal places.

    Args:
        matched_session_df: session rows that have a broker match (from matcher)
        broker_df: normalised broker reply DataFrame
        incred_cp_codes: optional dict of ISIN → CP Code from InCred reply

    Returns:
        pd.DataFrame with ALLOCATION_COLUMNS, sorted Batch → S.No, S.No re-numbered from 1.
    """
    session = matched_session_df.copy()
    broker = broker_df.copy()

    broker["_ISIN_upper"] = broker["ISIN"].astype(str).str.strip().str.upper()
    broker["_Dir_upper"] = broker["Direction"].astype(str).str.strip().str.upper()
    broker = broker.set_index(["_ISIN_upper", "_Dir_upper"])

    records = []

    # Sort session by Batch then S.No to preserve original order
    session = session.sort_values(["Batch", "S.No"])

    # Group by ISIN + Direction
    session["_ISIN_upper"] = session["ISIN"].astype(str).str.strip().str.upper()
    session["_Dir_upper"] = session["Direction"].astype(str).str.strip().str.upper()

    for (isin_upper, dir_upper), group in session.groupby(
        ["_ISIN_upper", "_Dir_upper"], sort=False
    ):
        key = (isin_upper, dir_upper)
        if key not in broker.index:
            continue

        broker_row = broker.loc[key]
        if isinstance(broker_row, pd.DataFrame):
            broker_row = broker_row.iloc[0]

        total_qty = group["Qty"].sum()

        # Calculate weights
        weights = group["Qty"] / total_qty

        # Verify weights sum to ~1.0
        if not math.isclose(weights.sum(), 1.0, rel_tol=1e-6):
            raise ValueError(
                f"Allocation error: weights do not sum to 1.0 for ISIN {isin_upper} "
                f"({dir_upper}): got {weights.sum()}. Check for zero or negative quantities."
            )

        trade_date = broker_row["TradeDate"]
        exchange = broker_row["Exchange"]

        group_records = []
        for i, (idx, row) in enumerate(group.iterrows()):
            is_last = i == len(group) - 1
            w = weights[idx]

            rec = {
                "Client Name": row["Client"],
                "CustomerNo": row["OFIN"],
                "TradeDate": trade_date,
                "Exchange Type": exchange,
                "Settlement No": None,
                "ISIN No": row["ISIN"],
                "Buy/ Sell": row["Direction"],
                "Input Quantity": int(row["Qty"]),
                "_Batch": row["Batch"],
                "_SNo": row["S.No"],
            }

            # CP Code: session file first, InCred fallback if blank
            cp = str(row.get("CP Code", "")).strip()
            if not cp and incred_cp_codes:
                cp = incred_cp_codes.get(row["ISIN"].strip().upper(), "")
            rec["CP CODE"] = cp

            # Allocate charge columns
            for charge_col, out_col in zip(
                CHARGE_COLS,
                ["InputBrokerage", "InputSTT", "InputStampDuty", "InputSEBIChrg",
                 "InputTurnOver", "InputOtherCharges", "InputGST"],
            ):
                broker_total = float(broker_row[charge_col])
                if is_last:
                    # Residual: broker_total minus sum of all previous clients
                    already_allocated = sum(
                        r[out_col] for r in group_records
                    )
                    rec[out_col] = broker_total - already_allocated  # full precision
                else:
                    precision = _CHARGE_PRECISION.get(out_col, 2)
                    rec[out_col] = round(w * broker_total, precision)

            # Net Amount
            broker_net = float(broker_row["NetAmount"])
            if is_last:
                already_net = sum(r["InputNetAmount"] for r in group_records)
                rec["InputNetAmount"] = broker_net - already_net  # full precision
            else:
                rec["InputNetAmount"] = round(w * broker_net, 2)

            # Net Rate - full precision
            rec["InputNetRate"] = rec["InputNetAmount"] / int(row["Qty"])

            group_records.append(rec)

        records.extend(group_records)

    if not records:
        return pd.DataFrame(columns=ALLOCATION_COLUMNS)

    result = pd.DataFrame(records)

    # Sort by Batch → S.No (original order)
    result = result.sort_values(["_Batch", "_SNo"]).reset_index(drop=True)
    result.insert(0, "S.No", range(1, len(result) + 1))

    # Drop internal columns
    result = result.drop(columns=["_Batch", "_SNo"], errors="ignore")

    return result[ALLOCATION_COLUMNS]
