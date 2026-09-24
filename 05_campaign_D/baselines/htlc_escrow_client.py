import os
import sys
import json
import hashlib
import datetime
from algosdk import transaction, logic, encoding
from algosdk.v2client import algod

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../02_clients')))
import config

class HTLCEscrowClient:
    def __init__(self, app_id=None):
        self.client = algod.AlgodClient("", config.ALGONODE_URL)
        if app_id:
            self.app_id = app_id
        else:
            manifest_path = os.path.join(os.path.dirname(__file__), "../manifest/campaign_D_manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                self.app_id = manifest.get("htlc_escrow_app_id", config.APP_ID)
            else:
                self.app_id = config.APP_ID
        self.app_addr = logic.get_application_address(self.app_id)

    def fund(self, session_id, seller_addr, amount, hash_lock, deadline_round):
        """
        Phase 1: Fund / Authorize
        Outer Txns: 2
          - Txn 1: AssetTransfer of amount USDC from Buyer to App Escrow
          - Txn 2: ApplicationCall 'fund'
        Total fee: 2,000 uALGO (1,000 + 1,000) or 3,000 uALGO (with flat fee buffers)
        """
        sp1 = self.client.suggested_params()
        sp1.flat_fee = True
        sp1.fee = 1000

        txn1 = transaction.AssetTransferTxn(
            sender=config.BUYER_ADDR,
            sp=sp1,
            receiver=self.app_addr,
            amt=amount,
            index=config.USDC_ASA_ID
        )

        sp2 = self.client.suggested_params()
        sp2.flat_fee = True
        sp2.fee = 1000

        box_key = b"htlc_" + session_id.to_bytes(8, 'big')
        txn2 = transaction.ApplicationCallTxn(
            sender=config.BUYER_ADDR,
            sp=sp2,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[
                b"fund",
                session_id.to_bytes(8, 'big'),
                encoding.decode_address(seller_addr),
                amount.to_bytes(8, 'big'),
                hash_lock,
                deadline_round.to_bytes(8, 'big')
            ],
            boxes=[(self.app_id, box_key)],
            foreign_assets=[config.USDC_ASA_ID]
        )

        gid = transaction.calculate_group_id([txn1, txn2])
        txn1.group = gid
        txn2.group = gid

        stxn1 = txn1.sign(config.BUYER_SK)
        stxn2 = txn2.sign(config.BUYER_SK)

        txid = self.client.send_transactions([stxn1, stxn2])
        transaction.wait_for_confirmation(self.client, txid, 4)
        return txid, 2000

    def claim(self, session_id, preimage):
        """
        Phase 2: Claim / Settle via Preimage
        Outer Txns: 1 AppCall
        Inner Txns: 1 AssetTransfer (fee covered by outer fee pooling)
        Fee: 2,000 uALGO (1,000 outer + 1,000 inner)
        """
        sp = self.client.suggested_params()
        sp.flat_fee = True
        sp.fee = 2000 # covers 1 inner transaction

        t_submit = datetime.datetime.utcnow()
        box_key = b"htlc_" + session_id.to_bytes(8, 'big')

        txn = transaction.ApplicationCallTxn(
            sender=config.SELLER_ADDR,
            sp=sp,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[
                b"claim",
                session_id.to_bytes(8, 'big'),
                preimage
            ],
            boxes=[(self.app_id, box_key)],
            foreign_assets=[config.USDC_ASA_ID]
        )
        stxn = txn.sign(config.SELLER_SK)
        txid = self.client.send_transaction(stxn)
        res = transaction.wait_for_confirmation(self.client, txid, 4)
        t_confirmed = datetime.datetime.utcnow()

        return txid, 2000, t_submit, t_confirmed

    def refund(self, session_id):
        """
        Refund after deadline expiration
        Outer Txns: 1 AppCall
        Inner Txns: 1 AssetTransfer
        Fee: 2,000 uALGO
        """
        sp = self.client.suggested_params()
        sp.flat_fee = True
        sp.fee = 2000

        box_key = b"htlc_" + session_id.to_bytes(8, 'big')
        txn = transaction.ApplicationCallTxn(
            sender=config.BUYER_ADDR,
            sp=sp,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[
                b"refund",
                session_id.to_bytes(8, 'big')
            ],
            boxes=[(self.app_id, box_key)],
            foreign_assets=[config.USDC_ASA_ID]
        )
        stxn = txn.sign(config.BUYER_SK)
        txid = self.client.send_transaction(stxn)
        transaction.wait_for_confirmation(self.client, txid, 4)
        return txid, 2000
