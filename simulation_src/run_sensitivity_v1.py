"""
run_sensitivity_v1.py - Orchestrates the Sensitivity Analysis v1 for T-REX simulation.
VALID_SIMULATION_ONLY: model-based synthetic estimates under stated assumptions.
No Algorand API calls. No transactions submitted.
"""
import sys, csv, json, time, hashlib, datetime
from pathlib import Path

sys.path.insert(0, '.')

from run_simulation import run_one
from sim_engine import SimConfig
import validators
import run_official

ROOT = Path(__file__).resolve().parent.parent

def get_sensitivity_design():
    # Baseline reference for missing params: lambda=10, packet_loss=0, malicious=0, byzantine=0, block_time=3.5
    # Configs:
    # 1. High Block Time: block_time_s=10.0
    # 2. Low Block Time: block_time_s=2.0
    # 3. High Service Latency: auth=2.0, seller=2.0, attester=1.0, relayer=1.0
    # 4. Extreme Packet Loss: packet_loss=0.20
    # 5. High Malicious: malicious=0.50
    # 6. Extreme Load: lambda=5000
    # 7. Attester Unavailability: attester_unavailability_prob=0.10
    # 8. Combined Adv: byzantine=1, packet_loss=0.10

    baseline = {'lambda_val': 10.0, 'packet_loss': 0.0, 'malicious_seller_rate': 0.0, 'byzantine_attesters': 0, 
                'block_time_s': 3.5, 'auth_service_scale_s': 0.5, 'seller_service_scale_s': 0.3, 
                'attester_service_scale_s': 0.1, 'relayer_service_scale_s': 0.2, 'attester_unavailability_prob': 0.0}
    
    configs = []
    
    # Config 1
    c1 = baseline.copy(); c1['block_time_s'] = 10.0
    configs.append(c1)
    # Config 2
    c2 = baseline.copy(); c2['block_time_s'] = 2.0
    configs.append(c2)
    # Config 3
    c3 = baseline.copy()
    c3.update({'auth_service_scale_s': 2.0, 'seller_service_scale_s': 2.0, 'attester_service_scale_s': 1.0, 'relayer_service_scale_s': 1.0})
    configs.append(c3)
    # Config 4
    c4 = baseline.copy(); c4['packet_loss'] = 0.20
    configs.append(c4)
    # Config 5
    c5 = baseline.copy(); c5['malicious_seller_rate'] = 0.50
    configs.append(c5)
    # Config 6
    c6 = baseline.copy(); c6['lambda_val'] = 5000.0
    configs.append(c6)
    # Config 7
    c7 = baseline.copy(); c7['attester_unavailability_prob'] = 0.10
    configs.append(c7)
    # Config 8
    c8 = baseline.copy(); c8['byzantine_attesters'] = 1; c8['packet_loss'] = 0.10
    configs.append(c8)

    return configs

def run_sensitivity():
    start_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    configs = get_sensitivity_design()
    seeds = list(range(5)) # N=5 runs per config
    
    run_results = []
    total_sessions = 0
    all_events = []
    all_adv = []
    
    # 1. Execute runs
    for c_idx, c_dict in enumerate(configs):
        for seed_idx in seeds:
            res = run_one(c_dict, seed_idx, run_suffix=f'_sens{c_idx+1}')
            run_results.append(res)
            total_sessions += len(res['session_records'])
            
            for e in res['event_rows']:
                all_events.append(e)
                
            advs = run_official.serialize_adversarial(res['session_records'], res['run_metadata']['run_id'])
            for a in advs:
                all_adv.append(a)

    # 2. Write outputs
    output_dir = ROOT / 'results' / 'simulation_v1_sensitivity'
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
    manifest = {
        'plan_version': 'simulation_v1_sensitivity_analysis_plan.md',
        'master_seed': 20260816,
        'creation_timestamp_utc': start_ts,
        'zero_transactions_submitted': True,
        'runs': len(run_results),
        'sessions': total_sessions
    }
    with open(output_dir / "simulation_manifest.json", 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print("Sensitivity analysis completed.")
    print("Number of runs:", len(run_results))
    print("Output directory:", output_dir.resolve())

if __name__ == '__main__':
    run_sensitivity()
