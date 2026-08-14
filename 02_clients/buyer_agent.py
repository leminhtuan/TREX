import json
import base64
import os
import datetime
import hashlib
from nacl.signing import SigningKey
from algosdk import transaction, encoding, logic
from algosdk.v2client import algod
import config

def to_uint64(val):
    return val.to_bytes(8, 'big')

class BuyerAgent:
    def __init__(self):
        self.sk = config.BUYER_SK
        self.addr = config.BUYER_ADDR
        self.client = algod.AlgodClient("", config.ALGONODE_URL)
        self.app_id = config.APP_ID
        self.app_addr = logic.get_application_address(self.app_id)
        
        params = self.client.suggested_params()
        self.chain_hash = base64.b64decode(params.gh)
        
    def get_signing_key(self):
        sk_bytes = base64.b64decode(self.sk)[:32]
        return SigningKey(sk_bytes)

    def authorize(self, seller_addr, amount_pay, amount_bounty, deadline_round):
        request_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        q_payload = json.dumps({"resource": "/api/data", "method": "GET"}, separators=(',', ':'))
        c_payload = json.dumps({"sla": "uptime>99.9"}, separators=(',', ':'))
        
        H_q = hashlib.sha256(q_payload.encode()).digest()
        H_c = hashlib.sha256(c_payload.encode()).digest()
        nonce = os.urandom(32)
        
        M_B = (
            config.PROTOCOL_DOMAIN +
            config.AUTH_PREFIX +
            to_uint64(self.app_id) +
            self.chain_hash +
            encoding.decode_address(self.addr) +
            encoding.decode_address(seller_addr) +
            to_uint64(config.USDC_ASA_ID) +
            to_uint64(amount_pay) +
            to_uint64(amount_bounty) +
            to_uint64(deadline_round) +
            nonce +
            H_q +
            H_c
        )
        
        signing_key = self.get_signing_key()
        signature = signing_key.sign(M_B).signature
        
        params = self.client.suggested_params()
        
        txn_usdc = transaction.AssetTransferTxn(
            sender=self.addr,
            sp=params,
            receiver=self.app_addr,
            amt=amount_pay,
            index=config.USDC_ASA_ID
        )
        
        txn_algo = transaction.PaymentTxn(
            sender=self.addr,
            sp=params,
            receiver=self.app_addr,
            amt=amount_bounty
        )
        
        app_info = self.client.application_info(self.app_id)
        next_id = 0
        for kv in app_info.get("params", {}).get("global-state", []):
            if base64.b64decode(kv["key"]) == b"next_id":
                next_id = kv["value"]["uint"]
                break
                
        nonce_box = (self.app_id, b"nonce:" + nonce)
        session_box = (self.app_id, b"session:" + to_uint64(next_id))
        
        from algosdk.abi import Method
        authorize_method = Method.from_signature("authorize(address,uint64,uint64,uint64,byte[32],byte[32],byte[32],byte[64],axfer,pay)uint64")
        
        app_params = self.client.suggested_params()
        app_params.flat_fee = True
        app_params.fee = 4000
        
        txn_app = transaction.ApplicationCallTxn(
            sender=self.addr,
            sp=app_params,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[
                authorize_method.get_selector(),
                encoding.decode_address(seller_addr),
                amount_pay.to_bytes(8, "big"),
                amount_bounty.to_bytes(8, "big"),
                deadline_round.to_bytes(8, "big"),
                nonce,
                H_q,
                H_c,
                signature
            ],
            boxes=[nonce_box, session_box]
        )
        
        opup_method = Method.from_signature("opup(uint64)void")
        
        # We need 4 AppCalls in total for 2800 budget
        txn_opup_1 = transaction.ApplicationCallTxn(
            sender=self.addr,
            sp=app_params,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[opup_method.get_selector(), (1).to_bytes(8, "big")]
        )
        
        txn_opup_2 = transaction.ApplicationCallTxn(
            sender=self.addr,
            sp=app_params,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[opup_method.get_selector(), (2).to_bytes(8, "big")]
        )
        
        txn_opup_3 = transaction.ApplicationCallTxn(
            sender=self.addr,
            sp=app_params,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[opup_method.get_selector(), (3).to_bytes(8, "big")]
        )
        
        # Group
        txns = [txn_usdc, txn_algo, txn_app, txn_opup_1, txn_opup_2, txn_opup_3]
        gid = transaction.calculate_group_id(txns)
        for t in txns:
            t.group = gid
        
        stxns = [t.sign(self.sk) for t in txns]
        
        app_call_submitted_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        tx_id = self.client.send_transactions(stxns)
        res = transaction.wait_for_confirmation(self.client, tx_id, 4)
        confirmed_round = res["confirmed-round"]
        
        payment_authorized_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        total_fee = sum(t.fee for t in txns)
        
        return {
            "session_id": next_id,
            "H_q": H_q,
            "H_c": H_c,
            "nonce": nonce,
            "tx_id": tx_id,
            "confirmed_round": confirmed_round,
            "fee": total_fee,
            "request_timestamp": request_timestamp,
            "app_call_submitted_timestamp": app_call_submitted_timestamp,
            "payment_authorized_timestamp": payment_authorized_timestamp
        }
