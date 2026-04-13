"""token-simulator — tokenomics-sim library.

Public API:

- :class:`SimConfig` — all parameters of a simulation.
- :class:`SimState` — per-month state produced by :func:`run`.
- :func:`run` — execute a simulation and return the trajectory.

The math is intentionally simple and readable. Replace pieces with better
models as needed; the test suite will flag regressions.
"""

from .model import RevenueStream, SimConfig, SimState, VestBucket, run

__all__ = [
    "RevenueStream",
    "SimConfig",
    "SimState",
    "VestBucket",
    "run",
]
