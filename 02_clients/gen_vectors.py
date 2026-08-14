import json
import base64
import hashlib
from algosdk import encoding

def to_uint64(val):
    return val.to_bytes(8, 'big')

def to_uint8(val):
    return val.to_bytes(1, 'big')

app_id = 769241061
# Algorand Testnet Genesis Hash
chain_hash = base64.b64decode("SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=")
buyer = "42CIA4I5Z7VAX4SON5WN7HL7KLY6MUTZR7N27UHBEM3MY5LGLMZRLPTBPI"
seller = "W75SYX3EE7JC34PC5MMAYG3EVHO3IDEBGQQRFRIEHNLIZNLRQTCB5TUYZY"
usdc_id = 10458941
amount_pay = 500000
amount_bounty = 500000
deadline_round = 1000
nonce = hashlib.sha256(b"nonce").digest()
hash_q = hashlib.sha256(b"hash_q").digest()
hash_c = hashlib.sha256(b"hash_c").digest()
hash_p = hashlib.sha256(b"hash_p").digest()
session_id = 1

M_B = b"T-REX/v1|AUTHORIZE|" + to_uint64(app_id) + chain_hash + \
      encoding.decode_address(buyer) + encoding.decode_address(seller) + \
      to_uint64(usdc_id) + to_uint64(amount_pay) + to_uint64(amount_bounty) + \
      to_uint64(deadline_round) + nonce + hash_q + hash_c

M_S = b"T-REX/v1|SETTLE|" + to_uint64(app_id) + chain_hash + \
      to_uint64(session_id) + nonce + hash_p

M_A = b"T-REX/v1|ATTEST|" + to_uint64(app_id) + chain_hash + \
      to_uint64(session_id) + nonce + to_uint8(1) + hash_q + hash_c + hash_p

vectors = {
    "inputs": {
        "buyer": buyer,
        "seller": seller,
        "app_id": app_id,
        "usdc_id": usdc_id,
        "amount_pay": amount_pay,
        "amount_bounty": amount_bounty,
        "deadline_round": deadline_round,
        "nonce": nonce.hex(),
        "hash_q": hash_q.hex(),
        "hash_c": hash_c.hex(),
        "hash_p": hash_p.hex(),
        "session_id": session_id,
        "verdict": 1
    },
    "expected_M_B_hex": M_B.hex(),
    "expected_M_S_hex": M_S.hex(),
    "expected_M_A_hex": M_A.hex()
}

with open("test_vectors.json", "w") as f:
    json.dump(vectors, f, indent=4)
print("Generated test_vectors.json")
