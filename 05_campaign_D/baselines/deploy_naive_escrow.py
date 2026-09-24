import os
import sys
import json
import time
from algosdk import transaction, account, mnemonic
from algosdk.v2client import algod

sys.path.insert(0, os.path.abspath('../../02_clients'))
import config

def compile_program(client, source_code):
    compile_response = client.compile(source_code)
    return compile_response['result'], compile_response['hash']

def deploy():
    client = algod.AlgodClient("", config.ALGONODE_URL)
    
    with open("naive_escrow_approval.teal", "r") as f:
        approval_src = f.read()
    with open("naive_escrow_clear.teal", "r") as f:
        clear_src = f.read()
        
    app_compiled, _ = compile_program(client, approval_src)
    clear_compiled, _ = compile_program(client, clear_src)
    
    import base64
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
    print(f"Deployed Naive Escrow App ID: {app_id}")
    
    from algosdk import logic
    app_addr = logic.get_application_address(app_id)
    
    # Fund app
    print("Funding App...")
    fund_txn = transaction.PaymentTxn(
        sender=config.RELAYER_ADDR,
        sp=sp,
        receiver=app_addr,
        amt=1_000_000 # 1 ALGO
    )
    client.send_transaction(fund_txn.sign(config.RELAYER_SK))
    time.sleep(2)
    
    # Opt-in to USDC
    print("Opting in to USDC...")
    sp.fee = 2000
    sp.flat_fee = True
    optin_txn = transaction.ApplicationCallTxn(
        sender=config.DEPLOYER_ADDR,
        sp=sp,
        index=app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"optin_asa"],
        foreign_assets=[config.USDC_ASA_ID]
    )
    signed_optin = optin_txn.sign(config.DEPLOYER_SK)
    txid2 = client.send_transaction(signed_optin)
    transaction.wait_for_confirmation(client, txid2, 4)
    print("Opt-in successful!")
    
    # Update manifest
    manifest_path = "../manifest/campaign_D_manifest.json"
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    manifest["naive_escrow_app_id"] = app_id
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=4)
        
    print(f"Manifest updated with naive_escrow_app_id: {app_id}")

if __name__ == '__main__':
    deploy()
