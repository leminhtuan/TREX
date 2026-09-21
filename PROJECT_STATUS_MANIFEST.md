# PROJECT STATUS MANIFEST: T-REX EXPERIMENTAL WORKSPACE
**Document Version:** 1.0  
**Generated At:** 2026-09-21  
**Target:** PeerJ Computer Science — Major Revision Audit & Experiment Protocol Design  
**Repository Working Directory:** `c:\Users\lemin\OneDrive\Desktop\trex-experiments`  

---

## 1. ENVIRONMENT & DEPENDENCIES

### 1.1 Host Operating System & Python Runtime
* **OS:** Microsoft Windows 11 Pro / Windows NT `10.0.26200.0`
* **Python Runtime:** Python `3.14.3` (`C:\Python314\python.exe`)
* **Shell:** PowerShell (`pwsh`)

### 1.2 Installed Package Versions (via `pip show`)
| Package Name | Installed Version | Status / Notes |
| :--- | :--- | :--- |
| `py-algorand-sdk` | **2.6.0** | Core SDK for transaction serialization, group encoding, and Algod API communication. |
| `pyteal` | **0.26.1** | Smart contract compilation AST generator. |
| `pandas` | **3.0.2** | Data manipulation and statistical analysis. |
| `scipy` | **1.17.1** | Statistical testing (confidence intervals, hypothesis tests). |
| `numpy` | **2.4.4** | Numerical computing. |
| `simpy` | **NOT INSTALLED** | Verified via `pip show simpy` (ModuleNotFoundError). Discrete-event simulation in `simulation_src/` is implemented natively without `simpy`. |

### 1.3 Repository Dependency Specifications
* **`01_contracts/requirements.txt`:**
  ```text
  pyteal==0.26.1
  py-algorand-sdk==2.6.0
  pytest==8.2.2
  algokit-utils>=2.2.1
  algokit==1.12.0
  pytest-cov==5.0.0
  ```
* **`simulation_src/requirements.txt`:**
  ```text
  # T-REX Simulation Requirements
  # Python 3.12.9
  # All outputs are model-based synthetic estimates under stated assumptions.
  # No Algorand API calls. No transactions submitted.
  numpy>=1.26.0,<2.0
  ```

---

## 2. REPOSITORY STRUCTURE & GIT STATE

### 2.1 Git Commit Log (`git log -n 5 --oneline`)
```text
41a5006 attested-fail-fixed
b654e95 pre-attested-fail-fix
```

### 2.2 Git Status Summary
* **Current Branch:** `main` (clean tracking against local commits `41a5006`)
* **Modified tracked files:**
  * `01_contracts/trex_escrow.py` (updated with active nonce boxes & spent markers)
  * `01_contracts/approval.teal`, `01_contracts/clear.teal`, `01_contracts/contract.json`
  * `02_clients/buyer_agent.py`, `02_clients/seller_agent.py`, `02_clients/attester.py`, `02_clients/relayer.py`
  * `artifacts/contract_app_id_testnet.txt`, `artifacts/contract_build_manifest.json`
* **Untracked experimental suites:**
  * `03_pilot/` (Pilot v2 logs and scripts)
  * `04_campaign_C/` (Campaign C orchestrators)
  * `05_campaign_D/` (Campaign D baseline comparison)
  * `06_delta/` (Targeted delta validation suite)
  * `07_final_campaign/` (Final functional validation campaign $N=100$)
  * `08_adversarial_campaign/` (Adversarial matrix $N=160$)
  * `simulation_src/` (Discrete-event simulation engine)
  * `benchmark_rerun.py` & `benchmark_rerun_final.csv` (Fair comparison interleaved benchmark $N=90$)

