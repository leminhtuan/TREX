import os
import time
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

USDC_ASA_ID = 10458941

def generate_and_save_accounts():
    env_path = "../01_contracts/.env"
    
    # Check existing
    load_dotenv(env_path)
    if os.environ.get("BUYER_MNEMONIC"):
        print("Accounts already exist in .env")
        buyer_sk = mnemonic.to_private_key(os.environ["BUYER_MNEMONIC"])
        seller_sk = mnemonic.to_private_key(os.environ["SELLER_MNEMONIC"])
        relayer_sk = mnemonic.to_private_key(os.environ["RELAYER_MNEMONIC"])
        return buyer_sk, seller_sk, relayer_sk

    print("Generating new accounts...")
    buyer_sk, buyer_addr = account.generate_account()
    seller_sk, seller_addr = account.generate_account()
    relayer_sk, relayer_addr = account.generate_account()
    
    buyer_mn = mnemonic.from_private_key(buyer_sk)
    seller_mn = mnemonic.from_private_key(seller_sk)
    relayer_mn = mnemonic.from_private_key(relayer_sk)
    
    with open(env_path, "a") as f:
        f.write(f'\nBUYER_MNEMONIC="{buyer_mn}"\n')
        f.write(f'SELLER_MNEMONIC="{seller_mn}"\n')
        f.write(f'RELAYER_MNEMONIC="{relayer_mn}"\n')
        
    print("Mnemonics saved to .env")
    return buyer_sk, seller_sk, relayer_sk

def opt_in(client, sk, asset_id):
    addr = account.address_from_private_key(sk)
    
    # Check if already opted in
    info = client.account_info(addr)
    for asset in info.get("assets", []):
        if asset["asset-id"] == asset_id:
            print(f"{addr} already opted in to {asset_id}")
            return
            
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
    print(f"Opting in {addr} to {asset_id}... TXID: {txid}")
    transaction.wait_for_confirmation(client, txid, 4)
    print("Confirmed!")

def main():
    buyer_sk, seller_sk, relayer_sk = generate_and_save_accounts()
    
    buyer_addr = account.address_from_private_key(buyer_sk)
    seller_addr = account.address_from_private_key(seller_sk)
    relayer_addr = account.address_from_private_key(relayer_sk)
    
    print("\n--- NEW ADDRESSES ---")
    print(f"BUYER:   {buyer_addr}")
    print(f"SELLER:  {seller_addr}")
    print(f"RELAYER: {relayer_addr}")
    print("---------------------\n")
    
    print("ACTION REQUIRED:")
    print("1. Fund BUYER with 2 ALGO and at least 10 USDC (Testnet ASA 31566704)")
    print("2. Fund SELLER with 1 ALGO")
    print("3. Fund RELAYER with 1 ALGO")
    print("You can get Testnet ALGO from: https://bank.testnet.algorand.network/")
    print("For USDC, you can swap ALGO on a testnet DEX or ask a faucet.")
    print("\nIMPORTANT: After funding ALGO, we need to Opt-in to USDC.")
    
    input("Press Enter once you have funded ALGO to all 3 accounts...")
    
    client = algod.AlgodClient("", "https://testnet-api.algonode.cloud")
    
    print("\nOpting in to USDC...")
    try:
        opt_in(client, buyer_sk, USDC_ASA_ID)
        opt_in(client, seller_sk, USDC_ASA_ID)
    except Exception as e:
        print(f"Opt-in failed: {e}")
        print("Please ensure accounts are funded with ALGO first!")

if __name__ == "__main__":
    main()
