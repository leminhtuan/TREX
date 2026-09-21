"""
All outputs are model-based synthetic estimates under stated assumptions.
No Algorand API calls. No transactions submitted.
"""
import random
import hashlib
import math

MASTER_SEED = 20260816
BLOCK_TIME_S = 3.5

# Empirical Latency Distribution Parameters fitted from 100-session campaign (N=40 Normal Settle)
# Fitted via scipy.stats.lognorm.fit(data, floc=0) ensuring standard physical support (0, inf)
# Theoretical mean formula: E[X] = loc + scale * exp(s^2 / 2) matches empirical mean to < 0.03%
LATENCY_DISTRIBUTIONS = {
    "authorize": {
        "distribution": "lognorm",
        "shape": 0.073378,
        "loc": 0.0,
        "scale": 4.714207,
        "mean_empirical": 4.728275,
        "std_empirical": 0.410182,
        "theoretical_mean": 4.726915,
        "ks_p_value": 0.000499,
    },
    "settle": {
        "distribution": "lognorm",
        "shape": 0.017032,
        "loc": 0.0,
        "scale": 4.907791,
        "mean_empirical": 4.908500,
        "std_empirical": 0.084189,
        "theoretical_mean": 4.908503,
        "ks_p_value": 0.956399,
    },
    "end_to_end": {
        "distribution": "lognorm",
        "shape": 0.037488,
        "loc": 0.0,
        "scale": 10.099459,
        "mean_empirical": 10.106900,
        "std_empirical": 0.412024,
        "theoretical_mean": 10.106559,
        "ks_p_value": 0.000733,
    },
}

def derive_run_seed(master_seed, lambda_val, packet_loss, malicious_seller_rate, byzantine_attesters, seed_index) -> int:
    seed_str = f"{master_seed}|{lambda_val}|{packet_loss}|{malicious_seller_rate}|{byzantine_attesters}|{seed_index}"
    digest = hashlib.sha256(seed_str.encode('utf-8')).hexdigest()
    return int(digest[:16], 16)

def make_rng(run_seed) -> random.Random:
    rng = random.Random()
    rng.seed(run_seed)
    return rng

def generate_session_arrivals(rng, lambda_val, n_sessions) -> list[float]:
    arrivals = []
    current_time = 0.0
    for _ in range(n_sessions):
        inter_arrival = rng.expovariate(lambda_val)
        current_time += inter_arrival
        arrivals.append(current_time)
    return arrivals

def exp_delay(rng, scale_seconds) -> float:
    return rng.expovariate(1.0 / scale_seconds)

def next_block_boundary(current_time, block_time=BLOCK_TIME_S) -> float:
    return math.ceil(current_time / block_time) * block_time

def sample_latency(phase: str, rng: random.Random = None) -> float:
    """
    Samples latency from the fitted empirical Lognormal distribution
    using exact inverse transform / normal deviate mapping:
        X = loc + scale * exp(shape * Z), where Z ~ N(0, 1).
    """
    if phase not in LATENCY_DISTRIBUTIONS:
        raise KeyError(f"Unknown phase '{phase}'. Available: {list(LATENCY_DISTRIBUTIONS.keys())}")
    
    params = LATENCY_DISTRIBUTIONS[phase]
    shape = params["shape"]
    loc = params["loc"]
    scale = params["scale"]
    
    z = rng.gauss(0.0, 1.0) if rng is not None else random.gauss(0.0, 1.0)
    return loc + scale * math.exp(shape * z)