### 2.3 Directory Tree (Top-Level & Submodules)
```text
trex-experiments/
+-- 00_setup/
+-- 01_contracts/
|   +-- approval.teal
|   +-- clear.teal
|   +-- compile.py
|   +-- conftest.py
|   +-- contract.json
|   +-- deploy.py
|   +-- requirements.txt
|   +-- test_trex_escrow.py
|   +-- test_vectors.json
|   +-- trex_escrow.py
+-- 02_clients/
|   +-- attester.py
|   +-- buyer_agent.py
|   +-- config.py
|   +-- gen_vectors.py
|   +-- relayer.py
|   +-- seller_agent.py
+-- 03_pilot/
|   +-- audit_scripts/
|   +-- run_pilot.py
|   +-- run_pilot_v2.py
|   +-- run_adversarial_subset.py
+-- 04_campaign_C/
|   +-- run_all_campaign_c.py
|   +-- run_stratified_campaign.py
+-- 04_simulation/
+-- 05_analysis/
+-- 05_campaign_D/
|   +-- baselines/
|   |   +-- direct_payment_client.py
|   |   +-- naive_escrow_client.py
|   |   +-- naive_escrow_approval.teal
|   |   +-- naive_escrow_clear.teal
|   +-- code/
|   +-- manifest/
|   +-- raw/
|   |   +-- campaign_D_combined.csv
|   +-- analyze_campaign_D.py
|   +-- run_campaign_D.py
+-- 06_delta/
|   +-- delta_sessions.csv
|   +-- delta_validation_report.md
|   +-- run_delta_validation.py
+-- 07_final_campaign/
|   +-- final_functional_campaign.csv
|   +-- final_functional_report.md
|   +-- run_final_campaign.py
+-- 08_adversarial_campaign/
|   +-- adversarial_security_matrix.csv
|   +-- adversarial_security_report.md
|   +-- run_adversarial.py
+-- 09_manuscript_updates/
+-- artifacts/
|   +-- contract_app_id_testnet.txt
|   +-- contract_build_manifest.json
|   +-- pilot_v2_manifest.json
|   +-- pilot_v2_receipt_audit.csv
+-- reports/
+-- repro/
+-- results/
|   +-- avm_char/
|   +-- campaign_C/
|   +-- pilot/
|   |   +-- transactions_v2.csv
|   +-- simulation_v1/
+-- simulation_src/
|   +-- metrics.py
|   +-- requirements.txt
|   +-- run_simulation.py
|   +-- sim_engine.py
|   +-- workload_generator.py
+-- benchmark_rerun.py
+-- benchmark_rerun_final.csv
+-- fee_decision_memo.md
+-- forensic_fee_ledger.csv
+-- forensic_fee_ledger.py
+-- manuscript.tex
+-- v28.tex
```

---

## 3. ARTIFACT TRACEABILITY & SMART CONTRACT AUDIT

### 3.1 Primary PyTeal & TEAL Source Files
1. **`01_contracts/trex_escrow.py`:** PyTeal v0.26.1 specification of the T-REX state machine. Enforces AVM opcode budget pooling, Ed25519 signature checks, session state transitions, active nonce tracking (`T-REX-ACTIVE-NONCE`), and terminal spent markers (`T-REX-SPENT`).
2. **`01_contracts/approval.teal`:** Compiled TEAL v11 approval program (414 lines of PyTeal generating 922 instructions).
3. **`01_contracts/clear.teal`:** Clear state program (`int 1`).
4. **`05_campaign_D/baselines/naive_escrow_approval.teal`:** Baseline naive escrow approval program for comparative evaluation.

### 3.2 Testnet App ID Lineage & Artifact Mapping
| App ID | Stage / Campaign | Commit / Artifact | Architectural Features & Limitations |
| :--- | :--- | :--- | :--- |
| **`769248116`** | Pilot v2, AVM Characterization | `b654e95` | **Initial contract.** Identified box retention bug: `session` and `nonce` boxes were not deleted at terminal state, monotonically locking MBR. |
| **`769453473`** | Campaign C ($N=100$), Campaign D ($N=180$) | `41a5006` | **Revised contract (TEAL v10).** Added explicit `App.box_delete()` at terminal transitions (`release`/`refund`) to reclaim MBR. |
| **`770373602`** | Delta Validation ($N=20$) | Hardened TEAL v11 | **Targeted Security Artifact.** Enforced persistent anti-replay markers and deadline binding. Evaluated via 20 targeted delta negative tests in `06_delta`. |
| **`770852814`** | Final Security Artifact | Current working HEAD | **Final Production-Candidate TEAL v11.** Full P0-3 on-chain nonce enforcement (`T-REX-ACTIVE-NONCE` box created at authorize, deleted at terminal, replaced with persistent `T-REX-SPENT` marker). Validated across `07_final_campaign` ($N=100$), `08_adversarial_campaign` ($N=160$), and `benchmark_rerun.py` ($N=90$). |

### 3.3 Message Domain Verification: $M_S$ and $M_{A_i}$
An explicit inspection of `01_contracts/trex_escrow.py`, `02_clients/seller_agent.py`, and `02_clients/attester.py` reveals the following exact byte composition:

