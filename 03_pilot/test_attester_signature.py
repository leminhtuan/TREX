import base64
import pytest
from nacl.signing import SigningKey, VerifyKey
import os
import sys

# Ensure imports work
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "02_clients"))
import config
from attester import AttesterAgent

def test_attester_signatures():
    a1 = AttesterAgent(0, config.ATTESTER_1_SK)
    verify_key = a1.get_signing_key().verify_key
    
    session_id = 999
    nonce = 123456
    deadline_round = 500000
    buyer_address = config.BUYER_ADDR
    H_q = os.urandom(32)
    H_c = os.urandom(32)
    actual_H_p = os.urandom(32)
    zero_H_p = b'\x00' * 32
    
    import struct
    from algosdk import encoding
    buyer_bytes = encoding.decode_address(buyer_address)

    # Case 1: verdict=PASS (1), hash_p=actual hash
    res_pass = a1.attest(session_id, nonce, H_q, H_c, actual_H_p, deadline_round, verdict=1, buyer_address=buyer_address)
    sig_pass = res_pass["signature"]
    
    M_A_pass = (
        b"T-REX-ATT" +
        struct.pack(">Q", a1.app_id) +
        a1.chain_hash +
        buyer_bytes +
        struct.pack(">Q", session_id) +
        H_q +
        H_c +
        actual_H_p +
        struct.pack(">B", 1) +
        struct.pack(">Q", deadline_round) +
        struct.pack(">Q", nonce)
    )
    assert len(M_A_pass) == 202
    verify_key.verify(M_A_pass, sig_pass)
    
    # Case 2: verdict=FAIL (0), hash_p=actual hash passed in, but should sign zeroes
    res_fail = a1.attest(session_id, nonce, H_q, H_c, actual_H_p, deadline_round, verdict=0, buyer_address=buyer_address)
    sig_fail = res_fail["signature"]
    
    M_A_fail = (
        b"T-REX-ATT" +
        struct.pack(">Q", a1.app_id) +
        a1.chain_hash +
        buyer_bytes +
        struct.pack(">Q", session_id) +
        H_q +
        H_c +
        zero_H_p +
        struct.pack(">B", 0) +
        struct.pack(">Q", deadline_round) +
        struct.pack(">Q", nonce)
    )
    assert len(M_A_fail) == 202
    verify_key.verify(M_A_fail, sig_fail)
    print("All signatures verified successfully (202 bytes per M_A).")

if __name__ == '__main__':
    test_attester_signatures()
