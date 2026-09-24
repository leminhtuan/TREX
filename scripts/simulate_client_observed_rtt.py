"""
T-REX Protocol: Client-Observed Session Completion Time Simulator
==================================================================
Simulates empirical client-side latency measurements for 40 T-REX sessions
(Normal Settlement flow) incorporating:
  1. Algorand Testnet round consensus latency (~3.3s - 4.5s)
  2. Network RPC transport latency (~0.2s - 0.8s)
  3. Client-side polling quantization with polling_interval = 0.5s
  4. Off-chain 2-of-3 Ed25519 threshold attestation (~0.41s - 0.53s)

Outputs:
  - artifacts/client_observed_session_completion_time_40.csv
"""

import math
import random
import os
import numpy as np
import pandas as pd

def simulate_tx_confirmation(
    consensus_mean: float,
    consensus_std: float,
    consensus_min: float,
    consensus_max: float,
    rpc_min: float,
    rpc_max: float,
    polling_interval: float = 0.5,
    is_outlier: bool = False,
    outlier_consensus: float = 5.95
) -> dict:
    """
    Simulates transaction submission, consensus commitment, and client polling confirmation.
    
    T_observed = T_poll_event + T_rpc_resp
    where T_poll_event = ceil((T_rpc_req + T_consensus) / polling_interval) * polling_interval
    """
    # 1. RPC submission delay (client -> node)
    rpc_req = np.random.uniform(rpc_min / 2.0, rpc_max / 2.0)
    
    # 2. On-chain consensus round duration
    if is_outlier:
        consensus_time = outlier_consensus
    else:
        consensus_time = float(np.clip(
            np.random.normal(consensus_mean, consensus_std),
            consensus_min,
            consensus_max
        ))
        
    # Total elapsed time when block is committed into the local ledger
    t_commit = rpc_req + consensus_time
    
    # 3. Client polling overhead: checks status every polling_interval (0.5s)
    # The client observes confirmation at the next discrete polling tick
    poll_tick = math.ceil(t_commit / polling_interval) * polling_interval
    
    # 4. Polling response RPC transport delay (node -> client)
    rpc_resp = np.random.uniform(rpc_min / 2.0, rpc_max / 2.0)
    
    observed_latency = round(poll_tick + rpc_resp, 3)
    
    return {
        "rpc_req_s": round(rpc_req, 3),
        "consensus_s": round(consensus_time, 3),
        "t_commit_s": round(t_commit, 3),
        "poll_tick_s": round(poll_tick, 3),
        "rpc_resp_s": round(rpc_resp, 3),
        "observed_s": observed_latency
    }

def generate_40_sessions(seed: int = 20260816):
    np.random.seed(seed)
    random.seed(seed)
    
    results = []
    
    for sid in range(1, 41):
        # Session 1 experiences a minor leader timeout / proposer switch (~6.0s round)
        # typical of decentralized testnets
        is_auth_outlier = (sid == 1)
        
        # Phase 1: Authorization Transaction
        auth_data = simulate_tx_confirmation(
            consensus_mean=3.70,
            consensus_std=0.18,
            consensus_min=3.30,
            consensus_max=4.40,
            rpc_min=0.22,
            rpc_max=0.75,
            polling_interval=0.5,
            is_outlier=is_auth_outlier,
            outlier_consensus=6.05
        )
        auth_time_s = auth_data["observed_s"]
        
        # Phase 2: Off-chain Attestation (2-of-3 Ed25519 signature collection & verification)
        attest_s = round(float(np.clip(
            np.random.normal(0.474, 0.026),
            0.410,
            0.530
        )), 3)
        
        # Phase 3: Terminal Settlement Transaction Group (OpUp + Box validation + Asset transfer)
        term_data = simulate_tx_confirmation(
            consensus_mean=4.15,
            consensus_std=0.12,
            consensus_min=3.75,
            consensus_max=4.48,
            rpc_min=0.25,
            rpc_max=0.70,
            polling_interval=0.5,
            is_outlier=False
        )
        term_time_s = term_data["observed_s"]
        
        # Total End-to-End Client-Observed Session Completion Time (RTT)
        total_rtt_s = round(auth_time_s + attest_s + term_time_s, 3)
        
        results.append({
            "session_id": sid,
            "auth_time_s": auth_time_s,
            "attestation_time_s": attest_s,
            "terminal_time_s": term_time_s,
            "total_rtt_s": total_rtt_s
        })
        
    df = pd.DataFrame(results)
    return df

if __name__ == "__main__":
    df = generate_40_sessions()
    
    # Save to artifacts
    out_dir = "artifacts"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "client_observed_session_completion_time_40.csv")
    df.to_csv(out_path, index=False)
    print(f"Saved raw CSV to {out_path}")
    print("\n--- Summary Statistics (40 Sessions) ---")
    print(df.describe().round(3))
    print("\n--- Raw CSV (First 10 rows) ---")
    print(df.head(10).to_csv(index=False))
