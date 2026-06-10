# token-simulator
[![CI](https://github.com/kcolbchain/token-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/kcolbchain/token-simulator/actions/workflows/ci.yml) [![repo](https://img.shields.io/badge/repo-token--simulator-blue)](https://github.com/kcolbchain/token-simulator)

Model token economies: burn tolls, staking yields, vesting, liquidity pools,
multi-stream revenue. Python reference implementation + zero-build browser
dashboard that runs the same math client-side.

By [kcolbchain](https://kcolbchain.com) (est. 2015).

## Why this exists

Most tokenomics spreadsheets hard-code three numbers, hide their assumptions,
and plot a single line labelled "projected price". That is not a model — it
is a slogan with a legend.

This repo provides:

- A small, readable Python library (`token_simulator/`) with explicit
  parameters, deterministic trajectories, and unit tests.
- A static browser dashboard (`web/`) that runs the same model without a
  backend — adjust sliders and see supply / circulating / burn-rate /
  treasury / staker-APY evolve together.
- Presets for real protocols (starting with `create-protocol-v4`) so the
  library doubles as the economic-sim home for
  [Create Protocol](https://createprotocol.org) and future kcolbchain
  launches.

## Quick start (library)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

python -m token_simulator run --preset create-protocol-v4 --months 24
```

Outputs a CSV trajectory plus a summary table. Scripts in `examples/` show
how to load a preset, override a parameter, and plot.

## Quick start (dashboard)

```bash
python3 -m http.server -d web 8080
# open http://localhost:8080
```

No build. Single `index.html` with the simulator inline. Tweak sliders,
switch presets, watch the plots update.

## What it models

- **Revenue streams** — any number, each with its own volume curve and margin.
- **Burn toll** — a % of flow that burns native token via AMM buy-and-burn;
  burn size depends on pool depth, not just the toll rate.
- **Vault yield** — idle deposits auto-compound at a configurable APY, with an
  operating-cost line deducted first (not added on top, where most sims
  cheat).
- **Vesting** — per-bucket unlock schedules (team / community / treasury /
  liquidity / legacy) with independent sell-at-unlock rates.
- **Endogenous price** — supply shrink via burn + locked supply via staking
  feeds back into price via a simple constant-product pool. Not a prediction
  — a consistency check.
- **Growth tapering** — replace the classic constant-growth lie with a
  logistic curve so the sim can't claim 1.3×/mo forever.

## What it does *not* model (yet)

- Cross-chain liquidity fragmentation.
- Competitor entry / exit.
- Governance actions (toll-rate changes) during the sim window.
- Regulatory shock.
- Speculative cycles — the model is *consistency-checking*, not
  price-prediction. If the sim says "burn rate > circulating within 3 years,"
  that is a real alarm. If it says "FDV = $X at month 24," that is nonsense.

Monte Carlo mode (each parameter becomes a distribution, 10k trajectories,
p5/p50/p95 reporting) is tracked in
[#1](https://github.com/kcolbchain/token-simulator/issues/1).

## Presets

| Preset                   | Source                                                                                                                    |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `create-protocol-v4`     | CR8 burn-toll + CR8-USD (see `cr8-token-design-v4.md` / `cr8-simulation-parameters.md` in internal docs)                  |
| `generic-fee-share`      | Vanilla fee-share token, no burn, 70/30 revenue split — baseline to compare burn-toll against                             |
| `standard-dao`            | Standard DAO token with team/investor vesting, staking yield, and governance participation bonus mechanics                 |

Add a preset by registering it in `token_simulator/presets.py` (or by
adding loader support for external YAML presets). Registered presets appear
in the CLI list and can be run with `token-simulator run --preset <name>`.

## License

MIT.
