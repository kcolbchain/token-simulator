"""V4 burn-toll scenario: Create Protocol burn-toll model with Monte Carlo.

Every $X of CR8-USD mint/redeem removes X * toll / price(t) CR8 from
circulating supply, where price(t) is endogenous (constant-product AMM).

This scenario exercises:
- Burn toll on stablecoin flow
- Operating-cost deduction from vault
- Logistic growth tapering with configurable params
- Beta-distributed vest-sell curve
- Endogenous CR8 price via AMM constant-product model
- Sensitivity dashboard (p5/p50/p95 at month 24)
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

from token_simulator import presets
from token_simulator.monte_carlo import mc_run


def run_scenario(
    preset_name: str = "create-protocol-v4",
    trials: int = 10_000,
    seed: int = 42,
    output: str = "json",
):
    cfg = presets.load(preset_name)
    cfg.months = 24

    distribution_overrides = {
        "burn_toll_pct": {"dist": "uniform", "loc": 0.005, "scale": 0.01},
        "operating_cost_usd_per_month": {"dist": "uniform", "loc": 2000, "scale": 6000},
    }

    result = mc_run(cfg, n=trials, seed=seed, distribution_overrides=distribution_overrides)

    summary = result.summary()
    summary["meta"] = {
        "preset": preset_name,
        "trials": trials,
        "seed": seed,
        "months": cfg.months,
        "ruin_probability": result.probability_of_ruin(),
    }

    if output == "json":
        json.dump(summary, sys.stdout, indent=2, default=str)
        print()
    else:
        print(f"=== V4 Burn-Toll Scenario Report ===")
        print(f"Preset: {preset_name} | Trials: {trials} | Seed: {seed}")
        print(f"Ruin probability: {result.probability_of_ruin():.4f}")
        print()
        for metric, stats in summary.items():
            if metric == "meta":
                continue
            print(f"  {metric}:")
            for k, v in stats.items():
                print(f"    {k}: {v}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="V4 burn-toll scenario runner")
    ap.add_argument("--preset", default="create-protocol-v4")
    ap.add_argument("--trials", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output", choices=["json", "text"], default="json")
    args = ap.parse_args()
    run_scenario(args.preset, args.trials, args.seed, args.output)
