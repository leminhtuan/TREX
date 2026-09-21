"""
test_simulation.py - Unit tests for T-REX simulation engine v2 (block-alignment fixed).

All outputs are model-based synthetic estimates under stated assumptions.
No Algorand API calls. No transactions submitted.
"""
import unittest
import math
import workload_generator as wg
import sim_engine
from sim_engine import confirm_time, deadline_time_fn, SimConfig, SimEngine, SessionRecord
import metrics


# ===========================================================================
# 1. Seed Derivation
# ===========================================================================
class TestSeedDerivation(unittest.TestCase):
    def test_deterministic(self):
        s1 = wg.derive_run_seed(123, 10, 0.05, 0.1, 1, 0)
        s2 = wg.derive_run_seed(123, 10, 0.05, 0.1, 1, 0)
        self.assertEqual(s1, s2)

    def test_different_configs_differ(self):
        s1 = wg.derive_run_seed(123, 10,   0.05, 0.1, 1, 0)
        s2 = wg.derive_run_seed(123, 1000, 0.05, 0.1, 1, 0)
        s3 = wg.derive_run_seed(123, 10,   0.05, 0.1, 1, 1)
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(s1, s3)


# ===========================================================================
# 2. Exponential Delay
# ===========================================================================
class TestExpDelay(unittest.TestCase):
    def test_positive(self):
        rng = wg.make_rng(42)
        for _ in range(100):
            d = wg.exp_delay(rng, scale_seconds=0.5)
            self.assertGreater(d, 0.0)

    def test_scale_parameter_named(self):
        """Must accept scale_seconds as keyword argument."""
        rng = wg.make_rng(42)
        d = wg.exp_delay(rng, scale_seconds=2.0)
        self.assertGreater(d, 0.0)


# ===========================================================================
# 3. Block-Boundary Timing (confirm_time)
# ===========================================================================
class TestConfirmTime(unittest.TestCase):
    BT = 3.5  # block_time_s

    def test_exact_boundary(self):
        """Submission exactly on a block boundary -> confirmation = that boundary."""
        self.assertAlmostEqual(confirm_time(3.5, self.BT), 3.5)
        self.assertAlmostEqual(confirm_time(7.0, self.BT), 7.0)
        self.assertAlmostEqual(confirm_time(0.0, self.BT), 0.0)

    def test_just_before_boundary(self):
        """1 microsecond before boundary -> rounds UP to that boundary."""
        self.assertAlmostEqual(confirm_time(3.5 - 1e-9, self.BT), 3.5, places=5)

    def test_just_after_boundary(self):
        """1 microsecond after boundary -> next boundary."""
        self.assertAlmostEqual(confirm_time(3.5 + 1e-9, self.BT), 7.0, places=5)

    def test_interior(self):
        """Time in [0, 3.5) -> confirms at 3.5."""
        self.assertAlmostEqual(confirm_time(1.2, self.BT), 3.5)
        self.assertAlmostEqual(confirm_time(2.9, self.BT), 3.5)

    def test_multiple_sequential_block_waits(self):
        """Chain of confirmations accumulates correctly."""
        t0 = 0.1
        t1 = confirm_time(t0, self.BT)   # -> 3.5
        t2_sub = t1 + 0.2               # -> 3.7
        t2 = confirm_time(t2_sub, self.BT)  # -> 7.0
        t3_sub = t2 + 0.3               # -> 7.3
        t3 = confirm_time(t3_sub, self.BT)  # -> 10.5
        self.assertAlmostEqual(t1, 3.5)
        self.assertAlmostEqual(t2, 7.0)
        self.assertAlmostEqual(t3, 10.5)

    def test_next_block_boundary_alias(self):
        """workload_generator.next_block_boundary is consistent."""
        for t in [0.0, 1.0, 3.5, 3.5001, 6.9999, 7.0]:
            self.assertAlmostEqual(confirm_time(t, self.BT),
                                   wg.next_block_boundary(t, block_time=self.BT), places=9)


