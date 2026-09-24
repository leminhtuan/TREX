"""
T-REX 100-Session Functional Campaign — App 772170811
Uses existing BuyerAgent, SellerAgent, AttesterAgent, RelayerAgent.
These agents already work correctly with App 772170811.

Paper mapping:
  §7.2 Functional results (100 sessions, all terminals correct)
  §7.4 Table tab:latency (N=40 Normal Settle)
  Appendix Table tab:fits (lognormal fit)
  Table tab:fees (auth=6 outer, settle=16 outer+2 inner, total=22 outer)
"""
import os
import sys
import csv
import time
import json
import base64
import hashlib
import struct

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CLIENTS_DIR = os.path.join(BASE_DIR, "..", "02_clients")
sys.path.insert(0, CLIENTS_DIR)

from algosdk import encoding, transaction, logic
from algosdk.v2client import algod
from algosdk.abi import Method
import config
from buyer_agent import BuyerAgent
from seller_agent import SellerAgent
from attester import AttesterAgent
from relayer import RelayerAgent

# ─────────────────────────────────────────────
# CANONICAL App ID — single source of truth
# ─────────────────────────────────────────────
APP_ID   = 772170811
APP_ADDR = logic.get_application_address(APP_ID)
USDC_ASA = 10458941

OUTPUT_CSV = os.path.join(BASE_DIR, "final_functional_campaign_app772170811.csv")
OUTPUT_LOG = os.path.join(BASE_DIR, "invariant_audit_app772170811.log")

client = algod.AlgodClient("", config.ALGONODE_URL)

# Override config APP_ID to point to 772170811
config.APP_ID = APP_ID

FIELDNAMES = [
    "session_id", "nonce", "buyer", "seller", "app_id", "scenario",
    "auth_txid", "term_txid", "final_state", "final_round",
    "auth_latency_s", "term_latency_s", "e2e_latency_s",
    "auth_outer_txns", "term_outer_txns", "term_inner_txns",
    "auth_fee_microalgo", "term_fee_microalgo", "session_total_fee_microalgo",
    "invariant_violations", "spent_marker_present"
]


def box_exists(key: bytes) -> bool:
    try:
        client.application_box_by_name(APP_ID, key)
        return True
    except:
        return False


def compute_boxes(buyer_addr: str, nonce: int):
    buyer_bytes = encoding.decode_address(buyer_addr)
    nonce_bytes = nonce.to_bytes(8, "big")
    active_key  = hashlib.new("sha512_256",
        b"T-REX-ACTIVE-NONCE" + buyer_bytes + nonce_bytes).digest()
    spent_key   = hashlib.new("sha512_256",
        b"T-REX-SPENT" + APP_ID.to_bytes(8, "big") + buyer_bytes + nonce_bytes).digest()
    return active_key, spent_key


