import os
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv

load_dotenv()

def fund_app():
    # Setup client
    client = algod.AlgodClient("", "https://testnet-api.algonode.cloud")
    
    # Get deployer account
    mnem = os.environ.get("DEPLOYER_MNEMONIC")
    sk = mnemonic.to_private_key(mnem)
    addr = account.address_from_private_key(sk)
    
    # App address
    app_addr = "DMVUKUS2COGO7KFMMMXPRNJHXYRIQZWFSOCL3PJDQ7HWRFQPUB22SHQVXA"
    
    # Build txn: 0.5 ALGO
    sp = client.suggested_params()
    txn = transaction.PaymentTxn(addr, sp, app_addr, 500_000)
    
    # Sign and send
    signed_txn = txn.sign(sk)
    txid = client.send_transaction(signed_txn)
    print(f"Sent 0.5 ALGO to App. TXID: {txid}")
    
    # Wait for confirmation
    transaction.wait_for_confirmation(client, txid, 4)
    print("Funding confirmed!")
    
    # Verify balance
    app_info = client.account_info(app_addr)
    print(f"App Balance: {app_info.get('amount') / 1e6} ALGO")

if __name__ == "__main__":
    fund_app()
