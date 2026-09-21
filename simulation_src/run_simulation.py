"""
orchestrates simulation runs. No Algorand API calls. No transactions submitted.
"""
import os
import sys
import csv
import json
import time
import hashlib
import datetime
import itertools
from pathlib import Path

import workload_generator as wg
import sim_engine
import metrics
import validators

MASTER_SEED = 20260816
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / 'results' / 'simulation_v1'
SRC_DIR = PROJECT_ROOT / 'simulation_src'

def get_reduced_design() -> list[dict]:
    lambdas = [10, 1000]
    packet_losses = [0.0, 0.05]
    malicious_rates = [0.0, 0.10]
    byzantines = [0, 1]
    configs = []
    for l, p, m, b in itertools.product(lambdas, packet_losses, malicious_rates, byzantines):
        configs.append({
            'lambda_val': l,
            'packet_loss': p,
            'malicious_seller_rate': m,
            'byzantine_attesters': b
        })
    return configs

def get_smoke_test_configs() -> list[dict]:
    return [{
        'lambda_val': 10,
        'packet_loss': 0.0,
        'malicious_seller_rate': 0.0,
        'byzantine_attesters': 0
    }]

def run_one(config_dict: dict, seed_index: int, run_suffix: str = '') -> dict:
    start_time = time.time()
    
    run_seed = wg.derive_run_seed(
        MASTER_SEED,
        config_dict['lambda_val'],
        config_dict['packet_loss'],
        config_dict['malicious_seller_rate'],
        config_dict['byzantine_attesters'],
        seed_index
    )
    
    run_id = f"run_{config_dict['lambda_val']}_{config_dict['packet_loss']}_{config_dict['malicious_seller_rate']}_{config_dict['byzantine_attesters']}_{seed_index}{run_suffix}"
    
    config = sim_engine.SimConfig(
        lambda_val=config_dict['lambda_val'],
        packet_loss=config_dict['packet_loss'],
        malicious_seller_rate=config_dict['malicious_seller_rate'],
        byzantine_attesters=config_dict['byzantine_attesters']
    )
    
    engine = sim_engine.SimEngine(config, run_seed, run_id)
    records, event_rows = engine.run()
    
    measurement_records = [r for r in records if not r.is_warmup]
    agg_metrics = metrics.compute_all_metrics(measurement_records, engine.sim_duration_s)
    agg_metrics['run_id'] = run_id
    agg_metrics['diagnostic_flags'] = ''
    
    sanity = validators.run_sanity_checks(agg_metrics, config)
    
    status = 'SUCCESS' if all(v == 'PASS' or v == 'NA' for v in sanity.values()) else 'FAIL'
    
    run_meta = {
        'run_id': run_id,
        'lambda_val': config_dict['lambda_val'],
        'packet_loss': config_dict['packet_loss'],
        'malicious_seller_rate': config_dict['malicious_seller_rate'],
        'byzantine_attesters': config_dict['byzantine_attesters'],
        'seed_index': seed_index,
        'run_seed': run_seed,
        'master_seed': MASTER_SEED,
        'events_total': len(records),
        'events_warmup': config.n_warmup,
        'simulation_duration_s': engine.sim_duration_s,
        'wall_clock_s': time.time() - start_time,
        'status': status,
        'diagnostic_flags': ''
    }
    
    return {
        'run_metadata': run_meta,
        'aggregate_metrics': agg_metrics,
        'session_records': records,
        'event_rows': event_rows,
        'sanity': sanity
    }

def write_outputs(run_results: list[dict], output_dir: Path, mode='smoke_test'):
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = '_smoke_test' if mode == 'smoke_test' else ''
    
    meta_path = output_dir / f"run_metadata{suffix}.csv"
    with open(meta_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=validators.REQUIRED_COLUMNS_RUN_METADATA)
        writer.writeheader()
        for r in run_results:
            writer.writerow(r['run_metadata'])
            
    agg_path = output_dir / f"aggregate_metrics{suffix}.csv"
    with open(agg_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=validators.REQUIRED_COLUMNS_AGGREGATE)
        writer.writeheader()
        for r in run_results:
            writer.writerow(r['aggregate_metrics'])

def write_manifest(output_dir: Path, configs: list, mode: str, start_ts: str, wall_clock_s: float, source_sha256: dict):
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = '_smoke_test' if mode == 'smoke_test' else ''
    manifest = {
        'mode': mode,
        'start_ts': start_ts,
        'wall_clock_s': wall_clock_s,
        'configs': configs,
        'source_sha256': source_sha256
    }
    with open(output_dir / f"simulation_manifest{suffix}.json", 'w') as f:
        json.dump(manifest, f, indent=2)

def main(mode='smoke_test'):
    print(f"Starting {mode}...")
    start_ts = datetime.datetime.now().isoformat()
    start_time = time.time()
    
    if mode == 'smoke_test':
        configs = get_smoke_test_configs()
        seeds = [0, 1, 2]
    else:
        configs = get_reduced_design()
        seeds = list(range(10))
        
    results = []
    total_sessions = 0
    sanity_fails = 0
    conservation_fails = 0
    
    for config in configs:
        for seed in seeds:
            res = run_one(config, seed, run_suffix='_smoke' if mode == 'smoke_test' else '')
            results.append(res)
            total_sessions += len(res['session_records'])
            
            if res['run_metadata']['status'] == 'FAIL':
                sanity_fails += 1
            if res['sanity'].get('conservation_check') == 'FAIL':
                conservation_fails += 1
                
    write_outputs(results, OUTPUT_DIR, mode)
    write_manifest(OUTPUT_DIR, configs, mode, start_ts, time.time() - start_time, {})
    
    print("\n--- Simulation Summary ---")
    print(f"Number of runs completed: {len(results)}")
    print(f"Number of sessions simulated: {total_sessions}")
    print(f"Sanity check results: {'PASS' if sanity_fails == 0 else 'FAIL'} ({sanity_fails} failed)")
    print(f"Conservation invariant status: {'PASS' if conservation_fails == 0 else 'FAIL'} ({conservation_fails} violations)")
    print(f"Master seed: {MASTER_SEED}")
    print("Zero transactions submitted: True")
    if mode == 'smoke_test':
        print("Official 160-run simulation has NOT started")

if __name__ == '__main__':
    main('smoke_test')
