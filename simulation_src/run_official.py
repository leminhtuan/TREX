"""
run_official.py - Orchestrates the 160-run reduced design for T-REX simulation.
VALID_SIMULATION_ONLY: model-based synthetic estimates under stated assumptions.
No Algorand API calls. No transactions submitted.
"""
import sys, csv, json, time, hashlib, datetime
from pathlib import Path

sys.path.insert(0, '.')

from run_simulation import get_reduced_design, run_one
import metrics as m
import validators

def serialize_events(event_rows):
    res = []
    for e in event_rows:
        res.append({
            'run_id': e.run_id,
            'event_id': e.event_id,
            'session_id': e.session_id,
            'event_type': e.event_type,
            'simulated_timestamp_s': e.simulated_timestamp_s,
            'seller_honest': e.seller_honest,
            'attester_honest': e.attester_honest,
            'packet_dropped': e.packet_dropped,
            'relayer_honest': e.relayer_honest,
            'failure_mode': e.failure_mode,
            'outcome': e.outcome,
            'is_warmup': e.is_warmup
        })
    return res

def serialize_adversarial(records, run_id):
    res = []
    for r in records:
        if r.bounty_farming_subscenario != 'none':
            res.append({
                'run_id': run_id,
                'session_id': r.session_id,
                'adversary_type': 'relayer' if r.bounty_farming_subscenario != 'relayer_attester_collusion' else 'collusion',
                'adversary_index': 0,
                'bounty_farming_subscenario': r.bounty_farming_subscenario,
                'attempted_action': r.bounty_farming_attempted,
                'detected_by_protocol': r.bounty_farming_detected,
                'outcome': r.outcome
            })
    return res