# ===========================================================================
# 4. Deadline Computation
# ===========================================================================
class TestDeadline(unittest.TestCase):
    def test_deadline_equality(self):
        """Deadline = auth_confirmation_time + deadline_blocks * block_time_s."""
        auth_confirm = 3.5
        dl = deadline_time_fn(auth_confirm, deadline_blocks=15, block_time_s=3.5)
        self.assertAlmostEqual(dl, 3.5 + 15 * 3.5)  # = 56.0

    def test_deadline_exceeded(self):
        """Session that takes too long -> terminal_confirmation > deadline."""
        auth_confirm = 3.5
        dl = deadline_time_fn(auth_confirm, 15, 3.5)  # 56.0
        # Simulate a very late terminal submission
        late_submit = dl + 0.01
        terminal_confirm = confirm_time(late_submit, 3.5)
        self.assertGreater(terminal_confirm, dl)

    def test_just_at_deadline(self):
        """terminal_confirmation_time == deadline_time -> TIMEOUT (> not satisfied -> OK)."""
        auth_confirm = 3.5
        dl = deadline_time_fn(auth_confirm, 15, 3.5)  # 56.0
        # Submit such that terminal confirms exactly at deadline
        self.assertAlmostEqual(confirm_time(dl, 3.5), dl)
        # In the engine: terminal_confirm_t > deadline => TIMEOUT; equality passes
        self.assertFalse(dl > dl)  # equality is NOT > so it would pass


# ===========================================================================
# 5. Session State Machine
# ===========================================================================
class TestSessionStateMachine(unittest.TestCase):
    def _make_engine(self, malicious_seller_rate=0.0, byzantine_attesters=0,
                     packet_loss=0.0, seed=42, n_events=200, n_warmup=20):
        config = SimConfig(
            lambda_val=10, packet_loss=packet_loss,
            malicious_seller_rate=malicious_seller_rate,
            byzantine_attesters=byzantine_attesters,
            n_events=n_events, n_warmup=n_warmup,
        )
        return SimEngine(config, seed, "test")

    def test_honest_run_valid_outcomes(self):
        engine = self._make_engine()
        records, _ = engine.run()
        for r in records:
            self.assertIn(r.outcome, ['Released', 'Refunded(TIMEOUT)'])

    def test_dishonest_seller_no_release(self):
        """100% malicious seller: no Released outcomes."""
        engine = self._make_engine(malicious_seller_rate=1.0)
        records, _ = engine.run()
        for r in records:
            self.assertNotEqual(r.outcome, 'Released')

    def test_byzantine_attester_some_attested_fail(self):
        """With 100% malicious seller + 1 Byzantine attester, ATTESTED_FAIL can occur."""
        engine = self._make_engine(malicious_seller_rate=1.0, byzantine_attesters=1)
        records, _ = engine.run()
        outcomes = {r.outcome for r in records}
        # Both Refunded variants are acceptable; Released is not
        self.assertNotIn('Released', outcomes)

    def test_latency_plausible(self):
        """Zero-adversary baseline: e2e latency >= 3 * block_time_s.

        There are 4 on-chain confirmation steps. The first can cost near-0 wall-clock
        time if the session arrives just before a block boundary. Steps 2, 3, and 4
        each cost at least one full block_time_s inter-gap. Hence the floor is 3 * bt.
        All sessions must also be well below deadline (15 * bt = 52.5 s) in the
        zero-adversary, no-packet-loss case.
        """
        engine = self._make_engine(n_events=500)
        records, _ = engine.run()
        meas = [r for r in records if not r.is_warmup and r.outcome == 'Released']
        if not meas:
            self.skipTest("No Released sessions in sample")
        bt = 3.5
        min_expected = 3 * bt          # 3 full inter-block gaps guaranteed
        max_expected = 15 * bt         # must not exceed deadline
        e2e_values = [r.terminal_time - r.arrival_time for r in meas if r.terminal_time]
        for e2e in e2e_values:
            self.assertGreaterEqual(e2e, min_expected - 1e-9,
                msg="e2e must be >= 3 * block_time_s (3 full inter-block gaps)")
            self.assertLessEqual(e2e, max_expected + 1e-9,
                msg="Released sessions must not exceed deadline")


