import os
import sys
import json
import base64
import argparse
import datetime
from algosdk import account, mnemonic, util
from algosdk.v2client import algod
from algosdk.transaction import ApplicationCreateTxn, StateSchema
import hashlib
from dotenv import load_dotenv
load_dotenv()

def get_algod_client(network):
    if network == "localnet":
        return algod.AlgodClient("a" * 64, "http://localhost:4001")
    elif network == "testnet":
        # using algonode free tier
        return algod.AlgodClient("", "https://testnet-api.algonode.cloud")
    elif network == "mainnet":
        return algod.AlgodClient("", "https://mainnet-api.algonode.cloud")
    raise ValueError("Invalid network")

def get_deployer_account():
    mnem = os.environ.get("DEPLOYER_MNEMONIC")
    if not mnem:
        raise ValueError("DEPLOYER_MNEMONIC environment variable not set")
    sk = mnemonic.to_private_key(mnem)
    addr = account.address_from_private_key(sk)
    return sk, addr

def get_attester_keys():
    # Helper to get public keys from mnemonic for attesters
    keys = []
    for i in range(1, 4):
        mnem = os.environ.get(f"ATTESTER_{i}_MNEMONIC")
        if not mnem:
            raise ValueError(f"ATTESTER_{i}_MNEMONIC not set")
        # Just getting public key address, then decode to bytes
        addr = account.address_from_private_key(mnemonic.to_private_key(mnem))
        from algosdk.encoding import decode_address
        keys.append(decode_address(addr))
    return keys

