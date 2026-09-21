"""
sim_engine.py - T-REX Discrete-Event Simulation Engine (v2, block-alignment fixed)

All outputs are model-based synthetic estimates under stated assumptions.
No Algorand API calls. No transactions submitted.

Block-alignment convention:
  - Each on-chain submission confirms at the FIRST block boundary >= submission_time.
  - If submission_time falls exactly ON a boundary, confirmation = that boundary.
  - Deadline = auth_confirmation_time + deadline_blocks * block_time_s
    (measured from the block that confirmed authorization).

Session timing flow:
  arrival_time
    -> auth_submit_time = arrival_time + auth_service_scale_s delay
    -> auth_confirmation_time = next_block_boundary(auth_submit_time)  [ON-CHAIN STEP 1]
    -> deadline_time = auth_confirmation_time + deadline_blocks * block_time_s
    -> seller_submit_time = auth_confirmation_time + seller_service_scale_s delay
    -> seller_confirmation_time = next_block_boundary(seller_submit_time)  [ON-CHAIN STEP 2]
    -> attest_submit_time[i] = seller_confirmation_time + attest_service_scale_s delay
    -> all_attest_confirmed = next_block_boundary(max(attest_submit_times))  [ON-CHAIN STEP 3]
    -> relayer_submit_time = all_attest_confirmed + relayer_service_scale_s delay
    -> terminal_confirmation_time = next_block_boundary(relayer_submit_time)  [ON-CHAIN STEP 4]
    -> if terminal_confirmation_time > deadline_time: outcome = Refunded(TIMEOUT)

Failure modes are tracked at sub-step granularity via failure_mode and failure_detail fields.
The primary failure_mode field preserves the frozen schema value for CSV output.
"""
import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List
import workload_generator as wg


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SessionState(Enum):
    CREATED = auto()
    AUTHORIZED = auto()
    PAYLOAD_SUBMITTED = auto()
    TIMED_OUT = auto()
    ATTESTED_PASS = auto()
    ATTESTED_FAIL = auto()
    RELEASED = auto()
    REFUNDED_TIMEOUT = auto()
    REFUNDED_ATTESTED_FAIL = auto()

class FailureMode(str, Enum):
    """Primary failure mode values (frozen in output schema)."""
    none                    = 'none'
    seller_omission         = 'seller_omission'
    packet_loss             = 'packet_loss'
    attester_unavailability = 'attester_unavailability'
    relayer_failure         = 'relayer_failure'
    byzantine_attester      = 'byzantine_attester'
    adversarial_relayer     = 'adversarial_relayer'

class FailureDetail(str, Enum):
    """Sub-classification within packet_loss (not in frozen schema; stored in failure_detail)."""
    none                    = 'none'
    packet_loss_authorize   = 'packet_loss_authorize'
    packet_loss_payload     = 'packet_loss_payload'
    packet_loss_attestation = 'packet_loss_attestation'

class BountyFarmingScenario(str, Enum):
    none                     = 'none'
    duplicate_claim          = 'duplicate_claim'
    replay_after_terminal    = 'replay_after_terminal'
    front_running            = 'front_running'
    relayer_attester_collusion = 'relayer_attester_collusion'


# ---------------------------------------------------------------------------
# Timing primitives (pure functions, no side-effects)
# ---------------------------------------------------------------------------

def confirm_time(submission_time: float, block_time_s: float) -> float:
    """Return the first block boundary >= submission_time.

    Convention:
      - If submission_time == k * block_time_s exactly, returns submission_time.
      - Otherwise returns ceil(submission_time / block_time_s) * block_time_s.

    This matches next_block_boundary in workload_generator but is explicit here
    so callers in sim_engine never depend on an imported helper for the core model.
    """
    if block_time_s <= 0:
        raise ValueError("block_time_s must be positive")
    ratio = submission_time / block_time_s
    block_index = math.ceil(ratio)
    return block_index * block_time_s

def deadline_time_fn(auth_confirmation_time: float, deadline_blocks: int, block_time_s: float) -> float:
    """Deadline = auth_confirmation_time + deadline_blocks * block_time_s."""
    return auth_confirmation_time + deadline_blocks * block_time_s


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SimConfig:
    lambda_val: float
    packet_loss: float
    malicious_seller_rate: float
    byzantine_attesters: int           # 0 or 1
    n_events: int = 10000
    n_warmup: int = 1000
    block_time_s: float = 3.5
    deadline_blocks: int = 15          # deadline = auth_confirm + 15 * block_time_s
    auth_service_scale_s: float = 0.5  # Exp mean for buyer->chain authorization delay
    seller_service_scale_s: float = 0.3
    attester_service_scale_s: float = 0.1
    relayer_service_scale_s: float = 0.2
    attester_unavailability_prob: float = 0.0
    relayer_failure_prob: float = 0.0