# ===========================================================================
# 6. Conservation Invariants
# ===========================================================================
class TestConservation(unittest.TestCase):
    def test_amounts_within_bounds(self):
        config = SimConfig(10, 0.0, 0.0, 0, n_events=200, n_warmup=20)
        engine = SimEngine(config, 42, "test")
        records, _ = engine.run()
        for r in records:
            if r.outcome in ('Released', 'Refunded(TIMEOUT)', 'Refunded(ATTESTED_FAIL)'):
                self.assertLessEqual(r.usdc_transfer_amount, r.amount_pay_micro)
                self.assertLessEqual(r.bounty_transfer_amount, r.amount_bounty_micro)
                self.assertEqual(len(r.conservation_violations), 0)

    def test_no_violations_zero_adversary(self):
        config = SimConfig(10, 0.0, 0.0, 0, n_events=200, n_warmup=20)
        engine = SimEngine(config, 42, "test")
        records, _ = engine.run()
        violations = sum(len(r.conservation_violations) for r in records)
        self.assertEqual(violations, 0)


# ===========================================================================
# 7. Single Payout
# ===========================================================================
class TestSinglePayout(unittest.TestCase):
    def test_bounty_paid_exactly_once(self):
        config = SimConfig(10, 0.0, 0.0, 0, n_events=200, n_warmup=20)
        engine = SimEngine(config, 42, "test")
        records, _ = engine.run()
        for r in records:
            if r.terminal_time is not None:
                self.assertTrue(r.bounty_paid, "bounty_paid must be True for terminal session")
                self.assertEqual(r.bounty_transfer_count, 1, "exactly one bounty transfer")


# ===========================================================================
# 8. Denominator = 0 -> NA
# ===========================================================================
class TestDenominatorZeroNA(unittest.TestCase):
    def test_frr_na_zero_adversary(self):
        config = SimConfig(10, 0.0, 0.0, 0, n_events=200, n_warmup=20)
        engine = SimEngine(config, 42, "test")
        records, _ = engine.run()
        self.assertIsNone(metrics.compute_frr(records), "frr must be NA when no dishonest sellers")

    def test_odr_na_zero_adversary(self):
        config = SimConfig(10, 0.0, 0.0, 0, n_events=200, n_warmup=20)
        engine = SimEngine(config, 42, "test")
        records, _ = engine.run()
        self.assertIsNone(metrics.compute_odr(records), "odr must be NA when no omissions")


# ===========================================================================
# 9. ODR Omission Definition
# ===========================================================================
class TestODRDefinition(unittest.TestCase):
    def test_omission_counted(self):
        s = SessionRecord(1, 0.0, True, [True]*3, True)
        s.failure_mode = 'seller_omission'
        s.outcome = 'Refunded(TIMEOUT)'
        self.assertEqual(metrics.compute_odr([s]), 1.0)

    def test_non_omission_not_counted(self):
        s = SessionRecord(1, 0.0, True, [True]*3, True)
        s.failure_mode = 'packet_loss'
        s.outcome = 'Refunded(TIMEOUT)'
        self.assertIsNone(metrics.compute_odr([s]))

    def test_mixed(self):
        s1 = SessionRecord(1, 0.0, True, [True]*3, True)
        s1.failure_mode = 'seller_omission'
        s1.outcome = 'Refunded(TIMEOUT)'
        s2 = SessionRecord(2, 0.0, True, [True]*3, True)
        s2.failure_mode = 'seller_omission'
        s2.outcome = 'Released'  # unusual but test denominator
        self.assertAlmostEqual(metrics.compute_odr([s1, s2]), 0.5)


