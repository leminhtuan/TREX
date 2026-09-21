"""
All outputs are VALID_SIMULATION_ONLY: model-based synthetic estimates under stated assumptions.
"""
import random
from typing import Optional, List, Dict, Any

def safe_divide(numerator, denominator) -> Optional[float]:
    if denominator == 0:
        return None
    return numerator / denominator

def na_str(val) -> str:
    if val is None:
        return 'NA'
    return str(val)

def compute_throughput(sessions_measurement, sim_duration_s) -> Optional[float]:
    if sim_duration_s == 0:
        return None
    terminals = sum(1 for s in sessions_measurement if s.terminal_time is not None)
    return terminals / sim_duration_s

def compute_latency_percentiles(sessions_measurement, percentiles=[50, 95]) -> dict:
    auth_lats = []
    e2e_lats  = []

    for s in sessions_measurement:
        # Support both old (authorized_time) and new (auth_confirmation_time) field names
        auth_t = getattr(s, 'auth_confirmation_time', None) or getattr(s, 'authorized_time', None)
        if auth_t is not None:
            auth_lats.append(auth_t - s.arrival_time)
        if s.terminal_time is not None:
            e2e_lats.append(s.terminal_time - s.arrival_time)

    def get_perc(lats, p):
        if len(lats) < 2:
            return None
        slats = sorted(lats)
        idx = min(int((p / 100.0) * len(slats)), len(slats) - 1)
        return slats[idx]

    return {
        'auth_p50': get_perc(auth_lats, 50),
        'auth_p95': get_perc(auth_lats, 95),
        'e2e_p50':  get_perc(e2e_lats,  50),
        'e2e_p95':  get_perc(e2e_lats,  95),
    }

def compute_frr(sessions_measurement) -> Optional[float]:
    dishonest = [s for s in sessions_measurement if not s.seller_honest]
    if not dishonest:
        return None
    released = [s for s in dishonest if s.outcome == 'Released']
    return len(released) / len(dishonest)

def compute_odr(sessions_measurement) -> Optional[float]:
    omissions = [s for s in sessions_measurement if s.failure_mode == 'seller_omission']
    if not omissions:
        return None
    refunded = [s for s in omissions if s.outcome == 'Refunded(TIMEOUT)']
    return len(refunded) / len(omissions)

def compute_bfsr(sessions_measurement) -> dict:
    scenarios = ['duplicate_claim', 'replay_after_terminal', 'front_running', 'relayer_attester_collusion']
    res = {}
    for s_name in scenarios:
        attempted = [s for s in sessions_measurement if s.bounty_farming_subscenario == s_name and s.bounty_farming_attempted]
        if not attempted:
            res[s_name] = None
        else:
            undetected = [s for s in attempted if not s.bounty_farming_detected]
            res[s_name] = len(undetected) / len(attempted)
    return {
        'duplicate_claim': res['duplicate_claim'],
        'replay_after_terminal': res['replay_after_terminal'],
        'front_running': res['front_running'],
        'relayer_attester_collusion': res['relayer_attester_collusion']
    }

def compute_invariant_violation_rate(sessions_measurement) -> Optional[float]:
    total = len(sessions_measurement)
    if total == 0:
        return None
    violations = sum(1 for s in sessions_measurement if len(s.conservation_violations) > 0)
    return violations / total

def compute_all_metrics(sessions_measurement, sim_duration_s) -> dict:
    out = {}
    out['throughput_sessions_per_s'] = compute_throughput(sessions_measurement, sim_duration_s)
    
    lats = compute_latency_percentiles(sessions_measurement)
    out['auth_latency_p50_s'] = lats['auth_p50']
    out['auth_latency_p95_s'] = lats['auth_p95']
    out['e2e_latency_p50_s'] = lats['e2e_p50']
    out['e2e_latency_p95_s'] = lats['e2e_p95']
    
    out['frr'] = compute_frr(sessions_measurement)
    out['odr'] = compute_odr(sessions_measurement)
    
    bfsr = compute_bfsr(sessions_measurement)
    out['bfsr_duplicate_claim'] = bfsr['duplicate_claim']
    out['bfsr_replay'] = bfsr['replay_after_terminal']
    out['bfsr_frontrun'] = bfsr['front_running']
    out['bfsr_collusion'] = bfsr['relayer_attester_collusion']
    
    out['invariant_violation_rate'] = compute_invariant_violation_rate(sessions_measurement)
    
    out['sessions_released'] = sum(1 for s in sessions_measurement if s.outcome == 'Released')
    out['sessions_refunded_timeout'] = sum(1 for s in sessions_measurement if s.outcome == 'Refunded(TIMEOUT)')
    out['sessions_refunded_attested_fail'] = sum(1 for s in sessions_measurement if s.outcome == 'Refunded(ATTESTED_FAIL)')
    out['sessions_total'] = len(sessions_measurement)
    
    out['metric_type'] = 'VALID_SIMULATION_ONLY'
    
    for k in out:
        if out[k] is None:
            out[k] = 'NA'
            
    return out

def bootstrap_ci_median(run_values: list, B=10000, ci_level=0.95, rng_seed=42) -> tuple[Optional[float], Optional[float]]:
    clean = [v for v in run_values if v is not None and v != 'NA']
    if len(clean) < 2:
        return None, None
        
    rng = random.Random(rng_seed)
    medians = []
    n = len(clean)
    for _ in range(B):
        sample = [rng.choice(clean) for _ in range(n)]
        ssample = sorted(sample)
        mid = n // 2
        if n % 2 == 0:
            medians.append((ssample[mid - 1] + ssample[mid]) / 2.0)
        else:
            medians.append(ssample[mid])
            
    medians.sort()
    lower_idx = int(((1.0 - ci_level) / 2.0) * B)
    upper_idx = int((1.0 - (1.0 - ci_level) / 2.0) * B)
    
    return medians[lower_idx], medians[min(upper_idx, B - 1)]
