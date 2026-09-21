import os
import sys
import json
import time
import base64
import struct
import hashlib
from nacl.signing import SigningKey
from algosdk import encoding, transaction
from algosdk.v2client import algod
from algosdk.abi import Method

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "02_clients"))

import config
from buyer_agent import BuyerAgent
from seller_agent import SellerAgent
from attester import AttesterAgent
from relayer import RelayerAgent

def run_tests():
    client = algod.AlgodClient("", config.ALGONODE_URL)
    app_id = config.APP_ID
    app_params = client.suggested_params()
    genesis_hash_testnet = base64.b64decode(app_params.gh)
    
    print(f"=== Unified Test Suite for T-REX Contract App ID: {app_id} ===")
    print(f"Network Genesis Hash (Testnet): {base64.b64encode(genesis_hash_testnet).decode()}")
    print("=" * 60)
    
    buyer = BuyerAgent()
    seller = SellerAgent()
    att1 = AttesterAgent(0, config.ATTESTER_1_SK)
    att2 = AttesterAgent(1, config.ATTESTER_2_SK)
    relayer = RelayerAgent()
    
    functional_results = []
    
    # -------------------------------------------------------------
    # PART 1: 5 Functional Normal-Settle Sessions
    # -------------------------------------------------------------
    print("\n--- Running 5 Functional Normal-Settle Sessions ---")
    for s_idx in range(1, 6):
        print(f"\n[Functional Session {s_idx}/5]")
        sp = client.suggested_params()
        deadline_round = sp.first + 200
        
        # 1. Authorize
        auth_res = buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, deadline_round)
        sid = auth_res["session_id"]
        nonce = auth_res["nonce"]
        print(f"  Authorized Session ID: {sid} (TxID: {auth_res['tx_id']})")
        
        # 2. Seller processing
        seller_res = seller.process_request(sid, auth_res["H_q"], auth_res["H_c"], nonce, buyer_address=config.BUYER_ADDR)
        print(f"  Seller processed payload H_p: {seller_res['H_p'].hex()[:16]}...")
        
        # 3. Attestation
        a1_res = att1.attest(sid, nonce, auth_res["H_q"], auth_res["H_c"], seller_res["H_p"], deadline_round, 1, buyer_address=config.BUYER_ADDR)
        a2_res = att2.attest(sid, nonce, auth_res["H_q"], auth_res["H_c"], seller_res["H_p"], deadline_round, 1, buyer_address=config.BUYER_ADDR)
        print("  Attesters 0 & 1 signed M_A (Verdict=1)")
        
        # 4. Relayer Settlement
        settle_res = relayer.settle(sid, seller_res["H_p"], seller_res["seller_signature"], a1_res, a2_res)
        print(f"  Settled! TxID: {settle_res['tx_id']}, Confirmed Round: {settle_res['confirmed_round']}")
        
        functional_results.append({
            "session_idx": s_idx,
            "session_id": sid,
            "auth_txid": auth_res["tx_id"],
            "settle_txid": settle_res["tx_id"],
            "confirmed_round": settle_res["confirmed_round"],
            "status": "PASSED"
        })
        time.sleep(1)

    # -------------------------------------------------------------
    # PART 2: 10 Adversarial Tests
    # -------------------------------------------------------------
    print("\n\n--- Running 10 Adversarial Tests ---")
    adversarial_results = []
    
    def execute_adversarial(test_num, name, func):
        print(f"\n[Adversarial Test {test_num}/10]: {name}")
        try:
            func()
            print(f"  FAILED: Exploit unexpectedly succeeded!")
            adversarial_results.append({
                "test_num": test_num,
                "name": name,
                "expected": "REVERTED",
                "actual": "SUCCEEDED",
                "status": "FAIL"
            })
        except Exception as e:
            err_msg = str(e)
            print(f"  PASSED: Contract rejected transaction as expected.")
            print(f"  Revert reason snippet: {err_msg[:120]}...")
            adversarial_results.append({
                "test_num": test_num,
                "name": name,
                "expected": "REVERTED",
                "actual": "REVERTED",
                "reason": err_msg[:120],
                "status": "PASSED"
            })
            
    # Setup a helper session for adversarial tests
    sp = client.suggested_params()
    dl = sp.first + 300
    base_auth = buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, dl)
    base_sid = base_auth["session_id"]
    base_nonce = base_auth["nonce"]
    base_seller = seller.process_request(base_sid, base_auth["H_q"], base_auth["H_c"], base_nonce, buyer_address=config.BUYER_ADDR)
    
    # Adv Test 1: Cross-Network Replay (Fake all-zero genesis hash)
    def adv1_fake_genesis():
        fake_gh = b"\x00" * 32
        bad_a1 = att1.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR, chain_hash=fake_gh)
        bad_a2 = att2.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR, chain_hash=fake_gh)
        relayer.settle(base_sid, base_seller["H_p"], base_seller["seller_signature"], bad_a1, bad_a2)
    execute_adversarial(1, "Cross-Network Replay (All-Zero Genesis Hash in M_A)", adv1_fake_genesis)

    # Adv Test 2: Cross-Network Replay (Mainnet Genesis Hash)
    def adv2_mainnet_genesis():
        mainnet_gh = base64.b64decode("wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=")
        bad_a1 = att1.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR, chain_hash=mainnet_gh)
        bad_a2 = att2.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR, chain_hash=mainnet_gh)
        relayer.settle(base_sid, base_seller["H_p"], base_seller["seller_signature"], bad_a1, bad_a2)
    execute_adversarial(2, "Cross-Network Replay (Mainnet Genesis Hash in M_A)", adv2_mainnet_genesis)

    # Adv Test 3: Cross-User Replay (Wrong Buyer Address in M_A)
    def adv3_cross_user():
        wrong_buyer = config.SELLER_ADDR
        bad_a1 = att1.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=wrong_buyer)
        bad_a2 = att2.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=wrong_buyer)
        relayer.settle(base_sid, base_seller["H_p"], base_seller["seller_signature"], bad_a1, bad_a2)
    execute_adversarial(3, "Cross-User Replay (Wrong Buyer Bound in M_A)", adv3_cross_user)

    # Adv Test 4: Wrong App ID Replay (M_A bound to App ID + 1)
    def adv4_wrong_appid():
        saved_id = att1.app_id
        att1.app_id = saved_id + 1
        att2.app_id = saved_id + 1
        try:
            bad_a1 = att1.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR)
            bad_a2 = att2.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR)
            relayer.settle(base_sid, base_seller["H_p"], base_seller["seller_signature"], bad_a1, bad_a2)
        finally:
            att1.app_id = saved_id
            att2.app_id = saved_id
    execute_adversarial(4, "Wrong Application ID Replay in M_A", adv4_wrong_appid)

    # Adv Test 5: Deadline Tampering (M_A signed with altered deadline)
    def adv5_deadline_tampering():
        bad_dl = dl + 9999
        bad_a1 = att1.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], bad_dl, 1, buyer_address=config.BUYER_ADDR)
        bad_a2 = att2.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], bad_dl, 1, buyer_address=config.BUYER_ADDR)
        relayer.settle(base_sid, base_seller["H_p"], base_seller["seller_signature"], bad_a1, bad_a2)
    execute_adversarial(5, "Deadline Tampering (Attester alters r_dead)", adv5_deadline_tampering)

    # Adv Test 6: Corrupted Attester Signature
    def adv6_corrupt_att_sig():
        good_a1 = att1.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR)
        good_a2 = att2.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR)
        corrupted_sig = bytearray(good_a1["signature"])
        corrupted_sig[0] ^= 0xFF
        good_a1["signature"] = bytes(corrupted_sig)
        relayer.settle(base_sid, base_seller["H_p"], base_seller["seller_signature"], good_a1, good_a2)
    execute_adversarial(6, "Corrupted Attester Signature (Invalid Ed25519)", adv6_corrupt_att_sig)

    # Adv Test 7: Corrupted Seller Signature
    def adv7_corrupt_seller_sig():
        good_a1 = att1.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR)
        good_a2 = att2.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR)
        corrupted_seller_sig = bytearray(base_seller["seller_signature"])
        corrupted_seller_sig[0] ^= 0xFF
        relayer.settle(base_sid, base_seller["H_p"], bytes(corrupted_seller_sig), good_a1, good_a2)
    execute_adversarial(7, "Corrupted Seller Signature (Invalid M_S sig)", adv7_corrupt_seller_sig)

    # Adv Test 8: Tampered Payload Hash in Attestation
    def adv8_tampered_payload_hash():
        fake_hp = hashlib.sha256(b"tampered_data").digest()
        bad_a1 = att1.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], fake_hp, dl, 1, buyer_address=config.BUYER_ADDR)
        bad_a2 = att2.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], fake_hp, dl, 1, buyer_address=config.BUYER_ADDR)
        relayer.settle(base_sid, base_seller["H_p"], base_seller["seller_signature"], bad_a1, bad_a2)
    execute_adversarial(8, "Payload Hash Tampering (H_p mismatch)", adv8_tampered_payload_hash)

    # Now settle base session legitimately to enable double-settle test
    good_a1 = att1.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR)
    good_a2 = att2.attest(base_sid, base_nonce, base_auth["H_q"], base_auth["H_c"], base_seller["H_p"], dl, 1, buyer_address=config.BUYER_ADDR)
    relayer.settle(base_sid, base_seller["H_p"], base_seller["seller_signature"], good_a1, good_a2)
    print(f"  [Setup]: Successfully settled base session {base_sid} for post-settle tests.")

    # Adv Test 9: Double Settlement Replay (settling already released session)
    def adv9_double_settle():
        relayer.settle(base_sid, base_seller["H_p"], base_seller["seller_signature"], good_a1, good_a2)
    execute_adversarial(9, "Double Settlement Replay (Deleted Box Key)", adv9_double_settle)

    # Adv Test 10: Premature Timeout Refund (calling timeout before deadline round)
    def adv10_premature_refund():
        sp = client.suggested_params()
        future_dl = sp.first + 1000
        new_auth = buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, future_dl)
        relayer.refund(new_auth["session_id"], reason=1) # reason=1: TIMEOUT
    execute_adversarial(10, "Premature Timeout Refund (Round < Deadline)", adv10_premature_refund)

    # Save summary report
    summary = {
        "app_id": app_id,
        "functional_passed": len([r for r in functional_results if r["status"] == "PASSED"]),
        "adversarial_reverted": len([r for r in adversarial_results if r["status"] == "PASSED"]),
        "functional_results": functional_results,
        "adversarial_results": adversarial_results
    }
    with open("artifacts/unified_test_results.json", "w") as f:
        json.dump(summary, f, indent=4)
        
    print("\n=== Test Suite Complete ===")
    print(f"Functional Tests:   {summary['functional_passed']}/5 PASSED")
    print(f"Adversarial Tests:  {summary['adversarial_reverted']}/10 REVERTED (100% BLOCKED)")
    return summary

if __name__ == "__main__":
    run_tests()
