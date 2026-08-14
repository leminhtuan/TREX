import csv
import math

def wilson_ci(successes, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denominator = 1 + z**2 / n
    centre = (p + z**2 / (2*n)) / denominator
    margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denominator
    return (centre - margin, centre + margin)

def main():
    rows = []
    with open("../results/pilot/transactions.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    released = 0
    refunded_correct = 0
    refunded_total = 0
    failed = 0
    
    # We map intent based on sequence as per prompt
    # 1-16: Released
    # 17-18: Refunded (TIMEOUT)
    # 19-20: Refunded (ATTESTED_FAIL) -> observed as Failed due to assert
    for i, r in enumerate(rows):
        idx = i + 1
        if idx <= 16:
            expected = "Released"
        else:
            expected = "Refunded"
            
        obs = r["outcome"]
        if obs == "Released":
            released += 1
        elif obs.startswith("Refunded"):
            refunded_total += 1
            if expected == "Refunded":
                refunded_correct += 1
        else:
            failed += 1

    success_rate = released / 20.0
    sr_ci = wilson_ci(released, 20)
    
    refund_precision = refunded_correct / refunded_total if refunded_total > 0 else 0
    rp_ci = wilson_ci(refunded_correct, refunded_total) if refunded_total > 0 else (0,0)
    
    expected_refunded = 4
    refund_recall = refunded_correct / expected_refunded
    rr_ci = wilson_ci(refunded_correct, expected_refunded)
    
    print(f"Outcome Audit:")
    print(f"Released: {released}")
    print(f"Refunded: {refunded_total}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {success_rate:.2f} CI: ({sr_ci[0]:.2f}, {sr_ci[1]:.2f})")
    print(f"Refund Precision: {refund_precision:.2f} CI: ({rp_ci[0]:.2f}, {rp_ci[1]:.2f})")
    print(f"Refund Recall: {refund_recall:.2f} CI: ({rr_ci[0]:.2f}, {rr_ci[1]:.2f})")

if __name__ == '__main__':
    main()
