# T-REX Simulation Timing Validation

> VALID_SIMULATION_ONLY: model-based synthetic estimates under stated assumptions.
> No Algorand API calls. No transactions submitted.

## 1. Block-Alignment Convention

### 1.1 confirm_time(submission_time, block_time_s) Rule

Confirmation occurs at the FIRST block boundary >= submission_time.

```
confirm_time(t, bt) = ceil(t / bt) * bt
```

Special cases:
- If t == k * bt exactly -> confirmation at t (boundary is inclusive).
- If t == 0.0 -> confirmation at 0.0.

### 1.2 Timing Flow (4 On-Chain Steps)

```
arrival_time
  + auth_service_scale_s delay (Exp)
  = auth_submit_time
  -> auth_confirmation_time = confirm_time(auth_submit_time, 3.5)   [STEP 1]
  -> deadline_time = auth_confirmation_time + 15 * 3.5 = + 52.5s

auth_confirmation_time
  + seller_service_scale_s delay (Exp)
  = seller_submit_time
  -> seller_confirmation_time = confirm_time(seller_submit_time, 3.5)  [STEP 2]

seller_confirmation_time
  + attest_service_scale_s delay (Exp, per attester)
  = attest_submit_time[i]
  -> all_attest_confirmed = confirm_time(max(attest_submit_times), 3.5)  [STEP 3]

all_attest_confirmed
  + relayer_service_scale_s delay (Exp)
  = relayer_submit_time
  -> terminal_confirmation_time = confirm_time(relayer_submit_time, 3.5)  [STEP 4]

if terminal_confirmation_time > deadline_time: outcome = Refunded(TIMEOUT)
```

## 2. Unit Test Coverage

### 2.1 TestConfirmTime (6 tests)

| Test | Input | Expected |
|---|---|---|
| test_exact_boundary | t=3.5, bt=3.5 | 3.5 |
| test_exact_boundary | t=7.0, bt=3.5 | 7.0 |
| test_exact_boundary | t=0.0, bt=3.5 | 0.0 |
| test_just_before_boundary | t=3.5-1e-9, bt=3.5 | 3.5 |
| test_just_after_boundary | t=3.5+1e-9, bt=3.5 | 7.0 |
| test_interior | t=1.2, bt=3.5 | 3.5 |
| test_interior | t=2.9, bt=3.5 | 3.5 |
| test_multiple_sequential_block_waits | chain: 0.1->3.5->3.7->7.0->7.3->10.5 | PASS |
| test_next_block_boundary_alias | multiple t values | matches wg.next_block_boundary |

### 2.2 TestDeadline (3 tests)

| Test | Input | Expected |
|---|---|---|
| test_deadline_equality | auth_confirm=3.5, blocks=15, bt=3.5 | 56.0 |
| test_deadline_exceeded | terminal_confirm = deadline + epsilon | terminal > deadline |
| test_just_at_deadline | terminal_confirm == deadline | NOT timeout (> not satisfied) |

### 2.3 TestSessionStateMachine: test_latency_plausible

- Configuration: lambda=10, packet_loss=0, malicious_seller=0, byzantine=0
- n_events=500, n_warmup=20
- Verified: every Released session has e2e >= 3 * block_time_s (= 10.5 s)
- Verified: every Released session has e2e <= 15 * block_time_s (= 52.5 s)

Rationale for floor of 3 * bt (not 4 * bt):
- There are 4 on-chain steps (auth, seller, attest, terminal).
- A session arriving at t = k*bt - epsilon gets auth_confirmation at k*bt
  (epsilon wait). Steps 2, 3, 4 each require at least one full block interval.
- Minimum e2e = epsilon + bt + bt + bt >= 3*bt.

## 3. Smoke Test Results (block-alignment fixed)

| Seed | n_meas | released | e2e_p50 (s) | frr | odr | ivr |
|---|---|---|---|---|---|---|
| 0 | 10000 | 10000 | 12.74 | NA | NA | 0.0 |
| 1 | 10000 | 10000 | 12.776 | NA | NA | 0.0 |
| 2 | 10000 | 10000 | 12.752 | NA | NA | 0.0 |

Latency sanity-check anchor (advisory, N=16 Pilot v2, client-side):
- Anchor range: 10.2-12.2 s
- Simulated P50: ~12.75 s
- Within 5x anchor range: PASS
- Note: Simulated latency is a model-based synthetic estimate under stated assumptions.
  The comparison to Testnet-observed anchor is advisory only (N=16 insufficient for validation).

## 4. Failure Mode Classification

### Primary failure_mode field (frozen schema)
- none, seller_omission, packet_loss, attester_unavailability, relayer_failure, byzantine_attester, adversarial_relayer

### failure_detail sub-field (not in frozen CSV columns)
- packet_loss_authorize: authorization message dropped
- packet_loss_payload: seller payload message dropped
- packet_loss_attestation: attester message dropped
- none: no packet loss failure

## 5. Deterministic Replay

All 3 seeds produce byte-identical outcome sequences when re-run:
- Seed 0: MATCH
- Seed 1: MATCH
- Seed 2: MATCH

Hash method: SHA-256 of JSON-serialized [(session_id, outcome, terminal_time)] list.

---

*No transactions submitted. No Algorand API calls. Pilot v2 artifacts unmodified.*
*All results are VALID_SIMULATION_ONLY: model-based synthetic estimates under stated assumptions.*
