import csv
from datetime import datetime
import statistics

def parse_iso(ts):
    if not ts or ts == "NA" or ts == "N/A": return None
    # e.g., 2026-08-14T13:45:15.920065Z
    try:
        ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except:
        return None

def calc_diff(t1, t2):
    if not t1 or not t2: return "NA"
    diff = t2 - t1
    return diff.total_seconds() * 1000.0

def main():
    rows = []
    with open("../results/pilot/transactions.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            
    out_rows = []
    auth_latencies = []
    attest_latencies = []
    settle_latencies = []
    e2e_latencies = []
    
    for r in rows:
        req = parse_iso(r["request_timestamp"])
        auth_sub = parse_iso(r["app_call_submitted_timestamp"])
        auth_conf = parse_iso(r["payment_authorized_timestamp"])
        att = parse_iso(r["attestation_timestamp"])
        fin = parse_iso(r["finality_timestamp"])
        
        # We don't have relayer_submitted in transactions.csv, only attestation_timestamp and finality_timestamp
        # Wait, the prompt says: attestation_latency = relayer_submitted - attestation
        # settlement_latency = finality - relayer_submitted
        # Since relayer_submitted isn't captured in the CSV separately (the script sends settlement tx immediately after attestation),
        # we will use finality_timestamp - attestation_timestamp for settlement latency, and mark attestation->relayer submission as NA or 0.
        # Looking at transactions.csv, attestation_timestamp == payment_authorized_timestamp often? No, attestation is done after.
        
        l_auth = calc_diff(auth_sub, auth_conf)
        l_attest = "NA" # Relayer submitted not explicitly tracked
        l_settle = calc_diff(att, fin) if (att and fin) else "NA"
        l_e2e = calc_diff(req, fin) if (req and fin) else "NA"
        
        status = "VALID"
        if l_auth == "NA" or l_auth == 0: status = "NOT VALID"
        
        out_rows.append({
            "session_id": r["session_id"],
            "authorization_latency_ms": f"{l_auth:.3f}" if l_auth != "NA" else "NA",
            "attestation_latency_ms": "NA",
            "settle_latency_ms": f"{l_settle:.3f}" if l_settle != "NA" else "NA",
            "end_to_end_latency_ms": f"{l_e2e:.3f}" if l_e2e != "NA" else "NA",
            "status": status,
            "note": "Relayer_submitted TS missing; Settlement latency is final-attest"
        })
        
        if l_auth != "NA" and l_auth > 0: auth_latencies.append(l_auth)
        if l_settle != "NA" and l_settle > 0: settle_latencies.append(l_settle)
        if l_e2e != "NA" and l_e2e > 0: e2e_latencies.append(l_e2e)
        
    with open("../results/pilot/latency_audit.csv", "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["session_id", "authorization_latency_ms", "attestation_latency_ms", "settle_latency_ms", "end_to_end_latency_ms", "status", "note"])
        writer.writeheader()
        writer.writerows(out_rows)
        
    def get_percentiles(latencies):
        if not latencies: return "NA", "NA", "NA"
        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) > 0 else latencies[-1]
        p99 = latencies[int(len(latencies) * 0.99)] if len(latencies) > 0 else latencies[-1]
        return p50, p95, p99

    a_p50, a_p95, a_p99 = get_percentiles(auth_latencies)
    print(f"Auth Latency: p50={a_p50} p95={a_p95} p99={a_p99}")
    e_p50, e_p95, e_p99 = get_percentiles(e2e_latencies)
    print(f"E2E Latency: p50={e_p50} p95={e_p95} p99={e_p99}")

if __name__ == '__main__':
    main()
