import csv

def main():
    rows = []
    with open("../results/pilot/transactions.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            
    # Load prices
    prices = []
    with open("../results/pilot/algo_usd_price.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            prices.append(float(row["price_usd"]))
            
    avg_price = sum(prices) / len(prices) if prices else 0.079 # fallback

    out_rows = []
    for r in rows:
        network_fee = int(r["network_fee"]) if r["network_fee"] else 0
        bounty = int(r["amount_bounty"]) if r["amount_bounty"] else 0
        payment = int(r["amount_pay"]) if r["amount_pay"] else 0
        
        illustrative_usd = (network_fee / 1e6) * avg_price
        
        out_rows.append({
            "session_id": r["session_id"],
            "network_fee_microalgo": network_fee,
            "bounty_microalgo": bounty,
            "payment_micro_usdc": payment,
            "algo_usd_price": f"{avg_price:.6f}",
            "illustrative_fee_usd": f"{illustrative_usd:.6f}",
            "status": "VALID" if network_fee > 0 else "NA"
        })
        
    with open("../results/pilot/cost_audit.csv", "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["session_id", "network_fee_microalgo", "bounty_microalgo", "payment_micro_usdc", "algo_usd_price", "illustrative_fee_usd", "status"])
        writer.writeheader()
        writer.writerows(out_rows)
        
    print("Cost Audit complete.")

if __name__ == '__main__':
    main()