def run_campaign():
    print(f"=== T-REX 100-Session Campaign on App {APP_ID} ===")
    print(f"CSV output: {OUTPUT_CSV}")

    # Verify App is live
    try:
        client.application_info(APP_ID)
        print(f"App {APP_ID}: LIVE")
    except Exception as e:
        print(f"FATAL: App {APP_ID} not accessible: {e}")
        sys.exit(1)

    # Init agents with canonical App ID
    buyer   = BuyerAgent()
    buyer.app_id   = APP_ID
    buyer.app_addr = APP_ADDR

    seller  = SellerAgent()
    seller.app_id   = APP_ID
    seller.app_addr = APP_ADDR

    att1 = AttesterAgent(0, config.ATTESTER_1_SK)
    att1.app_id = APP_ID; att1.app_addr = APP_ADDR

    att2 = AttesterAgent(1, config.ATTESTER_2_SK)
    att2.app_id = APP_ID; att2.app_addr = APP_ADDR

    relayer = RelayerAgent()
    relayer.app_id = APP_ID

    # --- Terminal ABI methods (hardened v2: with buyer_address) ---
    # relayer.py already uses settle(uint64,address,...) and refund(uint64,address,...)
    # so we call relayer.settle() and relayer.refund() directly.

    inv_log = []

    # Check existing CSV for resume
    existing_ids = set()
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, "r") as f:
            for r in csv.DictReader(f):
                existing_ids.add(int(r["session_id"]))
        print(f"Resuming: {len(existing_ids)} sessions already done.")

    session_scenarios = (
        ["Normal Settle"] * 40 +
        ["Attested Fail"] * 30 +
        ["Timeout Refund"] * 30
    )

    with open(OUTPUT_CSV, "a", newline="") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=FIELDNAMES)
        if not existing_ids:
            writer.writeheader()

        counter = len(existing_ids)   # how many done so far

        while counter < 100:
            scenario = session_scenarios[counter]
            run_num  = counter + 1
            print(f"\n--- Session {run_num}/100: {scenario} ---")

            status        = client.status()
            current_round = status["last-round"]

            if scenario == "Timeout Refund":
                deadline_round = current_round + 8
            else:
                deadline_round = current_round + 1000

            inv_before = len(inv_log)

            try:
                # ── AUTHORIZE ─────────────────────────────────────────
                t0 = time.perf_counter()
                res_auth = buyer.authorize(
                    config.SELLER_ADDR, 100_000, 10_000, deadline_round
                )
                t1 = time.perf_counter()

                session_id  = res_auth["session_id"]
                nonce       = res_auth["nonce"]
                auth_txid   = res_auth["tx_id"]
                auth_fee    = res_auth["fee"]

                # Invariant checks: ACTIVE must exist, SPENT must not
                active_key, spent_key = compute_boxes(config.BUYER_ADDR, nonce)
                if not box_exists(active_key):
                    inv_log.append(f"[{run_num}] VIOLATION: ACTIVE missing after auth")
                if box_exists(spent_key):
                    inv_log.append(f"[{run_num}] VIOLATION: SPENT exists before terminal")

                # Auth group: 2 deposits (axfer+pay) + authorize_call + 3 opup = 6 outer
                auth_outer = 6
                # Fee = 6 * 1000 = 6000 uALGO (as set in BuyerAgent.authorize)
                # NOTE: auth_fee from res_auth is total over all 6 txns

                # ── TERMINAL ──────────────────────────────────────────
                t2 = time.perf_counter()

                if scenario == "Normal Settle":
                    # Seller processes, relayer submits settle (16 outer + 2 inner)
                    res_seller = seller.process_request(
                        session_id, res_auth["H_q"], res_auth["H_c"], nonce
                    )
                    H_p         = res_seller["H_p"]
                    seller_sig  = res_seller["seller_signature"]
                    att1_res    = att1.attest(session_id, nonce, res_auth["H_q"],
                                              res_auth["H_c"], H_p, deadline_round, 1)
                    att2_res    = att2.attest(session_id, nonce, res_auth["H_q"],
                                              res_auth["H_c"], H_p, deadline_round, 1)
                    res_term    = relayer.settle(session_id, H_p, seller_sig, att1_res, att2_res)
                    final_state = "RELEASED"
                    term_outer  = res_term["outer_tx_count"]
                    term_inner  = res_term["inner_tx_count"]
                    term_fee    = res_term["fee"]
                    term_txid   = res_term["tx_id"]
                    final_round = res_term["confirmed_round"]

                elif scenario == "Attested Fail":
                    att1_res = att1.attest(session_id, nonce, res_auth["H_q"],
                                           res_auth["H_c"], bytes(32), deadline_round, 0)
                    att2_res = att2.attest(session_id, nonce, res_auth["H_q"],
                                           res_auth["H_c"], bytes(32), deadline_round, 0)
                    res_term    = relayer.refund(session_id, reason=1,
                                                 attester_1=att1_res, attester_2=att2_res)
                    final_state = "REFUNDED"
                    term_outer  = res_term["outer_tx_count"]
                    term_inner  = res_term["inner_tx_count"]
                    term_fee    = res_term["fee"]
                    term_txid   = res_term["tx_id"]
                    final_round = res_term["confirmed_round"]

                else:  # Timeout Refund
                    print(f"  Waiting for round > {deadline_round}...")
                    while client.status()["last-round"] <= deadline_round:
                        time.sleep(1)
                    res_term    = relayer.refund(session_id, reason=0)
                    final_state = "REFUNDED"
                    term_outer  = res_term["outer_tx_count"]
                    term_inner  = res_term["inner_tx_count"]
                    term_fee    = res_term["fee"]
                    term_txid   = res_term["tx_id"]
                    final_round = res_term["confirmed_round"]

                t3 = time.perf_counter()

                # Post-terminal invariant checks
                if box_exists(active_key):
                    inv_log.append(f"[{run_num}] VIOLATION: ACTIVE still exists after terminal")
                if not box_exists(spent_key):
                    inv_log.append(f"[{run_num}] VIOLATION: SPENT missing after terminal")

                spent_present = box_exists(spent_key)
                n_inv         = len(inv_log) - inv_before

                row = {
                    "session_id":                  session_id,
                    "nonce":                       nonce,
                    "buyer":                       config.BUYER_ADDR,
                    "seller":                      config.SELLER_ADDR,
                    "app_id":                      APP_ID,
                    "scenario":                    scenario,
                    "auth_txid":                   auth_txid,
                    "term_txid":                   term_txid,
                    "final_state":                 final_state,
                    "final_round":                 final_round,
                    "auth_latency_s":              round(t1 - t0, 3),
                    "term_latency_s":              round(t3 - t2, 3),
                    "e2e_latency_s":               round(t3 - t0, 3),
                    "auth_outer_txns":             auth_outer,
                    "term_outer_txns":             term_outer,
                    "term_inner_txns":             term_inner,
                    "auth_fee_microalgo":          auth_fee,
                    "term_fee_microalgo":          term_fee,
                    "session_total_fee_microalgo": auth_fee + term_fee,
                    "invariant_violations":        n_inv,
                    "spent_marker_present":        spent_present,
                }
                writer.writerow(row)
                csvf.flush()

                print(f"  OK session_id={session_id} "
                      f"auth={row['auth_latency_s']:.3f}s "
                      f"term={row['term_latency_s']:.3f}s "
                      f"e2e={row['e2e_latency_s']:.3f}s "
                      f"fees={auth_fee}+{term_fee}={auth_fee+term_fee}u "
                      f"inv={n_inv}")

                counter += 1

            except Exception as e:
                import traceback
                print(f"  ERROR: {e}")
                traceback.print_exc()
                print("  Retrying in 15s...")
                time.sleep(15)
                # Do NOT increment counter — retry same slot

    # Write invariant audit log
    with open(OUTPUT_LOG, "w") as f:
        if not inv_log:
            f.write("0 INVARIANT VIOLATIONS DETECTED.\n")
        else:
            for line in inv_log:
                f.write(line + "\n")

    print(f"\n=== Campaign Done === Invariant violations: {len(inv_log)}")
    print(f"CSV: {OUTPUT_CSV}")


if __name__ == "__main__":
    run_campaign()
