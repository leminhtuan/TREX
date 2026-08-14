import os
import sys
import base64
from algosdk import account, mnemonic, transaction, logic
from algosdk.v2client import algod
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "02_clients"))
import config
from dotenv import load_dotenv
load_dotenv()

def get_algod_client(network):
    if network == "testnet":
        return algod.AlgodClient("", "https://testnet-api.algonode.cloud")
    raise ValueError("Invalid network")

def main():
    client = get_algod_client("testnet")
    mnem = os.environ.get("DEPLOYER_MNEMONIC")
    sk = mnemonic.to_private_key(mnem)
    addr = account.address_from_private_key(sk)
    
    import importlib
    importlib.reload(config)
    app_id = config.APP_ID
    app_addr = logic.get_application_address(app_id)
    
    print(f"App ID: {app_id}")
    print(f"App Addr: {app_addr}")
    
    params = client.suggested_params()
    
    # 1. Fund app with 0.5 ALGO
    txn_fund = transaction.PaymentTxn(
        sender=addr,
        sp=params,
        receiver=app_addr,
        amt=500000
    )
    
    # 2. Call opt_in_asa
    from algosdk.abi import Method
    opt_in_method = Method.from_signature("opt_in_asa(asset)void")
    
    app_params = client.suggested_params()
    app_params.flat_fee = True
    app_params.fee = 2000
    
    # The foreign asset is USDC_ASA_ID
    # The ABI argument is the index into foreign_assets array (which is 0)
    txn_app = transaction.ApplicationCallTxn(
        sender=addr,
        sp=app_params,
        index=app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[
            opt_in_method.get_selector(),
            (0).to_bytes(1, "big")  # index 0 in foreign_assets
        ],
        foreign_assets=[config.USDC_ASA_ID]
    )
    
    # Group them
    gid = transaction.calculate_group_id([txn_fund, txn_app])
    txn_fund.group = gid
    txn_app.group = gid
    
    stxn_fund = txn_fund.sign(sk)
    stxn_app = txn_app.sign(sk)
    
    try:
        txid = client.send_transactions([stxn_fund, stxn_app])
        print(f"Opt-in transaction sent: {txid}")
        transaction.wait_for_confirmation(client, txid, 4)
        print("Opt-in successful!")
    except Exception as e:
        print(f"Opt-in failed: {e}")

if __name__ == "__main__":
    main()
