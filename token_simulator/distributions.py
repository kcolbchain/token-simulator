"""Scipy-style distribution descriptors for Monte Carlo config values.

Each distribution is a dict with the same shape that ``scipy.stats``
would accept::

    {"dist": "beta", "a": 2, "b": 8}
    {"dist": "uniform", "loc": 0, "scale": 1}
    {"dist": "norm", "loc": 100, "scale": 20}

A scalar float/int is treated as a degenerate distribution that always
returns the same value (no sampling overhead).
"""

from __future__ import annotations

import math
import random
from typing import Any, Mapping


class DistributionParseError(ValueError):
    """Raised when a distribution descriptor cannot be parsed."""


SAMPLE_CACHE: dict[str, Any] = {}


def _beta_sample(a: float, b: float, rng: random.Random) -> float:
    """Generate a sample from Beta(a, b) using only stdlib ``random``."""
    # Use the Beta variate via Gamma: Beta(a,b) = Gamma(a,1) / (Gamma(a,1) + Gamma(b,1))
    # Use Marsaglia-Tsang for Gamma
    def _gamma(shape: float) -> float:
        if shape < 1:
            return _gamma(shape + 1) * (rng.random() ** (1 / shape))
        d = shape - 1 / 3
        c = 1 / math.sqrt(9 * d)
        while True:
            x = rng.gauss(0, 1)
            v = 1 + c * x
            if v <= 0:
                continue
            v = v ** 3
            u = rng.random()
            if u < 1 - 0.0331 * (x * x) ** 2:
                return d * v
            if math.log(u) < 0.5 * x * x + d * (1 - v + math.log(v)):
                return d * v

    ga = _gamma(a)
    gb = _gamma(b)
    return ga / (ga + gb)


def sample_value(spec: Any, rng: random.Random) -> float:
    """Draw a single sample from a distribution descriptor or return the scalar.

    Parameters
    ----------
    spec:
        A dict like ``{"dist": "beta", "a": 2, "b": 8}``, or a plain
        float/int that is returned as-is.
    rng:
        A ``random.Random`` instance (seeded for reproducibility).

    Returns
    -------
    A single float sample.
    """
    if isinstance(spec, (int, float)):
        return float(spec)
    if not isinstance(spec, Mapping):
        raise DistributionParseError(f"Expected dict or number, got {type(spec).__name__}")

    dist = spec.get("dist")
    if not dist:
        raise DistributionParseError("Distribution descriptor missing 'dist' key")

    if dist == "beta":
        return _beta_sample(float(spec["a"]), float(spec["b"]), rng)
    elif dist == "uniform":
        return rng.uniform(float(spec.get("loc", 0)), float(spec.get("loc", 0)) + float(spec.get("scale", 1)))
    elif dist == "norm":
        return rng.gauss(float(spec.get("loc", 0)), float(spec.get("scale", 1)))
    elif dist == "loguniform":
        low = math.log(float(spec.get("low", 1)))
        high = math.log(float(spec.get("high", 10)))
        return math.exp(rng.uniform(low, high))
    elif dist == "triangular":
        return rng.triangular(
            float(spec.get("low", 0)),
            float(spec.get("high", 1)),
            float(spec.get("mode", 0.5)),
        )
    elif dist == "choice":
        values = spec.get("values", [])
        weights = spec.get("weights")
        if weights:
            return rng.choices(values, weights=weights, k=1)[0]
        return rng.choice(values)
    else:
        raise DistributionParseError(f"Unknown distribution: {dist!r}")


def is_distribution(spec: Any) -> bool:
    """Return True if *spec* describes a random distribution (vs. a scalar)."""
    return isinstance(spec, Mapping) and "dist" in spec


def resolve_distributions(config_obj: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Walk a config dict and replace all distribution descriptors with sampled values.

    Nested dicts and lists are traversed recursively. Non-distribution values
    are left unchanged.
    """
    out: dict[str, Any] = {}
    for k, v in config_obj.items():
        if isinstance(v, Mapping) and "dist" in v:
            out[k] = sample_value(v, rng)
        elif isinstance(v, list):
            out[k] = [_resolve_list_item(item, rng) for item in v]
        elif isinstance(v, dict):
            out[k] = resolve_distributions(v, rng)
        else:
            out[k] = v
    return out


def _resolve_list_item(item: Any, rng: random.Random) -> Any:
    if isinstance(item, Mapping) and "dist" in item:
        return sample_value(item, rng)
    return item
