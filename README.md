# T-REX Reproducibility Artifact

This repository contains the complete empirical evaluation artifacts, data, and scripts for the manuscript: **"T-REX: SLA-Bound Conditional Settlement for HTTP-Native Agentic Commerce"**. 

It serves as the **Single Source of Truth (SSOT)** for all claims, measurements, and reproducibility steps.

---

## 1. Environment Setup

To independently reproduce the experiments or audit the artifacts, prepare the following environment:

*   **Language:** Python 3.12+
*   **Dependencies:** `py-algorand-sdk`, `python-dotenv`, `pandas`, `numpy`, `simpy`.
*   **Network Access:** Algorand Testnet. Default configuration uses free AlgoNode public endpoints:
    *   ALGOD: `https://testnet-api.algonode.cloud`
    *   INDEXER: `https://testnet-idx.algonode.cloud`

**Wallet Configuration (`.env`):**
To run on-chain experiments, you must supply 3 Algorand Testnet 25-word mnemonics in a `.env` file at the root directory:
```env
BUYER_MNEMONIC="word1 word2 ... word25"
SELLER_MNEMONIC="word1 word2 ... word25"
RELAYER_MNEMONIC="word1 word2 ... word25"

ALGOD_ADDRESS=https://testnet-api.algonode.cloud
ALGOD_TOKEN=
INDEXER_ADDRESS=https://testnet-idx.algonode.cloud
INDEXER_TOKEN=
```
*Note: Ensure all wallets are funded via the Algorand Testnet Dispenser and opted into the Testnet USDC ASA (`10458941`). You can use `optin_assets.py` to automate opt-ins.*

---

## 2. Canonical Evidence Hierarchy

All experimental evidence is strictly partitioned into three independent streams. **No Testnet data is extrapolated to claim Mainnet performance or capacity.**

### 2.1. Algorand Testnet Functional Pilot (Pilot v2)
*   **Goal:** Establish end-to-end protocol conformance, receipt verifiability, and safety invariant adherence.
*   **Target:** `App ID 769248116`, `USDC ASA 10458941`
*   **Scale:** 20 sessions (16 Normal, 2 Timeout, 2 Attested-Fail).
*   **Key Results:** 20/20 USDC and bounty receipts verified, 100% refund precision, 0 invariant violations.
*   **Canonical Artifacts:**
    *   `results/pilot/transactions_v2.csv`
    *   `artifacts/pilot_v2_receipt_audit.csv`
    *   `artifacts/pilot_v2_invariant_audit_v2.csv`
    *   `reports/pilot_v2_forensic_audit_report_v2.md`
*   **Reproduce:** Run `python run_pilot_v2.py`.

### 2.2. Testnet AVM Characterization
*   **Goal:** Empirically measure atomic group execution layouts, microALGO fees, and client-side latencies.
*   **Target:** `App ID 769248116`, `USDC ASA 10458941`
*   **Scale:** 30 sessions (10 Normal, 10 Timeout, 10 Attested-Fail).
*   **Key Results:** 
    *   Normal settlement: 10 outer transactions (1 AppCall + 9 OpUps) $\rightarrow$ 21,000 $\mu$ALGO group fee.
    *   Refund settlement: 7 outer transactions (1 AppCall + 6 OpUps) $\rightarrow$ 18,000 $\mu$ALGO group fee.
    *   Median Client-side Latency: 12.32s
*   **Canonical Artifacts:**
    *   `results/avm_char/avm_char_sessions.csv`
    *   `results/avm_char/avm_char_fee_audit.csv`
    *   `results/avm_char/avm_char_latency_audit.csv`
    *   `reports/avm_char_forensic_audit.md`
*   **Reproduce:** Run `python run_avm_char.py`.
*   **Audit:** Run `python audit_avm_char.py` to independently cryptographically verify all 30 sessions against the blockchain Indexer without creating new data.

### 2.3. Discrete-Event Simulation (Simulation v1)
*   **Goal:** Model large-scale system behavior under adversarial network conditions and Byzantine attesters.
*   **Constraint:** *VALID_SIMULATION_ONLY: model-based synthetic estimates under stated assumptions.* No blockchain calls.
*   **Scale:** 160 runs, 1.76M events.
*   **Key Results:** 100% precision with 0 False Release Rate (FRR) under modeled (3,2) threshold assumptions ($f \le 1$).
*   **Canonical Artifacts:**
    *   `results/simulation_v1/aggregate_metrics.csv`
    *   `results/simulation_v1/events.csv`
*   **Reproduce:** Scripts located in the `simulation_src/` directory.

### 2.4. Empirical AVM Opcode & Budget Profiling (SDK Simulation)
*   **Goal:** Measure exact opcode execution cost units (`app-budget-consumed`) and fee pooling breakdown using the Algorand SDK `simulate_raw_transactions` endpoint against Testnet state.
*   **Key Findings:**
    *   **Authorization Optimization:** Buyer signature ($\sigma_B$) verification (1,900 cost units) is executed on-chain during `authorize` and cryptographically bound to the session box. The terminal phase only verifies Seller ($\sigma_S$) and Attester ($\Sigma_A$) signatures.
    *   **Normal Settlement Group:** 10 outer transactions (1 AppCall + 9 OpUps) providing 8,400 pooled cost units. Consumes **6,740 cost units** (Margin: **1,660 units**). Total terminal group fee: **12,000 $\mu$ALGO**.
    *   **Refund Settlement Group:** 7 outer transactions (1 AppCall + 6 OpUps) providing 6,300 pooled cost units. Consumes **4,522 cost units** (Margin: **1,778 units**). Total terminal group fee: **9,000 $\mu$ALGO**.
    *   **Inner Tx Fee Payer:** Inner `AssetTransfer` transactions set `fee = 0` and are completely covered by pooled fees from the outer group.
*   **Summary Table:**
    | Path | Total Pooled Budget | Actual Opcode Used | Margin | Total Fee ($\mu$ALGO) | Inner Tx Fee Payer |
    |---|---|---|---|---|---|
    | Normal Group | 8,400 (12 tx) | 6,740 | 1,660 | 12,000 | Pooled from outer group |
    | Refund Group | 6,300 (9 tx) | 4,522 | 1,778 | 9,000 | Pooled from outer group |
*   **Canonical Artifacts:**
    *   `run_avm_simulation.py`
    *   `sim_settle.json`
    *   `sim_refund.json`
*   **Reproduce:** Run `python run_avm_simulation.py`.

---

## 3. Manuscript Integrity Audits

To ensure 100% fidelity between the raw artifacts and the academic manuscript, a comprehensive, read-only automated audit was executed. The results are available in the `reports/` directory, specifically:

*   `reports/full_manuscript_numerical_claim_audit.md`: Verifies every numerical claim against the canonical CSVs.
*   `reports/full_manuscript_evidence_separation_audit.md`: Confirms strict separation between Testnet and Simulation evidence.
*   `reports/full_manuscript_terminology_symbol_audit.md`: Enforces correct terminology (e.g., forbidding "finality" in place of "client-side latency").
*   `reports/full_manuscript_blocking_issues.md`: Logs critical manuscript corrections made prior to submission.

---

## 4. Source Code and Contracts

*   **`01_contracts/`**: Contains the PyTeal source code for the T-REX escrow state machine and the compiled TEAL artifacts.
*   **`02_clients/`**: Contains the Python `asyncio` SDK for the Buyer, Seller, Attester, and Relayer agents.
*   **`00_setup/`**: Contains utilities for deploying contracts and bootstrapping ASA assets.

*Disclaimer: Experimental software. Do not deploy to Algorand Mainnet.*
