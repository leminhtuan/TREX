"""
read-only validation. No transactions submitted.
"""
def validate_session_state_machine(session) -> list[str]:
    violations = []
    valid_terminal_outcomes = {
        'REFUNDED_TIMEOUT': 'Refunded(TIMEOUT)',
        'REFUNDED_ATTESTED_FAIL': 'Refunded(ATTESTED_FAIL)',
        'RELEASED': 'Released'
    }
    
    if session.state in valid_terminal_outcomes:
        if session.outcome != valid_terminal_outcomes[session.state]:
            violations.append(f"Outcome {session.outcome} does not match state {session.state}")
            
    return violations

def run_sanity_checks(aggregate_metrics: dict, config) -> dict[str, str]:
    checks = {}
    
    frr = None if aggregate_metrics['frr'] == 'NA' else float(aggregate_metrics['frr'])
    if config.malicious_seller_rate == 0 and config.byzantine_attesters == 0:
        if frr is None or frr == 0.0:
            checks['frr_zero_baseline'] = 'PASS'
        else:
            checks['frr_zero_baseline'] = 'FAIL'
    else:
        checks['frr_zero_baseline'] = 'NA'
        
    odr = None if aggregate_metrics['odr'] == 'NA' else float(aggregate_metrics['odr'])
    if config.malicious_seller_rate == 0:
        if odr is None:
            checks['odr_na_baseline'] = 'PASS'
        else:
            checks['odr_na_baseline'] = 'FAIL'
    else:
        checks['odr_na_baseline'] = 'NA'
        
    ivr = None if aggregate_metrics['invariant_violation_rate'] == 'NA' else float(aggregate_metrics['invariant_violation_rate'])
    if config.malicious_seller_rate == 0 and config.byzantine_attesters == 0:
        if ivr == 0.0:
            checks['invariant_zero_baseline'] = 'PASS'
        else:
            checks['invariant_zero_baseline'] = 'FAIL'
    else:
        checks['invariant_zero_baseline'] = 'NA'
        
    if ivr is None or ivr == 0.0:
        checks['conservation_check'] = 'PASS'
    else:
        checks['conservation_check'] = 'FAIL'
        
    tp = None if aggregate_metrics['throughput_sessions_per_s'] == 'NA' else float(aggregate_metrics['throughput_sessions_per_s'])
    if tp is not None and tp > 0:
        checks['throughput_positive'] = 'PASS'
    else:
        checks['throughput_positive'] = 'FAIL'
        
    if int(aggregate_metrics['sessions_total']) >= 100:
        checks['session_count_valid'] = 'PASS'
    else:
        checks['session_count_valid'] = 'FAIL'
        
    return checks

def check_throughput_monotonicity(metrics_by_lambda: dict) -> bool:
    lambdas = sorted(metrics_by_lambda.keys())
    if len(lambdas) < 2:
        return None
    for i in range(len(lambdas) - 1):
        if metrics_by_lambda[lambdas[i]] > metrics_by_lambda[lambdas[i+1]]:
            return False
    return True

def validate_output_schema(rows: list[dict], required_columns: list[str]) -> bool:
    for row in rows:
        for col in required_columns:
            if col not in row:
                return False
    return True

REQUIRED_COLUMNS_RUN_METADATA = [
    'run_id','lambda_val','packet_loss','malicious_seller_rate',
    'byzantine_attesters','seed_index','run_seed','master_seed',
    'events_total','events_warmup','simulation_duration_s',
    'wall_clock_s','status','diagnostic_flags'
]

REQUIRED_COLUMNS_AGGREGATE = [
    'run_id','throughput_sessions_per_s','auth_latency_p50_s',
    'auth_latency_p95_s','e2e_latency_p50_s','e2e_latency_p95_s',
    'frr','odr','bfsr_duplicate_claim','bfsr_replay',
    'bfsr_frontrun','bfsr_collusion','invariant_violation_rate',
    'sessions_released','sessions_refunded_timeout',
    'sessions_refunded_attested_fail','sessions_total',
    'metric_type','diagnostic_flags'
]
