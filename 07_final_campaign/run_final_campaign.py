import os
import sys
import json
import csv
import time
import base64
from algosdk import encoding, transaction, account, logic
from algosdk.v2client import algod
import hashlib
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, "02_clients"))
sys.path.append(os.path.join(BASE_DIR, "01_contracts"))

import config
from buyer_agent import BuyerAgent
from seller_agent import SellerAgent
from attester import AttesterAgent

algod_client = algod.AlgodClient("", config.ALGONODE_URL)

def deploy_new_contract():
    print("Deploying new contract...")
    with open(os.path.join(BASE_DIR, "01_contracts", "approval.teal"), "r") as f:
        approval_source = f.read()
    with open(os.path.join(BASE_DIR, "01_contracts", "clear.teal"), "r") as f:
        clear_source = f.read()
        
    approval_prog = base64.b64decode(algod_client.compile(approval_source)["result"])
    clear_prog = base64.b64decode(algod_client.compile(clear_source)["result"])
    
    sp = algod_client.suggested_params()
    from algosdk.abi import Method
    create_method = Method.from_signature("create_app(address,address,address,address)void")
    
    txn = transaction.ApplicationCallTxn(
        sender=config.BUYER_ADDR, sp=sp, index=0,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval_prog, clear_program=clear_prog,
        global_schema=transaction.StateSchema(num_uints=3, num_byte_slices=4),
        local_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
        app_args=[create_method.get_selector(), 
                  encoding.decode_address(config.ATTESTER_1_ADDR),
                  encoding.decode_address(config.ATTESTER_2_ADDR),
                  encoding.decode_address(config.ATTESTER_3_ADDR),
                  encoding.decode_address(config.BUYER_ADDR)]
    )
    
    signed_txn = txn.sign(config.BUYER_SK)
    txid = algod_client.send_transaction(signed_txn)
    res = transaction.wait_for_confirmation(algod_client, txid, 4)
    app_id = res["application-index"]
    app_addr = logic.get_application_address(app_id)
    print(f"Contract deployed! App ID: {app_id}, Address: {app_addr}")
    
    print("Funding contract...")
    txn_fund = transaction.PaymentTxn(sender=config.BUYER_ADDR, sp=algod_client.suggested_params(), receiver=app_addr, amt=5_000_000)
    stxn_fund = txn_fund.sign(config.BUYER_SK)
    algod_client.send_transaction(stxn_fund)
    transaction.wait_for_confirmation(algod_client, txn_fund.get_txid(), 4)
    
    print("Opting app into USDC...")
    optin_method = Method.from_signature("opt_in_asa(asset)void")
    sp_optin = algod_client.suggested_params()
    sp_optin.fee = 2000
    sp_optin.flat_fee = True
    txn_optin = transaction.ApplicationCallTxn(
        sender=config.BUYER_ADDR, sp=sp_optin, index=app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[optin_method.get_selector(), (config.USDC_ASA_ID).to_bytes(8, 'big')],
        foreign_assets=[config.USDC_ASA_ID]
    )
    stxn_optin = txn_optin.sign(config.BUYER_SK)
    algod_client.send_transaction(stxn_optin)
    transaction.wait_for_confirmation(algod_client, txn_optin.get_txid(), 4)
    print("Opt-in complete.")
    return app_id, app_addr

