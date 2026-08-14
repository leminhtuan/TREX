from pyteal import *
from typing import Literal

MIN_AVM_VERSION = 8

# Protocol Constants
PROTOCOL_DOMAIN = Bytes("T-REX/v1")
AUTH_PREFIX = Bytes("|AUTHORIZE|")
SETTLE_PREFIX = Bytes("|SETTLE|")
ATTEST_PREFIX = Bytes("|ATTEST|")

STATE_IDLE = Int(0)
STATE_AUTHORIZED = Int(1)
STATE_RELEASED = Int(2)
STATE_REFUNDED = Int(3)

VERDICT_FAIL = Int(0)
VERDICT_PASS = Int(1)

REASON_TIMEOUT = Int(0)
REASON_ATTESTED_FAIL = Int(1)

# Global Keys
NEXT_ID = Bytes("next_id")
ATTESTER_PK_0 = Bytes("attester_pk_0")
ATTESTER_PK_1 = Bytes("attester_pk_1")
ATTESTER_PK_2 = Bytes("attester_pk_2")
APP_ADMIN = Bytes("app_admin")
PROTOCOL_VERSION = Bytes("protocol_version")
USDC_ASA_ID = Bytes("usdc_asa_id")

class SessionRecord(abi.NamedTuple):
    state: abi.Field[abi.Uint8]
    buyer: abi.Field[abi.Address]
    seller: abi.Field[abi.Address]
    asset_id: abi.Field[abi.Uint64]
    amount_pay: abi.Field[abi.Uint64]
    amount_bounty: abi.Field[abi.Uint64]
    deadline_round: abi.Field[abi.Uint64]
    nonce: abi.Field[abi.StaticBytes[Literal[32]]]
    hash_q: abi.Field[abi.StaticBytes[Literal[32]]]
    hash_c: abi.Field[abi.StaticBytes[Literal[32]]]
    hash_p: abi.Field[abi.StaticBytes[Literal[32]]]
    bounty_paid: abi.Field[abi.Uint8]
    attester_threshold: abi.Field[abi.Uint8]
    attester_count: abi.Field[abi.Uint8]

def get_session_box_key(session_id: Expr) -> Expr:
    return Concat(Bytes("session:"), Itob(session_id))

def get_nonce_box_key(nonce: Expr) -> Expr:
    return Concat(Bytes("nonce:"), nonce)

router = Router(
    "T-REX-Escrow",
    BareCallActions(
        no_op=OnCompleteAction.create_only(Approve()),
        opt_in=OnCompleteAction.never(),
        close_out=OnCompleteAction.never(),
        update_application=OnCompleteAction.never(),
        delete_application=OnCompleteAction.never(),
    ),
    clear_state=Approve(),
)

@router.method(no_op=CallConfig.CREATE)
def create_app(
    attester_0: abi.Address,
    attester_1: abi.Address,
    attester_2: abi.Address,
    admin: abi.Address
) -> Expr:
    return Seq(
        Assert(Len(attester_0.get()) == Int(32)),
        Assert(Len(attester_1.get()) == Int(32)),
        Assert(Len(attester_2.get()) == Int(32)),
        Assert(attester_0.get() != attester_1.get()),
        Assert(attester_1.get() != attester_2.get()),
        Assert(attester_0.get() != attester_2.get()),
        
        App.globalPut(NEXT_ID, Int(0)),
        App.globalPut(ATTESTER_PK_0, attester_0.get()),
        App.globalPut(ATTESTER_PK_1, attester_1.get()),
        App.globalPut(ATTESTER_PK_2, attester_2.get()),
        App.globalPut(APP_ADMIN, admin.get()),
        App.globalPut(PROTOCOL_VERSION, Int(1)),
        App.globalPut(USDC_ASA_ID, Int(10458941)),
    )

@router.method
def opup(n: abi.Uint64) -> Expr:
    i = ScratchVar(TealType.uint64)
    return Seq(
        i.store(Int(0)),
        While(i.load() < n.get()).Do(
            i.store(i.load() + Int(1))
        )
    )

@router.method
def opt_in_asa(asset: abi.Asset) -> Expr:
    return Seq(
        Assert(Txn.sender() == App.globalGet(APP_ADMIN)),
        Assert(asset.asset_id() == App.globalGet(USDC_ASA_ID)),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: asset.asset_id(),
            TxnField.asset_receiver: Global.current_application_address(),
            TxnField.asset_amount: Int(0),
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.Submit(),
    )