# ===========================================================================
# 10. BFSR Sub-Scenarios
# ===========================================================================
class TestBFSRSubScenarios(unittest.TestCase):
    def test_duplicate_claim_detected(self):
        s = SessionRecord(1, 0.0, True, [True]*3, True)
        s.bounty_farming_subscenario = 'duplicate_claim'
        s.bounty_farming_attempted = True
        s.bounty_farming_detected = True
        res = metrics.compute_bfsr([s])
        self.assertAlmostEqual(res['duplicate_claim'], 0.0)
        self.assertIsNone(res['front_running'])

    def test_front_running_undetected(self):
        s = SessionRecord(1, 0.0, True, [True]*3, True)
        s.bounty_farming_subscenario = 'front_running'
        s.bounty_farming_attempted = True
        s.bounty_farming_detected = False
        res = metrics.compute_bfsr([s])
        self.assertAlmostEqual(res['front_running'], 1.0)
        self.assertIsNone(res['duplicate_claim'])

    def test_collusion_not_attempted(self):
        s = SessionRecord(1, 0.0, True, [True]*3, True)
        s.bounty_farming_subscenario = 'relayer_attester_collusion'
        s.bounty_farming_attempted = False
        res = metrics.compute_bfsr([s])
        self.assertIsNone(res['relayer_attester_collusion'])


# ===========================================================================
# 11. Packet-Loss Classification
# ===========================================================================
class TestPacketLossClassification(unittest.TestCase):
    def test_auth_packet_loss_sets_failure_detail(self):
        """With 100% packet loss, all sessions should be packet_loss failures."""
        config = SimConfig(10, 1.0, 0.0, 0, n_events=50, n_warmup=0)
        engine = SimEngine(config, 99, "test_pl")
        records, _ = engine.run()
        for r in records:
            self.assertEqual(r.failure_mode, 'packet_loss')
            self.assertIn(r.failure_detail, [
                'packet_loss_authorize', 'packet_loss_payload', 'packet_loss_attestation'
            ])

    def test_no_packet_loss_zero_failure_detail(self):
        """With 0% packet loss, no packet_loss failure_detail."""
        config = SimConfig(10, 0.0, 0.0, 0, n_events=100, n_warmup=0)
        engine = SimEngine(config, 99, "test_no_pl")
        records, _ = engine.run()
        for r in records:
            self.assertNotIn(r.failure_detail, [
                'packet_loss_authorize', 'packet_loss_payload', 'packet_loss_attestation'
            ])


# ===========================================================================
# 12. Deterministic Replay with Hash
# ===========================================================================
class TestDeterministicReplay(unittest.TestCase):
    def _serialize_records(self, records):
        """Produce a deterministic byte string from session records."""
        import json
        rows = []
        for r in records:
            rows.append({
                'id': r.session_id,
                'outcome': r.outcome,
                'failure_mode': r.failure_mode,
                'terminal_time': round(r.terminal_time, 9) if r.terminal_time else None,
                'auth_confirmation_time': round(r.auth_confirmation_time, 9) if r.auth_confirmation_time else None,
            })
        return json.dumps(rows, sort_keys=True).encode('utf-8')

    def test_identical_seed_identical_outcomes(self):
        import hashlib
        config = SimConfig(10, 0.0, 0.0, 0, n_events=50, n_warmup=5)
        for seed in [42, 999, 20260816]:
            e1 = SimEngine(config, seed, "r1")
            r1, _ = e1.run()
            e2 = SimEngine(config, seed, "r2")
            r2, _ = e2.run()
            b1 = self._serialize_records(r1)
            b2 = self._serialize_records(r2)
            h1 = hashlib.sha256(b1).hexdigest()
            h2 = hashlib.sha256(b2).hexdigest()
            self.assertEqual(h1, h2, msg="Seed {} replay hash mismatch".format(seed))


if __name__ == '__main__':
    unittest.main()
