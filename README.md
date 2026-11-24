# Pump.fun Replay Sprint — Paper Bot

![Pump.fun Replay Sprint](https://make.fun/badge/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122.svg)
![Rank](https://make.fun/badge/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122/Flowjack94/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122/rank.svg)
![Reward](https://make.fun/badge/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122/Flowjack94/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122/reward.svg)

Entry for the [Pump.fun Replay Sprint — Paper Bot, Real Ranking](https://make.fun/bounty/u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122) competition on make.fun. Paper trading only — no real funds are ever spent.

## Strategy

Early-momentum paper trading on pump.fun bonding curves, written from scratch:

1. **Enter on early momentum** — a new coin is bought only when its price is up ≥12% from first seen, with ≥4 trades, within ~6 minutes of creation. Stake is up to 0.12 SOL per coin (capped by the harness size limit), at most 5 open positions, with a 0.5 SOL cash reserve kept untouched.
2. **Exit by rule** — take profit at +45% vs average cost, stop loss at −20%, time exit after ~10 minutes if still below +10%, and any position older than ~40 minutes is flattened so slots recycle to fresh coins.
3. **Deterministic** — no clock, no environment, no randomness; two runs on the same input produce byte-identical replies. Max slippage 800 bps.

## Run

The grader runs `python3 -P -s main.py` (Python 3.13, stdlib only). The
`makefun_bot` protocol shim is vendored under `vendor/` as its docstring
instructs. `main.py` inserts `vendor/` on `sys.path` and calls
`makefun_bot.run(on_batch)`.

## License

MIT — see [LICENSE](LICENSE).
