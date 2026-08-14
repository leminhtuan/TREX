import base64
from nacl.signing import SigningKey
from algosdk import encoding
import config

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

    def attest(self, session_id, nonce, H_q, H_c, H_p, verdict=1):
        # 1. Evaluate SLA (mocked to match verdict)
        # 2. Construct M_A
        # In attested fail (verdict 0), the contract expects hash_p to be 32 bytes of zeros.
        final_H_p = H_p if verdict == 1 else (b'\x00' * 32)
        
        M_A = (
            config.PROTOCOL_DOMAIN +
            config.ATTEST_PREFIX +
            to_uint64(self.app_id) +
            self.chain_hash +
            to_uint64(session_id) +
            nonce +
            to_uint8(verdict) +
            H_q +
            H_c +
            final_H_p
        )
        
        # 3. Sign M_A
        signing_key = self.get_signing_key()
        signature = signing_key.sign(M_A).signature
        
        print(f"M_A signed by Attester {self.index}.")
        
        return {
            "index": self.index,
            "signature": signature
        }

if __name__ == "__main__":
    a1 = AttesterAgent(0, config.ATTESTER_1_SK)
    a2 = AttesterAgent(1, config.ATTESTER_2_SK)
    print("Attesters initialized.")
