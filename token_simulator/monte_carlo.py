"""Monte Carlo simulation mode for the token-economy model.

Each config parameter can be either a scalar or a distribution descriptor
(see :mod:`token_simulator.distributions`). ``mc_run`` draws ``n``
independent trajectories and returns aggregated statistics.
"""

from __future__ import annotations

import random
from dataclasses import asdict, fields, is_dataclass
from typing import Any, List, Optional, get_args, get_origin, get_type_hints

from . import distributions as dists
from .model import RevenueStream, SimConfig, VestBucket, run

MC_DEFAULT_TRIALS = 10_000


class MCTrajectory:
    """Holds data for a single Monte Carlo trial."""

    def __init__(self, trial: int, states: list, config_snapshot: dict):
        self.trial = trial
        self.states = states
        self.config_snapshot = config_snapshot

    @property
    def final_state(self):
        return self.states[-1] if self.states else None

    @property
    def ruined(self) -> bool:
        return len(self.states) < self.config_snapshot.get("months", 24)


class MCResult:
    """Aggregated Monte Carlo output.

    For each numeric metric, provides p5 / p50 / p95 across the
    ensemble of trajectories.
    """

    def __init__(self, trajectories: List[MCTrajectory]):
        self.trajectories = trajectories
        self._metrics: dict[str, list[float]] = {}
        self._aggregated: dict[str, dict[str, float]] = {}

    def _extract(self, attr: str) -> list[float]:
        if attr not in self._metrics:
            vals = []
            for t in self.trajectories:
                fs = t.final_state
                if fs is not None:
                    vals.append(getattr(fs, attr))
            self._metrics[attr] = vals
        return self._metrics[attr]

    def _percentile(self, vals: list[float], p: float) -> float:
        if not vals:
            return float("nan")
        sorted_vals = sorted(vals)
        idx = int(len(sorted_vals) * p / 100)
        if idx >= len(sorted_vals):
            idx = len(sorted_vals) - 1
        return sorted_vals[idx]

    def p5(self, attr: str) -> float:
        return self._percentile(self._extract(attr), 5)

    def p50(self, attr: str) -> float:
        return self._percentile(self._extract(attr), 50)

    def p95(self, attr: str) -> float:
        return self._percentile(self._extract(attr), 95)

    def mean(self, attr: str) -> float:
        vals = self._extract(attr)
        return sum(vals) / len(vals) if vals else float("nan")

    def probability_of_ruin(self) -> float:
        ruined = sum(1 for t in self.trajectories if t.ruined)
        return ruined / len(self.trajectories) if self.trajectories else float("nan")

    def summary(self, attrs: Optional[list[str]] = None) -> dict[str, dict[str, float]]:
        if attrs is None:
            attrs = [
                "circulating_supply", "price_usd", "mcap_usd",
                "staker_apy", "burn_toll_usd", "tokens_burned",
                "vault_usd",
            ]
        out = {}
        for attr in attrs:
            out[attr] = {
                "p5": self.p5(attr),
                "p50": self.p50(attr),
                "p95": self.p95(attr),
                "mean": self.mean(attr),
            }
        out["probability_of_ruin"] = {"p5": self.probability_of_ruin(), "p50": self.probability_of_ruin(), "p95": self.probability_of_ruin(), "mean": self.probability_of_ruin()}
        return out


def _dataclass_to_dict(obj: Any) -> dict:
    """Recursively convert a dataclass (and its nested dataclasses) to a flat dict."""
    if is_dataclass(obj):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            if is_dataclass(value):
                result[field_name] = _dataclass_to_dict(value)
            elif isinstance(value, list) and value and is_dataclass(value[0]):
                result[field_name] = [_dataclass_to_dict(item) for item in value]
            else:
                result[field_name] = value
        return result
    return obj


def _dict_to_config(d: dict) -> SimConfig:
    """Convert a flat dict back to a SimConfig, rehydrating nested dataclass lists."""
    field_types = get_type_hints(SimConfig)
    cfg = SimConfig()
    for key, value in d.items():
        if not hasattr(cfg, key):
            continue
        item_cls = _list_item_dataclass(field_types.get(key))
        if item_cls and isinstance(value, list):
            value = [item_cls(**v) if isinstance(v, dict) else v for v in value]
        setattr(cfg, key, value)
    return cfg


def _list_item_dataclass(type_hint: Any) -> Optional[type]:
    """Return the dataclass element type for ``List[Foo]`` style hints, else None."""
    if get_origin(type_hint) is list:
        args = get_args(type_hint)
        if args and is_dataclass(args[0]):
            return args[0]
    return None


def mc_run(
    config: SimConfig,
    n: int = MC_DEFAULT_TRIALS,
    seed: Optional[int] = None,
    distribution_overrides: Optional[dict[str, Any]] = None,
) -> MCResult:
    """Run ``n`` Monte Carlo trajectories.

    Parameters
    ----------
    config:
        Base ``SimConfig``. Scalar fields are used as-is unless overridden.
    n:
        Number of independent trajectories.
    seed:
        RNG seed for reproducibility.
    distribution_overrides:
        A dict mapping field names (dotted paths supported) to distribution
        descriptors. Overrides scalar values in *config*.

    Returns
    -------
    An ``MCResult`` with aggregated statistics.
    """
    rng = random.Random(seed)
    base_dict = _dataclass_to_dict(config)

    trajectories: List[MCTrajectory] = []

    for trial in range(n):
        trial_config = base_dict.copy()
        if distribution_overrides:
            overrides = dists.resolve_distributions(distribution_overrides, rng)
            trial_config.update(overrides)

        cfg = _dict_to_config(trial_config)
        states = run(cfg)
        trajectories.append(MCTrajectory(trial, states, trial_config))

    return MCResult(trajectories)
