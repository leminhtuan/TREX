import os
import sys
import json
import csv
import time
import base64
import random
import struct
from algosdk import encoding, transaction, logic
from algosdk.v2client import algod
import hashlib
from nacl.signing import SigningKey

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, "02_clients"))
sys.path.append(os.path.join(BASE_DIR, "01_contracts"))

import config
from buyer_agent import BuyerAgent
from seller_agent import SellerAgent
from attester import AttesterAgent
from algosdk.abi import Method

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
    print(f"Contract deployed! App ID: {app_id}")
    
    sp_fund = algod_client.suggested_params()
    txn_fund = transaction.PaymentTxn(sender=config.RELAYER_ADDR, sp=sp_fund, receiver=app_addr, amt=1_500_000)
    stxn_fund = txn_fund.sign(config.RELAYER_SK)
    algod_client.send_transaction(stxn_fund)
    transaction.wait_for_confirmation(algod_client, txn_fund.get_txid(), 4)
    
    sp_optin = algod_client.suggested_params()
    sp_optin.fee = 2000
    sp_optin.flat_fee = True
    optin_method = Method.from_signature("opt_in_asa(asset)void")
    txn_optin = transaction.ApplicationCallTxn(
        sender=config.BUYER_ADDR, sp=sp_optin, index=app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[optin_method.get_selector(), (config.USDC_ASA_ID).to_bytes(8, 'big')],
        foreign_assets=[config.USDC_ASA_ID]
    )
    stxn_optin = txn_optin.sign(config.BUYER_SK)
    algod_client.send_transaction(stxn_optin)
    transaction.wait_for_confirmation(algod_client, txn_optin.get_txid(), 4)
    return app_id, app_addr

# Option to reuse or deploy new contract
override_id = os.environ.get("TREX_APP_ID")
if override_id:
    app_id = int(override_id)
    app_addr = logic.get_application_address(app_id)
    print(f"Reusing existing contract App ID: {app_id}")
else:
    app_id, app_addr = deploy_new_contract()

buyer = BuyerAgent(); buyer.app_id = app_id; buyer.app_addr = app_addr
seller = SellerAgent(); seller.app_id = app_id; seller.app_addr = app_addr
att1 = AttesterAgent(0, config.ATTESTER_1_SK); att1.app_id = app_id; att1.app_addr = app_addr
att2 = AttesterAgent(1, config.ATTESTER_2_SK); att2.app_id = app_id; att2.app_addr = app_addr

settle_method = Method.from_signature("settle(uint64,address,byte[32],byte[64],uint8,byte[64],uint8,byte[64],address)void")
refund_method = Method.from_signature("refund(uint64,address,uint8,uint8,byte[64],uint8,byte[64],address)void")
opup_method = Method.from_signature("opup(uint64)void")

results = []
buyer_addr_bytes = encoding.decode_address(config.BUYER_ADDR)
chain_hash_bytes = base64.b64decode(algod_client.suggested_params().gh)

def run_test(attack_id, attack_class, expected, test_func):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            test_func()
            print(f"FAILED (Exploit Successful): {attack_class}")
            results.append({
                "attack_id": attack_id, "attack_class": attack_class, "final_app_id": app_id,
                "session_id": 0, "nonce": 0, "expected_rejection": expected,
                "actual_result": "SUCCESS", "revert_reason": "NONE"
            })
            return
        except Exception as e:
            reason = str(e)
            if "logic eval error" in reason or "already in ledger" in reason or "box" in reason or "assert" in reason:
                actual = "REVERTED"
                msg = reason.split("logic eval error:")[-1].strip() if "logic eval error" in reason else reason
                results.append({
                    "attack_id": attack_id, "attack_class": attack_class, "final_app_id": app_id,
                    "session_id": getattr(test_func, 'session_id', 0), "nonce": getattr(test_func, 'nonce', 0),
                    "expected_rejection": expected, "actual_result": actual, "revert_reason": msg
                })
                return
            elif attempt < max_retries - 1 and ("10054" in reason or "ConnectionResetError" in reason or "RemoteDisconnected" in reason or "timeout" in reason.lower()):
                time.sleep(0.5)
                continue
            else:
                actual = "ERROR"
                msg = reason
                results.append({
                    "attack_id": attack_id, "attack_class": attack_class, "final_app_id": app_id,
                    "session_id": getattr(test_func, 'session_id', 0), "nonce": getattr(test_func, 'nonce', 0),
                    "expected_rejection": expected, "actual_result": actual, "revert_reason": msg
                })
                return

