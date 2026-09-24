import os
import sys
import json
import time
import base64
from algosdk import transaction, account, mnemonic, logic
from algosdk.v2client import algod

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../02_clients')))
import config

def compile_program(client, source_code):
    compile_response = client.compile(source_code)
    return compile_response['result'], compile_response['hash']

def deploy():
    client = algod.AlgodClient("", config.ALGONODE_URL)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base_dir, "htlc_escrow_approval.teal"), "r") as f:
        approval_src = f.read()
    with open(os.path.join(base_dir, "htlc_escrow_clear.teal"), "r") as f:
        clear_src = f.read()
        
    app_compiled, _ = compile_program(client, approval_src)
    clear_compiled, _ = compile_program(client, clear_src)
    
    app_bytes = base64.b64decode(app_compiled)
    clear_bytes = base64.b64decode(clear_compiled)
    
    sp = client.suggested_params()
    
    txn = transaction.ApplicationCreateTxn(
        sender=config.DEPLOYER_ADDR,
        sp=sp,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=app_bytes,
        clear_program=clear_bytes,
        global_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
        local_schema=transaction.StateSchema(num_uints=0, num_byte_slices=0)
    )
    
    signed = txn.sign(config.DEPLOYER_SK)
    txid = client.send_transaction(signed)
    res = transaction.wait_for_confirmation(client, txid, 4)
    app_id = res['application-index']
    print(f"Deployed HTLC Escrow App ID: {app_id}")
    
    app_addr = logic.get_application_address(app_id)
    print(f"HTLC Escrow App Address: {app_addr}")
    
    # Fund app with 1 ALGO minimum balance
    print("Funding HTLC App with 1 ALGO...")
    fund_txn = transaction.PaymentTxn(
        sender=config.RELAYER_ADDR,
        sp=sp,
        receiver=app_addr,
        amt=1_000_000
    )
    txid_fund = client.send_transaction(fund_txn.sign(config.RELAYER_SK))
    transaction.wait_for_confirmation(client, txid_fund, 4)
    
    # Opt-in to USDC ASA
    print("Opting in HTLC App to USDC ASA...")
    sp_opt = client.suggested_params()
    sp_opt.fee = 2000
    sp_opt.flat_fee = True
    opt_txn = transaction.ApplicationCallTxn(
        sender=config.DEPLOYER_ADDR,
        sp=sp_opt,
        index=app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"optin_asa"],
        foreign_assets=[config.USDC_ASA_ID]
    )
    txid_opt = client.send_transaction(opt_txn.sign(config.DEPLOYER_SK))
    transaction.wait_for_confirmation(client, txid_opt, 4)
    print("HTLC Escrow deployed and opted-in successfully!")
    
    return app_id

if __name__ == "__main__":
    deploy()
