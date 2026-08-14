import os
import sys
import csv
import json
import base64
import requests
import time
from pathlib import Path
import hashlib
import urllib.parse

# Endpoints
INDEXER_URL = "https://testnet-idx.algonode.cloud/v2"
ALGOD_URL = "https://testnet-api.algonode.cloud/v2"

project_root = Path(os.path.abspath(__file__)).parent.parent.parent
results_pilot_dir = project_root / 'results' / 'pilot'
artifacts_dir = project_root / 'artifacts'
reports_dir = project_root / 'reports'

def query_tx(txid):
    url = f"{INDEXER_URL}/transactions/{txid}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('transaction')
    except:
        pass
    return None

def query_group(group_id_b64):
    gid_safe = urllib.parse.quote(group_id_b64)
    url = f"{INDEXER_URL}/transactions?group-id={gid_safe}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('transactions', [])
    except:
        pass
    return []

def query_app(app_id):
    url = f"{ALGOD_URL}/applications/{app_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None
        
def get_deployment_tx(app_id):
    url = f"{INDEXER_URL}/transactions?application-id={app_id}&tx-type=appl"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            txs = resp.json().get('transactions', [])
            for tx in txs:
                if 'created-application-index' in tx:
                    return tx
    except:
        pass
    return None

def main():
    print("Loading TXIDs...")
    with open(artifacts_dir / 'tx_ids_pilot.txt', 'r', encoding='utf-8') as f:
        txid_list = [line.strip() for line in f if line.strip()]
        
    session_mapping = {}
    with open(results_pilot_dir / 'transactions.csv', 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['tx_id']:
                session_mapping[row['tx_id']] = row['session_id']
                
    audit_rows = []
    app_old_count = 0
    app_final_count = 0
    unverifiable_count = 0
    
    session_app_map = {}
    
    print("Querying Transactions from Indexer...")
    for txid in txid_list:
        time.sleep(0.1)
        tx = query_tx(txid)
        
        sid = session_mapping.get(txid, "NA")
        tx_source = "transactions.csv" if sid != "NA" else "tx_ids_pilot.txt"
        
        lookup_status = "NOT_VERIFIABLE"
        app_id = "NA"
        method = "NA"
        conf_round = "NA"
        group_id = "NA"
        sender = "NA"
        note = "NA"
        
        if tx:
            conf_round = tx.get('confirmed-round', "NA")
            sender = tx.get('sender', "NA")
            group_id = tx.get('group', "NA")
            
            app_txn = None
            if tx.get('tx-type') == 'appl':
                app_txn = tx['application-transaction']
            elif group_id != "NA":
                time.sleep(0.1)
                gtxs = query_group(group_id)
                for gtx in gtxs:
                    if gtx.get('tx-type') == 'appl':
                        app_txn = gtx.get('application-transaction')
                        break
            
            if app_txn:
                app_id = app_txn.get('application-id', "NA")
                args = app_txn.get('application-args', [])
                if args:
                    try:
                        method = base64.b64decode(args[0]).decode('utf-8', errors='ignore')
                        if not all(32 <= ord(c) < 127 for c in method):
                            method = base64.b64decode(args[0]).hex()
                    except:
                        method = args[0]
                
                if str(app_id) != "NA":
                    lookup_status = "VERIFIED"
                    if str(app_id) == "769241061": app_old_count += 1
                    elif str(app_id) == "769248116": app_final_count += 1
                else:
                    note = "AppID missing in app-txn"
            else:
                note = "No appl transaction in group"
                lookup_status = "NOT_FOUND"
                unverifiable_count += 1
        else:
            lookup_status = "NOT_FOUND"
            note = "Transaction not found on Indexer"
            unverifiable_count += 1
            
        if sid != "NA":
            if sid not in session_app_map:
                session_app_map[sid] = set()
            if str(app_id) != "NA":
                session_app_map[sid].add(str(app_id))
            
        audit_rows.append({
            "session_id": sid,
            "tx_id": txid,
            "tx_source": tx_source,
            "lookup_status": lookup_status,
            "application_id": app_id,
            "method": method,
            "confirmed_round": conf_round,
            "group_id": group_id,
            "sender": sender,
            "evidence_note": note
        })
        
    print("Writing TX Audit CSV...")
    with open(artifacts_dir / 'pilot_tx_application_audit.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=audit_rows[0].keys())
        writer.writeheader()
        writer.writerows(audit_rows)
        
    print("Auditing Deployment Transactions...")
    app_ids_to_check = [769241061, 769248116]
    deployment_audit = {}
    
    for aid in app_ids_to_check:
        tx = get_deployment_tx(aid)
        if tx:
            cround = tx.get('confirmed-round')
            app_txn = tx.get('application-transaction', {})
            apap_b64 = app_txn.get('approval-program', "")
            apsu_b64 = app_txn.get('clear-state-program', "")
            apap_bytes = base64.b64decode(apap_b64) if apap_b64 else b""
            apsu_bytes = base64.b64decode(apsu_b64) if apsu_b64 else b""
            deployment_audit[str(aid)] = {
                "creation_txid": tx.get('id'),
                "creation_round": cround,
                "approval_program_len": len(apap_bytes),
                "approval_program_sha256": hashlib.sha256(apap_bytes).hexdigest() if apap_bytes else None,
                "clear_program_len": len(apsu_bytes),
                "clear_program_sha256": hashlib.sha256(apsu_bytes).hexdigest() if apsu_bytes else None
            }
        else:
            app_info = query_app(aid)
            if app_info:
                params = app_info.get('params', {})
                apap_b64 = params.get('approval-program', "")
                apsu_b64 = params.get('clear-state-program', "")
                apap_bytes = base64.b64decode(apap_b64) if apap_b64 else b""
                apsu_bytes = base64.b64decode(apsu_b64) if apsu_b64 else b""
                deployment_audit[str(aid)] = {
                    "creation_txid": "NOT_FOUND_ON_INDEXER",
                    "creation_round": "ALGOD_LATEST",
                    "approval_program_len": len(apap_bytes),
                    "approval_program_sha256": hashlib.sha256(apap_bytes).hexdigest() if apap_bytes else None,
                    "clear_program_len": len(apsu_bytes),
                    "clear_program_sha256": hashlib.sha256(apsu_bytes).hexdigest() if apsu_bytes else None
                }
            else:
                deployment_audit[str(aid)] = {"error": "Could not fetch app info"}
                
    with open(artifacts_dir / 'app_deployment_audit.json', 'w', encoding='utf-8') as f:
        json.dump(deployment_audit, f, indent=2)

    consistent_final = sum(1 for s, apps in session_app_map.items() if len(apps) == 1 and "769248116" in apps)
    mixed_unknown = len(session_app_map) - consistent_final
    
    print("\nGenerating Report...")
    
    md = f'''# Application ID Forensic Verification Report

## 1. Overview
This audit verifies the exact Application ID invoked by each transaction during the pilot phase.
Two Application IDs were investigated:
- App Old: 769241061
- App Final: 769248116

## 2. Transaction Audits
Total TXIDs analyzed: {len(txid_list)}
- VERIFIED (App Old): {app_old_count}
- VERIFIED (App Final): {app_final_count}
- NOT_FOUND/NOT_VERIFIABLE: {unverifiable_count}

## 3. Session Consistency
- Sessions consistently using App Final: {consistent_final}
- Sessions with mixed or unknown Apps: {mixed_unknown}

## 4. Deployment Forensics
`json
{json.dumps(deployment_audit, indent=2)}
`

## 5. Conclusion
Based on strictly verifiable on-chain evidence:
'''
    if app_old_count == 0 and unverifiable_count == 0 and app_final_count > 0:
        md += "a) Toan bo pilot dung app final (769248116).\n"
    elif app_final_count > 0 and app_old_count > 0:
        md += "b) Chi mot phan dung app final.\n"
    elif app_final_count > 0 and unverifiable_count > 0:
        md += f"c) Da so dung app final (769248116), nhung co {unverifiable_count} giao dich khong the xac minh do API loi hoac transaction failed/pending.\n"
    else:
        md += "c) Khong the xac minh day du.\n"
        
    md += "\n(Note: No assumptions regarding OpUp were made without direct deployment bytecode evidence.)\n"

    assert all(ord(c) >= 32 or c in "\n\t\r" for c in md), "Control characters found!"
    
    (reports_dir / 'appid_verification_v2.md').write_text(md, encoding='utf-8')
    
    print("\n--- SAFETY OUTPUT ---")
    print(f"Total TXIDs checked: {len(txid_list)}")
    print(f"Total VERIFIED: {app_old_count + app_final_count}")
    print(f"Total NOT_FOUND/NOT_VERIFIABLE: {unverifiable_count}")
    print(f"App 769241061: {app_old_count} txs")
    print(f"App 769248116: {app_final_count} txs")
    print("CONFIRMATION: Zero transactions submitted. Read-only strictly followed.")

if __name__ == '__main__':
    main()