def run_campaign():
    app_id = 770852814
    app_addr = "TJ22AIIEYQFXWSQJZQ4KBTBGG2WEVVPCQJEBVJXKFA4V4X2E7IHRW2LZHA"
    
    buyer = BuyerAgent()
    buyer.app_id = app_id; buyer.app_addr = app_addr
    seller = SellerAgent()
    seller.app_id = app_id; seller.app_addr = app_addr
    att1 = AttesterAgent(0, config.ATTESTER_1_SK)
    att1.app_id = app_id; att1.app_addr = app_addr
    att2 = AttesterAgent(1, config.ATTESTER_2_SK)
    att2.app_id = app_id; att2.app_addr = app_addr
    
    results = []
    inv_log = []
    
    from algosdk.abi import Method
    settle_method = Method.from_signature("settle(uint64,byte[32],byte[64],uint8,byte[64],uint8,byte[64],address)void")
    refund_method = Method.from_signature("refund(uint64,uint8,uint8,byte[64],uint8,byte[64],address)void")
    opup_method = Method.from_signature("opup(uint64)void")
    
    def log_inv(msg):
        inv_log.append(msg)
        print(msg)
        
    for i in range(100):
        if i < 40:
            scenario = "Normal Settle"
        elif i < 70:
            scenario = "Attested Fail"
        else:
            scenario = "Timeout Refund"
            
        print(f"\n--- Running Session {i+1}/100: {scenario} ---")
        
        status = algod_client.status()
        current_round = status["last-round"]
        
        # Determine deadline
        if scenario == "Timeout Refund":
            deadline_round = current_round + 3 # Short deadline
        else:
            deadline_round = current_round + 1000 # Long deadline
            
        t0 = time.time()
        
        # AUTHORIZE
        res_auth = buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, deadline_round)
        t1 = time.time()
        
        session_id = res_auth["session_id"]
        nonce = res_auth["nonce"]
        auth_txid = res_auth["tx_id"]
        auth_fee = res_auth["fee"]
        auth_outer_txns = 3 # axfer, pay, app call (wait, authorize in BuyerAgent sends axfer, pay, app call, opup? Let's check. Actually BuyerAgent authorize sends 3 txns usually)
        # Wait, let's look at BuyerAgent.authorize(): axfer, pay, app_call = 3 txns.
        # But BuyerAgent authorize returns fee.
        
        # Verify Active box exists
        buyer_addr_bytes = encoding.decode_address(config.BUYER_ADDR)
        active_box_key = hashlib.new("sha512_256", b"T-REX-ACTIVE-NONCE" + buyer_addr_bytes + nonce.to_bytes(8, "big")).digest()
        spent_box_key = hashlib.new("sha512_256", b"T-REX-SPENT" + app_id.to_bytes(8, "big") + buyer_addr_bytes + nonce.to_bytes(8, "big")).digest()
        
        try:
            algod_client.application_box_by_name(app_id, active_box_key)
            active_exists = True
        except:
            active_exists = False
            
        try:
            algod_client.application_box_by_name(app_id, spent_box_key)
            spent_exists_before = True
        except:
            spent_exists_before = False
            
        if not active_exists: log_inv(f"Violation [{i}]: Active box missing after auth")
        if spent_exists_before: log_inv(f"Violation [{i}]: Spent box exists before terminal")
        
        # TERMINAL TRANSITION
        t2 = time.time()
        term_txid = ""
        term_fee = 0
        term_outer_txns = 0
        term_inner_txns = 2 # USCD and Algo bounty
        
        if scenario == "Normal Settle":
            res_seller = seller.process_request(session_id, res_auth["H_q"], res_auth["H_c"], nonce)
            H_p = res_seller["H_p"]
            seller_sig = res_seller["seller_signature"]
            att1_res = att1.attest(session_id, nonce, res_auth["H_q"], res_auth["H_c"], H_p, deadline_round, 1)
            att2_res = att2.attest(session_id, nonce, res_auth["H_q"], res_auth["H_c"], H_p, deadline_round, 1)
            
            app_params = algod_client.suggested_params()
            app_params.flat_fee = True
            app_params.fee = 11000
            
            app_args = [
                settle_method.get_selector(),
                session_id.to_bytes(8, "big"),
                H_p,
                seller_sig,
                (0).to_bytes(1, "big"),
                att1_res["signature"],
                (1).to_bytes(1, "big"),
                att2_res["signature"],
                encoding.decode_address(config.RELAYER_ADDR)
            ]
            
            nonce_box = (app_id, active_box_key)
            session_box = (app_id, b"session:" + session_id.to_bytes(8, "big"))
            spent_box = (app_id, spent_box_key)
            
            txn_app = transaction.ApplicationCallTxn(
                sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC,
                app_args=app_args, boxes=[session_box, nonce_box, spent_box], foreign_assets=[config.USDC_ASA_ID],
                accounts=[config.SELLER_ADDR, config.RELAYER_ADDR]
            )
            txns = [txn_app]
            for j in range(9):
                txns.append(transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j).to_bytes(8, "big")]))
            
            gid = transaction.calculate_group_id(txns)
            stxns = [t.sign(config.SELLER_SK) for t in txns]
            for t in stxns: t.transaction.group = gid
            stxns = [t.sign(config.SELLER_SK) for t in txns]
            
            txid = algod_client.send_transactions(stxns)
            res = transaction.wait_for_confirmation(algod_client, txid, 4)
            term_txid = txid
            term_fee = 11000
            term_outer_txns = 10
            
        elif scenario == "Attested Fail":
            att1_res = att1.attest(session_id, nonce, res_auth["H_q"], res_auth["H_c"], b'\x00'*32, deadline_round, 0)
            att2_res = att2.attest(session_id, nonce, res_auth["H_q"], res_auth["H_c"], b'\x00'*32, deadline_round, 0)
            
            app_params = algod_client.suggested_params()
            app_params.flat_fee = True
            app_params.fee = 8000
            
            app_args = [
                refund_method.get_selector(),
                session_id.to_bytes(8, "big"),
                (1).to_bytes(1, "big"), # reason ATTESTED_FAIL
                (0).to_bytes(1, "big"),
                att1_res["signature"],
                (1).to_bytes(1, "big"),
                att2_res["signature"],
                encoding.decode_address(config.RELAYER_ADDR)
            ]
            
            nonce_box = (app_id, active_box_key)
            session_box = (app_id, b"session:" + session_id.to_bytes(8, "big"))
            spent_box = (app_id, spent_box_key)
            
            txn_app = transaction.ApplicationCallTxn(
                sender=config.BUYER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC,
                app_args=app_args, boxes=[session_box, nonce_box, spent_box], foreign_assets=[config.USDC_ASA_ID],
                accounts=[config.BUYER_ADDR, config.RELAYER_ADDR]
            )
            txns = [txn_app]
            for j in range(6):
                txns.append(transaction.ApplicationCallTxn(sender=config.BUYER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j).to_bytes(8, "big")]))
                
            gid = transaction.calculate_group_id(txns)
            stxns = [t.sign(config.BUYER_SK) for t in txns]
            for t in stxns: t.transaction.group = gid
            stxns = [t.sign(config.BUYER_SK) for t in txns]
            
            txid = algod_client.send_transactions(stxns)
            res = transaction.wait_for_confirmation(algod_client, txid, 4)
            term_txid = txid
            term_fee = 8000
            term_outer_txns = 7
            
        elif scenario == "Timeout Refund":
            while algod_client.status()["last-round"] <= deadline_round:
                time.sleep(1)
                
            app_params = algod_client.suggested_params()
            app_params.flat_fee = True
            app_params.fee = 4000
            
            app_args = [
                refund_method.get_selector(),
                session_id.to_bytes(8, "big"),
                (0).to_bytes(1, "big"), # reason TIMEOUT
                (0).to_bytes(1, "big"), b'\x00'*64, # Dummy sigs for timeout
                (0).to_bytes(1, "big"), b'\x00'*64,
                encoding.decode_address(config.RELAYER_ADDR)
            ]
            
            nonce_box = (app_id, active_box_key)
            session_box = (app_id, b"session:" + session_id.to_bytes(8, "big"))
            spent_box = (app_id, spent_box_key)
            
            txn_app = transaction.ApplicationCallTxn(
                sender=config.BUYER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC,
                app_args=app_args, boxes=[session_box, nonce_box, spent_box], foreign_assets=[config.USDC_ASA_ID],
                accounts=[config.BUYER_ADDR, config.RELAYER_ADDR]
            )
            txns = [txn_app]
            for j in range(2):
                txns.append(transaction.ApplicationCallTxn(sender=config.BUYER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j).to_bytes(8, "big")]))
                
            gid = transaction.calculate_group_id(txns)
            stxns = [t.sign(config.BUYER_SK) for t in txns]
            for t in stxns: t.transaction.group = gid
            stxns = [t.sign(config.BUYER_SK) for t in txns]
            
            txid = algod_client.send_transactions(stxns)
            res = transaction.wait_for_confirmation(algod_client, txid, 4)
            term_txid = txid
            term_fee = 4000
            term_outer_txns = 3
            
        t3 = time.time()
        final_round = res["confirmed-round"]
        
        # Verify markers
        try:
            algod_client.application_box_by_name(app_id, active_box_key)
            active_exists_after = True
        except:
            active_exists_after = False
            
        try:
            algod_client.application_box_by_name(app_id, spent_box_key)
            spent_exists_after = True
        except:
            spent_exists_after = False
            
        if active_exists_after: log_inv(f"Violation [{i}]: Active box still exists after terminal")
        if not spent_exists_after: log_inv(f"Violation [{i}]: Spent box missing after terminal")
        
        # Record
        row = {
            "session_id": session_id,
            "nonce": nonce,
            "buyer": config.BUYER_ADDR,
            "seller": config.SELLER_ADDR,
            "app_id": app_id,
            "scenario": scenario,
            "auth_txid": auth_txid,
            "term_txid": term_txid,
            "final_state": "RELEASED" if scenario == "Normal Settle" else "REFUNDED",
            "final_round": final_round,
            "auth_latency_s": round(t1 - t0, 3),
            "term_latency_s": round(t3 - t2, 3),
            "e2e_latency_s": round(t3 - t0, 3),
            "auth_outer_txns": 3,
            "term_outer_txns": term_outer_txns,
            "term_inner_txns": 2,
            "auth_fee_microalgo": auth_fee,
            "term_fee_microalgo": term_fee,
            "session_total_fee_microalgo": auth_fee + term_fee,
            "invariant_violations": len(inv_log),
            "spent_marker_present": spent_exists_after
        }
        results.append(row)
        
        csv_path = os.path.join(BASE_DIR, "07_final_campaign", "final_functional_campaign.csv")
        file_exists = os.path.isfile(csv_path)
        with open(csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        
    
        
    with open(os.path.join(BASE_DIR, "07_final_campaign", "invariant_audit.log"), "w") as f:
        if not inv_log:
            f.write("0 INVARIANT VIOLATIONS DETECTED.\n")
        else:
            for l in inv_log: f.write(l + "\n")
            
    os.system("python generate_report.py")
    print("Done generating CSV and log.")

if __name__ == "__main__":
    run_campaign()
