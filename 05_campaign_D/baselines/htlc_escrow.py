"""
Hash Time-Locked Contract (HTLC) Baseline for Algorand (TEAL v11)
Standard cryptographic escrow baseline simulating a perfect hash-oracle predicate.
Buyer funds with a hash-lock H; Seller claims with preimage P (sha256(P) == H);
Buyer reclaims after deadline timeout.
"""

import os
import sys
from pyteal import *

def approval_program():
    # Box mapping: "htlc_{session_id}" -> (state, buyer, seller, amount, hash_lock, deadline)
    # Box layout (113 bytes total):
    # - state: 1 byte (0: Active/Funded, 1: Claimed, 2: Refunded)
    # - buyer: 32 bytes (offset 1)
    # - seller: 32 bytes (offset 33)
    # - amount: 8 bytes (offset 65)
    # - hash_lock: 32 bytes (offset 73)
    # - deadline: 8 bytes (offset 105)

    session_id = Btoi(Txn.application_args[1])
    box_key = Concat(Bytes("htlc_"), Itob(session_id))
    box_len = App.box_length(box_key)

    # 1. FUND (Authorize & Deposit)
    # Group of 2:
    #   Gtxn[0]: AssetTransfer (USDC) from Buyer to App Escrow
    #   Gtxn[1]: ApplicationCall 'fund', session_id, seller, amount, hash_lock, deadline
    on_fund = Seq(
        Assert(Global.group_size() == Int(2)),
        Assert(Gtxn[0].type_enum() == TxnType.AssetTransfer),
        Assert(Gtxn[0].xfer_asset() == Txn.assets[0]),
        Assert(Gtxn[0].asset_receiver() == Global.current_application_address()),
        Assert(Gtxn[0].asset_amount() == Btoi(Txn.application_args[3])),
        Assert(Gtxn[0].sender() == Txn.sender()),
        Assert(Len(Txn.application_args[4]) == Int(32)), # SHA-256 hash lock
        
        # Ensure box does not already exist
        box_len,
        Assert(Not(box_len.hasValue())),
        
        # Write state to box
        App.box_put(box_key, Concat(
            Bytes("\x00"),             # state: 0 (Active)
            Txn.sender(),              # buyer (32 bytes)
            Txn.application_args[2],   # seller (32 bytes)
            Txn.application_args[3],   # amount (8 bytes)
            Txn.application_args[4],   # hash_lock (32 bytes)
            Txn.application_args[5]    # deadline (8 bytes)
        )),
        Approve()
    )

    # 2. CLAIM (Settle by Preimage)
    # 1 Outer Txn by Seller:
    #   AppCall 'claim', session_id, preimage
    # Checks:
    #   - Box exists and is Active
    #   - Round <= deadline
    #   - Txn.sender() == seller
    #   - Sha256(preimage) == hash_lock
    preimage = Txn.application_args[2]
    on_claim = Seq(
        box_len,
        Assert(box_len.hasValue()),
        # Check active state
        Assert(App.box_extract(box_key, Int(0), Int(1)) == Bytes("\x00")),
        # Check deadline
        Assert(Global.round() <= Btoi(App.box_extract(box_key, Int(105), Int(8)))),
        # Check sender is designated seller
        Assert(Txn.sender() == App.box_extract(box_key, Int(33), Int(32))),
        # Verify preimage hash-lock
        Assert(Sha256(preimage) == App.box_extract(box_key, Int(73), Int(32))),
        
        # Transfer asset to seller via inner transaction
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: Txn.assets[0],
            TxnField.asset_receiver: Txn.sender(),
            TxnField.asset_amount: Btoi(App.box_extract(box_key, Int(65), Int(8))),
            TxnField.fee: Int(0) # covered by outer fee pooling
        }),
        InnerTxnBuilder.Submit(),
        
        # Delete box upon terminal settlement
        Pop(App.box_delete(box_key)),
        Approve()
    )

    # 3. REFUND (Timeout reclaim by Buyer)
    # 1 Outer Txn:
    #   AppCall 'refund', session_id
    # Checks:
    #   - Box exists and is Active
    #   - Round > deadline
    on_refund = Seq(
        box_len,
        Assert(box_len.hasValue()),
        Assert(App.box_extract(box_key, Int(0), Int(1)) == Bytes("\x00")),
        Assert(Global.round() > Btoi(App.box_extract(box_key, Int(105), Int(8)))),
        
        # Transfer asset back to buyer via inner transaction
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: Txn.assets[0],
            TxnField.asset_receiver: App.box_extract(box_key, Int(1), Int(32)),
            TxnField.asset_amount: Btoi(App.box_extract(box_key, Int(65), Int(8))),
            TxnField.fee: Int(0)
        }),
        InnerTxnBuilder.Submit(),
        
        Pop(App.box_delete(box_key)),
        Approve()
    )

    # 4. OPT-IN TO ASA (USDC)
    on_optin_asa = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: Txn.assets[0],
            TxnField.asset_receiver: Global.current_application_address(),
            TxnField.asset_amount: Int(0),
            TxnField.fee: Int(0)
        }),
        InnerTxnBuilder.Submit(),
        Approve()
    )

    on_call = Cond(
        [Txn.application_args[0] == Bytes("fund"), on_fund],
        [Txn.application_args[0] == Bytes("claim"), on_claim],
        [Txn.application_args[0] == Bytes("refund"), on_refund],
        [Txn.application_args[0] == Bytes("optin_asa"), on_optin_asa]
    )

    program = Cond(
        [Txn.application_id() == Int(0), Approve()],
        [Txn.on_completion() == OnComplete.NoOp, on_call],
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(Txn.sender() == Global.creator_address())]
    )

    return program

def clear_state_program():
    return Approve()

if __name__ == "__main__":
    approval_teal = compileTeal(approval_program(), mode=Mode.Application, version=10)
    # Upgrade pragma to 11
    approval_teal = approval_teal.replace("#pragma version 10", "#pragma version 11")
    
    clear_teal = compileTeal(clear_state_program(), mode=Mode.Application, version=10)
    clear_teal = clear_teal.replace("#pragma version 10", "#pragma version 11")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(base_dir, "htlc_escrow_approval.teal")
    clr_path = os.path.join(base_dir, "htlc_escrow_clear.teal")

    with open(app_path, "w") as f:
        f.write(approval_teal)

    with open(clr_path, "w") as f:
        f.write(clear_teal)

    print(f"HTLC Approval TEAL v11 generated at: {app_path}")
    print(f"HTLC Clear TEAL v11 generated at: {clr_path}")
