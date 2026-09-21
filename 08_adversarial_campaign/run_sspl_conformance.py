#!/usr/bin/env python3
"""
SSPL Formal Conformance Suite & Fail-Open Resistance Test Runner
Tests Kleene Strong 3-Valued Logic (K_3) and Fail-Closed semantics
across 10+ critical edge-case vectors (RFC 6901 pointer resolution,
type compatibility, nested negation, and partial evaluation).
"""

import os
import sys
import json
from dataclasses import asdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, "02_clients"))

import sspl_eval
from sspl_eval import (
    Verdict,
    Compare,
    Not,
    And,
    Or,
    eval_kleene,
    evaluate,
    canonical_hash
)

# Definition of the 10 core + 2 auxiliary edge-case vectors
CONFORMANCE_VECTORS = [
    {
        "test_id": "SSPL-TC-01",
        "name": "Positive Baseline (Path Exists, Satisfied)",
        "payload": {"status": 200, "latency": 45, "cached": True},
        "predicate": Compare("/latency", "<=", 50),
        "expected_kleene": Verdict.PASS,
        "expected_fail_closed": Verdict.PASS,
        "fail_open_risk": "None (Valid Pass)",
        "notes": "Valid payload where RFC 6901 path resolves and literal satisfies condition."
    },
    {
        "test_id": "SSPL-TC-02",
        "name": "Definitive SLA Failure (Path Exists, Value Violates)",
        "payload": {"status": 200, "latency": 85},
        "predicate": Compare("/latency", "<=", 50),
        "expected_kleene": Verdict.FAIL,
        "expected_fail_closed": Verdict.FAIL,
        "fail_open_risk": "None (Valid Fail)",
        "notes": "Valid integer resolved, comparison evaluates to definitive false."
    },
    {
        "test_id": "SSPL-TC-03",
        "name": "Missing Path Direct Rejection",
        "payload": {"status": 200},
        "predicate": Compare("/latency", "<=", 50),
        "expected_kleene": Verdict.ERROR,
        "expected_fail_closed": Verdict.FAIL,
        "fail_open_risk": "Mitigated",
        "notes": "Missing field yields bottom (ERROR); fail-closed maps root to FAIL."
    },
    {
        "test_id": "SSPL-TC-04",
        "name": "Missing Path Under Negation (P0 Fail-Open Vector)",
        "payload": {"data": "ok"},
        "predicate": Not(Compare("/error", "=", True)),
        "expected_kleene": Verdict.ERROR,
        "expected_fail_closed": Verdict.FAIL,
        "fail_open_risk": "CRITICAL (Classic 2-valued logic yields PASS!)",
        "notes": "Seller omits '/error'. 2-valued Not(FAIL)=PASS (exploit). K_3 Not(ERROR)=ERROR -> FAIL."
    },
    {
        "test_id": "SSPL-TC-05",
        "name": "Type Incompatibility (Ordering on String)",
        "payload": {"latency": "35ms"},
        "predicate": Compare("/latency", "<=", 50),
        "expected_kleene": Verdict.ERROR,
        "expected_fail_closed": Verdict.FAIL,
        "fail_open_risk": "Mitigated",
        "notes": "String literal resolved against numeric operator produces type mismatch ERROR."
    },
    {
        "test_id": "SSPL-TC-06",
        "name": "Type Incompatibility Under Negation (Fail-Open Defense)",
        "payload": {"latency": "fast"},
        "predicate": Not(Compare("/latency", ">", 100)),
        "expected_kleene": Verdict.ERROR,
        "expected_fail_closed": Verdict.FAIL,
        "fail_open_risk": "CRITICAL (Classic logic yields PASS on type error)",
        "notes": "Type error in nested comparison must propagate as ERROR through Not."
    },
    {
        "test_id": "SSPL-TC-07",
        "name": "Nested Negation with Missing Deep Path",
        "payload": {"service": {"meta": {}}},
        "predicate": Not(Not(Compare("/service/meta/sla/uptime", "<", 99.9))),
        "expected_kleene": Verdict.ERROR,
        "expected_fail_closed": Verdict.FAIL,
        "fail_open_risk": "Mitigated",
        "notes": "Deep pointer traversal failure (/service/meta/sla) propagates through multiple Not gates."
    },
    {
        "test_id": "SSPL-TC-08",
        "name": "Kleene Conjunction with Unknown: And(PASS, ERROR)",
        "payload": {"status": 200},
        "predicate": And(
            Compare("/status", "=", 200),
            Compare("/security_scan/passed", "=", True)
        ),
        "expected_kleene": Verdict.ERROR,
        "expected_fail_closed": Verdict.FAIL,
        "fail_open_risk": "Mitigated",
        "notes": "Left branch PASS, right branch missing ERROR -> Conjunction is unknown (ERROR)."
    },
    {
        "test_id": "SSPL-TC-09",
        "name": "Kleene Disjunction with Unknown: Or(FAIL, ERROR)",
        "payload": {"status": 500},
        "predicate": Or(
            Compare("/status", "=", 200),
            Compare("/fallback_ok", "=", True)
        ),
        "expected_kleene": Verdict.ERROR,
        "expected_fail_closed": Verdict.FAIL,
        "fail_open_risk": "Mitigated",
        "notes": "Left branch FAIL, right branch missing ERROR -> Disjunction is unknown (ERROR)."
    },
    {
        "test_id": "SSPL-TC-10",
        "name": "RFC 6901 Array Indexing & 64-bit Integer Boundaries",
        "payload": {"metrics": [10, -500, 9223372036854775807], "zero_point": 0},
        "predicate": And(
            Compare("/metrics/1", "<", 0),
            Compare("/metrics/2", ">=", 9223372036854775807)
        ),
        "expected_kleene": Verdict.PASS,
        "expected_fail_closed": Verdict.PASS,
        "fail_open_risk": "None (Valid Pass)",
        "notes": "RFC 6901 array index resolution with negative numbers and int64 max boundary."
    },
    {
        "test_id": "SSPL-TC-11",
        "name": "Kleene Conjunction Short-Circuit: And(FAIL, ERROR)",
        "payload": {"status": 500},
        "predicate": And(
            Compare("/status", "=", 200),
            Compare("/missing_sla_probe", "<", 50)
        ),
        "expected_kleene": Verdict.FAIL,
        "expected_fail_closed": Verdict.FAIL,
        "fail_open_risk": "None (Definitive Fail)",
        "notes": "Left is definitively FAIL; Kleene logic establishes FAIL without resolving right."
    },
    {
        "test_id": "SSPL-TC-12",
        "name": "Kleene Disjunction Short-Circuit: Or(PASS, ERROR)",
        "payload": {"status": 200},
        "predicate": Or(
            Compare("/status", "=", 200),
            Compare("/missing_backup_probe", "=", "active")
        ),
        "expected_kleene": Verdict.PASS,
        "expected_fail_closed": Verdict.PASS,
        "fail_open_risk": "None (Definitive Pass)",
        "notes": "Left is definitively PASS; Kleene logic establishes PASS without resolving right."
    }
]