@dataclass
class SessionRecord:
    session_id: int
    arrival_time: float
    seller_honest: bool
    attester_honest: list              # [bool, bool, bool]
    relayer_honest: bool
    amount_pay_micro: int = 500000
    amount_bounty_micro: int = 500000
    # Timing (all in simulated seconds)
    auth_submit_time: Optional[float] = None
    auth_confirmation_time: Optional[float] = None  # first block boundary >= auth_submit
    deadline_time: Optional[float] = None
    seller_submit_time: Optional[float] = None
    seller_confirmation_time: Optional[float] = None
    attest_submit_times: list = field(default_factory=list)
    all_attest_confirmed_time: Optional[float] = None
    relayer_submit_time: Optional[float] = None
    terminal_confirmation_time: Optional[float] = None  # = terminal_time for schema compat
    terminal_time: Optional[float] = None              # alias, kept for metric compatibility
    state: str = 'CREATED'
    outcome: str = 'Pending'
    failure_mode: str = 'none'         # frozen schema value
    failure_detail: str = 'none'       # sub-classification; not in frozen CSV but logged
    usdc_transfer_count: int = 0
    usdc_transfer_amount: int = 0
    bounty_transfer_count: int = 0
    bounty_transfer_amount: int = 0
    bounty_paid: bool = False
    conservation_violations: list = field(default_factory=list)
    is_warmup: bool = False
    bounty_farming_subscenario: str = 'none'
    bounty_farming_attempted: bool = False
    bounty_farming_detected: bool = False

    # Computed convenience: use terminal_confirmation_time as terminal_time
    def __post_init__(self):
        pass  # terminal_time set explicitly after finalization

@dataclass
class EventRow:
    run_id: str
    event_id: int
    session_id: int
    event_type: str
    simulated_timestamp_s: float
    seller_honest: bool
    attester_honest: list
    packet_dropped: bool
    relayer_honest: bool
    failure_mode: str
    outcome: str
    is_warmup: bool


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------

