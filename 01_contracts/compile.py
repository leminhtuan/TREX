import json
import hashlib
from trex_escrow import get_router

def compile_contract():
    router = get_router()
    approval, clear, contract = router.compile_program(
        version=10,
        assemble_constants=True,
        optimize=None
    )

    with open("approval.teal", "w") as f:
        f.write(approval.replace("#pragma version 10", "#pragma version 11"))
    
    with open("clear.teal", "w") as f:
        f.write(clear.replace("#pragma version 10", "#pragma version 11"))
        
    with open("contract.json", "w") as f:
        f.write(json.dumps(contract.dictify(), indent=4))
        
    # Calculate sha256 of source
    with open("trex_escrow.py", "rb") as f:
        source_hash = hashlib.sha256(f.read()).hexdigest()
        
    with open("../artifacts/contract_source_sha256.txt", "w") as f:
        f.write(source_hash)

if __name__ == "__main__":
    compile_contract()
    print("Compilation successful.")