#### A. Seller Message $M_S$
In `02_clients/seller_agent.py` (lines 36–44):
```python
M_S = (
    config.PROTOCOL_DOMAIN +
    config.SETTLE_PREFIX +
    to_uint64(self.app_id) +
    self.chain_hash +
    to_uint64(session_id) +
    struct.pack(">Q", nonce) +
    H_p
)
```
In `01_contracts/trex_escrow.py` (lines 259–267):
```python
(msg_s := ScratchVar(TealType.bytes)).store(Concat(
    PROTOCOL_DOMAIN,
    SETTLE_PREFIX,
    Itob(Global.current_application_id()),
    Global.genesis_hash(),
    Itob(session_id.get()),
    Itob(nonce.get()),
    hash_p.get()
)),
```
* **Contains `appId`:** **YES** (`to_uint64(self.app_id)` / `Itob(Global.current_application_id())`).
* **Contains `B` (Buyer Address):** **NO**. (Neither client nor contract includes Buyer address in $M_S$).

#### B. Attester Message $M_{A_i}$
In `02_clients/attester.py` (lines 34–43):
```python
M_A = (
    b"T-REX-ATT" +
    struct.pack(">Q", session_id) +
    H_q +
    H_c +
    final_H_p +
    struct.pack(">B", verdict) +
    struct.pack(">Q", deadline_round) +
    struct.pack(">Q", nonce)
)
```
In `01_contracts/trex_escrow.py` (lines 274–283):
```python
(msg_a := ScratchVar(TealType.bytes)).store(Concat(
    Bytes("T-REX-ATT"),
    Itob(session_id.get()),
    hash_q.get(),
    hash_c.get(),
    hash_p.get(),
    Extract(Itob(VERDICT_PASS), Int(7), Int(1)),
    Itob(deadline_round.get()),
    Itob(nonce.get())
)),
```
* **Contains `appId`:** **NO**.
* **Contains `B` (Buyer Address):** **NO**.

---

## 4. SSPL EVALUATOR STATE

### 4.1 Implementation Status
* There is **no external AST evaluator** file (such as `sspl.py` or `predicate.py`) in the codebase.
* SLA satisfaction logic is currently hardcoded/mocked directly inside `02_clients/attester.py` (lines 27–31):
  ```python
  def attest(self, session_id, nonce, H_q, H_c, H_p, deadline_round, verdict=1):
      # 1. Evaluate SLA (mocked to match verdict)
      # 2. Construct M_A
      # In attested fail (verdict 0), the contract expects hash_p to be 32 bytes of zeros.
      final_H_p = H_p if verdict == 1 else (b'\x00' * 32)
  ```

### 4.2 Semantic Value Model: Strictly 2-Valued
* In `01_contracts/trex_escrow.py` (lines 17–18):
  ```python
  VERDICT_FAIL = Int(0)
  VERDICT_PASS = Int(1)
  ```
* **Status:** The current system is strictly **2-valued** ($\{0, 1\}$).
* **Deficiency for Revision:** There is **no 3-valued semantics** ($\text{PASS}=1, \text{FAIL}=0, \text{ERROR}=\bot$) and no algebraic support for operators (`Not()`, `And()`, `Or()`, `resolve()`). Any non-standard predicate result is coerced directly into a binary `0` or `1`.

---

## 5. ORCHESTRATION, TEST HARNESS & FEE ACCOUNTING AUDIT

### 5.1 Campaign Orchestrator Scripts
1. **Pilot & Baseline Characterization:**
   * `03_pilot/run_pilot_v2.py`: 20-session pilot run on App `769248116`.
   * `run_avm_char.py`: 30-session AVM opcode characterization test.
2. **Historical Validation Campaigns:**
   * `04_campaign_C/run_stratified_campaign.py`: 100-session stratified campaign on App `769453473`.
   * `05_campaign_D/run_campaign_D.py`: 180-session baseline comparative campaign (Direct vs Naive vs T-REX).
3. **Security & Delta Validation:**
   * `06_delta/run_delta_validation.py`: 20 targeted negative replay & binding tests on App `770373602`.
   * `07_final_campaign/run_final_campaign.py`: 100-session stratified validation on Final Artifact `770852814`.
   * `08_adversarial_campaign/run_adversarial.py`: 160-attempt adversarial security test matrix on App `770852814`.
4. **Current Benchmark (Fair Comparison Rerun):**
   * `benchmark_rerun.py`: 90-session ($30 \times 3$) interleaved round-robin benchmark on App `770852814`.

