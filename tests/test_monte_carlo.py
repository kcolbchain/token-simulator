"""Tests for Monte Carlo mode and distribution support."""

from __future__ import annotations

import json
import random

import pytest

from token_simulator.distributions import sample_value, is_distribution, resolve_distributions
from token_simulator.monte_carlo import mc_run, MCResult
from token_simulator import presets


def test_scalar_returns_self():
    rng = random.Random(42)
    assert sample_value(3.14, rng) == 3.14
    assert sample_value(42, rng) == 42.0


def test_beta_distribution():
    rng = random.Random(42)
    spec = {"dist": "beta", "a": 2, "b": 8}
    vals = [sample_value(spec, random.Random(42 + i)) for i in range(1000)]
    assert all(0 < v < 1 for v in vals)
    mean = sum(vals) / len(vals)
    assert 0.1 < mean < 0.4  # Beta(2,8) mean ≈ 0.2


def test_uniform_distribution():
    rng = random.Random(42)
    spec = {"dist": "uniform", "loc": 10, "scale": 5}
    vals = [sample_value(spec, random.Random(42 + i)) for i in range(100)]
    assert all(10 <= v <= 15 for v in vals)


def test_normal_distribution():
    rng = random.Random(42)
    spec = {"dist": "norm", "loc": 100, "scale": 10}
    vals = [sample_value(spec, random.Random(42 + i)) for i in range(1000)]
    mean = sum(vals) / len(vals)
    assert 90 < mean < 110


def test_is_distribution():
    assert is_distribution({"dist": "beta", "a": 1, "b": 1})
    assert not is_distribution(42)
    assert not is_distribution("hello")


def test_resolve_distributions():
    rng = random.Random(42)
    config = {
        "burn_toll_pct": {"dist": "uniform", "loc": 0.005, "scale": 0.01},
        "operating_cost_usd_per_month": 5000,
    }
    resolved = resolve_distributions(config, rng)
    assert 0.005 <= resolved["burn_toll_pct"] <= 0.015
    assert resolved["operating_cost_usd_per_month"] == 5000


def test_mc_run_reproducible():
    cfg = presets.load("create-protocol-v4")
    r1 = mc_run(cfg, n=50, seed=42)
    r2 = mc_run(cfg, n=50, seed=42)
    assert r1.trajectories[0].final_state.circulating_supply == r2.trajectories[0].final_state.circulating_supply


def test_mc_run_with_distribution_overrides():
    cfg = presets.load("create-protocol-v4")
    overrides = {
        "burn_toll_pct": {"dist": "uniform", "loc": 0.005, "scale": 0.01},
    }
    result = mc_run(cfg, n=20, seed=42, distribution_overrides=overrides)
    assert len(result.trajectories) == 20
    summary = result.summary()
    assert "circulating_supply" in summary
    assert "price_usd" in summary
    assert "probability_of_ruin" in summary


def test_mc_result_percentiles():
    cfg = presets.load("create-protocol-v4")
    result = mc_run(cfg, n=50, seed=42)
    p5 = result.p5("circulating_supply")
    p50 = result.p50("circulating_supply")
    p95 = result.p95("circulating_supply")
    assert p5 <= p50 <= p95


def test_mc_result_probability_of_ruin():
    cfg = presets.load("create-protocol-v4")
    result = mc_run(cfg, n=20, seed=42)
    pr = result.probability_of_ruin()
    assert 0.0 <= pr <= 1.0


def test_scalar_collapses_to_deterministic():
    """With all-scalar config (no distributions), MC should produce identical trajectories."""
    cfg = presets.load("create-protocol-v4")
    del cfg.revenue_streams[0]
    cfg.revenue_streams = []
    cfg.vest_buckets = []
    cfg.months = 6
    result = mc_run(cfg, n=10, seed=0)
    vals = [t.final_state.circulating_supply for t in result.trajectories]
    assert all(v == vals[0] for v in vals)