class SimEngine:
    """Discrete-event simulation engine for T-REX protocol.

    All outputs are model-based synthetic estimates under stated assumptions.
    """

    def __init__(self, config: SimConfig, run_seed: int, run_id: str):
        self.config = config
        self.run_seed = run_seed
        self.run_id = run_id
        self.rng = wg.make_rng(run_seed)
        self.event_counter = 0
        self._records: List[SessionRecord] = []

    # ------------------------------------------------------------------
    # Agent assignment
    # ------------------------------------------------------------------

    def _assign_session_agents(self) -> tuple:
        """Draw agent honesty flags. Consumes 1 rng.random() call for seller."""
        seller_honest = self.rng.random() >= self.config.malicious_seller_rate
        # Byzantine attester: index 0 is always Byzantine if byzantine_attesters == 1
        attester_honest = [True, True, True]
        if self.config.byzantine_attesters == 1:
            attester_honest[0] = False
        relayer_honest = True  # reduced design: relayer always honest
        return seller_honest, attester_honest, relayer_honest

    # ------------------------------------------------------------------
    # Core session simulation
    # ------------------------------------------------------------------

    def _simulate_session(self, session_id: int, arrival_time: float, is_warmup: bool) -> SessionRecord:
        cfg = self.config
        seller_honest, attester_honest, relayer_honest = self._assign_session_agents()

        s = SessionRecord(
            session_id=session_id,
            arrival_time=arrival_time,
            seller_honest=seller_honest,
            attester_honest=attester_honest,
            relayer_honest=relayer_honest,
            is_warmup=is_warmup,
        )

        # ---- STEP 1: Authorization ----------------------------------------
        # Buyer submits authorization. Network delay is a service time draw.
        auth_service_delay = wg.exp_delay(self.rng, cfg.auth_service_scale_s)
        auth_submit_t = arrival_time + auth_service_delay
        s.auth_submit_time = auth_submit_t

        # Packet loss on authorization message
        auth_packet_dropped = self.rng.random() < cfg.packet_loss
        if auth_packet_dropped:
            # Authorization message never reaches chain -> session eventually times out
            # terminal_time = auth_submit_t (the moment the drop is "detected" by timeout)
            # In protocol, buyer would retry; in this model, loss => timeout
            s.failure_mode = FailureMode.packet_loss.value
            s.failure_detail = FailureDetail.packet_loss_authorize.value
            s.outcome = 'Refunded(TIMEOUT)'
            s.state = SessionState.REFUNDED_TIMEOUT.name
            # terminal time = next block boundary after submission (when timeout is detected)
            s.terminal_confirmation_time = confirm_time(auth_submit_t, cfg.block_time_s)
            s.terminal_time = s.terminal_confirmation_time
            self._finalize_session(s)
            return s

        # Authorization confirmed at first block boundary
        s.auth_confirmation_time = confirm_time(auth_submit_t, cfg.block_time_s)
        s.deadline_time = deadline_time_fn(s.auth_confirmation_time, cfg.deadline_blocks, cfg.block_time_s)
        s.state = SessionState.AUTHORIZED.name

        # ---- STEP 2: Seller submits payload --------------------------------
        seller_service_delay = wg.exp_delay(self.rng, cfg.seller_service_scale_s)
        seller_submit_t = s.auth_confirmation_time + seller_service_delay
        s.seller_submit_time = seller_submit_t

        # Packet loss on payload message
        seller_packet_dropped = self.rng.random() < cfg.packet_loss
        if seller_packet_dropped:
            s.failure_mode = FailureMode.packet_loss.value
            s.failure_detail = FailureDetail.packet_loss_payload.value
            s.outcome = 'Refunded(TIMEOUT)'
            s.state = SessionState.REFUNDED_TIMEOUT.name
            s.terminal_confirmation_time = confirm_time(s.deadline_time, cfg.block_time_s)
            s.terminal_time = s.terminal_confirmation_time
            self._finalize_session(s)
            return s

        # Seller omission: service time exceeds remaining window before deadline
        seller_confirm_t = confirm_time(seller_submit_t, cfg.block_time_s)
        if seller_confirm_t >= s.deadline_time:
            s.failure_mode = FailureMode.seller_omission.value
            s.failure_detail = FailureDetail.none.value
            s.outcome = 'Refunded(TIMEOUT)'
            s.state = SessionState.REFUNDED_TIMEOUT.name
            s.terminal_confirmation_time = confirm_time(s.deadline_time, cfg.block_time_s)
            s.terminal_time = s.terminal_confirmation_time
            self._finalize_session(s)
            return s

        s.seller_confirmation_time = seller_confirm_t
        s.state = SessionState.PAYLOAD_SUBMITTED.name

        # ---- STEP 3: Attestation ------------------------------------------
        # Each of 3 attesters independently observes payload and submits vote.
        attest_votes: list = []
        attest_submit_times: list = []

        for i in range(3):
            attest_service_delay = wg.exp_delay(self.rng, cfg.attester_service_scale_s)
            attester_unavail = self.rng.random() < cfg.attester_unavailability_prob
            if attester_unavail:
                # This attester does not respond; no random draw for vote
                continue

            attest_st = s.seller_confirmation_time + attest_service_delay
            attest_submit_times.append(attest_st)

            # Packet loss on attestation message
            attest_packet_dropped = self.rng.random() < cfg.packet_loss
            if attest_packet_dropped:
                # This attester's message lost; effectively unavailable
                continue

            # Honest vote: PASS if seller_honest, FAIL if not
            honest_vote = 'PASS' if s.seller_honest else 'FAIL'
            vote = ('FAIL' if honest_vote == 'PASS' else 'PASS') if not attester_honest[i] else honest_vote
            attest_votes.append(vote)

        s.attest_submit_times = attest_submit_times

        # Need at least 2 votes for a quorum
        if len(attest_votes) < 2:
            s.failure_mode = FailureMode.attester_unavailability.value
            s.failure_detail = FailureDetail.none.value
            s.outcome = 'Refunded(TIMEOUT)'
            s.state = SessionState.REFUNDED_TIMEOUT.name
            s.terminal_confirmation_time = confirm_time(s.deadline_time, cfg.block_time_s)
            s.terminal_time = s.terminal_confirmation_time
            self._finalize_session(s)
            return s

        pass_count = attest_votes.count('PASS')
        fail_count = attest_votes.count('FAIL')

        if pass_count >= 2:
            verdict = 'PASS'
            s.state = SessionState.ATTESTED_PASS.name
        elif fail_count >= 2:
            verdict = 'FAIL'
            s.state = SessionState.ATTESTED_FAIL.name
            s.failure_mode = FailureMode.byzantine_attester.value if not all(attester_honest) else FailureMode.none.value
        else:
            # Tie (1 PASS, 1 FAIL from 2 votes) -> unresolvable -> timeout
            s.failure_mode = FailureMode.attester_unavailability.value
            s.outcome = 'Refunded(TIMEOUT)'
            s.state = SessionState.REFUNDED_TIMEOUT.name
            s.terminal_confirmation_time = confirm_time(s.deadline_time, cfg.block_time_s)
            s.terminal_time = s.terminal_confirmation_time
            self._finalize_session(s)
            return s

        # All attest messages confirmed at first block boundary after last submission
        if attest_submit_times:
            s.all_attest_confirmed_time = confirm_time(max(attest_submit_times), cfg.block_time_s)
        else:
            s.all_attest_confirmed_time = confirm_time(s.seller_confirmation_time, cfg.block_time_s)

        # ---- STEP 4: Relayer submits terminal transaction ------------------
        relayer_service_delay = wg.exp_delay(self.rng, cfg.relayer_service_scale_s)
        relayer_submit_t = s.all_attest_confirmed_time + relayer_service_delay
        s.relayer_submit_time = relayer_submit_t

        relayer_fail = self.rng.random() < cfg.relayer_failure_prob
        if relayer_fail:
            s.failure_mode = FailureMode.relayer_failure.value
            s.outcome = 'Refunded(TIMEOUT)'
            s.state = SessionState.REFUNDED_TIMEOUT.name
            s.terminal_confirmation_time = confirm_time(s.deadline_time, cfg.block_time_s)
            s.terminal_time = s.terminal_confirmation_time
            self._finalize_session(s)
            return s

        # Terminal tx confirmed at first block boundary after relayer submission
        terminal_confirm_t = confirm_time(relayer_submit_t, cfg.block_time_s)
        s.terminal_confirmation_time = terminal_confirm_t
        s.terminal_time = terminal_confirm_t  # alias for metric compatibility

        # Deadline check: terminal must confirm BEFORE deadline
        if terminal_confirm_t > s.deadline_time:
            s.outcome = 'Refunded(TIMEOUT)'
            s.state = SessionState.REFUNDED_TIMEOUT.name
            self._finalize_session(s)
            return s

        # Outcome determined by verdict
        if verdict == 'PASS':
            s.outcome = 'Released'
            s.state = SessionState.RELEASED.name
        else:
            s.outcome = 'Refunded(ATTESTED_FAIL)'
            s.state = SessionState.REFUNDED_ATTESTED_FAIL.name

        self._finalize_session(s)

        # Bounty-farming check (adversarial scenarios only, non-warmup)
        if not is_warmup and self.config.malicious_seller_rate > 0.0:
            self._check_bounty_farming(s)

        return s

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def _finalize_session(self, s: SessionRecord):
        """Set conservation fields and check invariants."""
        if s.outcome in ('Released', 'Refunded(TIMEOUT)', 'Refunded(ATTESTED_FAIL)'):
            s.usdc_transfer_count = 1
            s.usdc_transfer_amount = 500000
            s.bounty_transfer_count = 1
            s.bounty_transfer_amount = 500000
            s.bounty_paid = True

        if s.usdc_transfer_amount > s.amount_pay_micro:
            s.conservation_violations.append('usdc_amount_exceeds_pay')
        if s.bounty_transfer_amount > s.amount_bounty_micro:
            s.conservation_violations.append('bounty_amount_exceeds_bounty')

    # ------------------------------------------------------------------
    # Adversarial bounty farming
    # ------------------------------------------------------------------

    def _check_bounty_farming(self, s: SessionRecord):
        scenarios = ['duplicate_claim', 'replay_after_terminal', 'front_running', 'relayer_attester_collusion']
        scenario = self.rng.choice(scenarios)
        s.bounty_farming_subscenario = scenario
        if scenario == 'relayer_attester_collusion':
            s.bounty_farming_attempted = False
        else:
            s.bounty_farming_attempted = True
            if scenario in ('duplicate_claim', 'replay_after_terminal'):
                s.bounty_farming_detected = True   # protocol always rejects
            elif scenario == 'front_running':
                # MODEL ASSUMPTION: adversary wins same-block race 10% of the time
                s.bounty_farming_detected = self.rng.random() < 0.9

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> tuple:
        total_sessions = self.config.n_warmup + self.config.n_events
        arrivals = wg.generate_session_arrivals(self.rng, self.config.lambda_val, total_sessions)

        records: List[SessionRecord] = []
        event_rows: List[EventRow] = []

        for i in range(total_sessions):
            is_warmup = i < self.config.n_warmup
            s = self._simulate_session(i, arrivals[i], is_warmup)
            records.append(s)

            self.event_counter += 1
            event_rows.append(EventRow(
                run_id=self.run_id,
                event_id=self.event_counter,
                session_id=s.session_id,
                event_type='TERMINAL',
                simulated_timestamp_s=s.terminal_time or 0.0,
                seller_honest=s.seller_honest,
                attester_honest=s.attester_honest,
                packet_dropped=(s.failure_mode == 'packet_loss'),
                relayer_honest=s.relayer_honest,
                failure_mode=s.failure_mode,
                outcome=s.outcome,
                is_warmup=s.is_warmup,
            ))

        self._records = records
        return records, event_rows

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def sim_duration_s(self) -> float:
        if not self._records:
            return 0.0
        meas = [r for r in self._records if not r.is_warmup and r.terminal_time is not None]
        if not meas:
            return 0.0
        first_t = min(r.terminal_time for r in meas)
        last_t  = max(r.terminal_time for r in meas)
        return max(0.0, last_t - first_t)