def format_pred_str(p) -> str:
    if isinstance(p, Compare):
        return f"Compare(\"{p.path}\", \"{p.op}\", {repr(p.lit)})"
    elif isinstance(p, Not):
        return f"Not({format_pred_str(p.child)})"
    elif isinstance(p, And):
        return f"And({format_pred_str(p.left)}, {format_pred_str(p.right)})"
    elif isinstance(p, Or):
        return f"Or({format_pred_str(p.left)}, {format_pred_str(p.right)})"
    return str(p)


def run_conformance_suite():
    print("=" * 80)
    print("T-REX SSPL CONFORMANCE SUITE: KLEENE 3-VALUED LOGIC & FAIL-CLOSED SEMANTICS")
    print("=" * 80)

    results = []
    all_passed = True
    fail_open_detected = False

    for tc in CONFORMANCE_VECTORS:
        t_id = tc["test_id"]
        name = tc["name"]
        payload = tc["payload"]
        pred = tc["predicate"]
        exp_k = tc["expected_kleene"]
        exp_fc = tc["expected_fail_closed"]

        actual_k = eval_kleene(pred, payload)
        actual_fc = evaluate(pred, payload)

        k_ok = (actual_k == exp_k)
        fc_ok = (actual_fc == exp_fc)
        passed = k_ok and fc_ok

        if not passed:
            all_passed = False

        # Fail-Open Detection check: Did any structural error evaluate to PASS?
        is_fail_open = (exp_k == Verdict.ERROR and actual_fc == Verdict.PASS)
        if is_fail_open:
            fail_open_detected = True

        results.append({
            "test_id": t_id,
            "name": name,
            "payload_snippet": json.dumps(payload, separators=(',', ':'))[:40],
            "predicate_str": format_pred_str(pred),
            "expected_kleene": exp_k.name,
            "actual_kleene": actual_k.name,
            "expected_verdict": exp_fc.name,
            "actual_verdict": actual_fc.name,
            "status": "PASS" if passed else "FAIL",
            "fail_open_prevented": not is_fail_open
        })

    # Print summary table
    print(f"\n{'Test ID':<11} | {'Status':<6} | {'Kleene (Actual/Exp)':<21} | {'Root Verdict':<14} | {'Fail-Open Prevented'}")
    print("-" * 80)
    for r in results:
        k_str = f"{r['actual_kleene']}/{r['expected_kleene']}"
        v_str = f"{r['actual_verdict']} ({r['expected_verdict']})"
        fo_str = "YES" if r["fail_open_prevented"] else "NO (VULNERABLE!)"
        print(f"{r['test_id']:<11} | {r['status']:<6} | {k_str:<21} | {v_str:<14} | {fo_str}")

    print("\n" + "=" * 80)
    if all_passed and not fail_open_detected:
        print("ALL 12 CONFORMANCE VECTORS PASSED! ZERO FAIL-OPEN SCENARIOS DETECTED.")
    else:
        print("CONFORMANCE FAILURES DETECTED! INVESTIGATE TRACE.")
    print("=" * 80)

    # Save Markdown report
    md_path = os.path.join(BASE_DIR, "08_adversarial_campaign", "sspl_conformance_report.md")
    with open(md_path, "w") as f:
        f.write("# SSPL Conformance & Fail-Open Resistance Report\n\n")
        f.write("Evaluation model: **Kleene Strong 3-Valued Logic ($K_3$) with Fail-Closed Root Semantics**.\n\n")
        f.write("| Test ID | JSON Payload (snippet) | SSPL Predicate | Expected Verdict | Actual Verdict | Result |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for r in results:
            f.write(f"| `{r['test_id']}` | `{r['payload_snippet']}` | `{r['predicate_str']}` | `{r['expected_verdict']}` | `{r['actual_verdict']}` | **{r['status']}** |\n")
        f.write("\n\n## Security Invariant Verification\n")
        f.write("- **Theorem (Fail-Closed Completeness):** For all JSON documents $R$ and predicates $P$, if any leaf comparison resolves to $\\bot$ (ERROR) due to missing RFC 6901 path or type incompatibility, the root evaluation under Fail-Closed semantics satisfies $\\texttt{evaluate}(P, R) \\in \\{\\text{FAIL}, \\text{PASS}\\}$ and cannot evaluate to $\\text{PASS}$ unless an independent disjunctive branch evaluates to definitive $\\text{PASS}$.\n")
        f.write(f"- **Vulnerability Check:** Fail-Open Vulnerability Detected = **{fail_open_detected}**.\n")

    return results


if __name__ == "__main__":
    run_conformance_suite()
