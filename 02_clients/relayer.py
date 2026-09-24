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
        
    def settle(self, session_id, H_p, seller_signature, attester_1, attester_2, opup_count: int = 15):
        params_main = self.client.suggested_params()
        params_main.flat_fee = True
        params_main.fee = 3000
        
        session_box = (self.app_id, b"session:" + to_uint64(session_id))
        
        # Read the session box to extract the buyer and nonce
        import base64
        import hashlib
        try:
            box_info = self.client.application_box_by_name(self.app_id, session_box[1])
            box_data = base64.b64decode(box_info['value'])
            buyer_bytes = box_data[1:33]
            nonce_bytes = box_data[97:105]
            nonce_box = (self.app_id, hashlib.new("sha512_256", b"T-REX-ACTIVE-NONCE" + buyer_bytes + nonce_bytes).digest())
            spent_box = (self.app_id, hashlib.new("sha512_256", b"T-REX-SPENT" + self.app_id.to_bytes(8, "big") + buyer_bytes + nonce_bytes).digest())
        except Exception as e:
            raise ValueError(f"Failed to read session box: {e}")
        
        from algosdk.abi import Method
        settle_method = Method.from_signature("settle(uint64,address,byte[32],byte[64],uint8,byte[64],uint8,byte[64],address)void")
        
        app_args=[
            settle_method.get_selector(),
            session_id.to_bytes(8, "big"),
            buyer_bytes,
            H_p,
            seller_signature,
            (attester_1["index"]).to_bytes(1, "big"),
            attester_1["signature"],
            (attester_2["index"]).to_bytes(1, "big"),
            attester_2["signature"],
            encoding.decode_address(self.addr)
        ]
        
        txn_app = transaction.ApplicationCallTxn(
            sender=self.addr,
            sp=params_main,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=app_args,
            boxes=[session_box, nonce_box, spent_box],
            foreign_assets=[config.USDC_ASA_ID],
            accounts=[config.SELLER_ADDR, self.addr]
        )
        
        params_opup = self.client.suggested_params()
        params_opup.flat_fee = True
        params_opup.fee = 1000
        
        opup_method = Method.from_signature("opup(uint64)void")
        txns = [txn_app]
        # Deployed configuration uses 15 OpUp AppCalls (16 outer AppCalls total)
        for i in range(opup_count):
            txn_opup = transaction.ApplicationCallTxn(
                sender=self.addr,
                sp=params_opup,
                index=self.app_id,
                on_complete=transaction.OnComplete.NoOpOC,
                app_args=[opup_method.get_selector(), (i).to_bytes(8, "big")]
            )
            txns.append(txn_opup)
            
        assert len(txns) <= 16, f"Group limit exceeded: {len(txns)} outer transactions"
        gid = transaction.calculate_group_id(txns)
        for t in txns:
            t.group = gid
            
        stxns = [t.sign(self.sk) for t in txns]
        total_fee = sum(t.fee for t in txns)
        
        tx_id = self.client.send_transactions(stxns)
        res = transaction.wait_for_confirmation(self.client, tx_id, 4)
        confirmed_round = res["confirmed-round"]
        
        finality_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        return {
            "tx_id": tx_id,
            "confirmed_round": confirmed_round,
            "outcome": "Released",
            "fee": total_fee,
            "outer_tx_count": len(txns),
            "inner_tx_count": 2,
            "finality_timestamp": finality_timestamp
        }
        
    def refund(self, session_id, reason, attester_1=None, attester_2=None, opup_count: int = None):
        params_main = self.client.suggested_params()
        params_main.flat_fee = True
        params_main.fee = 3000
        
        session_box = (self.app_id, b"session:" + to_uint64(session_id))
        
        # Read the session box to extract the buyer and nonce
        import base64
        import hashlib
        try:
            box_info = self.client.application_box_by_name(self.app_id, session_box[1])
            box_data = base64.b64decode(box_info['value'])
            buyer_bytes = box_data[1:33]
            nonce_bytes = box_data[97:105]
            nonce_box = (self.app_id, hashlib.new("sha512_256", b"T-REX-ACTIVE-NONCE" + buyer_bytes + nonce_bytes).digest())
            spent_box = (self.app_id, hashlib.new("sha512_256", b"T-REX-SPENT" + self.app_id.to_bytes(8, "big") + buyer_bytes + nonce_bytes).digest())
        except Exception as e:
            raise ValueError(f"Failed to read session box: {e}")
        
        from algosdk.abi import Method
        refund_method = Method.from_signature("refund(uint64,address,uint8,uint8,byte[64],uint8,byte[64],address)void")
        
        # If timeout, attesters can be dummy
        if not attester_1:
            attester_1 = {"index": 0, "signature": bytes([0]*64)}
        if not attester_2:
            attester_2 = {"index": 1, "signature": bytes([0]*64)}
            
        txn_app = transaction.ApplicationCallTxn(
            sender=self.addr,
            sp=params_main,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[
                refund_method.get_selector(),
                session_id.to_bytes(8, "big"),
                buyer_bytes,
                reason.to_bytes(1, "big"),
                (attester_1["index"]).to_bytes(1, "big"),
                attester_1["signature"],
                (attester_2["index"]).to_bytes(1, "big"),
                attester_2["signature"],
                encoding.decode_address(self.addr)
            ],
            boxes=[session_box, nonce_box, spent_box],
            foreign_assets=[config.USDC_ASA_ID],
            accounts=[config.BUYER_ADDR, self.addr]
        )
        
        params_opup = self.client.suggested_params()
        params_opup.flat_fee = True
        params_opup.fee = 1000
        
        opup_method = Method.from_signature("opup(uint64)void")
        txns = [txn_app]
        # Attested Fail requires 6 opups (7 AppCalls total, budget 4900). Timeout requires 2 opups (3 AppCalls total).
        if opup_count is None:
            opup_count = 6 if reason == 1 else 2
        for i in range(opup_count):
            txn_opup = transaction.ApplicationCallTxn(
                sender=self.addr,
                sp=params_opup,
                index=self.app_id,
                on_complete=transaction.OnComplete.NoOpOC,
                app_args=[opup_method.get_selector(), (i).to_bytes(8, "big")]
            )
            txns.append(txn_opup)
            
        assert len(txns) <= 16, f"Group limit exceeded: {len(txns)} outer transactions"
        gid = transaction.calculate_group_id(txns)
        for t in txns:
            t.group = gid
            
        stxns = [t.sign(self.sk) for t in txns]
        total_fee = sum(t.fee for t in txns)
        
        tx_id = self.client.send_transactions(stxns)
        res = transaction.wait_for_confirmation(self.client, tx_id, 4)
        confirmed_round = res["confirmed-round"]
        
        finality_timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        reason_str = "TIMEOUT" if reason == 0 else "ATTESTED_FAIL"
        
        return {
            "tx_id": tx_id,
            "confirmed_round": confirmed_round,
            "outcome": f"Refunded ({reason_str})",
            "fee": total_fee,
            "outer_tx_count": len(txns),
            "inner_tx_count": 2,
            "finality_timestamp": finality_timestamp
        }
