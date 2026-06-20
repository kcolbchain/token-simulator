# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability in this token simulator:

1. **Do not open a public issue** — use GitHub Security Advisories instead
2. Email security@kcolbchain.com with details
3. Allow 48 hours for acknowledgment, 14 days for fix

## Scope

This project simulates token economics including burn tolls, staking yields, vesting schedules, liquidity pools, and multi-stream revenue. Vulnerabilities in:
- The simulation math (incorrect yield calculations, vesting schedule bugs)
- Browser dashboard XSS vectors
- Python dependency supply-chain issues

Will be triaged and fixed.

## Disclosure Policy

We follow coordinated disclosure. Patches will be credited in release notes.