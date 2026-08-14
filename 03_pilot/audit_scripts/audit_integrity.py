import hashlib
import json
import csv
import datetime
import os

def calculate_sha256(file_path):
    if not os.path.exists(file_path):
        return None
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def main():
    # 1. Manifest
    files_to_hash = [
        "../results/pilot/transactions.csv",
        "../results/pilot/algo_usd_price.csv",
        "../artifacts/tx_ids_pilot.txt",
        "../results/pilot/pilot_report.md",
        "../artifacts/contract_app_id_testnet.txt",
        "../config.yaml",
        "../02_clients/test_vectors.json"
    ]
    manifest = {}
    for f in files_to_hash:
        h = calculate_sha256(f)
        if h:
            manifest[os.path.basename(f)] = {
                "sha256": h,
                "timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat() + "Z"
            }
            
    with open("../artifacts/pilot_raw_data_manifest.json", "w") as out_manifest:
        json.dump(manifest, out_manifest, indent=4)
        
    # 2. Mapping
    with open("../artifacts/tx_ids_pilot.txt", "r") as f:
        tx_ids = [line.strip() for line in f if line.strip()]
        
    session_mapping = {}
    with open("../results/pilot/transactions.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            session_mapping[row["session_id"]] = []

    session_order = list(session_mapping.keys())
    
    tx_idx = 0
    for s_id in session_order:
        if s_id in [session_order[-2], session_order[-1]]:
            for attempt in range(1, 4):
                if tx_idx < len(tx_ids):
                    session_mapping[s_id].append(tx_ids[tx_idx])
                    tx_idx += 1
        else:
            if tx_idx < len(tx_ids):
                session_mapping[s_id].append(tx_ids[tx_idx])
                tx_idx += 1
                
    with open("../artifacts/tx_id_to_session_mapping.json", "w") as f:
        json.dump(session_mapping, f, indent=4)
        
    # 3. Data Quality Table (print to console)
    missing = {"outcome": 0, "final_ts": 0}
    with open("../results/pilot/transactions.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row["outcome"]: missing["outcome"] += 1
            if not row["finality_timestamp"]: missing["final_ts"] += 1
            
    print(f"Data Quality Table:")
    print(f"outcome missing: {missing['outcome']}")
    print(f"final_ts missing: {missing['final_ts']} (Expected for failed sessions)")
    
if __name__ == '__main__':
    main()
