"""Sensitivity dashboard — one plot per param showing 24-month p5 staker APY.

Sweeps a parameter over a range and runs a Monte Carlo ensemble at each
point, reporting the p5/p50/p95 of the target metric at month 24.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable

from .model import SimConfig, run
from .monte_carlo import mc_run


def sweep(
    config: SimConfig,
    param_path: str,
    values: list[Any],
    target_metric: str = "staker_apy",
    trials_per_point: int = 500,
    seed: int = 42,
) -> list[dict]:
    """Sweep *param_path* across *values* and collect p5/p50/p95 of *target_metric*.

    *param_path* is a dotted attribute name like ``burn_toll_pct`` or
    ``operating_cost_usd_per_month``.
    """
    results = []
    for v in values:
        cfg = _set_param(config, param_path, v)
        result = mc_run(cfg, n=trials_per_point, seed=seed)
        summary = result.summary([target_metric])
        s = summary[target_metric]
        s["param_value"] = v
        results.append(s)
    return results


def _set_param(cfg: SimConfig, path: str, value: Any) -> SimConfig:
    import copy
    cfg = copy.deepcopy(cfg)
    parts = path.split(".")
    obj = cfg
    for p in parts[:-1]:
        obj = getattr(obj, p)
    setattr(obj, parts[-1], value)
    return cfg


def cli_main():
    import argparse
    ap = argparse.ArgumentParser(description="Sensitivity dashboard")
    ap.add_argument("--preset", default="create-protocol-v4")
    ap.add_argument("--param", default="burn_toll_pct")
    ap.add_argument("--values", type=str, default="0.001,0.005,0.01,0.02,0.05")
    ap.add_argument("--target", default="staker_apy")
    ap.add_argument("--trials", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    from . import presets
    cfg = presets.load(args.preset)
    values = [float(v) for v in args.values.split(",")]
    results = sweep(cfg, args.param, values, args.target, args.trials, args.seed)

    json.dump(results, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    cli_main()
