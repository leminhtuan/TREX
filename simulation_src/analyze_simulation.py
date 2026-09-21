"""
analysis and reporting. No Algorand API calls. No transactions submitted. All outputs are VALID_SIMULATION_ONLY.
"""
import csv
from pathlib import Path
from typing import Optional
import metrics

def load_aggregate_metrics(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                if v == 'NA':
                    row[k] = None
                else:
                    try:
                        row[k] = float(v)
                    except (ValueError, TypeError):
                        pass
            rows.append(row)
    return rows

def compute_cross_run_stats(run_values: list[Optional[float]], metric_name: str) -> dict:
    clean = [v for v in run_values if v is not None]
    if not clean:
        return {
            f"{metric_name}_median": None,
            f"{metric_name}_p25": None,
            f"{metric_name}_p75": None,
            f"{metric_name}_p95": None,
            f"{metric_name}_ci_lower": None,
            f"{metric_name}_ci_upper": None,
            'metric_type': 'VALID_SIMULATION_ONLY'
        }
    clean.sort()
    n = len(clean)
    
    def get_p(p):
        idx = int((p / 100.0) * n)
        idx = min(idx, n - 1)
        return clean[idx]
        
    lower, upper = metrics.bootstrap_ci_median(clean)
    
    return {
        f"{metric_name}_median": get_p(50),
        f"{metric_name}_p25": get_p(25),
        f"{metric_name}_p75": get_p(75),
        f"{metric_name}_p95": get_p(95),
        f"{metric_name}_ci_lower": lower,
        f"{metric_name}_ci_upper": upper,
        'metric_type': 'VALID_SIMULATION_ONLY'
    }

def check_monotonicity(configs_and_metrics: list[dict]) -> list[str]:
    msgs = []
    lambda_map = {}
    for row in configs_and_metrics:
        l = row.get('lambda_val')
        if l is not None:
            if l not in lambda_map:
                lambda_map[l] = []
            tp = row.get('throughput_sessions_per_s')
            if tp is not None:
                lambda_map[l].append(tp)
                
    medians = {}
    for l, vals in lambda_map.items():
        vals.sort()
        if vals:
            medians[l] = vals[len(vals)//2]
            
    lambdas = sorted(medians.keys())
    for i in range(len(lambdas) - 1):
        if medians[lambdas[i]] > medians[lambdas[i+1]]:
            msgs.append(f"Monotonicity violation: throughput at lambda {lambdas[i]} ({medians[lambdas[i]]}) > throughput at lambda {lambdas[i+1]} ({medians[lambdas[i+1]]})")
            
    return msgs

def write_summary_report(report_path: Path, stats: dict, sanity: dict, mode: str):
    lines = [
        f"# Simulation Report ({mode})",
        "",
        "**VALID_SIMULATION_ONLY: model-based synthetic estimates under stated assumptions**",
        "",
        "## Cross-Run Statistics",
    ]
    for k, v in stats.items():
        lines.append(f"- **{k}**: {v}")
        
    lines.extend([
        "",
        "## Sanity Checks",
    ])
    for k, v in sanity.items():
        lines.append(f"- **{k}**: {v}")
        
    content = "\n".join(lines) + "\n"
    if any(ord(c) < 32 and c not in '\n\r\t' for c in content):
        raise ValueError("Control characters found in report")
        
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    proj_root = Path(__file__).parent.parent
    agg_path = proj_root / 'results' / 'simulation_v1' / 'aggregate_metrics_smoke_test.csv'
    if not agg_path.exists():
        print(f"{agg_path} does not exist.")
        return
        
    rows = load_aggregate_metrics(agg_path)
    if not rows:
        return
        
    tp_vals = [r.get('throughput_sessions_per_s') for r in rows]
    stats = compute_cross_run_stats(tp_vals, 'throughput_sessions_per_s')
    
    report_path = proj_root / 'results' / 'simulation_v1' / 'summary_report.md'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_summary_report(report_path, stats, {}, 'smoke_test')
    
if __name__ == '__main__':
    main()