print("Starting Adversarial Matrix...")

# Setup sessions
status = algod_client.status()
cr = status["last-round"]
res_normal = buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, cr + 1000)

# Settle the normal session
res_seller = seller.process_request(res_normal["session_id"], res_normal["H_q"], res_normal["H_c"], res_normal["nonce"], buyer_address=config.BUYER_ADDR)
att1_res = att1.attest(res_normal["session_id"], res_normal["nonce"], res_normal["H_q"], res_normal["H_c"], res_seller["H_p"], cr+1000, 1, buyer_address=config.BUYER_ADDR)
att2_res = att2.attest(res_normal["session_id"], res_normal["nonce"], res_normal["H_q"], res_normal["H_c"], res_seller["H_p"], cr+1000, 1, buyer_address=config.BUYER_ADDR)

app_params = algod_client.suggested_params()
app_params.flat_fee = True
app_params.fee = 11000
nonce_box = (app_id, hashlib.new('sha512_256', b'T-REX-ACTIVE-NONCE' + buyer_addr_bytes + res_normal['nonce'].to_bytes(8, 'big')).digest())
session_box = (app_id, b'session:' + res_normal['session_id'].to_bytes(8, 'big'))
spent_box = (app_id, hashlib.new('sha512_256', b'T-REX-SPENT' + app_id.to_bytes(8, 'big') + buyer_addr_bytes + res_normal['nonce'].to_bytes(8, 'big')).digest())

app_args_settle = [
    settle_method.get_selector(),
    res_normal["session_id"].to_bytes(8, "big"),
    buyer_addr_bytes,
    res_seller["H_p"],
    res_seller["seller_signature"],
    (0).to_bytes(1, "big"), att1_res["signature"],
    (1).to_bytes(1, "big"), att2_res["signature"],
    encoding.decode_address(config.RELAYER_ADDR)
]
txn_app = transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=app_args_settle, boxes=[session_box, nonce_box, spent_box], foreign_assets=[config.USDC_ASA_ID], accounts=[config.SELLER_ADDR, config.RELAYER_ADDR])
txns = [txn_app]
for j in range(9): txns.append(transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j).to_bytes(8, "big")]))
gid = transaction.calculate_group_id(txns)
for t in txns: t.group = gid
stxns = [t.sign(config.SELLER_SK) for t in txns]
txid = algod_client.send_transactions(stxns)
transaction.wait_for_confirmation(algod_client, txid, 4)

# Setup Refunded Session
res_refund = buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, cr + 1000)
att1_fail = att1.attest(res_refund["session_id"], res_refund["nonce"], res_refund["H_q"], res_refund["H_c"], b'\x00'*32, cr+1000, 0, buyer_address=config.BUYER_ADDR)
att2_fail = att2.attest(res_refund["session_id"], res_refund["nonce"], res_refund["H_q"], res_refund["H_c"], b'\x00'*32, cr+1000, 0, buyer_address=config.BUYER_ADDR)

app_params.fee = 8000
nonce_box2 = (app_id, hashlib.new('sha512_256', b'T-REX-ACTIVE-NONCE' + buyer_addr_bytes + res_refund['nonce'].to_bytes(8, 'big')).digest())
session_box2 = (app_id, b'session:' + res_refund['session_id'].to_bytes(8, 'big'))
spent_box2 = (app_id, hashlib.new('sha512_256', b'T-REX-SPENT' + app_id.to_bytes(8, 'big') + buyer_addr_bytes + res_refund['nonce'].to_bytes(8, 'big')).digest())
app_args_refund = [
    refund_method.get_selector(),
    res_refund["session_id"].to_bytes(8, "big"),
    buyer_addr_bytes,
    (1).to_bytes(1, "big"), # reason
    (0).to_bytes(1, "big"), att1_fail["signature"],
    (1).to_bytes(1, "big"), att2_fail["signature"],
    encoding.decode_address(config.RELAYER_ADDR)
]
txn_app2 = transaction.ApplicationCallTxn(sender=config.BUYER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=app_args_refund, boxes=[session_box2, nonce_box2, spent_box2], foreign_assets=[config.USDC_ASA_ID], accounts=[config.BUYER_ADDR, config.RELAYER_ADDR])
txns2 = [txn_app2]
for j in range(6): txns2.append(transaction.ApplicationCallTxn(sender=config.BUYER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j).to_bytes(8, "big")]))
gid2 = transaction.calculate_group_id(txns2)
for t in txns2: t.group = gid2
stxns2 = [t.sign(config.BUYER_SK) for t in txns2]
txid2 = algod_client.send_transactions(stxns2)
transaction.wait_for_confirmation(algod_client, txid2, 4)

