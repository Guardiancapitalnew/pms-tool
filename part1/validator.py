"""
Sell and buy validation logic for Part 1.
Returns the research DataFrame enriched with Status, Reason, ISIN, and Context columns.
"""
import pandas as pd

from utils.isin import lookup_isin, build_isin_index


def _get_committed_cash(existing_session_df: pd.DataFrame | None) -> dict[str, float]:
    """Calculate committed cash per OFIN from an existing session file.

    Only BUY rows contribute to committed cash.

    Args:
        existing_session_df: existing session file DataFrame or None

    Returns:
        dict mapping OFIN → total committed cash (float)
    """
    if existing_session_df is None or existing_session_df.empty:
        return {}

    buys = existing_session_df[
        existing_session_df["Direction"].str.upper() == "BUY"
    ].copy()

    buys["committed"] = pd.to_numeric(buys["Qty"], errors="coerce") * \
                        pd.to_numeric(buys["Ref Price"], errors="coerce")

    return buys.groupby("OFIN")["committed"].sum().to_dict()


def validate_orders(
    research_df: pd.DataFrame,
    bank_book: dict[str, float],
    scrip_df: pd.DataFrame,
    isin_db: pd.DataFrame,
    existing_session_df: pd.DataFrame | None = None,
    tolerance: float = 0.0,
) -> pd.DataFrame:
    """Validate all orders in the research file.

    Sell validation: units_held >= qty_ordered
    Buy validation: (bank_balance - committed_cash) >= qty * ref_price * (1 + tol/100)

    Args:
        research_df: parsed research file DataFrame
        bank_book: dict of {OFIN: cash_balance}
        scrip_df: parsed scrip-wise report DataFrame [OFIN, Scrip Name, ISIN, Quantity]
        isin_db: ISIN database DataFrame
        existing_session_df: optional existing session file for batch-2 committed cash
        tolerance: price tolerance % for buy cash check (default 0)

    Returns:
        research_df with additional columns:
            ISIN (str), Status ('GREEN'|'RED'), Reason (str), Context (str)
    """
    df = research_df.copy()

    # Normalise scrip_df for merging
    scrip_norm = scrip_df.copy()
    scrip_norm["Scrip Name"] = scrip_norm["Scrip Name"].str.upper().str.strip()
    scrip_norm["OFIN"] = scrip_norm["OFIN"].astype(str).str.strip()

    # Build O(1) lookup index once - avoids re-scanning 5K rows per order
    isin_index = build_isin_index(isin_db)

    # ISIN lookup - scrip_df first, then isin_db index
    def _lookup_isin_for_row(ticker: str, ofin: str, direction: str) -> str:
        # Try scrip-wise report for this ticker (any client row)
        matches = scrip_norm[scrip_norm["Scrip Name"] == ticker.upper().strip()]
        if not matches.empty and matches.iloc[0]["ISIN"]:
            return matches.iloc[0]["ISIN"]
        # Fall back to ISIN database - O(1) dict lookup
        isin = lookup_isin(ticker, isin_db, _index=isin_index)
        return isin if isin else ""

    df["ISIN"] = df.apply(
        lambda r: _lookup_isin_for_row(str(r["Ticker"]), str(r["OFIN"]), str(r["Direction"])),
        axis=1,
    )

    # Committed cash from existing session file
    committed_cash = _get_committed_cash(existing_session_df)

    statuses, reasons, contexts = [], [], []

    # Merge sell rows with holdings in one vectorised pass
    sells_mask = df["Direction"] == "SELL"
    buys_mask = df["Direction"] == "BUY"

    # --- SELL VALIDATION ---
    if sells_mask.any():
        sells = df[sells_mask].copy()
        sells["_Ticker_upper"] = sells["Ticker"].str.upper().str.strip()

        merged = sells.merge(
            scrip_norm[["OFIN", "Scrip Name", "Quantity"]].rename(
                columns={"Quantity": "_held", "Scrip Name": "_Ticker_upper"}
            ),
            on=["OFIN", "_Ticker_upper"],
            how="left",
        )

        sell_status, sell_reason, sell_context = [], [], []
        for _, row in merged.iterrows():
            held = row.get("_held")
            qty = row["Qty"]

            if pd.isna(held):
                sell_status.append("RED")
                sell_reason.append("Client not found in holdings report")
                sell_context.append("")
            elif held == 0:
                sell_status.append("RED")
                sell_reason.append(f"Client holds 0 units of {row['Ticker']}")
                sell_context.append("0 Units")
            elif held < qty:
                sell_status.append("RED")
                sell_reason.append(
                    f"Insufficient units - holds {int(held):,}, needs {int(qty):,}"
                )
                sell_context.append(f"{int(held):,} Units")
            else:
                sell_status.append("GREEN")
                sell_reason.append("")
                sell_context.append(f"{int(held):,} Units")

        # Map results back to original index order
        sell_results = pd.DataFrame({
            "Status": sell_status,
            "Reason": sell_reason,
            "Context": sell_context,
        }, index=merged.index)

        for idx, orig_idx in enumerate(df[sells_mask].index):
            statuses.append((orig_idx, sell_results.iloc[idx]["Status"]))
            reasons.append((orig_idx, sell_results.iloc[idx]["Reason"]))
            contexts.append((orig_idx, sell_results.iloc[idx]["Context"]))

    # --- BUY VALIDATION ---
    if buys_mask.any():
        for orig_idx, row in df[buys_mask].iterrows():
            ofin = str(row["OFIN"])
            qty = row["Qty"]
            ref_price = row["Ref Price"]

            if ofin not in bank_book:
                statuses.append((orig_idx, "RED"))
                reasons.append((orig_idx, "Client not found in bank book"))
                contexts.append((orig_idx, ""))
                continue

            balance = bank_book[ofin]
            committed = committed_cash.get(ofin, 0.0)
            available = balance - committed
            required = qty * ref_price * (1 + tolerance / 100)

            if available < 0:
                statuses.append((orig_idx, "RED"))
                reasons.append((orig_idx, f"Negative cash balance: −₹{abs(available):,.2f}"))
                contexts.append((orig_idx, f"Available: −₹{abs(available):,.2f}"))
            elif available < required:
                statuses.append((orig_idx, "RED"))
                reasons.append((orig_idx,
                    f"Insufficient cash - available ₹{available:,.2f}, needs ₹{required:,.2f}"
                ))
                contexts.append((orig_idx, f"Available: ₹{available:,.2f}"))
            else:
                statuses.append((orig_idx, "GREEN"))
                reasons.append((orig_idx, ""))
                contexts.append((orig_idx, f"Available: ₹{available:,.2f}"))

    # Write results back to df in original row order
    status_map = dict(statuses)
    reason_map = dict(reasons)
    context_map = dict(contexts)

    df["Status"] = df.index.map(status_map)
    df["Reason"] = df.index.map(reason_map)
    df["Context"] = df.index.map(context_map)

    return df
