import os
import sys
from pyteal import *

def approval_program():
    # Box mapping: "session_{id}" -> (buyer, seller, amount, deadline, state)
    # ABI Types:
    # State: 1 byte (0: Authorized, 1: Released, 2: Refunded)
    # Buyer: 32 bytes
    # Seller: 32 bytes
    # Amount: 8 bytes
    # Deadline: 8 bytes
    # Total Box Size = 1 + 32 + 32 + 8 + 8 = 81 bytes
    
    session_id = Btoi(Txn.application_args[1])
    box_key = Concat(Bytes("session_"), Itob(session_id))
    
    # Authorize: sender=buyer, amount=USDC (checked via asset transfer)
    # Args: authorize, session_id, seller, amount, deadline
    on_authorize = Seq(
        Assert(Global.group_size() == Int(2)),
        Assert(Gtxn[0].type_enum() == TxnType.AssetTransfer),
        Assert(Gtxn[0].xfer_asset() == Txn.assets[0]), # USDC
        Assert(Gtxn[0].asset_receiver() == Global.current_application_address()),
        Assert(Gtxn[0].asset_amount() == Btoi(Txn.application_args[3])),
        Assert(Gtxn[0].sender() == Txn.sender()),
        
        # Save to box
        App.box_put(box_key, Concat(
            Bytes("\x00"), # Authorized
            Txn.sender(),
            Txn.application_args[2], # seller
            Txn.application_args[3], # amount
            Txn.application_args[4]  # deadline
        )),
        Approve()
    )
    
    box_len = App.box_length(box_key)
    
    # Release: sender=seller, round <= deadline
    on_release = Seq(
        box_len,
        Assert(box_len.hasValue()),
        Assert(Txn.sender() == App.box_extract(box_key, Int(33), Int(32))),
        Assert(Global.round() <= Btoi(App.box_extract(box_key, Int(73), Int(8)))),
        Assert(App.box_extract(box_key, Int(0), Int(1)) == Bytes("\x00")),
        
        # Inner Asset Transfer to seller
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: Txn.assets[0],
            TxnField.asset_receiver: Txn.sender(),
            TxnField.asset_amount: Btoi(App.box_extract(box_key, Int(65), Int(8))),
            TxnField.fee: Int(0) # covered by outer
        }),
        InnerTxnBuilder.Submit(),
        
        Pop(App.box_delete(box_key)),
        Approve()
    )
    
    # Refund: round > deadline
    on_refund = Seq(
        box_len,
        Assert(box_len.hasValue()),
        Assert(Global.round() > Btoi(App.box_extract(box_key, Int(73), Int(8)))),
        Assert(App.box_extract(box_key, Int(0), Int(1)) == Bytes("\x00")),
        
        # Inner Asset Transfer to buyer
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

    # Opt-in to ASA (USDC)
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
        [Txn.application_args[0] == Bytes("authorize"), on_authorize],
        [Txn.application_args[0] == Bytes("release"), on_release],
        [Txn.application_args[0] == Bytes("refund"), on_refund],
        [Txn.application_args[0] == Bytes("optin_asa"), on_optin_asa]
    )

    return Cond(
        [Txn.application_id() == Int(0), Approve()],
        [Txn.on_completion() == OnComplete.DeleteApplication, Approve()],
        [Txn.on_completion() == OnComplete.UpdateApplication, Approve()],
        [Txn.on_completion() == OnComplete.OptIn, Approve()],
        [Txn.on_completion() == OnComplete.CloseOut, Approve()],
        [Txn.on_completion() == OnComplete.NoOp, on_call]
    )

def clear_program():
    return Approve()

def compile_contract():
    app_teal = compileTeal(approval_program(), mode=Mode.Application, version=10)
    clear_teal = compileTeal(clear_program(), mode=Mode.Application, version=10)
    with open("naive_escrow_approval.teal", "w") as f:
        f.write(app_teal)
    with open("naive_escrow_clear.teal", "w") as f:
        f.write(clear_teal)

if __name__ == "__main__":
    compile_contract()