@router.method
def authorize(
    seller: abi.Address,
    amount_pay: abi.Uint64,
    amount_bounty: abi.Uint64,
    deadline_round: abi.Uint64,
    nonce: abi.StaticBytes[Literal[32]],
    hash_q: abi.StaticBytes[Literal[32]],
    hash_c: abi.StaticBytes[Literal[32]],
    buyer_signature: abi.StaticBytes[Literal[64]],
    axfer_usdc: abi.AssetTransferTransaction,
    pay_algo: abi.PaymentTransaction,
    *, output: abi.Uint64
) -> Expr:
    buyer = Txn.sender()
    usdc_id = App.globalGet(USDC_ASA_ID)
    session_id = App.globalGet(NEXT_ID)
    
    # Message to verify
    message = Concat(
        PROTOCOL_DOMAIN,
        AUTH_PREFIX,
        Itob(Global.current_application_id()),
        Global.genesis_hash(),
        buyer,
        seller.get(),
        Itob(usdc_id),
        Itob(amount_pay.get()),
        Itob(amount_bounty.get()),
        Itob(deadline_round.get()),
        nonce.get(),
        hash_q.get(),
        hash_c.get()
    )
    
    return Seq(
        Assert(amount_pay.get() > Int(0)),
        Assert(amount_bounty.get() > Int(0)),
        Assert(deadline_round.get() > Global.round()),
        
        # Verify group transactions
        Assert(axfer_usdc.get().asset_receiver() == Global.current_application_address()),
        Assert(axfer_usdc.get().xfer_asset() == usdc_id),
        Assert(axfer_usdc.get().asset_amount() == amount_pay.get()),
        Assert(axfer_usdc.get().sender() == buyer),
        
        Assert(pay_algo.get().receiver() == Global.current_application_address()),
        Assert(pay_algo.get().amount() == amount_bounty.get()),
        Assert(pay_algo.get().sender() == buyer),
        
        # Verify Ed25519 signature
        Assert(Ed25519Verify_Bare(message, buyer_signature.get(), buyer)),
        
        # Nonce uniqueness check
        (nonce_len := App.box_length(get_nonce_box_key(nonce.get()))),
        Assert(Not(nonce_len.hasValue())),
        App.box_put(get_nonce_box_key(nonce.get()), Itob(session_id)),
        
        # Create session box
        (s_state := abi.Uint8()).set(STATE_AUTHORIZED),
        (s_buyer := abi.Address()).set(buyer),
        (s_seller := abi.Address()).set(seller.get()),
        (s_asset := abi.Uint64()).set(usdc_id),
        (s_amount_pay := abi.Uint64()).set(amount_pay.get()),
        (s_amount_bounty := abi.Uint64()).set(amount_bounty.get()),
        (s_deadline := abi.Uint64()).set(deadline_round.get()),
        (s_nonce := abi.StaticBytesTypeSpec(32).new_instance()).set(nonce.get()),
        (s_hash_q := abi.StaticBytesTypeSpec(32).new_instance()).set(hash_q.get()),
        (s_hash_c := abi.StaticBytesTypeSpec(32).new_instance()).set(hash_c.get()),
        (s_hash_p := abi.StaticBytesTypeSpec(32).new_instance()).set(BytesZero(Int(32))),
        (s_bounty_paid := abi.Uint8()).set(Int(0)),
        (s_threshold := abi.Uint8()).set(Int(2)),
        (s_count := abi.Uint8()).set(Int(3)),
        
        (box_data := SessionRecord()).set(
            s_state, s_buyer, s_seller, s_asset, s_amount_pay, s_amount_bounty,
            s_deadline, s_nonce, s_hash_q, s_hash_c, s_hash_p,
            s_bounty_paid, s_threshold, s_count
        ),
        App.box_put(get_session_box_key(session_id), box_data.encode()),
        
        # Increment next_id
        App.globalPut(NEXT_ID, session_id + Int(1)),
        
        Log(Concat(Bytes("AUTHORIZED:"), Itob(session_id))),
        output.set(session_id)
    )

