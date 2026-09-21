import os
import sys
import csv
import base64
import time
from algosdk.v2client import algod, indexer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "02_clients"))
import config

algod_client = algod.AlgodClient("", config.ALGONODE_URL)
indexer_client = indexer.IndexerClient("", "https://testnet-idx.algonode.cloud")

csv_in = os.path.join(BASE_DIR, "07_final_campaign", "final_functional_campaign.csv")
csv_out = os.path.join(BASE_DIR, "forensic_fee_ledger.csv")

results = []
with open(csv_in, "r") as f:
    reader = csv.DictReader(f)
    for r in reader:
        results.append(r)

print("Starting Forensic Fee Ledger Audit...")

def get_group_fee(txid):
    try:
        res = indexer_client.search_transactions(txid=txid)
        if not res or not res.get("transactions"):
            return 0, 0, 0
            
        txn_info = res["transactions"][0]
        group = txn_info.get("group")
        round_num = txn_info.get("confirmed-round")
        
        if not group:
            outer = 1
            inner = len(txn_info.get("inner-txns", []))
            fee = txn_info.get("fee", 0)
            return outer, inner, fee
            
        block = algod_client.block_info(round_num)
        
        outer_count = 0
        inner_count = 0
        total_fee = 0
        
        for t in block["block"]["txns"]:
            grp = t["txn"].get("grp")
            if grp:
                if isinstance(grp, str):
                    grp_b64 = grp
                else:
                    grp_b64 = base64.b64encode(grp).decode('utf-8')
                    
                if grp_b64 == group:
                    outer_count += 1
                    total_fee += t["txn"].get("fee", 0)
                    dt = t.get("dt", {})
                    itx = dt.get("itx", [])
                    inner_count += len(itx)
        
        return outer_count, inner_count, total_fee
    except Exception as e:
        print(f"Error for txid {txid}: {e}")
        return 0, 0, 0

out_rows = []
seen_scenarios = set()

for i, r in enumerate(results):
    scenario = r["scenario"]
    auth_txid = r["auth_txid"]
    term_txid = r["term_txid"]
    
    auth_outer, auth_inner, auth_fee = get_group_fee(auth_txid)
    term_outer, term_inner, term_fee = get_group_fee(term_txid)
    
    total_outer = auth_outer + term_outer
    total_inner = auth_inner + term_inner
    actual_fee = auth_fee + term_fee
    
    expected_outer = int(r["auth_outer_txns"]) + int(r["term_outer_txns"])
    min_required_fee = (total_outer + total_inner) * 1000
    
    out_rows.append({
        "scenario": scenario,
        "expected_outer": expected_outer,
        "actual_outer": total_outer,
        "actual_inner": total_inner,
        "actual_group_fee_microalgo": actual_fee,
        "min_required_fee": min_required_fee
    })
    
    if scenario not in seen_scenarios:
        seen_scenarios.add(scenario)
        print(f"[{scenario}]")
        print(f"  Auth: {auth_outer} outer, {auth_inner} inner, Fee: {auth_fee}")
        print(f"  Term: {term_outer} outer, {term_inner} inner, Fee: {term_fee}")
        print(f"  Session Total Outer: {total_outer}")
        print(f"  Session Total Inner: {total_inner}")
        print(f"  Actual Network Fee Deduced: {actual_fee} microALGO")
        print(f"  Old Orchestrator Logged: {r['session_total_fee_microalgo']} microALGO")
        print(f"  Minimum Theoretical Fee: {min_required_fee} microALGO")
        print("-" * 50)
        
    # Wait lightly to avoid rate limits
    time.sleep(0.05)

with open(csv_out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=out_rows[0].keys())
    w.writeheader()
    for row in out_rows:
        w.writerow(row)

print(f"Analysis saved to {csv_out}")
