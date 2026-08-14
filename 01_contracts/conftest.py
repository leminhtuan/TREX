import pytest
import algokit_utils
from algosdk import account, atomic_transaction_composer, transaction
import pyteal
from algosdk.v2client.algod import AlgodClient
from algokit_utils.network_clients import get_algod_client, get_default_localnet_config
from algokit_utils.account import get_account, get_dispenser_account
from trex_escrow import get_router, USDC_ASA_ID
import json
import base64

@pytest.fixture(scope="session")
def algod_client():
    return get_algod_client(get_default_localnet_config("algod"))

@pytest.fixture(scope="session")
def localnet():
    # Implicitly relies on algokit localnet being running
    return get_algod_client(get_default_localnet_config("algod"))

@pytest.fixture(scope="session")
def dispenser(localnet):
    return get_dispenser_account(localnet)

@pytest.fixture(scope="function")
def deployer_account(localnet, dispenser):
    acct = get_account(localnet, "deployer", fund_with_algo_amount=100)
    return acct

@pytest.fixture(scope="session")
def usdc_id(algod_client, dispenser):
    # Create mock USDC asset
    sp = algod_client.suggested_params()
    txn = transaction.AssetConfigTxn(
        sender=dispenser.address,
        sp=sp,
        total=1000000000,
        default_frozen=False,
        unit_name="USDC",
        asset_name="USDC",
        manager=dispenser.address,
        reserve=dispenser.address,
        freeze=dispenser.address,
        clawback=dispenser.address,
        url="",
        decimals=6,
    )
    signed_txn = txn.sign(dispenser.private_key)
    txid = algod_client.send_transaction(signed_txn)
    result = transaction.wait_for_confirmation(algod_client, txid, 4)
    asset_id = result["asset-index"]
    return asset_id

@pytest.fixture(scope="function")
def buyer_account(localnet, dispenser, usdc_id):
    buyer = get_account(localnet, "buyer", fund_with_algo_amount=10)
    # Opt-in to USDC
    sp = localnet.suggested_params()
    optin_txn = transaction.AssetOptInTxn(buyer.address, sp, usdc_id)
    signed_optin = optin_txn.sign(buyer.private_key)
    txid = localnet.send_transaction(signed_optin)
    transaction.wait_for_confirmation(localnet, txid, 4)
    
    # Fund with USDC
    xfer_txn = transaction.AssetTransferTxn(dispenser.address, sp, buyer.address, 100000000, usdc_id)
    signed_xfer = xfer_txn.sign(dispenser.private_key)
    localnet.send_transaction(signed_xfer)
    return buyer

@pytest.fixture(scope="function")
def seller_account(localnet):
    return get_account(localnet, "seller", fund_with_algo_amount=5)

@pytest.fixture(scope="function")
def attester_accounts(localnet):
    a1 = get_account(localnet, "attester1", fund_with_algo_amount=5)
    a2 = get_account(localnet, "attester2", fund_with_algo_amount=5)
    a3 = get_account(localnet, "attester3", fund_with_algo_amount=5)
    return [a1, a2, a3]

@pytest.fixture(scope="function")
def relayer_account(localnet):
    return get_account(localnet, "relayer", fund_with_algo_amount=5)

@pytest.fixture(scope="function")
def deployed_app(localnet, deployer_account, attester_accounts, usdc_id):
    router = get_router()
    approval, clear, contract = router.compile_program(version=8, assemble_constants=True, optimize=None)
    
    # Compile
    app_res = localnet.compile(approval)
    approval_bytes = base64.b64decode(app_res['result'])
    clear_res = localnet.compile(clear)
    clear_bytes = base64.b64decode(clear_res['result'])
    
    sp = localnet.suggested_params()
    
    # Deploy
    create_txn = transaction.ApplicationCreateTxn(
        deployer_account.address,
        sp,
        transaction.OnComplete.NoOpOC,
        approval_bytes,
        clear_bytes,
        GlobalStateSchema=transaction.StateSchema(num_uints=2, num_byte_slices=5),
        LocalStateSchema=transaction.StateSchema(num_uints=0, num_byte_slices=0),
        app_args=[
            attester_accounts[0].public_key_bytes(),
            attester_accounts[1].public_key_bytes(),
            attester_accounts[2].public_key_bytes(),
            deployer_account.public_key_bytes()
        ]
    )
    signed = create_txn.sign(deployer_account.private_key)
    txid = localnet.send_transaction(signed)
    res = transaction.wait_for_confirmation(localnet, txid, 4)
    app_id = res['application-index']
    app_addr = transaction.logic.get_application_address(app_id)
    
    # Fund app
    fund = transaction.PaymentTxn(deployer_account.address, sp, app_addr, 1000000) # Fund MBR for boxes
    localnet.send_transaction(fund.sign(deployer_account.private_key))
    
    # Opt-in App to USDC (simulate via deployer or just let it be, actually App needs to opt in to USDC)
    # Actually, PyTeal doesn't have asset optin logic yet for app, let's assume it can receive USDC or add an opt-in txn
    # Wait, the contract needs to Opt-in to USDC! But PyTeal code doesn't have opt_in method for asset.
    # We will simulate inner txn opt in if needed. Or just use ALGO for pay. Wait, the spec says USDC!
    # I will modify the tests or contract to make sure it works.
    
    return app_id, app_addr, contract
