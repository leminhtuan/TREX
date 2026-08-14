import os
import sys
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

USDC_ASA_ID = 10458941
ALGONODE_URL = "https://testnet-api.algonode.cloud"

def get_account_from_mnemonic(mnem: str):
    sk = mnemonic.to_private_key(mnem)
    addr = account.address_from_private_key(sk)
    return sk, addr

def opt_in_asset(client, sk, asset_id):
    addr = account.address_from_private_key(sk)
    info = client.account_info(addr)
    for asset in info.get("assets", []):
        if asset["asset-id"] == asset_id:
            return f"Already opted in (amount: {asset.get('amount', 0)})"
            
    sp = client.suggested_params()
    txn = transaction.AssetTransferTxn(
        sender=addr,
        sp=sp,
        receiver=addr,
        amt=0,
        index=asset_id
    )
    signed = txn.sign(sk)
    txid = client.send_transaction(signed)
    transaction.wait_for_confirmation(client, txid, 4)
    return f"Opt-in successful (TXID: {txid})"

def check_account_balance(client, addr, asset_id):
    info = client.account_info(addr)
    algo_balance = info.get("amount", 0) / 1_000_000
    usdc_balance = 0
    opted_in = False
    for asset in info.get("assets", []):
        if asset["asset-id"] == asset_id:
            opted_in = True
            usdc_balance = asset.get("amount", 0) / 1_000_000 # USDC standard 6 decimals
            break
    return algo_balance, usdc_balance, opted_in

def main():
    env_path = os.path.join(os.path.dirname(__file__), "..", "01_contracts", ".env")
    load_dotenv(env_path)
    
    client = algod.AlgodClient("", ALGONODE_URL)
    
    accounts = {
        "BUYER": os.environ.get("BUYER_MNEMONIC"),
        "SELLER": os.environ.get("SELLER_MNEMONIC"),
        "RELAYER": os.environ.get("RELAYER_MNEMONIC"),
        "DEPLOYER": os.environ.get("DEPLOYER_MNEMONIC"),
        "ATTESTER_1": os.environ.get("ATTESTER_1_MNEMONIC"),
        "ATTESTER_2": os.environ.get("ATTESTER_2_MNEMONIC"),
        "ATTESTER_3": os.environ.get("ATTESTER_3_MNEMONIC"),
    }
    
    print(f"=== OPT-IN AND CHECK BALANCES FOR USDC ASA ({USDC_ASA_ID}) ===\n")
    
    # We will opt in Buyer, Seller, Relayer (primary transaction actors)
    target_optin = ["BUYER", "SELLER", "RELAYER", "DEPLOYER"]
    
    results = {}
    
    for role, mnem in accounts.items():
        if not mnem:
            print(f"[-] {role}: Mnemonic not found in .env")
            continue
        sk, addr = get_account_from_mnemonic(mnem)
        
        opt_status = "N/A"
        if role in target_optin:
            try:
                opt_status = opt_in_asset(client, sk, USDC_ASA_ID)
            except Exception as e:
                opt_status = f"Opt-in failed: {e}"
                
        algo_bal, usdc_bal, opted_in = check_account_balance(client, addr, USDC_ASA_ID)
        
        results[role] = {
            "address": addr,
            "algo_balance": algo_bal,
            "usdc_balance": usdc_bal,
            "opted_in": opted_in,
            "opt_status": opt_status
        }
        
    print(f"{'Role':<12} | {'Address':<58} | {'ALGO':<8} | {'USDC':<8} | {'Opt-in Status'}")
    print("-" * 120)
    for role, data in results.items():
        print(f"{role:<12} | {data['address']:<58} | {data['algo_balance']:<8.4f} | {data['usdc_balance']:<8.2f} | {data['opt_status']}")
        
if __name__ == "__main__":
    main()
