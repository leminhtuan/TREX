# SSPL Conformance & Fail-Open Resistance Report

Evaluation model: **Kleene Strong 3-Valued Logic ($K_3$) with Fail-Closed Root Semantics**.

| Test ID | JSON Payload (snippet) | SSPL Predicate | Expected Verdict | Actual Verdict | Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SSPL-TC-01` | `{"status":200,"latency":45,"cached":true` | `Compare("/latency", "<=", 50)` | `PASS` | `PASS` | **PASS** |
| `SSPL-TC-02` | `{"status":200,"latency":85}` | `Compare("/latency", "<=", 50)` | `FAIL` | `FAIL` | **PASS** |
| `SSPL-TC-03` | `{"status":200}` | `Compare("/latency", "<=", 50)` | `FAIL` | `FAIL` | **PASS** |
| `SSPL-TC-04` | `{"data":"ok"}` | `Not(Compare("/error", "=", True))` | `FAIL` | `FAIL` | **PASS** |
| `SSPL-TC-05` | `{"latency":"35ms"}` | `Compare("/latency", "<=", 50)` | `FAIL` | `FAIL` | **PASS** |
| `SSPL-TC-06` | `{"latency":"fast"}` | `Not(Compare("/latency", ">", 100))` | `FAIL` | `FAIL` | **PASS** |
| `SSPL-TC-07` | `{"service":{"meta":{}}}` | `Not(Not(Compare("/service/meta/sla/uptime", "<", 99.9)))` | `FAIL` | `FAIL` | **PASS** |
| `SSPL-TC-08` | `{"status":200}` | `And(Compare("/status", "=", 200), Compare("/security_scan/passed", "=", True))` | `FAIL` | `FAIL` | **PASS** |
| `SSPL-TC-09` | `{"status":500}` | `Or(Compare("/status", "=", 200), Compare("/fallback_ok", "=", True))` | `FAIL` | `FAIL` | **PASS** |
| `SSPL-TC-10` | `{"metrics":[10,-500,9223372036854775807]` | `And(Compare("/metrics/1", "<", 0), Compare("/metrics/2", ">=", 9223372036854775807))` | `PASS` | `PASS` | **PASS** |
| `SSPL-TC-11` | `{"status":500}` | `And(Compare("/status", "=", 200), Compare("/missing_sla_probe", "<", 50))` | `FAIL` | `FAIL` | **PASS** |
| `SSPL-TC-12` | `{"status":200}` | `Or(Compare("/status", "=", 200), Compare("/missing_backup_probe", "=", 'active'))` | `PASS` | `PASS` | **PASS** |


## Security Invariant Verification
- **Theorem (Fail-Closed Completeness):** For all JSON documents $R$ and predicates $P$, if any leaf comparison resolves to $\bot$ (ERROR) due to missing RFC 6901 path or type incompatibility, the root evaluation under Fail-Closed semantics satisfies $\texttt{evaluate}(P, R) \in \{\text{FAIL}, \text{PASS}\}$ and cannot evaluate to $\text{PASS}$ unless an independent disjunctive branch evaluates to definitive $\text{PASS}$.
- **Vulnerability Check:** Fail-Open Vulnerability Detected = **False**.
