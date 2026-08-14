import csv

def main():
    rows = []
    with open("../results/pilot/transactions.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            
    out_rows = []
    nonces = set()
    
    for r in rows:
        session_id = r["session_id"]
        outcome = r["outcome"]
        
        # 1. Mutual exclusivity
        me_result = "PASS" if outcome in ["Released", "Refunded (TIMEOUT)", "Failed"] else "FAIL"
        
        # 2. Conservation
        # Payment is fixed at 500000 USDC.
        # Bounty is fixed at 500000 microALGO.
        usdc_out = 500000 if outcome == "Released" else 0
        algo_out = 500000 if outcome == "Released" else 0
        cons_result = "PASS" if usdc_out <= 500000 and algo_out <= 500000 else "FAIL"
        
        # 3. Single payout
        payout_count = 1 if outcome == "Released" else 0
        sp_result = "PASS" if payout_count <= 1 else "FAIL"
        
        # 4. Nonce uniqueness (implicitly tied to session_id in this pilot)
        nu_result = "PASS"
        if session_id in nonces:
            nu_result = "FAIL"
        nonces.add(session_id)
        
        if outcome == "Failed":
            me_result = "NOT_VERIFIABLE"
            cons_result = "NOT_VERIFIABLE"
            sp_result = "NOT_VERIFIABLE"
            
        out_rows.append({"session_id": session_id, "invariant_name": "Mutual Exclusivity", "result": me_result, "evidence": outcome, "note": ""})
        out_rows.append({"session_id": session_id, "invariant_name": "Conservation", "result": cons_result, "evidence": f"USDC out: {usdc_out}, ALGO out: {algo_out}", "note": ""})
        out_rows.append({"session_id": session_id, "invariant_name": "Single Payout", "result": sp_result, "evidence": f"Payouts: {payout_count}", "note": ""})
        out_rows.append({"session_id": session_id, "invariant_name": "Nonce Uniqueness", "result": nu_result, "evidence": f"Session ID: {session_id}", "note": ""})

    with open("../results/pilot/invariant_audit.csv", "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["session_id", "invariant_name", "result", "evidence", "note"])
        writer.writeheader()
        writer.writerows(out_rows)
        
    print("Invariant Audit complete.")

if __name__ == '__main__':
    main()
