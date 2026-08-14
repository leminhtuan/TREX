import os
from algosdk import account, mnemonic
from dotenv import load_dotenv

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "01_contracts", ".env")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
RESULTS_DIR = os.path.join(BASE_DIR, "results", "pilot")

# Load environment variables
load_dotenv(ENV_PATH)

def get_account_from_mnemonic(env_var: str):
    mnem = os.environ.get(env_var)
    if not mnem:
        raise ValueError(f"{env_var} not set in .env")
    sk = mnemonic.to_private_key(mnem)
    addr = account.address_from_private_key(sk)
    return sk, addr

# Load accounts
BUYER_SK, BUYER_ADDR = get_account_from_mnemonic("BUYER_MNEMONIC")
SELLER_SK, SELLER_ADDR = get_account_from_mnemonic("SELLER_MNEMONIC")
RELAYER_SK, RELAYER_ADDR = get_account_from_mnemonic("RELAYER_MNEMONIC")
ATTESTER_1_SK, ATTESTER_1_ADDR = get_account_from_mnemonic("ATTESTER_1_MNEMONIC")
ATTESTER_2_SK, ATTESTER_2_ADDR = get_account_from_mnemonic("ATTESTER_2_MNEMONIC")
ATTESTER_3_SK, ATTESTER_3_ADDR = get_account_from_mnemonic("ATTESTER_3_MNEMONIC")
DEPLOYER_SK, DEPLOYER_ADDR = get_account_from_mnemonic("DEPLOYER_MNEMONIC")

# Network configs
NETWORK = "testnet"
ALGONODE_URL = "https://testnet-api.algonode.cloud"
USDC_ASA_ID = 10458941

# Load App ID
APP_ID_FILE = os.path.join(ARTIFACTS_DIR, "contract_app_id_testnet.txt")
try:
    with open(APP_ID_FILE, "r") as f:
        APP_ID = int(f.read().strip())
except Exception as e:
    # Fallback to the one deployed in logs (769246390)
    APP_ID = 769246390

# Domain Separators (matched from TEAL 10 contract)
PROTOCOL_DOMAIN = b"T-REX/v1"
AUTH_PREFIX = b"|AUTHORIZE|"
SETTLE_PREFIX = b"|SETTLE|"
ATTEST_PREFIX = b"|ATTEST|"

# Ensure results dir exists
os.makedirs(RESULTS_DIR, exist_ok=True)