# Setup Active Session
print("Setting up active...")
res_active = buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, cr + 1000)
print("Active setup done!")

a_id = 0

# Attack 1: Replay Auth after Released
print("Running Attack 1: Replay Auth (Released)...")
for i in range(20):
    a_id += 1
    def att1_func():
        buyer.nonce_override = res_normal["nonce"]
        buyer.note_override = os.urandom(16)
        buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, cr+1000)
    att1_func.nonce = res_normal["nonce"]; att1_func.session_id = res_normal["session_id"]
    run_test(a_id, "Replay Auth (Released)", "Assert SPENT marker", att1_func)
buyer.nonce_override = None; buyer.note_override = None

# Attack 2: Replay Auth after Refunded
print("Running Attack 2: Replay Auth (Refunded)...")
for i in range(20):
    a_id += 1
    def att2_func():
        buyer.nonce_override = res_refund["nonce"]
        buyer.note_override = os.urandom(16)
        buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, cr+1000)
    att2_func.nonce = res_refund["nonce"]; att2_func.session_id = res_refund["session_id"]
    run_test(a_id, "Replay Auth (Refunded)", "Assert SPENT marker", att2_func)
buyer.nonce_override = None; buyer.note_override = None

# Attack 3: Duplicate terminal group
print("Running Attack 3: Duplicate Terminal Group...")
for i in range(20):
    a_id += 1
    def att3_func():
        app_params.fee = 11000
        txn_app = transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=app_args_settle, boxes=[session_box, nonce_box, spent_box], foreign_assets=[config.USDC_ASA_ID], accounts=[config.SELLER_ADDR, config.RELAYER_ADDR], note=os.urandom(16))
        txns = [txn_app]
        for j in range(9): txns.append(transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j+100).to_bytes(8, "big")]))
        gid = transaction.calculate_group_id(txns)
        for t in txns: t.group = gid
        stxns = [t.sign(config.SELLER_SK) for t in txns]
        algod_client.send_transactions(stxns)
    att3_func.nonce = res_normal["nonce"]; att3_func.session_id = res_normal["session_id"]
    run_test(a_id, "Duplicate Terminal Group", "Assert ACTIVE marker", att3_func)

# Attack 4: Concurrent duplicate nonce
print("Running Attack 4: Concurrent Auth Duplicate...")
for i in range(20):
    a_id += 1
    def att4_func():
        buyer.nonce_override = res_active["nonce"]
        buyer.note_override = os.urandom(16)
        buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, cr+1000)
    att4_func.nonce = res_active["nonce"]; att4_func.session_id = res_active["session_id"]
    run_test(a_id, "Concurrent Auth Duplicate", "ACTIVE box exists", att4_func)
buyer.nonce_override = None; buyer.note_override = None

