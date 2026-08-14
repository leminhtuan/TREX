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
    nonce = os.urandom(32)
    H_q = os.urandom(32)
    H_c = os.urandom(32)
    actual_H_p = os.urandom(32)
    zero_H_p = b'\x00' * 32
    
    # Case 1: verdict=PASS (1), hash_p=actual hash
    res_pass = a1.attest(session_id, nonce, H_q, H_c, actual_H_p, verdict=1)
    sig_pass = res_pass["signature"]
    
    M_A_pass = (
        config.PROTOCOL_DOMAIN + config.ATTEST_PREFIX +
        a1.app_id.to_bytes(8, 'big') + a1.chain_hash +
        session_id.to_bytes(8, 'big') + nonce +
        (1).to_bytes(1, 'big') + H_q + H_c + actual_H_p
    )
    # This should pass without raising
    verify_key.verify(M_A_pass, sig_pass)
    
    # Case 2: verdict=FAIL (0), hash_p=actual hash passed in, but should sign zeroes
    res_fail = a1.attest(session_id, nonce, H_q, H_c, actual_H_p, verdict=0)
    sig_fail = res_fail["signature"]
    
    M_A_fail = (
        config.PROTOCOL_DOMAIN + config.ATTEST_PREFIX +
        a1.app_id.to_bytes(8, 'big') + a1.chain_hash +
        session_id.to_bytes(8, 'big') + nonce +
        (0).to_bytes(1, 'big') + H_q + H_c + zero_H_p
    )
    # This should pass without raising
    verify_key.verify(M_A_fail, sig_fail)
    print("All signatures verified successfully.")

if __name__ == '__main__':
    test_attester_signatures()