@Subroutine(TealType.bytes)
def get_attester_pk(index: Expr) -> Expr:
    return Cond(
        [index == Int(0), App.globalGet(ATTESTER_PK_0)],
        [index == Int(1), App.globalGet(ATTESTER_PK_1)],
        [index == Int(2), App.globalGet(ATTESTER_PK_2)],
    )

@router.method
def settle(
    session_id: abi.Uint64,
    hash_p: abi.StaticBytes[Literal[32]],
    seller_signature: abi.StaticBytes[Literal[64]],
    attester_index_1: abi.Uint8,
    attester_signature_1: abi.StaticBytes[Literal[64]],
    attester_index_2: abi.Uint8,
    attester_signature_2: abi.StaticBytes[Literal[64]],
    relayer: abi.Address,
) -> Expr:
    box_key = get_session_box_key(session_id.get())
    box_data = App.box_get(box_key)
    session = SessionRecord()
    
    return Seq(
        box_data,
        Assert(box_data.hasValue()),
        session.decode(box_data.value()),
        
        (state := abi.Uint8()).set(session.state),
        Assert(state.get() == STATE_AUTHORIZED),
        
        (deadline_round := abi.Uint64()).set(session.deadline_round),
        Assert(Global.round() <= deadline_round.get()),
        
        (buyer := abi.Address()).set(session.buyer),
        (seller := abi.Address()).set(session.seller),
        Assert(relayer.get() != buyer.get()),
        Assert(relayer.get() != seller.get()),
        
        Assert(attester_index_1.get() != attester_index_2.get()),
        Assert(attester_index_1.get() <= Int(2)),
        Assert(attester_index_2.get() <= Int(2)),
        
        (bounty_paid := abi.Uint8()).set(session.bounty_paid),
        Assert(bounty_paid.get() == Int(0)),
        
        # Verify Seller Signature
        (nonce := abi.StaticBytesTypeSpec(32).new_instance()).set(session.nonce),
        (msg_s := ScratchVar(TealType.bytes)).store(Concat(
            PROTOCOL_DOMAIN,
            SETTLE_PREFIX,
            Itob(Global.current_application_id()),
            Global.genesis_hash(),
            Itob(session_id.get()),
            nonce.get(),
            hash_p.get()
        )),
        
        Assert(Ed25519Verify_Bare(msg_s.load(), seller_signature.get(), seller.get())),
        
        # Verify Attester Signatures
        (hash_q := abi.StaticBytesTypeSpec(32).new_instance()).set(session.hash_q),
        (hash_c := abi.StaticBytesTypeSpec(32).new_instance()).set(session.hash_c),
        (msg_a := ScratchVar(TealType.bytes)).store(Concat(
            PROTOCOL_DOMAIN,
            ATTEST_PREFIX,
            Itob(Global.current_application_id()),
            Global.genesis_hash(),
            Itob(session_id.get()),
            nonce.get(),
            Extract(Itob(VERDICT_PASS), Int(7), Int(1)),
            hash_q.get(),
            hash_c.get(),
            hash_p.get()
        )),
        
        Assert(Ed25519Verify_Bare(msg_a.load(), attester_signature_1.get(), get_attester_pk(attester_index_1.get()))),
        Assert(Ed25519Verify_Bare(msg_a.load(), attester_signature_2.get(), get_attester_pk(attester_index_2.get()))),
        
        # Transfers
        (amount_pay := abi.Uint64()).set(session.amount_pay),
        (asset_id := abi.Uint64()).set(session.asset_id),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: asset_id.get(),
            TxnField.asset_receiver: seller.get(),
            TxnField.asset_amount: amount_pay.get(),
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.Submit(),
        
        (amount_bounty := abi.Uint64()).set(session.amount_bounty),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver: relayer.get(),
            TxnField.amount: amount_bounty.get(),
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.Submit(),
        
        # Update State
        (s_state := abi.Uint8()).set(STATE_RELEASED),
        (s_bounty_paid := abi.Uint8()).set(Int(1)),
        (s_threshold := abi.Uint8()).set(Int(2)),
        (s_count := abi.Uint8()).set(Int(3)),
        
        session.set(
            s_state, buyer, seller, asset_id, amount_pay, amount_bounty,
            deadline_round, nonce, hash_q, hash_c, hash_p,
            s_bounty_paid, s_threshold, s_count
        ),
        App.box_put(box_key, session.encode()),
        Log(Concat(Bytes("RELEASED:"), Itob(session_id.get())))
    )

