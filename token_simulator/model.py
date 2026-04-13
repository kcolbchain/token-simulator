"""Deterministic token-economy model.

The model runs month-by-month. Each month:

1. Apply growth tapering to the user base.
2. Roll the revenue-stream volumes forward.
3. Burn native token via AMM buy-and-burn (burn-toll on stablecoin flow).
4. Accumulate vault from protocol margin; pay operating costs first.
5. Compute vault yield, split between stakers (in settlement asset) and
   treasury.
6. Unlock vested tokens; a configurable fraction is sold into the pool,
   the rest is assumed to remain locked.
7. Update the constant-product pool state; recompute endogenous price.

This is deliberately not a price predictor — it is a consistency check.
If the parameters are unreasonable, the output will be obviously broken
(supply goes negative, pool empties, staker APY explodes), and that is
the signal to fix the parameters, not to publish a marketing chart.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------- config


@dataclass
class RevenueStream:
    """A single revenue line (e.g. agent payments, compute marketplace).

    ``volume_usd_m0`` is the stream's monthly stablecoin flow at month 0.
    Volume grows at ``growth_rate`` per month until the carrying capacity
    kicks in (logistic tapering, ``volume_cap_usd``).

    ``margin_pct`` is the fraction of flow that the protocol keeps as
    margin; the remainder leaves the system (e.g. to a compute provider).

    ``touches_burn_toll`` is ``True`` if flow on this stream triggers the
    stablecoin mint/redeem burn toll. Some streams (e.g. a listing fee)
    may be one-way and should be excluded.
    """

    name: str
    volume_usd_m0: float
    growth_rate: float = 1.15
    volume_cap_usd: float = 5_000_000.0
    margin_pct: float = 0.35
    touches_burn_toll: bool = True


@dataclass
class VestBucket:
    """A token-allocation bucket with a linear unlock schedule.

    ``fraction_of_supply`` is this bucket's share of total supply.
    ``cliff_months`` is a delay before unlocks begin.
    ``unlock_months`` is the linear-vesting window length.
    ``sell_at_unlock_pct`` is the fraction of each month's unlock that is
    sold into the AMM pool (the rest is held or restaked — modelled as
    locked out of the pool for simplicity)."""

    name: str
    fraction_of_supply: float
    cliff_months: int = 0
    unlock_months: int = 12
    sell_at_unlock_pct: float = 0.50


@dataclass
class SimConfig:
    # token
    total_supply: float = 11_100_000_000
    initial_circulating_pct: float = 0.045
    initial_price_usd: float = 0.0009

    # pool (constant-product USDC × CR8 at launch)
    pool_usdc_m0: float = 100_000.0
    # CR8 side is derived from pool_usdc_m0 and initial_price_usd.

    # burn toll on stablecoin flow
    burn_toll_pct: float = 0.01  # combined mint+redeem round trip
    enable_burn_toll: bool = True

    # vault economics
    vault_yield_apy: float = 0.05
    staker_yield_share: float = 0.60
    treasury_yield_share: float = 0.40
    operating_cost_usd_per_month: float = 5_000.0

    # staking
    staked_fraction_of_circulating: float = 0.25

    # vesting
    vest_buckets: List[VestBucket] = field(default_factory=list)

    # revenue streams
    revenue_streams: List[RevenueStream] = field(default_factory=list)

    # simulation horizon
    months: int = 24


# ---------------------------------------------------------------- state


@dataclass
class SimState:
    month: int
    volume_usd: float
    margin_usd: float
    vault_usd: float
    ops_paid_usd: float
    vault_yield_usd: float
    staker_yield_usd: float
    treasury_yield_usd: float
    burn_toll_usd: float
    tokens_burned: float
    circulating_supply: float
    staked_supply: float
    price_usd: float
    pool_usdc: float
    pool_cr8: float
    fdv_usd: float
    mcap_usd: float
    staker_apy: float


# ---------------------------------------------------------------- helpers


def _logistic_growth(v: float, g: float, cap: float) -> float:
    """One-month logistic volume step toward ``cap`` at nominal rate ``g``."""
    if cap <= 0:
        return v * g
    # r = g - 1 is the continuous-ish rate; tapered by headroom.
    r = max(0.0, g - 1.0)
    headroom = max(0.0, 1.0 - v / cap)
    return v + v * r * headroom


def _constant_product_price(pool_usdc: float, pool_cr8: float) -> float:
    if pool_cr8 <= 0:
        return float("inf")
    return pool_usdc / pool_cr8


def _amm_buy_cr8_and_burn(
    pool_usdc: float, pool_cr8: float, usdc_in: float
) -> tuple[float, float, float]:
    """Spend ``usdc_in`` to buy CR8 from the x*y=k pool. Return
    (new_pool_usdc, new_pool_cr8, cr8_bought_and_burned)."""
    if usdc_in <= 0 or pool_cr8 <= 0:
        return pool_usdc, pool_cr8, 0.0
    k = pool_usdc * pool_cr8
    new_pool_usdc = pool_usdc + usdc_in
    new_pool_cr8 = k / new_pool_usdc
    cr8_bought = pool_cr8 - new_pool_cr8
    # burn = remove from pool AND from circulating supply
    return new_pool_usdc, new_pool_cr8, cr8_bought


def _amm_sell_cr8(
    pool_usdc: float, pool_cr8: float, cr8_in: float
) -> tuple[float, float, float]:
    """Sell ``cr8_in`` into the pool. Return (new_pool_usdc, new_pool_cr8, usdc_out)."""
    if cr8_in <= 0 or pool_usdc <= 0:
        return pool_usdc, pool_cr8, 0.0
    k = pool_usdc * pool_cr8
    new_pool_cr8 = pool_cr8 + cr8_in
    new_pool_usdc = k / new_pool_cr8
    usdc_out = pool_usdc - new_pool_usdc
    return new_pool_usdc, new_pool_cr8, usdc_out


# ---------------------------------------------------------------- main loop


def run(cfg: SimConfig) -> List[SimState]:
    # initialize pool
    pool_cr8 = cfg.pool_usdc_m0 / cfg.initial_price_usd
    pool_usdc = cfg.pool_usdc_m0

    # initial circulating = friends round unlocked + pool CR8
    circulating = cfg.total_supply * cfg.initial_circulating_pct

    # supply bookkeeping
    supply_burned = 0.0
    per_bucket_unlocked = [0.0 for _ in cfg.vest_buckets]

    # volumes
    stream_volumes = [s.volume_usd_m0 for s in cfg.revenue_streams]

    vault_usd = 0.0

    trajectory: List[SimState] = []

    for m in range(cfg.months):
        # 1. advance volumes
        for i, s in enumerate(cfg.revenue_streams):
            stream_volumes[i] = _logistic_growth(stream_volumes[i], s.growth_rate, s.volume_cap_usd)

        total_volume = sum(stream_volumes)
        total_margin = sum(v * s.margin_pct for v, s in zip(stream_volumes, cfg.revenue_streams))
        toll_flow = sum(v for v, s in zip(stream_volumes, cfg.revenue_streams) if s.touches_burn_toll)

        # 2. burn toll via AMM buy-and-burn
        burn_toll_usd = toll_flow * cfg.burn_toll_pct if cfg.enable_burn_toll else 0.0
        pool_usdc, pool_cr8, cr8_burned = _amm_buy_cr8_and_burn(pool_usdc, pool_cr8, burn_toll_usd)
        circulating -= cr8_burned
        supply_burned += cr8_burned

        # 3. vault accumulates margin net of ops
        vault_usd += total_margin
        ops_paid = min(vault_usd, cfg.operating_cost_usd_per_month)
        vault_usd -= ops_paid

        # 4. yield on vault
        vault_yield = vault_usd * cfg.vault_yield_apy / 12
        staker_yield = vault_yield * cfg.staker_yield_share
        treasury_yield = vault_yield * cfg.treasury_yield_share

        # 5. vesting unlocks — linear, per-bucket
        for i, b in enumerate(cfg.vest_buckets):
            if m < b.cliff_months:
                continue
            months_into_unlock = m - b.cliff_months
            if months_into_unlock >= b.unlock_months:
                continue
            monthly_unlock = (b.fraction_of_supply * cfg.total_supply) / b.unlock_months
            per_bucket_unlocked[i] += monthly_unlock
            # add to circulating, but a fraction is sold into the pool
            circulating += monthly_unlock
            cr8_sold = monthly_unlock * b.sell_at_unlock_pct
            pool_usdc, pool_cr8, _ = _amm_sell_cr8(pool_usdc, pool_cr8, cr8_sold)

        # 6. staked supply (snapshot — simple fraction of circulating)
        staked = circulating * cfg.staked_fraction_of_circulating

        # 7. metrics
        price = _constant_product_price(pool_usdc, pool_cr8)
        mcap = circulating * price
        fdv = cfg.total_supply * price
        staker_apy_value = (staker_yield * 12) / max(1.0, staked * price)

        trajectory.append(
            SimState(
                month=m,
                volume_usd=total_volume,
                margin_usd=total_margin,
                vault_usd=vault_usd,
                ops_paid_usd=ops_paid,
                vault_yield_usd=vault_yield,
                staker_yield_usd=staker_yield,
                treasury_yield_usd=treasury_yield,
                burn_toll_usd=burn_toll_usd,
                tokens_burned=cr8_burned,
                circulating_supply=circulating,
                staked_supply=staked,
                price_usd=price,
                pool_usdc=pool_usdc,
                pool_cr8=pool_cr8,
                fdv_usd=fdv,
                mcap_usd=mcap,
                staker_apy=staker_apy_value,
            )
        )

        if circulating <= 0 or pool_cr8 <= 0 or not math.isfinite(price):
            # blow-up — stop early; let the caller see the broken state.
            break

    return trajectory