# Attack 5: Payload tampering (H_p)
print("Running Attack 5: Payload Tampering (H_p)...")
res_b = buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, cr + 1000)
res_s = seller.process_request(res_b["session_id"], res_b["H_q"], res_b["H_c"], res_b["nonce"], buyer_address=config.BUYER_ADDR)
att_r1 = att1.attest(res_b["session_id"], res_b["nonce"], res_b["H_q"], res_b["H_c"], res_s["H_p"], cr+1000, 1, buyer_address=config.BUYER_ADDR)
att_r2 = att2.attest(res_b["session_id"], res_b["nonce"], res_b["H_q"], res_b["H_c"], res_s["H_p"], cr+1000, 1, buyer_address=config.BUYER_ADDR)
for i in range(20):
    a_id += 1
    def att5_func():
        bad_H_p = os.urandom(32)
        app_args = [settle_method.get_selector(), res_b["session_id"].to_bytes(8, "big"), buyer_addr_bytes, bad_H_p, res_s["seller_signature"], (0).to_bytes(1, "big"), att_r1["signature"], (1).to_bytes(1, "big"), att_r2["signature"], encoding.decode_address(config.RELAYER_ADDR)]
        sb = (app_id, b'session:' + res_b['session_id'].to_bytes(8, 'big'))
        nb = (app_id, hashlib.new('sha512_256', b'T-REX-ACTIVE-NONCE' + buyer_addr_bytes + res_b['nonce'].to_bytes(8, 'big')).digest())
        spb = (app_id, hashlib.new('sha512_256', b'T-REX-SPENT' + app_id.to_bytes(8, 'big') + buyer_addr_bytes + res_b['nonce'].to_bytes(8, 'big')).digest())
        txn = transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=app_args, boxes=[sb, nb, spb], foreign_assets=[config.USDC_ASA_ID], accounts=[config.SELLER_ADDR, config.RELAYER_ADDR])
        txns = [txn]
        for j in range(9): txns.append(transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j+200+i).to_bytes(8, "big")]))
        gid = transaction.calculate_group_id(txns)
        for t in txns: t.group = gid
        stxns = [t.sign(config.SELLER_SK) for t in txns]
        algod_client.send_transactions(stxns)
    att5_func.nonce = res_b["nonce"]; att5_func.session_id = res_b["session_id"]
    run_test(a_id, "Payload Tampering (H_p)", "ed25519verify_bare fail", att5_func)

# Attack 6: Bad Attester Signature
print("Running Attack 6: Bad Attester Signature...")
for i in range(20):
    a_id += 1
    def att6_func():
        bad_sig = os.urandom(64)
        app_args = [settle_method.get_selector(), res_b["session_id"].to_bytes(8, "big"), buyer_addr_bytes, res_s["H_p"], res_s["seller_signature"], (0).to_bytes(1, "big"), bad_sig, (1).to_bytes(1, "big"), att_r2["signature"], encoding.decode_address(config.RELAYER_ADDR)]
        sb = (app_id, b'session:' + res_b['session_id'].to_bytes(8, 'big'))
        nb = (app_id, hashlib.new('sha512_256', b'T-REX-ACTIVE-NONCE' + buyer_addr_bytes + res_b['nonce'].to_bytes(8, 'big')).digest())
        spb = (app_id, hashlib.new('sha512_256', b'T-REX-SPENT' + app_id.to_bytes(8, 'big') + buyer_addr_bytes + res_b['nonce'].to_bytes(8, 'big')).digest())
        txn = transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=app_args, boxes=[sb, nb, spb], foreign_assets=[config.USDC_ASA_ID], accounts=[config.SELLER_ADDR, config.RELAYER_ADDR])
        txns = [txn]
        for j in range(9): txns.append(transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j+300+i).to_bytes(8, "big")]))
        gid = transaction.calculate_group_id(txns)
        for t in txns: t.group = gid
        stxns = [t.sign(config.SELLER_SK) for t in txns]
        algod_client.send_transactions(stxns)
    att6_func.nonce = res_b["nonce"]; att6_func.session_id = res_b["session_id"]
    run_test(a_id, "Bad Attester Signature", "ed25519verify_bare fail", att6_func)
    
# Attack 7: Deadline tampering (Attester signs bad r_dead)
print("Running Attack 7: Deadline Tampering...")
for i in range(20):
    a_id += 1
    def att7_func():
        bad_r_dead = cr + 9999
        # Malicious attester creates sig over bad r_dead
        msg = (
            b"T-REX-ATT" +
            struct.pack(">Q", app_id) +
            chain_hash_bytes +
            buyer_addr_bytes +
            struct.pack(">Q", res_b["session_id"]) +
            res_b["H_q"] +
            res_b["H_c"] +
            res_s["H_p"] +
            struct.pack(">B", 1) +
            struct.pack(">Q", bad_r_dead) +
            struct.pack(">Q", res_b["nonce"])
        )
        key = SigningKey(base64.b64decode(config.ATTESTER_1_SK)[:32])
        bad_sig = key.sign(msg).signature
        app_args = [settle_method.get_selector(), res_b["session_id"].to_bytes(8, "big"), buyer_addr_bytes, res_s["H_p"], res_s["seller_signature"], (0).to_bytes(1, "big"), bad_sig, (1).to_bytes(1, "big"), att_r2["signature"], encoding.decode_address(config.RELAYER_ADDR)]
        sb = (app_id, b'session:' + res_b['session_id'].to_bytes(8, 'big'))
        nb = (app_id, hashlib.new('sha512_256', b'T-REX-ACTIVE-NONCE' + buyer_addr_bytes + res_b['nonce'].to_bytes(8, 'big')).digest())
        spb = (app_id, hashlib.new('sha512_256', b'T-REX-SPENT' + app_id.to_bytes(8, 'big') + buyer_addr_bytes + res_b['nonce'].to_bytes(8, 'big')).digest())
        txn = transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=app_args, boxes=[sb, nb, spb], foreign_assets=[config.USDC_ASA_ID], accounts=[config.SELLER_ADDR, config.RELAYER_ADDR])
        txns = [txn]
        for j in range(9): txns.append(transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j+400+i).to_bytes(8, "big")]))
        gid = transaction.calculate_group_id(txns)
        for t in txns: t.group = gid
        stxns = [t.sign(config.SELLER_SK) for t in txns]
        algod_client.send_transactions(stxns)
    att7_func.nonce = res_b["nonce"]; att7_func.session_id = res_b["session_id"]
    run_test(a_id, "Deadline Tampering", "ed25519verify_bare fail", att7_func)

