import os
import sys
import json
import datetime
from algosdk import transaction, logic, encoding
from algosdk.v2client import algod

sys.path.insert(0, os.path.abspath('../../02_clients'))
import config

class NaiveEscrowClient:
    def __init__(self):
        self.client = algod.AlgodClient("", config.ALGONODE_URL)
        with open("05_campaign_D/manifest/campaign_D_manifest.json", "r") as f:
            self.manifest = json.load(f)
        self.app_id = self.manifest["naive_escrow_app_id"]
        self.app_addr = logic.get_application_address(self.app_id)
        
    def authorize(self, session_id, seller_addr, amount, deadline_round):
        sp = self.client.suggested_params()
        sp.flat_fee = True
        sp.fee = 2000
        
        # Asset Transfer
        txn1 = transaction.AssetTransferTxn(
            sender=config.BUYER_ADDR,
            sp=sp,
            receiver=self.app_addr,
            amt=amount,
            index=config.USDC_ASA_ID
        )
        
        # App Call
        sp2 = self.client.suggested_params()
        sp2.flat_fee = True
        sp2.fee = 1000
        
        box_key = b"session_" + session_id.to_bytes(8, 'big')
        txn2 = transaction.ApplicationCallTxn(
            sender=config.BUYER_ADDR,
            sp=sp2,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[
                b"authorize", 
                session_id.to_bytes(8, 'big'),
                encoding.decode_address(seller_addr),
                amount.to_bytes(8, 'big'),
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
        
        ptx = self.client.pending_transaction_info(txid)
        # Auth fee = fee of txn1 + txn2
        # But pending_transaction_info only gives txn1 fee? No, we know it's 2000 + 1000. Wait, actually we can just read it.
        # It's better to just sum the fees we set.
        return txid, 3000

    def release(self, session_id):
        sp = self.client.suggested_params()
        sp.flat_fee = True
        sp.fee = 2000 # covers inner
        
        t_submit = datetime.datetime.utcnow()
        box_key = b"session_" + session_id.to_bytes(8, 'big')
        
        txn = transaction.ApplicationCallTxn(
            sender=config.SELLER_ADDR,
            sp=sp,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[b"release", session_id.to_bytes(8, 'big')],
            boxes=[(self.app_id, box_key)],
            foreign_assets=[config.USDC_ASA_ID]
        )
        stxn = txn.sign(config.SELLER_SK)
        txid = self.client.send_transaction(stxn)
        transaction.wait_for_confirmation(self.client, txid, 4)
        t_confirmed = datetime.datetime.utcnow()
        
        return txid, 2000, t_submit, t_confirmed

    def refund(self, session_id):
        sp = self.client.suggested_params()
        sp.flat_fee = True
        sp.fee = 2000 # covers inner
        
        t_submit = datetime.datetime.utcnow()
        box_key = b"session_" + session_id.to_bytes(8, 'big')
        
        txn = transaction.ApplicationCallTxn(
            sender=config.RELAYER_ADDR, # Anyone can call refund, let's use relayer
            sp=sp,
            index=self.app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[b"refund", session_id.to_bytes(8, 'big')],
            boxes=[(self.app_id, box_key)],
            foreign_assets=[config.USDC_ASA_ID],
            accounts=[config.BUYER_ADDR]
        )
        stxn = txn.sign(config.RELAYER_SK)
        txid = self.client.send_transaction(stxn)
        transaction.wait_for_confirmation(self.client, txid, 4)
        t_confirmed = datetime.datetime.utcnow()
        
        return txid, 2000, t_submit, t_confirmed
