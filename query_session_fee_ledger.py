import json
import base64
from algosdk.v2client import indexer, algod

idx = indexer.IndexerClient("", "https://testnet-idx.algonode.cloud")

auth_txid = "32EJHJFAQDBGP75CFZMXUS27UW45HSSE3CSNFZCEUD2FQZIRL5CA"
term_txid = "APMYYOIJ2MWVWSVPJKVNOLWKPGS2SLVDDMZYTOXJYPAKOETQMYWQ"

def inspect_group(txid, label):
    print(f"\n{'='*20} {label} ({txid}) {'='*20}")
    tx_data = idx.transaction(txid)["transaction"]
    gid = tx_data.get("group")
    round_num = tx_data.get("confirmed-round")
    print(f"Confirmed Round: {round_num}")
    print(f"Group ID (b64): {gid}")
    
    # Query block transactions or search by round
    res = idx.search_transactions(round_num=round_num)
    matching_txns = [t for t in res.get("transactions", []) if t.get("group") == gid]
    
    # Sort by intra-round-offset if available
    matching_txns.sort(key=lambda t: t.get("intra-round-offset", 0))
    
    print(f"Outer Transactions Found: {len(matching_txns)}")
    total_outer_fee = 0
    total_inners = 0
    
    for i, t in enumerate(matching_txns):
        t_id = t.get("id")
        t_type = t.get("tx-type")
        t_fee = t.get("fee", 0)
        total_outer_fee += t_fee
        inners = t.get("inner-txns", [])
        total_inners += len(inners)
        
        detail = ""
        if t_type == "axfer":
            amt = t.get("asset-transfer-transaction", {}).get("amount", 0)
            asset = t.get("asset-transfer-transaction", {}).get("asset-id")
            detail = f"Asset={asset}, Amount={amt}"
        elif t_type == "pay":
            amt = t.get("payment-transaction", {}).get("amount", 0)
            detail = f"Amount={amt} microALGO"
        elif t_type == "appl":
            args = t.get("application-transaction", {}).get("application-args", [])
            app_id = t.get("application-transaction", {}).get("application-id")
            detail = f"AppID={app_id}, ArgsCount={len(args)}"
            
        print(f"  [{i+1:2d}] TxID: {t_id} | Type: {t_type:5s} | Fee: {t_fee:5d} µALGO | Inners: {len(inners)} | {detail}")
        for j, in_t in enumerate(inners):
            in_type = in_t.get("tx-type")
            in_fee = in_t.get("fee", 0)
            print(f"       -> Inner {j+1}: Type={in_type:5s}, Fee={in_fee} µALGO")

    print(f"Total Outer Fee: {total_outer_fee} µALGO")
    print(f"Total Transactions (Outer + Inner): {len(matching_txns) + total_inners}")
    return {
        "label": label,
        "txid": txid,
        "round": round_num,
        "gid": gid,
        "outer_count": len(matching_txns),
        "inner_count": total_inners,
        "total_tx_count": len(matching_txns) + total_inners,
        "actual_fee_uALGO": total_outer_fee
    }

if __name__ == "__main__":
    auth_summary = inspect_group(auth_txid, "AUTHORIZE GROUP")
    term_summary = inspect_group(term_txid, "TERMINAL GROUP")
    
    total_tx = auth_summary["total_tx_count"] + term_summary["total_tx_count"]
    total_fee = auth_summary["actual_fee_uALGO"] + term_summary["actual_fee_uALGO"]
    
    print("\n" + "="*60)
    print("SESSION TOTALS:")
    print(f"Total Transaction Count (Outer + Inner): {total_tx}")
    print(f"Total Session Fee (F_session): {total_fee} µALGO")
    print("="*60)
