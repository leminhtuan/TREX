# Security Assumptions

This document outlines the security assumptions for the T-REX escrow smart contract.

## 1. Attester Key Security
- It is assumed that the private keys of the 3 attesters are kept secure off-chain.
- The system relies on a 2-of-3 honest majority. If 2 keys are compromised, funds can be falsely released or refunded.

## 2. Honest-Threshold Assumption
- We assume at most $f = 1$ attester is Byzantine.

## 3. Off-Chain Predicate Evaluation
- The smart contract does NOT verify the correctness of the SLA predicate evaluation. It only verifies the cryptographic signatures of the attesters asserting the evaluation result.

## 4. Availability and Liveness
- The protocol relies on the availability of permissionless relayers to trigger `settle` or `refund`. If no relayers are available (e.g., bounty is too low relative to network fees), funds may remain locked until a timeout is manually triggered.

## 5. Privacy
- The Algorand blockchain is a public ledger. Session IDs, hashed payloads ($H_q$, $H_c$, $H_p$), participant addresses, and amounts are visible to all network observers. There is no privacy guarantee for transaction metadata.

## 6. Cryptographic Primitives
- Ed25519 signatures are assumed unforgeable under chosen-message attacks.
- SHA-256 is assumed collision-resistant.