### 5.2 Root Cause of the SDK Fee-Pooling Overpayment Leak (128,000 µALGO)
In `07_final_campaign/run_final_campaign.py` (lines 172–199), the orchestrator configured fees as follows:
```python
app_params = algod_client.suggested_params()
app_params.flat_fee = True
app_params.fee = 11000  # Intended total fee for the 10-tx group

txn_app = transaction.ApplicationCallTxn(..., sp=app_params)
txns = [txn_app]
for j in range(9):
    txns.append(transaction.ApplicationCallTxn(..., sp=app_params, ...))
```
* **Mechanism of Failure:** In `py-algorand-sdk`, `sp.fee` in flat-fee mode sets the fee **per transaction**, not per group. Because the exact same `app_params` reference with `fee = 11000` was passed to all 10 transactions in the atomic group, Algorand charged $10 \times 11{,}000 = 110{,}000$ µALGO for the settle group. Combined with an overcharged authorize group ($4 \times 4{,}000 + 2{,}000 = 18{,}000$ µALGO in `02_clients/buyer_agent.py`), the logged on-chain fee totaled **128,000 µALGO**.

### 5.3 Remediation in `benchmark_rerun.py`
The fee allocation was corrected using independent `SuggestedParams` instances per transaction:
```python
def sp_for(algod: AlgodClient, fee: int = MIN_FEE):
    """Create a FRESH SuggestedParams with explicit flat fee.
    NEVER reuse a single SuggestedParams across multiple transactions
    in an atomic group — this was the root cause of the 128,000 µALGO
    fee-pooling abstraction leak."""
    sp = algod.suggested_params()
    sp.flat_fee = True
    sp.fee = fee
    return sp
```
* **Correct Phase Accounting:**
  * **Authorize:** 6 outer transactions $\times 1{,}000$ = **6,000 µALGO**.
  * **Settle:** 1 main call ($3{,}000$, covering 2 inner transfers) + 15 OpUp/pad calls ($15 \times 1{,}000$) = **18,000 µALGO**.
  * **Total Session Fee:** $6{,}000 + 18{,}000 =$ **24,000 µALGO**.

---

## 6. RAW DATA INVENTORY

All empirical logs, latency traces, and transaction records from Testnet executions are cataloged below:

