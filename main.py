# SPDX-License-Identifier: MIT
"""Pump.fun Replay Sprint paper bot — early-momentum entries, disciplined exits.

Strategy (written from scratch for agent-fun/replay/v2):
  * Watch every new bonding curve from its CreateEvent and record its first
    seen price (virtual_quote_reserves / virtual_token_reserves).
  * Enter when a coin shows early momentum: price up >= 12% from first seen,
    at least 4 trades, within 900 slots (~6 min) of creation. Stake is
    min(0.12 SOL, the harness size cap), at least 0.02 SOL, at most 5 open
    positions, and cash is never drawn below a 0.5 SOL reserve.
  * Exit every position by rule, never by hope: take profit at +45% vs the
    average cost price, stop loss at -20%, and a time exit after 1500 slots
    (~10 min) if the position is still below +10%. Old positions are
    flattened after 6000 slots so slots recycle for fresh coins.
  * Max slippage 800 bps. No real funds are ever touched: this is paper
    trading on a replay; the bot only ever emits buy/sell orders.

Determinism: no clock, no environment, no randomness. All state lives in
insertion-ordered dicts and is iterated in insertion order only.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bot  # noqa: E402

SOL = makefun_bot.LAMPORTS_PER_SOL
STAKE_LAMPORTS = 12 * SOL // 100          # 0.12 SOL target stake per coin
MIN_STAKE_LAMPORTS = 2 * SOL // 100       # 0.02 SOL minimum meaningful stake
CASH_RESERVE_LAMPORTS = SOL // 2          # keep 0.5 SOL cash untouched
MAX_SLIPPAGE_BPS = 800

ENTRY_RISE_NUM = 112                      # price >= 112% of first-seen price
ENTRY_MIN_TRADES = 4
ENTRY_WINDOW_SLOTS = 900                  # ~6 min after creation
TAKE_PROFIT_NUM = 145                     # +45% vs average cost price
STOP_LOSS_NUM = 80                        # -20% vs average cost price
TIME_EXIT_SLOTS = 1500                    # ~10 min
TIME_EXIT_MIN_NUM = 110                   # time exit only if below +10%
MAX_HOLD_SLOTS = 6000                     # flatten anything older than this

# mint -> [first_price_num, first_price_den, first_slot]; insertion ordered.
_seen = {}
# mint -> slot the buy order was sent on.
_buy_slot = {}


def _price(curve):
    """Current price as (numerator, denominator) in lamports per token, or None."""
    if curve is None or curve.virtual_token_reserves <= 0:
        return None
    return (curve.virtual_quote_reserves, curve.virtual_token_reserves)


def _ratio_ge(num_a, den_a, num_b, den_b, pct_num, pct_den=100):
    """True when a/b >= pct_num/pct_den, using exact integer arithmetic."""
    return num_a * den_b * pct_den >= num_b * den_a * pct_num


def on_batch(state, batch):
    caps = state.hello["caps"]
    tx = state.tx_fee_lamports()
    free = state.free_cash_lamports()
    slots = caps["max_open_positions"] - state.committed_position_count()
    orders = []
    max_orders = caps["max_orders_per_batch"]
    slot = state.slot

    # --- exits first: free slots and lock in results before buying more. ---
    pending_sell = set()
    for p in state.pending.values():
        if p.order["side"] == "sell":
            pending_sell.add(p.order["mint"])
    for mint in list(state.positions.keys()):
        if len(orders) >= max_orders:
            break
        if mint in pending_sell:
            continue
        holding = state.positions[mint]
        curve = state.curves.get(mint)
        if curve is None or curve.complete or holding.token_amount <= 0:
            continue
        price = _price(curve)
        if price is None:
            continue
        # cost price = cost_lamports per token held.
        cost_num, cost_den = holding.cost_lamports, holding.token_amount
        p_num, p_den = price
        age = slot - _buy_slot.get(mint, slot)
        take_profit = _ratio_ge(p_num, p_den, cost_num, cost_den, TAKE_PROFIT_NUM)
        stop_loss = not _ratio_ge(p_num, p_den, cost_num, cost_den, STOP_LOSS_NUM)
        time_exit = age >= TIME_EXIT_SLOTS and not _ratio_ge(
            p_num, p_den, cost_num, cost_den, TIME_EXIT_MIN_NUM
        )
        if take_profit or stop_loss or time_exit or age >= MAX_HOLD_SLOTS:
            orders.append(
                {
                    "side": "sell",
                    "mint": mint,
                    "token_amount": holding.token_amount,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            )
            pending_sell.add(mint)

    # --- entries: early momentum on coins created in this window. ---
    for e in batch["events"]:
        if len(orders) >= max_orders or slots <= 0:
            break
        mint = e["mint"]
        kind = e["event"]
        curve = state.curves.get(mint)
        if curve is None or curve.complete:
            _seen.pop(mint, None)
            continue
        if kind == "CreateEvent":
            price = _price(curve)
            if price is not None and mint not in _seen:
                _seen[mint] = [price[0], price[1], e["slot"]]
            continue
        if kind != "TradeEvent":
            continue
        first = _seen.get(mint)
        if first is None:
            continue
        if mint in state.positions:
            continue
        if any(p.order["mint"] == mint for p in state.pending.values()):
            continue
        if slot - first[2] > ENTRY_WINDOW_SLOTS:
            _seen.pop(mint, None)
            continue
        if curve.trades < ENTRY_MIN_TRADES:
            continue
        price = _price(curve)
        if price is None:
            continue
        if not _ratio_ge(price[0], price[1], first[0], first[1], ENTRY_RISE_NUM):
            continue
        cap = state.max_buy_lamports(mint)
        if cap < MIN_STAKE_LAMPORTS:
            continue
        amount = cap if cap < STAKE_LAMPORTS else STAKE_LAMPORTS
        if free < amount + tx + CASH_RESERVE_LAMPORTS:
            continue
        orders.append(
            {
                "side": "buy",
                "mint": mint,
                "quote_lamports": amount,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }
        )
        _buy_slot[mint] = slot
        _seen.pop(mint, None)
        free -= amount + tx
        slots -= 1

    return orders


if __name__ == "__main__":
    makefun_bot.run(on_batch)
