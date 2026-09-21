import json
import base64
import os
import hashlib
from nacl.signing import SigningKey
from algosdk import encoding
import config

def to_uint64(val):
    return val.to_bytes(8, 'big')

class SellerAgent:
    def __init__(self):
        self.sk = config.SELLER_SK
        self.addr = config.SELLER_ADDR
        self.app_id = config.APP_ID
        
        from algosdk.v2client import algod
        self.client = algod.AlgodClient("", config.ALGONODE_URL)
        params = self.client.suggested_params()
        self.chain_hash = base64.b64decode(params.gh)
        
    def get_signing_key(self):
        sk_bytes = base64.b64decode(self.sk)[:32]
        return SigningKey(sk_bytes)

    def process_request(self, session_id, H_q, H_c, nonce, buyer_address=None, simulate_mismatch=False):
        # 1. Provide the data (payload P)
        p_payload = json.dumps({"status": "success", "data": "dummy_data"}, separators=(',', ':'))
        H_p = hashlib.sha256(p_payload.encode()).digest()
        
        if simulate_mismatch:
            H_p = hashlib.sha256(b"wrong_data").digest()
        
        if buyer_address is None:
            buyer_addr_bytes = encoding.decode_address(config.BUYER_ADDR)
        elif isinstance(buyer_address, str):
            buyer_addr_bytes = encoding.decode_address(buyer_address)
        else:
            buyer_addr_bytes = bytes(buyer_address)
        
        import struct
        M_S = (
            config.PROTOCOL_DOMAIN +
            config.SETTLE_PREFIX +
            to_uint64(self.app_id) +
            self.chain_hash +
            buyer_addr_bytes +
            to_uint64(session_id) +
            struct.pack(">Q", nonce) +
            H_p
        )
        
        # 3. Sign M_S
        signing_key = self.get_signing_key()
        signature = signing_key.sign(M_S).signature
        
        print("M_S signed by Seller.")
        
        return {
            "session_id": session_id,
            "H_q": H_q,
            "H_c": H_c,
            "H_p": H_p,
            "nonce": nonce,
            "seller_signature": signature
        }

if __name__ == "__main__":
    # Test only
    seller = SellerAgent()
    print("Seller initialized:", seller.addr)