| File Path | File Size | Description | Key Column Headers |
| :--- | :---: | :--- | :--- |
| [`results/pilot/transactions_v2.csv`](file:///c:/Users/lemin/OneDrive/Desktop/trex-experiments/results/pilot/transactions_v2.csv) | 6,870 bytes | Pilot v2 raw transaction log ($N=20$, App `769248116`) | `session_id, scenario, expected_outcome, observed_outcome, application_id, method, confirmed_round, payment_amount_micro_usdc, bounty_amount_micro_algo, network_fee_micro_algo, tx_id, settlement_or_refund_tx_id, box_state, bounty_paid` |
| [`results/pilot/pilot_v2_latency_audit.csv`](file:///c:/Users/lemin/OneDrive/Desktop/trex-experiments/results/pilot/pilot_v2_latency_audit.csv) | 4,117 bytes | Pilot v2 latency breakdown | `session_id, scenario, request_utc, authorize_submitted_utc, authorize_confirmed_utc, relayer_submitted_utc, finality_utc, ordering_valid, client_authorization_latency_s, client_terminal_latency_s, client_e2e_latency_s` |
| [`results/campaign_C/trex_campaign_C_combined.csv`](file:///c:/Users/lemin/OneDrive/Desktop/trex-experiments/results/campaign_C/trex_campaign_C_combined.csv) | 27,776 bytes | Campaign C stratified dataset ($N=100$, App `769453473`) | `session_id, type, deadline_round, t_request_initiated, t_terminal_submit, t_terminal_confirmed, finality_latency_ms, e2e_latency_ms, outer_tx_count, inner_tx_count, total_fee_uALGO, terminal_outcome, expected_outcome, invariant_violation, authorize_txid, terminal_txid, status` |
| [`05_campaign_D/raw/campaign_D_combined.csv`](file:///c:/Users/lemin/OneDrive/Desktop/trex-experiments/05_campaign_D/raw/campaign_D_combined.csv) | 53,622 bytes | Campaign D baseline comparison ($N=180$, App `769453473`) | `campaign_id, design, outcome, run_index, session_id, t_submit, t_confirmed, finality_latency_ms, e2e_latency_ms, outer_tx_count, inner_tx_count, total_fee_uALGO, terminal_outcome, expected_outcome, status, authorize_txid, terminal_txid` |
| [`06_delta/delta_sessions.csv`](file:///c:/Users/lemin/OneDrive/Desktop/trex-experiments/06_delta/delta_sessions.csv) | 4,014 bytes | Targeted delta validation ($N=20$, App `770373602`) | `Test ID, Category, Test Name, Status, TxID, Error Code, Budget Consumed, SPENT Box Verified` |
| [`07_final_campaign/final_functional_campaign.csv`](file:///c:/Users/lemin/OneDrive/Desktop/trex-experiments/07_final_campaign/final_functional_campaign.csv) | 34,428 bytes | Final functional campaign ($N=100$, App `770852814`) | `session_id, nonce, buyer, seller, app_id, scenario, auth_txid, term_txid, final_state, final_round, auth_latency_s, term_latency_s, e2e_latency_s, auth_outer_txns, term_outer_txns, term_inner_txns, auth_fee_microalgo, term_fee_microalgo, session_total_fee_microalgo, invariant_violations, spent_marker_present` |
| [`08_adversarial_campaign/adversarial_security_matrix.csv`](file:///c:/Users/lemin/OneDrive/Desktop/trex-experiments/08_adversarial_campaign/adversarial_security_matrix.csv) | 20,633 bytes | Adversarial test suite ($N=160$, App `770852814`) | `attack_id, attack_class, final_app_id, session_id, nonce, expected_rejection, actual_result, revert_reason` |
| [`benchmark_rerun_final.csv`](file:///c:/Users/lemin/OneDrive/Desktop/trex-experiments/benchmark_rerun_final.csv) | 25,097 bytes | Fair comparison interleaved rerun ($N=90$, App `770852814`) | `session_id, design_type, authorize_fee_uALGO, settle_fee_uALGO, total_fee_uALGO, authorize_tx_count, settle_tx_count, total_tx_count, authorize_latency_s, settle_latency_s, e2e_latency_seconds, start_time_utc, end_time_utc, first_round, last_round, tx_ids, status, error_reason` |
| [`forensic_fee_ledger.csv`](file:///c:/Users/lemin/OneDrive/Desktop/trex-experiments/forensic_fee_ledger.csv) | 3,605 bytes | Forensic fee analysis of group transactions | `scenario, expected_outer, actual_outer, actual_inner, actual_group_fee_microalgo, min_required_fee` |

### 6.1 Sample Raw Data Traces (First 3 Data Rows)

#### A. Final Functional Campaign (`07_final_campaign/final_functional_campaign.csv`)
```csv
session_id,nonce,buyer,seller,app_id,scenario,auth_txid,term_txid,final_state,final_round,auth_latency_s,term_latency_s,e2e_latency_s,auth_outer_txns,term_outer_txns,term_inner_txns,auth_fee_microalgo,term_fee_microalgo,session_total_fee_microalgo,invariant_violations,spent_marker_present
128,11179812756790102430,42CIA4I5Z7VAX4SON5WN7HL7KLY6MUTZR7N27UHBEM3MY5LGLMZRLPTBPI,W75SYX3EE7JC34PC5MMAYG3EVHO3IDEBGQQRFRIEHNLIZNLRQTCB5TUYZY,770852814,Normal Settle,3PWGAGMJCQDIPQKOWESYDF7GJZNNPRVPEDSM3UAJ2L4BB2ZNIJLA,5FFYAQBZVAFSNTEJ5F4KA7YR7QQY7BQRF2VOI7QHNBAUXRXESZBQ,RELEASED,66899201,5.668,5.004,11.155,3,10,2,18000,11000,29000,0,True
129,2536608217087499703,42CIA4I5Z7VAX4SON5WN7HL7KLY6MUTZR7N27UHBEM3MY5LGLMZRLPTBPI,W75SYX3EE7JC34PC5MMAYG3EVHO3IDEBGQQRFRIEHNLIZNLRQTCB5TUYZY,770852814,Normal Settle,YEENUIEKXS2YCDXWLV3F3UCO54AEA5J2H55GP3HTDS4IU7DB3GDQ,VDL7PCKUVTENOSXO4N5DPU24JPY3CEIOK27KBXBGQ3YDTGWG2IXQ,RELEASED,66899205,4.667,5.054,10.138,3,10,2,18000,11000,29000,0,True
130,8691308251703913106,42CIA4I5Z7VAX4SON5WN7HL7KLY6MUTZR7N27UHBEM3MY5LGLMZRLPTBPI,W75SYX3EE7JC34PC5MMAYG3EVHO3IDEBGQQRFRIEHNLIZNLRQTCB5TUYZY,770852814,Normal Settle,3XOL4OISLAAFEQTDJNXUDJYP75MPUKA5YC2GXH5OF7FYIOSRZEFQ,VCA2T2HDLIXSZ5HSKXKHGLK6ZIYOU5WTABW3CZU5XXD7SF3EGZGA,RELEASED,66899209,4.668,4.921,10.032,3,10,2,18000,11000,29000,0,True
```

#### B. Fair Comparison Benchmark Rerun (`benchmark_rerun_final.csv`)
```csv
session_id,design_type,authorize_fee_uALGO,settle_fee_uALGO,total_fee_uALGO,authorize_tx_count,settle_tx_count,total_tx_count,authorize_latency_s,settle_latency_s,e2e_latency_seconds,start_time_utc,end_time_utc,first_round,last_round,tx_ids,status,error_reason
33ecd09c-b2e6-44aa-9ceb-42deef5d3038,Direct,0,1000,1000,0,1,1,0.0,5.416,5.416,2026-09-15T05:58:53.230687+00:00,2026-09-15T05:58:58.647060+00:00,67320088,67320088,"[""3RC2O2TW3GXRBR7ZRVWFTTZDOUUNGYIBDPCIOHJBPGYT7QFDAB2Q""]",SUCCESS,
a704f636-e48d-408a-a611-0e2656c33cad,Naive,3000,2000,5000,2,1,3,5.131,5.166,10.556,2026-09-15T05:59:02.007119+00:00,2026-09-15T05:59:12.563399+00:00,67320091,67320093,"[""RE7TPHT2HQUIG752HL2LOOGMGRLPTVRJAUSQDBDAM7KHHU65O45A"", ""TGVVAPPT3KXO4ZWE6TMG6S56465ICTXNEEUNMLZ6QDTNQPMBAMIA""]",SUCCESS,
4ff4bb3e-71e1-4cff-a2e6-6ff9580fa90e,T-REX,6000,18000,24000,6,16,22,6.141,4.259,15.438,2026-09-15T05:59:16.064827+00:00,2026-09-15T05:59:31.502699+00:00,67320097,67320100,"[""32EJHJFAQDBGP75CFZMXUS27UW45HSSE3CSNFZCEUD2FQZIRL5CA"", ""APMYYOIJ2MWVWSVPJKVNOLWKPGS2SLVDDMZYTOXJYPAKOETQMYWQ""]",SUCCESS,
```

#### C. Adversarial Security Matrix (`08_adversarial_campaign/adversarial_security_matrix.csv`)
```csv
attack_id,attack_class,final_app_id,session_id,nonce,expected_rejection,actual_result,revert_reason
1,Replay Auth (Released),770852814,957,8983597045,Assertion / SPENT Marker,REVERTED,assertion / spent marker
2,Replay Auth (Released),770852814,973,1852024168,Assertion / SPENT Marker,REVERTED,assertion / spent marker
3,Replay Auth (Released),770852814,859,9144444754,Assertion / SPENT Marker,REVERTED,assertion / spent marker
```

---

## 7. SUMMARY & ARCHITECTURAL RECOMMENDATIONS FOR PEERJ CS

1. **Message Domain Hardening ($M_S$ & $M_{A_i}$):**
   * Currently, $M_S$ binds `appId` but lacks Buyer address $B$.
   * $M_{A_i}$ currently binds neither `appId` nor $B$.
   * *Recommendation:* Update contract and client serialization to include $B$ in $M_S$, and both `appId` and $B$ in $M_A$ to achieve complete cross-chain and cross-application domain separation.
2. **SSPL 3-Valued Logic Upgrade:**
   * Replace the binary `verdict = 0 | 1` stub with an explicit 3-valued truth-evaluator ($\text{PASS}=1, \text{FAIL}=0, \text{ERROR}=\bot$).
   * Formulate clear Kleene/Bochvar truth tables for compositional clauses.
3. **Artifact Consistency:**
   * All experimental evidence for PeerJ CS should strictly benchmark against Final Artifact **App ID `770852814`** (or its hardened derivative) using the verified fee pattern established in `benchmark_rerun.py`.
