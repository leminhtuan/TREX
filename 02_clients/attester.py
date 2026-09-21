import base64
import struct
from nacl.signing import SigningKey
from algosdk import encoding
import config
import sspl_eval

def to_uint64(val):
    return val.to_bytes(8, 'big')
    
def to_uint8(val):
    return val.to_bytes(1, 'big')

class AttesterAgent:
    def __init__(self, index, sk_b64):
        self.index = index
        self.sk = sk_b64
        self.app_id = config.APP_ID
        
        from algosdk.v2client import algod
        self.client = algod.AlgodClient("", config.ALGONODE_URL)
        params = self.client.suggested_params()
        self.chain_hash = base64.b64decode(params.gh)
        
    def get_signing_key(self):
        sk_bytes = base64.b64decode(self.sk)[:32]
        return SigningKey(sk_bytes)

    def attest(
        self,
        session_id,
        nonce,
        H_q,
        H_c,
        H_p,
        deadline_round,
        verdict=None,
        buyer_address=None,
        predicate_json=None,
        response_json=None,
        chain_hash=None
    ):
        # 1. Evaluate SLA using SSPL Evaluator
        # If predicate_json and response_json are provided, evaluate them with strict
        # Kleene 3-valued logic and Fail-Closed semantics.
        if predicate_json is not None and response_json is not None:
            verdict = int(sspl_eval.evaluate(predicate_json, response_json))
        elif verdict is None:
            verdict = 1  # Default fallback if neither predicate nor explicit verdict is supplied
        else:
            verdict = int(verdict)

        # 2. Construct M_A
        # In attested fail (verdict 0), the contract expects hash_p to be 32 bytes of zeros.
        final_H_p = H_p if verdict == 1 else (b'\x00' * 32)
        
        if buyer_address is None:
            buyer_addr_bytes = encoding.decode_address(config.BUYER_ADDR)
        elif isinstance(buyer_address, str):
            buyer_addr_bytes = encoding.decode_address(buyer_address)
        else:
            buyer_addr_bytes = bytes(buyer_address)

        if chain_hash is None:
            chain_hash_bytes = self.chain_hash
        elif isinstance(chain_hash, str):
            chain_hash_bytes = base64.b64decode(chain_hash)
        else:
            chain_hash_bytes = bytes(chain_hash)
            
        M_A = (
            b"T-REX-ATT" +
            struct.pack(">Q", self.app_id) +
            chain_hash_bytes +
            buyer_addr_bytes +
            struct.pack(">Q", session_id) +
            H_q +
            H_c +
            final_H_p +
            struct.pack(">B", verdict) +
            struct.pack(">Q", deadline_round) +
            struct.pack(">Q", nonce)
        )
        
        # 3. Sign M_A
        signing_key = self.get_signing_key()
        signature = signing_key.sign(M_A).signature
        
        print(f"M_A signed by Attester {self.index} (Verdict={verdict}).")
        
        return {
            "index": self.index,
            "verdict": verdict,
            "signature": signature
        }

if __name__ == "__main__":
    a1 = AttesterAgent(0, config.ATTESTER_1_SK)
    a2 = AttesterAgent(1, config.ATTESTER_2_SK)
    print("Attesters initialized.")
