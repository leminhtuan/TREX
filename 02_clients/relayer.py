import os
import datetime
import time
from algosdk import transaction, encoding
from algosdk.v2client import algod
import config

def to_uint64(val):
    return val.to_bytes(8, 'big')

class RelayerAgent:
    def __init__(self):
        self.sk = config.RELAYER_SK
        self.addr = config.RELAYER_ADDR
        self.app_id = config.APP_ID
        self.client = algod.AlgodClient("", config.ALGONODE_URL)
        
    def settle(self, session_id, H_p, seller_signature, attester_1, attester_2):
        params = self.client.suggested_params()
        params.flat_fee = True
        params.fee = 3000
        
        session_box = (self.app_id, b"session:" + to_uint64(session_id))
        
        from algosdk.abi import Method
        settle_method = Method.from_signature("settle(uint64,byte[32],byte[64],uint8,byte[64],uint8,byte[64],address)void")
        
        app_args=[
            settle_method.get_selector(),
            session_id.to_bytes(8, "big"),
            H_p,
            seller_signature,
            (attester_1["index"]).to_bytes(1, "big"),
            attester_1["signature"],
            (attester_2["index"]).to_bytes(1, "big"),
            attester_2["signature"],
            encoding.decode_address(self.addr)
        ]
        print(f"app_args[4] (attester 1 index): {app_args[4]}")
        print(f"app_args[6] (attester 2 index): {app_args[6]}")
        txn_app = transaction.ApplicationCallTxn(
            sender=self.addr,
            sp=params,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[session_box],
            foreign_assets=[config.USDC_ASA_ID],
            accounts=[config.SELLER_ADDR, self.addr]
        )
        
        opup_method = Method.from_signature("opup(uint64)void")
        txns = [txn_app]
        # We need 10 AppCalls total for settle (1 main + 9 opups)
        for i in range(9):
            txn_opup = transaction.ApplicationCallTxn(
                sender=self.addr,
                sp=params,
                index=self.app_id,
                on_complete=transaction.OnComplete.NoOpOC,
                app_args=[opup_method.get_selector(), (i).to_bytes(8, "big")]
            )
            txns.append(txn_opup)
            
        gid = transaction.calculate_group_id(txns)
        for t in txns:
            t.group = gid
            
        stxns = [t.sign(self.sk) for t in txns]
        
        tx_id = self.client.send_transactions(stxns)
        res = transaction.wait_for_confirmation(self.client, tx_id, 4)
        confirmed_round = res["confirmed-round"]
        
        finality_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        return {
            "tx_id": tx_id,
            "confirmed_round": confirmed_round,
            "outcome": "Released",
            "fee": params.fee,
            "finality_timestamp": finality_timestamp
        }
        
    def refund(self, session_id, reason, attester_1=None, attester_2=None):
        params = self.client.suggested_params()
        params.flat_fee = True
        params.fee = 3000
        
        session_box = (self.app_id, b"session:" + to_uint64(session_id))
        
        from algosdk.abi import Method
        refund_method = Method.from_signature("refund(uint64,uint8,uint8,byte[64],uint8,byte[64],address)void")
        
        # If timeout, attesters can be dummy
        if not attester_1:
            attester_1 = {"index": 0, "signature": bytes([0]*64)}
        if not attester_2:
            attester_2 = {"index": 1, "signature": bytes([0]*64)}
            
        txn_app = transaction.ApplicationCallTxn(
            sender=self.addr,
            sp=params,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[
                refund_method.get_selector(),
                session_id.to_bytes(8, "big"),
                reason.to_bytes(1, "big"),
                (attester_1["index"]).to_bytes(1, "big"),
                attester_1["signature"],
                (attester_2["index"]).to_bytes(1, "big"),
                attester_2["signature"],
                encoding.decode_address(self.addr)
            ],
            boxes=[session_box],
            foreign_assets=[config.USDC_ASA_ID],
            accounts=[config.BUYER_ADDR, self.addr]
        )
        
        opup_method = Method.from_signature("opup(uint64)void")
        txns = [txn_app]
        # We need 7 AppCalls total for refund (1 main + 6 opups)
        for i in range(6):
            txn_opup = transaction.ApplicationCallTxn(
                sender=self.addr,
                sp=params,
                index=self.app_id,
                on_complete=transaction.OnComplete.NoOpOC,
                app_args=[opup_method.get_selector(), (i).to_bytes(8, "big")]
            )
            txns.append(txn_opup)
            
        gid = transaction.calculate_group_id(txns)
        for t in txns:
            t.group = gid
            
        stxns = [t.sign(self.sk) for t in txns]
        
        tx_id = self.client.send_transactions(stxns)
        res = transaction.wait_for_confirmation(self.client, tx_id, 4)
        confirmed_round = res["confirmed-round"]
        
        finality_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        reason_str = "TIMEOUT" if reason == 0 else "ATTESTED_FAIL"
        
        return {
            "tx_id": tx_id,
            "confirmed_round": confirmed_round,
            "outcome": f"Refunded ({reason_str})",
            "fee": params.fee,
            "finality_timestamp": finality_timestamp
        }
