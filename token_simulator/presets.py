"""Named parameter presets.

Each preset returns a :class:`SimConfig`. Keep presets explicit — they
double as documentation for real-world protocol designs.
"""

from __future__ import annotations

from .model import RevenueStream, SimConfig, VestBucket

PRESETS = {}


def _register(name):
    def wrap(fn):
        PRESETS[name] = fn
        return fn
    return wrap


@_register("create-protocol-v4")
def create_protocol_v4() -> SimConfig:
    """CR8 burn-toll model as described in cr8-token-design-v4.md.

    One revenue stream at launch (agent payments). Burn toll 1% round-trip.
    11.1B fixed supply, 4.5% initial circulating. Distribution per
    relaunch-plan.md. Growth tapered by logistic cap; the sim will expose
    when the burn rate becomes unsustainable.
    """
    return SimConfig(
        total_supply=11_100_000_000,
        initial_circulating_pct=0.045,
        initial_price_usd=0.0009,
        pool_usdc_m0=100_000.0,
        burn_toll_pct=0.01,
        enable_burn_toll=True,
        vault_yield_apy=0.05,
        staker_yield_share=0.60,
        treasury_yield_share=0.40,
        operating_cost_usd_per_month=5_000.0,
        staked_fraction_of_circulating=0.25,
        months=24,
        revenue_streams=[
            RevenueStream(
                name="Agent payments (CR8-USD)",
                volume_usd_m0=5_000.0,
                growth_rate=1.25,
                volume_cap_usd=5_000_000.0,
                margin_pct=0.35,
                touches_burn_toll=True,
            ),
        ],
        vest_buckets=[
            VestBucket("Community/ecosystem", fraction_of_supply=0.40, cliff_months=3, unlock_months=36, sell_at_unlock_pct=0.40),
            VestBucket("Team + advisors",     fraction_of_supply=0.20, cliff_months=6, unlock_months=36, sell_at_unlock_pct=0.30),
            VestBucket("Treasury",            fraction_of_supply=0.15, cliff_months=0, unlock_months=48, sell_at_unlock_pct=0.10),
            VestBucket("Liquidity",           fraction_of_supply=0.11, cliff_months=0, unlock_months=1,  sell_at_unlock_pct=0.00),
            VestBucket("Legacy",              fraction_of_supply=0.10, cliff_months=0, unlock_months=12, sell_at_unlock_pct=0.65),
            VestBucket("Friends round",       fraction_of_supply=0.04, cliff_months=6, unlock_months=12, sell_at_unlock_pct=0.50),
        ],
    )


@_register("generic-fee-share")
def generic_fee_share() -> SimConfig:
    """Vanilla 70/30 fee-share token, no burn — baseline for comparison."""
    cfg = create_protocol_v4()
    cfg.enable_burn_toll = False
    cfg.staker_yield_share = 0.70
    cfg.treasury_yield_share = 0.30
    return cfg


def load(name: str) -> SimConfig:
    if name not in PRESETS:
        raise KeyError(f"unknown preset: {name!r}. known: {sorted(PRESETS)}")
    return PRESETS[name]()


def list_presets() -> list[str]:
    return sorted(PRESETS)
