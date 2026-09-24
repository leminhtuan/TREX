# T-REX: Syntactic Predicate-Conditioned Threshold-Attested Settlement and AVM Budget Management for HTTP-Native Agentic Commerce

[![Paper](https://img.shields.io/badge/PeerJ_CS-Camera--Ready-blue.svg)](PeerJ-v7.tex)
[![Testnet App ID](https://img.shields.io/badge/Algorand_Testnet-App_772170811-green.svg)](https://testnet.explorer.perawallet.app/application/772170811/)
[![Reproducibility Audit](https://img.shields.io/badge/Audit-100%25_Verified-brightgreen.svg)](repro/verify_peerj_claims.py)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

Official empirical reproducibility repository and **Single Source of Truth (SSOT)** for the manuscript:
> **"T-REX: Syntactic Predicate-Conditioned Threshold-Attested Settlement and AVM Budget Management for HTTP-Native Agentic Commerce"**  
> *PeerJ Computer Science* (Camera-Ready Submission).

---

## Table of Contents
1. [Overview & Unified Artifact (App 772170811)](#1-overview--unified-artifact-app-772170811)
2. [Manuscript-to-Code Mapping Matrix](#2-manuscript-to-code-mapping-matrix)
3. [Environment Setup & Prerequisites](#3-environment-setup--prerequisites)
4. [One-Click Automated Reproducibility Audit](#4-one-click-automated-reproducibility-audit)
5. [Step-by-Step Reproduction Guide](#5-step-by-step-reproduction-guide)
   - [5.1 Verifying the 100-Session Functional Campaign](#51-verifying-the-100-session-functional-campaign)
   - [5.2 Verifying Client-Observed RPC Round-Trip Time & Lognormal Fits](#52-verifying-client-observed-rpc-round-trip-time--lognormal-fits)
   - [5.3 Verifying Fee Accounting & 22-Outer-Transaction Group](#53-verifying-fee-accounting--22-outer-transaction-group)
   - [5.4 Verifying Baseline Benchmarks (HTLC & Direct Payment)](#54-verifying-baseline-benchmarks-htlc--direct-payment)
   - [5.5 Verifying the 10 Targeted Negative Security Tests](#55-verifying-the-10-targeted-negative-security-tests)
6. [Live On-Chain Re-Execution on Algorand Testnet](#6-live-on-chain-re-execution-on-algorand-testnet)
7. [Cryptographic Manifest & Ledger Provenance](#7-cryptographic-manifest--ledger-provenance)

---

## 1. Overview & Unified Artifact (App 772170811)

To guarantee scientific integrity and prevent the pooling of historical development data with final security validations, all empirical results in the manuscript are unified on a single, frozen Algorand Testnet application artifact:

* **Canonical Application ID:** `772170811`
* **Application Address:** `JYDZRPKR2CGMZSKWKUCJUU7FNR5IF3NE33W2QHKFFZYKMKMNQFCLT2ILBQ`
* **Testnet USDC ASA ID:** `10458941`
* **Approval Program Hash:** `RRYTW7VQWWP722I74TFQGPVDE6T2HWPQEJXDP5CGFAXG2UGSJJ62P3OOBM`
* **Clear State Program Hash:** `74XQDOUMP27NMKK6IX55GRY7WLE7V5Z5E64PCTUKENQ3YP67RT4ZCSTDJE`
* **Frozen Deployment Commit:** `f84a769`
* **Repository Canonical Commit:** `9629369904795a24718c3e95835f1da7be996f7b` (Tag: `v1.0.0-peerjcs`)

### Core Hardened Features of App 772170811
1. **Cross-Network Replay Protection:** Both $M_S$ and $M_{A_i}$ domain messages cryptographically bind `Global.genesis_hash()`.
2. **Cross-User Replay Protection:** Both $M_S$ and $M_{A_i}$ bind the 32-byte `buyer_address`.
3. **AVM Signature Verification:** Uses `ed25519verify_bare` (raw byte verification) rather than `ed25519verify` (which prefixes `ProgData`).
4. **Kleene 3-Valued Fail-Closed Logic:** Off-chain evaluation collapses any unresolvable path or schema error ($\bot$) directly to $\mathsf{FAIL}$ before quorum signing.
5. **Persistent Anti-Replay Marker:** The $\mathsf{SPENT}$ box (`T-REX-SPENT` + $\alpha$ + $B$ + $n$) is retained permanently after terminal payout, guaranteeing that each session identity can terminate at most once.

---

## 2. Manuscript-to-Code Mapping Matrix

The following matrix provides a complete 1:1 bidirectional mapping between the claims in `PeerJ-v7.tex` and the source code implementation:

| Paper Element | Description & Reported Value | Implementation Source Code | Canonical Ledger Trace / Artifact |
|---|---|---|---|
| **Abstract / §7.2** | 100 functional sessions: 40 Normal, 30 Attested-Fail, 30 Timeout; 0 invariant violations; 100% SPENT retention. | [`09_campaign_app772170811/run_campaign_772170811.py`](09_campaign_app772170811/run_campaign_772170811.py) | [`07_final_campaign/final_functional_campaign.csv`](07_final_campaign/final_functional_campaign.csv) |
| **Abstract / §7.4 (Table 5)** | Normal Settle RPC RTT: Mean **9.87s** (Auth: 4.50s / 45.6%, Attestation: 0.47s / 4.8%, Terminal: 4.90s / 49.6%). | [`02_clients/buyer_agent.py`](02_clients/buyer_agent.py), [`02_clients/relayer.py`](02_clients/relayer.py) | [`07_final_campaign/final_functional_campaign.csv`](07_final_campaign/final_functional_campaign.csv) |
| **§4.1 (Eq. 1–3)** | Cryptographic commitments $H_q, H_c, H_p$ using SHA-256 over RFC 8785 canonical JSON (JCS). | [`02_clients/buyer_agent.py#L32-L36`](02_clients/buyer_agent.py#L32-L36), [`02_clients/seller_agent.py#L28-L30`](02_clients/seller_agent.py#L28-L30) | Live Testnet Session Boxes |
| **§4.2 (Def. 1, Tab. 1)** | SSPL Evaluator: Strong Kleene 3-valued logic ($\land, \lor, \neg$) with strict Fail-Closed root collapse $\psi(x)$. | [`02_clients/sspl_eval.py`](02_clients/sspl_eval.py) | [`08_adversarial_campaign/run_sspl_conformance.py`](08_adversarial_campaign/run_sspl_conformance.py) (12 vectors pass) |
| **§4.3 (Eq. 5–7)** | Byte encoding of $M_B$ (153 B), $M_S$ (161 B), and $M_A$ (exactly 202 B) with `genesis_hash` and `buyer_address`. | [`02_clients/attester.py#L71-L84`](02_clients/attester.py#L71-L84), [`01_contracts/trex_escrow.py#L261-L289`](01_contracts/trex_escrow.py#L261-L289) | Verified 202-byte vector test |
| **§4.5 (Eq. 8–9)** | Double-spending protection via ephemeral $k_a(B,n)$ (`ACTIVE`) and persistent $k_s(B,n)$ (`SPENT`) boxes. | [`01_contracts/trex_escrow.py#L51-L60`](01_contracts/trex_escrow.py#L51-L60), [`01_contracts/trex_escrow.py#L318-L321`](01_contracts/trex_escrow.py#L318-L321) | Box key SHA512/256 derivations |
| **§5.1 (Table 2)** | TEAL v11 Profiling: Settle requires 6,730 cost units (Budget: 7,000); Refund requires 4,511 (Budget: 4,900). | [`01_contracts/trex_escrow.py`](01_contracts/trex_escrow.py) | Algorand SDK Simulate Trace |
| **§5.2 (Table 4)** | Deployed Fee Accounting: Auth (6 outer = 6,000 $\mu$ALGO); Terminal (16 outer + 2 inner = 18,000 $\mu$ALGO); Total = **24,000 $\mu$ALGO**. | [`02_clients/buyer_agent.py#L141`](02_clients/buyer_agent.py#L141), [`02_clients/relayer.py#L70-L82`](02_clients/relayer.py#L70-L82) | Ledger Fee Audit; `benchmark_rerun_final.csv` |
| **§7.1 (Table 1)** | Attribution of historical and canonical artifacts across development and camera-ready milestones. | [`PeerJ-v7.tex#L489-L505`](PeerJ-v7.tex#L489-L505) | [`artifacts/program_hashes.json`](artifacts/program_hashes.json) |
| **§7.3 (Table 3)** | Baseline Comparison: Direct (1,000 $\mu$ALGO / 5.28s); HTLC (4,000 $\mu$ALGO / **10.51s**); Naive (12,000 $\mu$ALGO / 13.50s); T-REX (24,000 $\mu$ALGO / 14.93s). | [`05_campaign_D/baselines/htlc_escrow.py`](05_campaign_D/baselines/htlc_escrow.py), [`05_campaign_D/baselines/htlc_escrow_client.py`](05_campaign_D/baselines/htlc_escrow_client.py) | [`artifacts/htlc_benchmark_results.csv`](artifacts/htlc_benchmark_results.csv), [`benchmark_rerun_final.csv`](benchmark_rerun_final.csv) |
| **§7.5 (Table 7)** | Targeted Negative Security Tests on App 772170811: 10/10 vectors REVERTED (100% rejection rate). | [`08_adversarial_campaign/run_adversarial.py`](08_adversarial_campaign/run_adversarial.py) | [`artifacts/unified_test_results.json`](artifacts/unified_test_results.json) |
| **Appendix (Table 6)** | Lognormal Distribution Fits ($floc=0$): Auth ($s=0.0672, \theta=4.4921$); Term ($s=0.0102, \theta=4.8957$); E2E ($s=0.0343, \theta=9.8679$). | [`repro/verify_peerj_claims.py#L48-L62`](repro/verify_peerj_claims.py#L48-L62) | Computed via `scipy.stats.lognorm.fit` |

---

## 3. Environment Setup & Prerequisites

### Hardware & Software
* **Operating System:** Linux, macOS, or Windows 10/11
* **Python Version:** 3.10+ (tested on Python 3.12 and 3.14)
* **Package Manager:** `pip`

### Installation
Clone the repository and install the frozen pinned dependencies:
```bash
git clone https://github.com/leminhtuan/TREX.git
cd TREX
pip install -r requirements.txt
```

Verify installed package versions:
```bash
python -c "import algosdk, pyteal, pandas, scipy, nacl; print('Dependencies verified successfully.')"
```

---

## 4. One-Click Automated Reproducibility Audit

You can independently verify **all claims, tables, and mathematical derivations in the paper in under 5 seconds** without needing wallet keys or blockchain funding by running the automated audit script:

```bash
python repro/verify_peerj_claims.py
```

### Expected Output:
```text
================================================================================
   T-REX REPRODUCIBILITY AUDIT: PeerJ-v7.tex vs TESTNET LEDGER DATA
================================================================================

[1] 100-SESSION FUNCTIONAL CAMPAIGN ON APP 772170811 (§7.2)
  Total sessions recorded: 100
  App ID in dataset: [772170811] (Must be [772170811])
  Scenarios:
    - Normal Settle: 40
    - Attested Fail: 30
    - Timeout Refund: 30
  Final States:
    - REFUNDED: 60
    - RELEASED: 40
  Invariant Violations: 0 (Expected: 0)
  SPENT markers present: True (Expected: True)
  -> Abstract & Section 7.2 verification: PASS

[2] CLIENT-OBSERVED RPC ROUND-TRIP TIME (Table 5, N=40 Normal Settle)
  Authorization: Mean=4.50s (Min=4.27s, Max=6.75s), Share=45.6%
  Off-chain:     Mean=0.47s (Min=0.41s, Max=0.53s), Share=4.8%
  Terminal:      Mean=4.90s (Min=4.77s, Max=4.98s), Share=49.6%
  Total RPC RTT: Mean=9.87s (Min=9.62s, Max=12.12s), Share=100.0%
  Auth + Term Share: 95.2% (Matches Paper Fig 5 caption ~95.2%)
  -> Table 5 verification: PASS

[3] LOGNORMAL FITS (Appendix Table 6)
  Authorize: s=0.0672, theta=4.4921, model_mean=4.5023s, empirical_mean=4.5037s
  Terminal : s=0.0102, theta=4.8957, model_mean=4.8959s, empirical_mean=4.8959s
  E2E      : s=0.0343, theta=9.8679, model_mean=9.8737s, empirical_mean=9.8741s
  -> Appendix Table 6 verification: PASS

[4] FEE ACCOUNTING (Table 4)
  Authorize: Outer=6, Inner=0, Fee=6,000 uALGO
  Terminal:  Outer=16, Inner=2, Fee=18,000 uALGO
  Session:   Outer=22, Inner=2, Fee=24,000 uALGO
  -> Table 4 verification: PASS

[5] BASELINE BENCHMARK DATA (Table 3)
  HTLC (N=15, App 772482753):
    Fee: 4,000 uALGO, Mean E2E: 10.51s
  Direct Payment (N=30):
    Fee: 1,000 uALGO, Median E2E: 5.28s
  T-REX Benchmark Run (N=30):
    Fee: 24,000 uALGO, Median E2E: 14.93s
  -> Table 3 verification: PASS

[6] TARGETED NEGATIVE TESTS (Table 7, App 772170811)
  App ID: 772170811
  Commit: cc4f8bf46476ef4d7a353fb1f2c62d7fb4bdf67d
  Tests Passed / Total: 10/10 REVERTED (100% rejection rate)
    - Test 01: Cross-Network Replay (All-Zero Genesis Hash in M_A) -> REVERTED (PASS)
    - Test 02: Cross-Network Replay (Mainnet Genesis Hash in M_A) -> REVERTED (PASS)
    - Test 03: Cross-User Replay (Wrong Buyer Bound in M_A) -> REVERTED (PASS)
    - Test 04: Wrong Application ID Replay in M_A -> REVERTED (PASS)
    - Test 05: Deadline Tampering (Attester alters r_dead) -> REVERTED (PASS)
    - Test 06: Corrupted Attester Signature (Invalid Ed25519) -> REVERTED (PASS)
    - Test 07: Corrupted Seller Signature (Invalid M_S sig) -> REVERTED (PASS)
    - Test 08: Payload Hash Tampering (H_p mismatch) -> REVERTED (PASS)
    - Test 09: Double Settlement Replay (Deleted Box Key) -> REVERTED (PASS)
    - Test 10: Premature Timeout Refund (Round < Deadline) -> REVERTED (PASS)
  -> Table 7 verification: PASS

================================================================================
   AUDIT COMPLETE: 100% OF CLAIMS VERIFIED WITH ON-CHAIN LEDGER EVIDENCE
================================================================================
```

---

## 5. Step-by-Step Reproduction Guide

### 5.1 Verifying the 100-Session Functional Campaign
The raw transaction records for all 100 sessions are archived in `07_final_campaign/final_functional_campaign.csv`. Every row includes:
* `auth_txid`: Transaction ID of the authorization group.
* `term_txid`: Transaction ID of the terminal transition (settlement or refund).
* `final_round`: The exact consensus block round confirming the terminal state.
* `spent_marker_present`: Cryptographic verification of the anti-replay box.

You can verify any transaction on the public explorer:
```
https://testnet.explorer.perawallet.app/tx/<auth_txid>
https://testnet.explorer.perawallet.app/tx/<term_txid>
```

### 5.2 Verifying Client-Observed RPC Round-Trip Time & Lognormal Fits
Run Python directly over the 40 normal settlement sessions:
```python
import pandas as pd, scipy.stats as stats, numpy as np

df = pd.read_csv("07_final_campaign/final_functional_campaign.csv")
normal = df[df["scenario"] == "Normal Settle"]

print("Mean E2E RTT:", normal["e2e_latency_s"].mean())
print("Mean Auth Latency:", normal["auth_latency_s"].mean())
print("Mean Terminal Latency:", normal["term_latency_s"].mean())

# Lognormal fit with location fixed at zero
s, loc, theta = stats.lognorm.fit(normal["e2e_latency_s"], floc=0)
print(f"E2E Model: s={s:.4f}, theta={theta:.4f}, Model Mean={theta * np.exp(s**2 / 2):.4f}s")
```

### 5.3 Verifying Fee Accounting & 22-Outer-Transaction Group
Inspect the structure of the authorization and settlement groups:
* **Authorization Group:** 6 outer transactions:
  1. `AssetTransferTxn` (USDC escrow deposit, 1,000 $\mu$ALGO)
  2. `PaymentTxn` (ALGO bounty deposit, 1,000 $\mu$ALGO)
  3. `ApplicationCallTxn` (`authorize()`, 1,000 $\mu$ALGO)
  4. 3 $\times$ `ApplicationCallTxn` (`opup()`, 3,000 $\mu$ALGO total)
  *Subtotal: 6,000 $\mu$ALGO.*
* **Settlement Group:** 16 outer transactions + 2 inner transactions:
  1. `ApplicationCallTxn` (`settle()`, 3,000 $\mu$ALGO covering 2 inner payouts)
  2. 15 $\times$ `ApplicationCallTxn` (`opup()`, 15,000 $\mu$ALGO total)
  *Subtotal: 18,000 $\mu$ALGO.*
* **Session Total:** $6,000 + 18,000 = \mathbf{24,000~\mu\text{ALGO}}$.

### 5.4 Verifying Baseline Benchmarks (HTLC & Direct Payment)
* **Direct Payment:** 1 Asset Transfer without escrow $\rightarrow$ **1,000 $\mu$ALGO**, Median E2E: **5.28s**.
* **HTLC Baseline:** Deployed on Algorand Testnet as App `772482753`. The benchmark dataset `artifacts/htlc_benchmark_results.csv` contains 15 full sessions (Fund group of 2 txns + Claim group of 1 app call + 1 inner transfer) $\rightarrow$ **4,000 $\mu$ALGO**, Mean E2E: **10.51s**.

### 5.5 Verifying the 10 Targeted Negative Security Tests
The complete cryptographic proof of rejection is documented in `artifacts/unified_test_results.json`:
```bash
python -c "import json; r = json.load(open('artifacts/unified_test_results.json')); print('Rejected:', r['adversarial_reverted'], '/', r['adversarial_total'])"
```

---

## 6. Live On-Chain Re-Execution on Algorand Testnet

If you wish to execute *new* live transactions on Algorand Testnet against App `772170811`:

1. Populate `.env` in `01_contracts/.env`:
   ```env
   BUYER_MNEMONIC="25-word mnemonic with Testnet ALGO and USDC"
   SELLER_MNEMONIC="25-word mnemonic with Testnet ALGO"
   RELAYER_MNEMONIC="25-word mnemonic with Testnet ALGO"
   ATTESTER_1_MNEMONIC="25-word mnemonic matching attester_pk_0"
   ATTESTER_2_MNEMONIC="25-word mnemonic matching attester_pk_1"
   ATTESTER_3_MNEMONIC="25-word mnemonic matching attester_pk_2"
   ```
2. Run a full 100-session campaign:
   ```bash
   python 09_campaign_app772170811/run_campaign_772170811.py
   ```
3. Run the targeted adversarial suite:
   ```bash
   python 08_adversarial_campaign/run_adversarial.py
   ```

---

## 7. Cryptographic Manifest & Ledger Provenance

### Reproducibility Anchors (Paper Table 7 & `REPRODUCIBILITY_MANIFEST.json`)

The following cryptographic anchors lock the exact environment, compiler, node build, and bytecode hashes supporting the paper's empirical claims:

| Parameter | Value / Hash |
| :--- | :--- |
| **Git Commit SHA** | `e72b37f08959cd99669975b24fb2f396f1515d04` |
| **PyTeal Version** | `0.26.1` |
| **py-algorand-sdk Version** | `2.6.0` |
| **Algod Node Version** | `5.0.2-AVAIL` (Build `fe1308bd+`) |
| **Canonical App ID** | `772170811` |
| **App Escrow Address** | `JYDZRPKR2CGMZSKWKUCJUU7FNR5IF3NE33W2QHKFFZYKMKMNQFCLT2ILBQ` |
| **Approval Source SHA-256** | `113714efe22d2be345d08759599dd57988a6f4e7b922fd2402be5f22499b9614` |
| **Approval Bytecode SHA-256** | `b825eed62827571db80d5db04961742da5284e8eaa2074cf66071f375dce22b6` |
| **Clear State Source SHA-256** | `5c7ae52bc739613df8e87cd03e6e826254cc26f3f596089d09de16ddd58e6901` |

To independently re-verify and generate this manifest on your machine:
```bash
python scripts/generate_reproducibility_manifest.py
```

### Registered On-Chain Keys (App 772170811 Global State)
* `attester_pk_0`: `8feb683f85f7574bcbde15dad54524516789b4bdf4e1884b966fe17e1cd5376e`
* `attester_pk_1`: `683b7592f4aa1d3767c2ae76f20df152abb3b67d6b854d43dc3e6b11ef90a0a4`
* `attester_pk_2`: `958c9cb629531f3f5b784a99d27047d9e9927d710d8bc213c5478bd035f67e71`
* `app_admin`: `e2e935f2aa951cfe3e5b2a29d71059dcf675351bd2aa8dd23f7b6c83d70b69e0`
* `protocol_version`: `1`
* `usdc_asa_id`: `10458941`

### State Machine Box Keys (Algorand Storage)
* **Session Box:** `b"session:" + uint64(session_id)` (Stores full `SessionRecord`, 202 bytes).
* **Active Marker:** $\text{SHA-512/256}(\texttt{"T-REX-ACTIVE-NONCE"} \parallel \text{buyer\_addr} \parallel \text{uint64}(n))$ (Created at `authorize`, deleted at terminal).
* **Spent Marker:** $\text{SHA-512/256}(\texttt{"T-REX-SPENT"} \parallel \text{uint64}(\alpha) \parallel \text{buyer\_addr} \parallel \text{uint64}(n))$ (Created at terminal, **never deleted**).

---

## License
This project and all reproducible artifacts are licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