def main():
    parser = argparse.ArgumentParser(description="Deploy T-REX Escrow")
    parser.add_argument("--network", choices=["localnet", "testnet", "mainnet"], default="testnet")
    parser.add_argument("--dry-run", action="store_true", help="Do not broadcast transaction")
    args = parser.parse_args()

    is_mainnet = args.network == "mainnet"
    dry_run = args.dry_run or is_mainnet

    if is_mainnet:
        if os.environ.get("ALLOW_MAINNET_DEPLOY") != "true":
            print("ERROR: ALLOW_MAINNET_DEPLOY=true is required for mainnet deployment.")
            sys.exit(1)
        if not args.dry_run:
            conf = input("Type 'DEPLOY_TREX_MAINNET' to confirm mainnet deployment: ")
            if conf != "DEPLOY_TREX_MAINNET":
                print("Confirmation failed. Aborting.")
                sys.exit(1)

    print(f"Deploying to {args.network}...")
    try:
        client = get_algod_client(args.network)
        client.status()
    except Exception as e:
        print(f"Failed to connect to network: {e}")
        sys.exit(1)

    sk, addr = get_deployer_account()
    print(f"Deployer address: {addr}")

    # Check balance
    acc_info = client.account_info(addr)
    balance = acc_info.get("amount", 0)
    print(f"Deployer balance: {balance / 1e6} ALGO")
    
    # Needs at least 1 ALGO (0.5 for deployment, 0.5 for funding app min balance later)
    if balance < 1_000_000:
        print("ERROR: Deployer balance < 1 ALGO. Insufficient funds.")
        sys.exit(1)

    # Check attester keys
    attester_keys = get_attester_keys()
    if len(set(attester_keys)) != 3:
        print("ERROR: Attester keys must be unique.")
        sys.exit(1)
    for k in attester_keys:
        if len(k) != 32:
            print("ERROR: Attester key is not 32 bytes.")
            sys.exit(1)

    # Load TEAL
    with open("approval.teal", "r") as f:
        approval_source = f.read()
    with open("clear.teal", "r") as f:
        clear_source = f.read()

    # Check TEAL version
    if "#pragma version 10" not in approval_source and "#pragma version 11" not in approval_source:
        print("ERROR: TEAL version >= 10 required.")
        sys.exit(1)

    approval_compiled = client.compile(approval_source)
    clear_compiled = client.compile(clear_source)
    
    approval_prog = base64.b64decode(approval_compiled["result"])
    clear_prog = base64.b64decode(clear_compiled["result"])
    
    # Check size < 64KB
    if len(approval_prog) > 65536 or len(clear_prog) > 65536:
        print("ERROR: Compiled program size exceeds 64KB limit.")
        sys.exit(1)
        
    print(f"Approval program size: {len(approval_prog)} bytes")

    sp = client.suggested_params()
    
    # Global state schema: next_id (1 uint), attester_pk_0/1/2 (3 bytes), app_admin (1 bytes), protocol_version (1 uint), usdc_asa_id (1 uint)
    # Total: 3 uints, 4 bytes
    global_schema = StateSchema(num_uints=3, num_byte_slices=4)
    local_schema = StateSchema(num_uints=0, num_byte_slices=0)
    
    # Method args for create_app
    from algosdk.abi import Method
    with open("contract.json", "r") as f:
        contract = json.load(f)
        
    create_method = None
    for m in contract["methods"]:
        if m["name"] == "create_app":
            create_method = Method.undictify(m)
            break
            
    if not create_method:
        print("ERROR: create_app method not found in ABI.")
        sys.exit(1)
        
    from algosdk.encoding import decode_address
    app_args = [
        create_method.get_selector(),
        attester_keys[0],
        attester_keys[1],
        attester_keys[2],
        decode_address(addr) # app_admin
    ]

    txn = ApplicationCreateTxn(
        sender=addr,
        sp=sp,
        on_complete=0,
        approval_program=approval_prog,
        clear_program=clear_prog,
        global_schema=global_schema,
        local_schema=local_schema,
        app_args=app_args,
        extra_pages=1
    )

    signed_txn = txn.sign(sk)
    
    print("\n--- Unsigned Transaction Summary ---")
    print(f"Sender: {txn.sender}")
    print(f"Fee: {txn.fee} microALGO")
    print(f"Global Schema: Uints={global_schema.num_uints}, Bytes={global_schema.num_byte_slices}")
    print("------------------------------------\n")

    if dry_run:
        print("DRY RUN: Transaction not sent.")
        sys.exit(0)

    try:
        txid = client.send_transaction(signed_txn)
        print(f"Transaction sent: {txid}")
        from algosdk.transaction import wait_for_confirmation
        res = wait_for_confirmation(client, txid, 4)
        app_id = res["application-index"]
        print(f"Deployed successfully. App ID: {app_id}")
        
        from algosdk.logic import get_application_address
        from algosdk.transaction import PaymentTxn, ApplicationCallTxn
        app_addr = get_application_address(app_id)
        print(f"Contract App Address: {app_addr}")

        # Fund the contract account with 2 ALGO for MBR and box storage
        print("Funding contract account with 2 ALGO...")
        sp_fund = client.suggested_params()
        txn_fund = PaymentTxn(sender=addr, sp=sp_fund, receiver=app_addr, amt=2_000_000)
        stxn_fund = txn_fund.sign(sk)
        txid_fund = client.send_transaction(stxn_fund)
        wait_for_confirmation(client, txid_fund, 4)
        print("Contract account funded successfully.")

        # Opt in to USDC ASA
        print("Opting contract into USDC ASA (ID: 10458941)...")
        optin_method = None
        for m in contract["methods"]:
            if m["name"] == "opt_in_asa":
                optin_method = Method.undictify(m)
                break
        
        sp_optin = client.suggested_params()
        sp_optin.fee = 2000
        sp_optin.flat_fee = True
        usdc_id = 10458941
        txn_optin = ApplicationCallTxn(
            sender=addr, sp=sp_optin, index=app_id,
            on_complete=0,
            app_args=[optin_method.get_selector(), usdc_id.to_bytes(8, 'big')],
            foreign_assets=[usdc_id]
        )
        stxn_optin = txn_optin.sign(sk)
        txid_optin = client.send_transaction(stxn_optin)
        wait_for_confirmation(client, txid_optin, 4)
        print("Contract opted into USDC ASA successfully.")
        
        # Save artifacts
        os.makedirs("../artifacts", exist_ok=True)
        with open("../artifacts/deploy_tx_id.txt", "w") as f:
            f.write(txid)
        with open("../artifacts/contract_app_id_testnet.txt", "w") as f:
            f.write(str(app_id))
            
        with open("trex_escrow.py", "rb") as f:
            source_hash = hashlib.sha256(f.read()).hexdigest()
            
        manifest = {
            "timestamp_utc": datetime.datetime.utcnow().isoformat(),
            "network": args.network,
            "app_id": app_id,
            "app_address": app_addr,
            "deploy_tx_id": txid,
            "source_sha256": source_hash,
            "teal_sha256": hashlib.sha256(approval_prog).hexdigest(),
            "python_version": sys.version,
            "usdc_asa_id": usdc_id
        }
        with open("../artifacts/contract_build_manifest.json", "w") as f:
            json.dump(manifest, f, indent=4)
            
        print("Manifest saved to artifacts/contract_build_manifest.json")
    except Exception as e:
        print(f"Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