@router.method
def refund(
    session_id: abi.Uint64,
    reason: abi.Uint8,
    attester_index_1: abi.Uint8,
    attester_signature_1: abi.StaticBytes[Literal[64]],
    attester_index_2: abi.Uint8,
    attester_signature_2: abi.StaticBytes[Literal[64]],
    relayer: abi.Address,
) -> Expr:
    box_key = get_session_box_key(session_id.get())
    box_data = App.box_get(box_key)
    session = SessionRecord()
    
    return Seq(
        box_data,
        Assert(box_data.hasValue()),
        session.decode(box_data.value()),
        
        (state := abi.Uint8()).set(session.state),
        Assert(state.get() == STATE_AUTHORIZED),
        
        (buyer := abi.Address()).set(session.buyer),
        (seller := abi.Address()).set(session.seller),
        Assert(relayer.get() != buyer.get()),
        Assert(relayer.get() != seller.get()),
        
        (bounty_paid := abi.Uint8()).set(session.bounty_paid),
        Assert(bounty_paid.get() == Int(0)),
        
        (nonce := abi.StaticBytesTypeSpec(32).new_instance()).set(session.nonce),
        (hash_q := abi.StaticBytesTypeSpec(32).new_instance()).set(session.hash_q),
        (hash_c := abi.StaticBytesTypeSpec(32).new_instance()).set(session.hash_c),
        (hash_p := abi.StaticBytesTypeSpec(32).new_instance()).set(session.hash_p),
        
        If(reason.get() == REASON_TIMEOUT).Then(
            Seq(
                (deadline_round := abi.Uint64()).set(session.deadline_round),
                Assert(Global.round() > deadline_round.get())
            )
        ).ElseIf(reason.get() == REASON_ATTESTED_FAIL).Then(
            Seq(
                Assert(attester_index_1.get() != attester_index_2.get()),
                Assert(attester_index_1.get() <= Int(2)),
                Assert(attester_index_2.get() <= Int(2)),
                
                (msg_a := ScratchVar(TealType.bytes)).store(Concat(
                    PROTOCOL_DOMAIN,
                    ATTEST_PREFIX,
                    Itob(Global.current_application_id()),
                    Global.genesis_hash(),
                    Itob(session_id.get()),
                    nonce.get(),
                    Extract(Itob(VERDICT_FAIL), Int(7), Int(1)),
                    hash_q.get(),
                    hash_c.get(),
                    hash_p.get()
                )),
                
                Assert(Ed25519Verify_Bare(msg_a.load(), attester_signature_1.get(), get_attester_pk(attester_index_1.get()))),
                Assert(Ed25519Verify_Bare(msg_a.load(), attester_signature_2.get(), get_attester_pk(attester_index_2.get()))),
            )
        ).Else(
            Err()
        ),
        
        # Transfers
        (amount_pay := abi.Uint64()).set(session.amount_pay),
        (asset_id := abi.Uint64()).set(session.asset_id),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: asset_id.get(),
            TxnField.asset_receiver: buyer.get(),
            TxnField.asset_amount: amount_pay.get(),
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.Submit(),
        
        (amount_bounty := abi.Uint64()).set(session.amount_bounty),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.receiver: relayer.get(),
            TxnField.amount: amount_bounty.get(),
            TxnField.fee: Int(0),
        }),
        InnerTxnBuilder.Submit(),
        
        # Update State
        (deadline_round := abi.Uint64()).set(session.deadline_round),
        (s_state := abi.Uint8()).set(STATE_REFUNDED),
        (s_bounty_paid := abi.Uint8()).set(Int(1)),
        (s_threshold := abi.Uint8()).set(Int(2)),
        (s_count := abi.Uint8()).set(Int(3)),
        
        session.set(
            s_state, buyer, seller, asset_id, amount_pay, amount_bounty,
            deadline_round, nonce, hash_q, hash_c, hash_p,
            s_bounty_paid, s_threshold, s_count
        ),
        App.box_put(box_key, session.encode()),
        Log(Concat(Bytes("REFUNDED:"), Itob(session_id.get()), Extract(Itob(reason.get()), Int(7), Int(1))))
    )

def get_router():
    return router
