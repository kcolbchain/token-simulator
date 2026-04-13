"""CLI entry point — `token-simulator run --preset create-protocol-v4`."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict

from . import presets
from .model import run


def _cmd_run(args):
    cfg = presets.load(args.preset)
    if args.months:
        cfg.months = args.months
    traj = run(cfg)
    rows = [asdict(s) for s in traj]
    fields = list(rows[0].keys())
    w = csv.DictWriter(sys.stdout, fieldnames=fields)
    w.writeheader()
    for r in rows:
        w.writerow(r)


def _cmd_list(args):
    for name in presets.list_presets():
        print(name)


def main():
    ap = argparse.ArgumentParser(prog="token-simulator")
    sub = ap.add_subparsers(required=True)

    pr = sub.add_parser("run", help="run a preset simulation and print CSV to stdout")
    pr.add_argument("--preset", required=True)
    pr.add_argument("--months", type=int, default=None)
    pr.set_defaults(fn=_cmd_run)

    pl = sub.add_parser("list", help="list available presets")
    pl.set_defaults(fn=_cmd_list)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