def run_official():
    start_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    start_time = time.time()
    
    configs = get_reduced_design()
    seeds = list(range(10))
    
    run_results = []
    total_sessions = 0
    all_events = []
    all_adv = []
    
    # 1. Execute 160 runs
    for config in configs:
        for seed_idx in seeds:
            res = run_one(config, seed_idx, run_suffix='')
            run_results.append(res)
            total_sessions += len(res['session_records'])
            
            for e in res['event_rows']:
                all_events.append(e)
                
            advs = serialize_adversarial(res['session_records'], res['run_metadata']['run_id'])
            for a in advs:
                all_adv.append(a)

    # 2. Write outputs
    output_dir = Path('..') / 'results' / 'simulation_v1'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # run_metadata
    meta_path = output_dir / "run_metadata.csv"
    with open(meta_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=validators.REQUIRED_COLUMNS_RUN_METADATA)
        writer.writeheader()
        for r in run_results:
            writer.writerow(r['run_metadata'])
            
    # aggregate_metrics
    agg_path = output_dir / "aggregate_metrics.csv"
    with open(agg_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=validators.REQUIRED_COLUMNS_AGGREGATE)
        writer.writeheader()
        for r in run_results:
            writer.writerow(r['aggregate_metrics'])
            
    # events.csv
    events_path = output_dir / "events.csv"
    event_fields = ['run_id', 'event_id', 'session_id', 'event_type', 'simulated_timestamp_s', 
                    'seller_honest', 'attester_honest', 'packet_dropped', 'relayer_honest', 
                    'failure_mode', 'outcome', 'is_warmup']
    with open(events_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=event_fields)
        writer.writeheader()
        for e in all_events:
            writer.writerow({
                'run_id': e.run_id, 'event_id': e.event_id, 'session_id': e.session_id, 'event_type': e.event_type,
                'simulated_timestamp_s': e.simulated_timestamp_s, 'seller_honest': e.seller_honest, 
                'attester_honest': str(e.attester_honest), 'packet_dropped': e.packet_dropped, 
                'relayer_honest': e.relayer_honest, 'failure_mode': e.failure_mode, 'outcome': e.outcome, 'is_warmup': e.is_warmup
            })

    # adversarial_cases.csv
    adv_path = output_dir / "adversarial_cases.csv"
    adv_fields = ['run_id', 'session_id', 'adversary_type', 'adversary_index', 'bounty_farming_subscenario', 'attempted_action', 'detected_by_protocol', 'outcome']
    with open(adv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=adv_fields)
        writer.writeheader()
        for a in all_adv:
            writer.writerow(a)

    # simulation_manifest.json
    source_files = list(Path('.').glob('*.py'))
    source_sha = {sf.name: hashlib.sha256(sf.read_bytes()).hexdigest() for sf in sorted(source_files)}
    
    manifest = {
        'plan_version': 'simulation_analysis_plan_v2_final.md',
        'master_seed': 20260816,
        'creation_timestamp_utc': start_ts,
        'frozen_pilot_v2_artifacts': {
            'transactions_v2.csv': '1c91545bd6bf928b65df550405db5ef8922069968fd2276fb80e790fd7b794b1',
            'pilot_v2_transaction_audit_v2.csv': '2e67b67638f18cc02a46e81f98efc01041ba82a1caccd35584fa356c0dfadce5',
            'pilot_v2_invariant_audit_v2.csv': 'fe566164d7d08789eaef9118776e999a8b17ed26d4d1511f0d82ced5c533c14a',
            'pilot_v2_receipt_audit.csv': '509862844a7732935b1cfdaeefed1c6698108ff5987a0e706608fbd1d095b642',
            'pilot_v2_fee_audit.csv': '6b61f8d97c90006edbcea64087cd745d60e85865fc433a3c8a7dd4e3eeb74fda',
            'pilot_v2_latency_audit.csv': 'cdd5bcce6b8226a97566fdac15b242aff4e9b6222cb369d2163c396c842e5fb6',
            'pilot_v2_forensic_audit_report_v2.md': '1c9d4aff46055dbbcd820bd1646cd34f6cad6d5d808937ea770138c8d6b26547',
            'pilot_v2_manifest.json': '8582e5d1458bae13088e272c8c4431cbea30010f3aea60648bac90cb97e6400e',
            'reproducibility_package_v2.zip': 'a41daf4314a01de8ac5f413cfe4dbe675897fbfa5d28920ff81ccb9995daca72'
        },
        'zero_transactions_submitted': True,
        'design_parameters': {
            'lambda_val': [10, 1000],
            'packet_loss': [0.0, 0.05],
            'malicious_seller_rate': [0.0, 0.10],
            'byzantine_attesters': [0, 1],
            'seeds_per_config': 10,
            'events_per_run': 10000,
            'warmup_events': 1000,
            'total_runs': 160
        },
        'python_version': sys.version.split()[0],
        'dependency_versions': {
            'numpy': '1.26.4'
        },
        'source_sha256': source_sha
    }
    with open(output_dir / "simulation_manifest.json", 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    # 3. Sanity and Replay
    meta_ok = validators.validate_output_schema([r['run_metadata'] for r in run_results], validators.REQUIRED_COLUMNS_RUN_METADATA)
    agg_ok  = validators.validate_output_schema([r['aggregate_metrics'] for r in run_results], validators.REQUIRED_COLUMNS_AGGREGATE)
    
    sanity_fails = 0
    conservation_fails = 0
    for r in run_results:
        if r['run_metadata']['status'] == 'FAIL':
            sanity_fails += 1
        for v in r['session_records']:
            if len(v.conservation_violations) > 0:
                conservation_fails += 1

    replay_pass = True
    for c, s in [(configs[0], 0), (configs[8], 4), (configs[15], 9)]:
        ra = run_one(c, s, '_ra')
        rb = run_one(c, s, '_rb')
        oa = [(v.session_id, v.outcome, v.terminal_time) for v in ra['session_records']]
        ob = [(v.session_id, v.outcome, v.terminal_time) for v in rb['session_records']]
        if oa != ob: replay_pass = False

    print("Number of runs completed:", len(run_results))
    print("Number of sessions simulated:", total_sessions)
    print("Sanity check results:", 'PASS' if sanity_fails == 0 else 'FAIL', f"({sanity_fails} failed)")
    print("Conservation invariant status:", 'PASS' if conservation_fails == 0 else 'FAIL', f"({conservation_fails} violations)")
    print("Schema validation:", 'PASS' if meta_ok and agg_ok else 'FAIL')
    print("Deterministic replay (3 runs):", 'PASS' if replay_pass else 'FAIL')
    print("Master seed: 20260816")
    print("Zero transactions submitted: True")
    print("Official 160-run simulation: COMPLETED")
    
    # Save a quick summary for report generator
    with open(output_dir / "summary.json", 'w') as f:
        json.dump({
            'runs': len(run_results),
            'sessions': total_sessions,
            'sanity_fails': sanity_fails,
            'conservation_fails': conservation_fails,
            'schema': meta_ok and agg_ok,
            'replay': replay_pass
        }, f)

if __name__ == '__main__':
    run_official()
