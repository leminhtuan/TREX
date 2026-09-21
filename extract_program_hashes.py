import os
import base64
import json
from algosdk import logic
from algosdk.v2client import algod

# Ensure algosdk.logic.program_hash is available (maps to logic.address per Algorand specification)
if not hasattr(logic, 'program_hash'):
    logic.program_hash = logic.address

def extract_hashes(algod_url="https://testnet-api.algonode.cloud"):
    client = algod.AlgodClient("", algod_url)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    approval_path = os.path.join(base_dir, "01_contracts", "approval.teal")
    clear_path = os.path.join(base_dir, "01_contracts", "clear.teal")
    
    with open(approval_path, "r") as f:
        approval_src = f.read()
    with open(clear_path, "r") as f:
        clear_src = f.read()
        
    approval_resp = client.compile(approval_src)
    clear_resp = client.compile(clear_src)
    
    approval_bytes = base64.b64decode(approval_resp["result"])
    clear_bytes = base64.b64decode(clear_resp["result"])
    
    approval_prog_hash = logic.program_hash(approval_bytes)
    clear_prog_hash = logic.program_hash(clear_bytes)
    
    result = {
        "approval_program_hash": approval_prog_hash,
        "approval_algod_hash": approval_resp.get("hash"),
        "clear_program_hash": clear_prog_hash,
        "clear_algod_hash": clear_resp.get("hash"),
        "approval_bytes_len": len(approval_bytes),
        "clear_bytes_len": len(clear_bytes)
    }
    
    print("=== Cryptographic Program Hashes (Algorand Addresses) ===")
    print(f"Approval Program Hash: {approval_prog_hash}")
    print(f"Clear Program Hash:    {clear_prog_hash}")
    print("==========================================================")
    
    output_path = os.path.join(base_dir, "artifacts", "program_hashes.json")
    with open(output_path, "w") as f:
        json.dump(result, f, indent=4)
        
    return result

if __name__ == "__main__":
    extract_hashes()