# Attack 8: Cross-User Replay
print("Running Attack 8: Cross-User Replay...")
# Buyer A authorizes session
res_a_user = buyer.authorize(config.SELLER_ADDR, 100_000, 10_000, cr + 1000)
res_s_user = seller.process_request(res_a_user["session_id"], res_a_user["H_q"], res_a_user["H_c"], res_a_user["nonce"], buyer_address=config.BUYER_ADDR)
att1_s_user = att1.attest(res_a_user["session_id"], res_a_user["nonce"], res_a_user["H_q"], res_a_user["H_c"], res_s_user["H_p"], cr+1000, 1, buyer_address=config.BUYER_ADDR)
att2_s_user = att2.attest(res_a_user["session_id"], res_a_user["nonce"], res_a_user["H_q"], res_a_user["H_c"], res_s_user["H_p"], cr+1000, 1, buyer_address=config.BUYER_ADDR)

# Buyer B authorizes session
buyer_b = BuyerAgent(); buyer_b.app_id = app_id; buyer_b.app_addr = app_addr
buyer_b.sk = config.DEPLOYER_SK; buyer_b.addr = config.DEPLOYER_ADDR
buyer_b_bytes = encoding.decode_address(config.DEPLOYER_ADDR)
res_b_user = buyer_b.authorize(config.SELLER_ADDR, 100_000, 10_000, cr + 1000)

session_box_ub = (app_id, b'session:' + res_b_user['session_id'].to_bytes(8, 'big'))
nonce_box_ub = (app_id, hashlib.new('sha512_256', b'T-REX-ACTIVE-NONCE' + buyer_b_bytes + res_b_user['nonce'].to_bytes(8, 'big')).digest())
spent_box_ub = (app_id, hashlib.new('sha512_256', b'T-REX-SPENT' + app_id.to_bytes(8, 'big') + buyer_b_bytes + res_b_user['nonce'].to_bytes(8, 'big')).digest())

for i in range(20):
    a_id += 1
    # 10 attempts passing buyer_address = Buyer A (fails Assert(buyer_address == session.buyer))
    # 10 attempts passing buyer_address = Buyer B with Buyer A's signatures (fails ed25519verify_bare)
    pass_buyer_a = (i < 10)
    def att8_func():
        target_buyer = buyer_addr_bytes if pass_buyer_a else buyer_b_bytes
        app_args = [
            settle_method.get_selector(),
            res_b_user["session_id"].to_bytes(8, "big"),
            target_buyer,
            res_s_user["H_p"],
            res_s_user["seller_signature"],
            (0).to_bytes(1, "big"), att1_s_user["signature"],
            (1).to_bytes(1, "big"), att2_s_user["signature"],
            encoding.decode_address(config.RELAYER_ADDR)
        ]
        txn = transaction.ApplicationCallTxn(
            sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC,
            app_args=app_args, boxes=[session_box_ub, nonce_box_ub, spent_box_ub],
            foreign_assets=[config.USDC_ASA_ID], accounts=[config.SELLER_ADDR, config.RELAYER_ADDR],
            note=os.urandom(16)
        )
        txns = [txn]
        for j in range(9): txns.append(transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j+500+i).to_bytes(8, "big")]))
        gid = transaction.calculate_group_id(txns)
        for t in txns: t.group = gid
        stxns = [t.sign(config.SELLER_SK) for t in txns]
        algod_client.send_transactions(stxns)
    att8_func.nonce = res_b_user["nonce"]; att8_func.session_id = res_b_user["session_id"]
    exp = "Assert buyer_address == session.buyer" if pass_buyer_a else "ed25519verify_bare (buyer binding mismatch)"
    run_test(a_id, "Cross-User Replay", exp, att8_func)

