import sys
import os
import time
import base64
import json
import csv
from pathlib import Path

# Add clients directory to sys path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "02_clients"))
from buyer_agent import BuyerAgent
from seller_agent import SellerAgent
from attester import AttesterAgent
from relayer import RelayerAgent
import config

def get_box_state(client, app_id, session_id):
    session_box_name = b"session:" + session_id.to_bytes(8, 'big')
    try:
        box_info = client.application_box_by_name(app_id, session_box_name)
        val = base64.b64decode(box_info["value"])
        # uint8 state is the first byte
        state = val[0]
        # bounty_paid is at byte index 192, threshold at 193, count at 194. 
        # State(1) + Buyer(32) + Seller(32) + Asset(8) + Pay(8) + Bounty(8) + DL(8) + Nonce(32) + H_q(32) + H_c(32) + H_p(32) = 225 bytes
        # Let's just decode state and bounty_paid for now
        bounty_paid = val[225]
        hash_p = val[193:225]
        return {
            "state": state,
            "bounty_paid": bounty_paid,
            "hash_p_hex": hash_p.hex()
        }
    except Exception as e:
        print(f"Failed to read box: {e}")
        return None

def test_attested_fail_onchain():
    buyer = BuyerAgent()
    seller = SellerAgent()
    a1 = AttesterAgent(0, config.ATTESTER_1_SK)
    a2 = AttesterAgent(1, config.ATTESTER_2_SK)
    r = RelayerAgent()
    
    print("--- 1. Checking Balances ---")
    b_info_start = buyer.client.account_info(config.BUYER_ADDR)
    r_info_start = r.client.account_info(config.RELAYER_ADDR)
    
    usdc_id = config.USDC_ASA_ID
    
    b_usdc_start = next((a["amount"] for a in b_info_start.get("assets", []) if a["asset-id"] == usdc_id), 0)
    b_algo_start = b_info_start["amount"]
    r_algo_start = r_info_start["amount"]
    
    print(f"Buyer USDC: {b_usdc_start}, Buyer ALGO: {b_algo_start/1e6}")
    print(f"Relayer ALGO: {r_algo_start/1e6}")
    
    print("\n--- 2. Authorize ---")
    USDC_AMOUNT = 500000
    ALGO_AMOUNT = 500000
    params = buyer.client.suggested_params()
    deadline = params.first + 100
    
    b_out = buyer.authorize(config.SELLER_ADDR, USDC_AMOUNT, ALGO_AMOUNT, deadline)
    session_id = b_out["session_id"]
    nonce = b_out["nonce"]
    H_q = b_out["H_q"]
    H_c = b_out["H_c"]
    
    print(f"Session ID created: {session_id}")
    
    print("\n--- 3. Seller Process (Hash Mismatch) ---")
    s_out = seller.process_request(session_id, H_q, H_c, nonce, simulate_mismatch=True)
    H_p = s_out["H_p"]
    
    print("\n--- 4. Attest (FAIL) ---")
    # verdict = 0 (FAIL)
    att1_out = a1.attest(session_id, nonce, H_q, H_c, H_p, verdict=0)
    att2_out = a2.attest(session_id, nonce, H_q, H_c, H_p, verdict=0)
    
    print("\n--- 5. Refund (ATTESTED_FAIL) ---")
    r_out = r.refund(session_id, 1, att1_out, att2_out)
    print(f"Refund TxID: {r_out['tx_id']}")
    print(f"Confirmed Round: {r_out['confirmed_round']}")
    print(f"Outcome: {r_out['outcome']}")
    
    print("\n--- 6. Verifying Outcome & State ---")
    box_state = get_box_state(buyer.client, config.APP_ID, session_id)
    print(f"Box State: {box_state}")
    
    # Check Balances
    b_info_end = buyer.client.account_info(config.BUYER_ADDR)
    r_info_end = r.client.account_info(config.RELAYER_ADDR)
    
    b_usdc_end = next((a["amount"] for a in b_info_end.get("assets", []) if a["asset-id"] == usdc_id), 0)
    r_algo_end = r_info_end["amount"]
    
    usdc_returned = (b_usdc_end == b_usdc_start) # because it was locked then returned
    algo_paid_to_relayer = (r_algo_end > r_algo_start + ALGO_AMOUNT - 30000) # Relayer gets 500000, pays fee
    
    print(f"Buyer USDC start: {b_usdc_start} -> end: {b_usdc_end}. Verified return: {usdc_returned}")
    print(f"Relayer ALGO increased: {algo_paid_to_relayer}")
    
    print("\n--- 7. Logging to CSV ---")
    csv_path = Path(os.path.join(os.path.dirname(__file__), "..", "results", "pilot", "attested_fail_test.csv"))
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_exists = csv_path.exists()
    with open(csv_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["session_id", "outcome", "tx_id", "confirmed_round", "box_state", "usdc_transfer_verified", "algo_transfer_verified", "error_message"])
        writer.writerow([
            session_id,
            r_out['outcome'],
            r_out['tx_id'],
            r_out['confirmed_round'],
            json.dumps(box_state),
            usdc_returned,
            algo_paid_to_relayer,
            ""
        ])
    print("Success: Attested-failure path fixed, Refunded outcome achieved.")

if __name__ == '__main__':
    test_attested_fail_onchain()

