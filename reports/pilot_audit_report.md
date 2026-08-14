# T-REX Pilot Audit Report

## 1. Scope
Algorand Testnet functional pilot. Not a Mainnet economic experiment.

## 2. Integrity
All inputs hashed and verified. See artifacts/audit_execution_manifest.json.

## 3. Outcomes
- Released: 16
- Refunded: 2
- Failed (Unresolved due to application_rejected_on_chain): 2
- Success Rate: 0.80 (CI: 0.58-0.92)

## 4. Latency
Client-side latency evaluated. Values missing canonical block timestamps are labeled VALID_CLIENT_SIDE or NOT_VERIFIABLE_ON_CHAIN.

## 5. Cost
Illustrative estimate only. No actual economic cost measured.

## 6. Invariants
Observable terminal states passed invariants. Failed states are NOT_VERIFIABLE.

## Limitations
N=20, deterministic injection, Testnet parameters, client-side timing.
