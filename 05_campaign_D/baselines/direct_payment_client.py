import os
import sys
import datetime
from algosdk import transaction
from algosdk.v2client import algod

sys.path.insert(0, os.path.abspath('../../02_clients'))
import config

def run_direct_payment(session_id, amount_usdc):
    client = algod.AlgodClient("", config.ALGONODE_URL)
    sp = client.suggested_params()
    
    t_submit = datetime.datetime.utcnow()
    
    txn = transaction.AssetTransferTxn(
        sender=config.BUYER_ADDR,
        sp=sp,
        receiver=config.SELLER_ADDR,
        amt=amount_usdc,
        index=config.USDC_ASA_ID
    )
    
    stxn = txn.sign(config.BUYER_SK)
    txid = client.send_transaction(stxn)
    
    res = transaction.wait_for_confirmation(client, txid, 4)
    t_confirmed = datetime.datetime.utcnow()
    
    finality_latency_ms = (t_confirmed - t_submit).total_seconds() * 1000
    
    # Read actual fee from pending_transaction_info
    ptx = client.pending_transaction_info(txid)
    actual_fee = ptx.get("txn", {}).get("txn", {}).get("fee", 0)
    
    return {
        "campaign_id": "CR-1_Campaign_D",
        "design": "direct",
        "outcome": "transfer",
        "session_id": session_id,
        "t_submit": t_submit.isoformat() + "Z",
        "t_confirmed": t_confirmed.isoformat() + "Z",
        "finality_latency_ms": finality_latency_ms,
        "e2e_latency_ms": finality_latency_ms, # for direct, e2e = finality
        "outer_tx_count": 1,
        "inner_tx_count": 0,
        "total_fee_uALGO": actual_fee,
        "terminal_outcome": "TRANSFERRED",
        "expected_outcome": "TRANSFERRED",
        "status": "SUCCESS",
        "error_message": "",
        "authorize_txid": "",
        "terminal_txid": txid,
        "recycling_needed": True,
        "recycling_txid": "",
        "recycling_latency_ms": 0
    }
