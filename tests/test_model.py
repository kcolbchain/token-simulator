"""Sanity tests for the token-simulator model."""

from __future__ import annotations

import pytest

from token_simulator import presets
from token_simulator.model import RevenueStream, SimConfig, VestBucket, run


def test_preset_loads_and_runs():
    cfg = presets.load("create-protocol-v4")
    traj = run(cfg)
    assert len(traj) == cfg.months
    assert all(s.circulating_supply > 0 for s in traj)
    assert traj[0].volume_usd > 0


def test_burn_toll_shrinks_circulating_relative_to_no_burn():
    on = presets.load("create-protocol-v4")
    off = presets.load("create-protocol-v4")
    off.enable_burn_toll = False

    t_on = run(on)[-1]
    t_off = run(off)[-1]
    # With burn on, the pool holds more USDC (toll pushed in) AND fewer CR8.
    assert t_on.pool_cr8 < t_off.pool_cr8
    assert t_on.circulating_supply < t_off.circulating_supply


def test_ops_cost_reduces_vault_yield():
    cfg = presets.load("create-protocol-v4")
    cfg.operating_cost_usd_per_month = 0
    without = run(cfg)[-1].vault_usd

    cfg = presets.load("create-protocol-v4")
    cfg.operating_cost_usd_per_month = 20_000
    withcost = run(cfg)[-1].vault_usd
    assert withcost < without


def test_growth_tapers_at_cap():
    cfg = SimConfig(
        months=24,
        revenue_streams=[
            RevenueStream(
                name="single",
                volume_usd_m0=1_000,
                growth_rate=1.50,
                volume_cap_usd=10_000,  # tiny cap → should hit it fast
                margin_pct=0.3,
                touches_burn_toll=True,
            )
        ],
        vest_buckets=[],
    )
    traj = run(cfg)
    final_volume = traj[-1].volume_usd
    # must asymptote at or below cap, not run to infinity
    assert final_volume <= 10_000 * 1.01


def test_generic_fee_share_has_zero_burn():
    cfg = presets.load("generic-fee-share")
    traj = run(cfg)
    assert all(s.tokens_burned == 0 for s in traj)
    assert all(s.burn_toll_usd == 0 for s in traj)


def test_circulating_never_negative_under_bear_case():
    cfg = presets.load("create-protocol-v4")
    # push every stream to hostile settings
    cfg.burn_toll_pct = 0.05            # 5% — comically high
    for s in cfg.revenue_streams:
        s.volume_usd_m0 = 500_000
        s.growth_rate = 1.30
        s.volume_cap_usd = 50_000_000
    traj = run(cfg)
    # even in the blow-up case, the simulator must stop cleanly.
    assert all(s.circulating_supply >= 0 for s in traj)
    assert traj[-1].price_usd > 0


def test_vesting_curve_respects_cliff_and_unlocks_full_allocation():
    """A linear vest bucket must hold supply flat through the cliff, then
    release exactly ``fraction_of_supply * total_supply`` over the unlock
    window — no more, no less.

    ``sell_at_unlock_pct=0`` keeps the unlocked tokens out of the AMM so the
    only thing moving circulating supply is the vesting curve itself, which
    is what this test isolates.
    """
    total_supply = 1_000_000_000.0
    fraction = 0.20
    cliff = 3
    unlock = 12
    cfg = SimConfig(
        total_supply=total_supply,
        initial_circulating_pct=0.10,
        enable_burn_toll=False,
        months=cliff + unlock + 3,  # run past the end of the unlock window
        revenue_streams=[],         # no burn / no AMM buy pressure
        vest_buckets=[
            VestBucket(
                name="Single bucket",
                fraction_of_supply=fraction,
                cliff_months=cliff,
                unlock_months=unlock,
                sell_at_unlock_pct=0.0,  # keep unlocks out of the pool
            )
        ],
    )
    traj = run(cfg)
    start = total_supply * cfg.initial_circulating_pct

    # During the cliff, nothing unlocks: circulating stays at the start value.
    for s in traj[:cliff]:
        assert s.circulating_supply == pytest.approx(start)

    # Unlocks are linear: one slice per month, none before the cliff.
    monthly = (fraction * total_supply) / unlock
    after_first_unlock = traj[cliff].circulating_supply
    assert after_first_unlock == pytest.approx(start + monthly)

    # Over the full window exactly the bucket's whole allocation is released.
    expected_total = start + fraction * total_supply
    final = traj[-1].circulating_supply
    assert final == pytest.approx(expected_total)
    # And it never overshoots its allocation after the window closes.
    assert final == pytest.approx(traj[cliff + unlock - 1].circulating_supply)


def test_standard_dao_preset_loads_and_models_governance_mechanics():
    cfg = presets.load("standard-dao")
    assert cfg.total_supply == 1_000_000_000
    assert cfg.vault_yield_apy > 0
    assert cfg.staked_fraction_of_circulating > 0
    assert any("Team" in b.name for b in cfg.vest_buckets)
    assert any("Investors" in b.name for b in cfg.vest_buckets)
    assert any("Governance participation bonus" == s.name for s in cfg.revenue_streams)

    traj = run(cfg)
    assert len(traj) == cfg.months
    assert traj[-1].circulating_supply > traj[0].circulating_supply
    assert traj[-1].staker_yield_usd > 0