# Attack 9: Cross-Instance Replay
print("Running Attack 9: Cross-Instance Replay...")
# Create valid signatures bound to alternative App ID X (e.g. 769453473 or app_id + 99999)
alt_app_id = app_id + 99999
seller_alt = SellerAgent(); seller_alt.app_id = alt_app_id; seller_alt.app_addr = app_addr
att1_alt = AttesterAgent(0, config.ATTESTER_1_SK); att1_alt.app_id = alt_app_id; att1_alt.app_addr = app_addr
att2_alt = AttesterAgent(1, config.ATTESTER_2_SK); att2_alt.app_id = alt_app_id; att2_alt.app_addr = app_addr

# Sign for alternative app ID
res_s_alt = seller_alt.process_request(res_a_user["session_id"], res_a_user["H_q"], res_a_user["H_c"], res_a_user["nonce"], buyer_address=config.BUYER_ADDR)
att1_s_alt = att1_alt.attest(res_a_user["session_id"], res_a_user["nonce"], res_a_user["H_q"], res_a_user["H_c"], res_s_alt["H_p"], cr+1000, 1, buyer_address=config.BUYER_ADDR)
att2_s_alt = att2_alt.attest(res_a_user["session_id"], res_a_user["nonce"], res_a_user["H_q"], res_a_user["H_c"], res_s_alt["H_p"], cr+1000, 1, buyer_address=config.BUYER_ADDR)

session_box_ua = (app_id, b'session:' + res_a_user['session_id'].to_bytes(8, 'big'))
nonce_box_ua = (app_id, hashlib.new('sha512_256', b'T-REX-ACTIVE-NONCE' + buyer_addr_bytes + res_a_user['nonce'].to_bytes(8, 'big')).digest())
spent_box_ua = (app_id, hashlib.new('sha512_256', b'T-REX-SPENT' + app_id.to_bytes(8, 'big') + buyer_addr_bytes + res_a_user['nonce'].to_bytes(8, 'big')).digest())

for i in range(20):
    a_id += 1
    def att9_func():
        app_args = [
            settle_method.get_selector(),
            res_a_user["session_id"].to_bytes(8, "big"),
            buyer_addr_bytes,
            res_s_alt["H_p"],
            res_s_alt["seller_signature"], # Contains alt_app_id
            (0).to_bytes(1, "big"), att1_s_alt["signature"], # Contains alt_app_id
            (1).to_bytes(1, "big"), att2_s_alt["signature"],
            encoding.decode_address(config.RELAYER_ADDR)
        ]
        txn = transaction.ApplicationCallTxn(
            sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC,
            app_args=app_args, boxes=[session_box_ua, nonce_box_ua, spent_box_ua],
            foreign_assets=[config.USDC_ASA_ID], accounts=[config.SELLER_ADDR, config.RELAYER_ADDR],
            note=os.urandom(16)
        )
        txns = [txn]
        for j in range(9): txns.append(transaction.ApplicationCallTxn(sender=config.SELLER_ADDR, sp=app_params, index=app_id, on_complete=transaction.OnComplete.NoOpOC, app_args=[opup_method.get_selector(), (j+600+i).to_bytes(8, "big")]))
        gid = transaction.calculate_group_id(txns)
        for t in txns: t.group = gid
        stxns = [t.sign(config.SELLER_SK) for t in txns]
        algod_client.send_transactions(stxns)
    att9_func.nonce = res_a_user["nonce"]; att9_func.session_id = res_a_user["session_id"]
    run_test(a_id, "Cross-Instance Replay", "ed25519verify_bare (App ID binding mismatch)", att9_func)

csv_path = os.path.join(BASE_DIR, "08_adversarial_campaign", "adversarial_security_matrix.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=results[0].keys())
    w.writeheader()
    for r in results: w.writerow(r)

print(f"Done generating Adversarial Matrix. Total attacks: {len(results)}")
