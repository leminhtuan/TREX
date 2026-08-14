# T-REX Escrow Smart Contract

This directory contains the PyTeal implementation of the T-REX conditional settlement escrow, designed to bind HTTP service requests, SLA predicates, and micropayment settlements on the Algorand blockchain.

## Architecture

The escrow uses a state machine defined in `trex_escrow.py` with the following transitions:
- `Idle` -> `Authorized`: Buyer locks funds.
- `Authorized` -> `Released`: Seller provides valid SLA payload and attester signatures.
- `Authorized` -> `Refunded`: Timeout or failed SLA attestation.

It utilizes Algorand's Box Storage (AVM 8+) to store session state dynamically.

## Build and Test

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Compile the contract:
   ```bash
   python compile.py
   ```
3. Run tests:
   ```bash
   pytest --cov=trex_escrow test_trex_escrow.py
   ```

## Deployment

To deploy to Testnet (or Localnet):
```bash
python deploy.py --network testnet
```

### Mainnet Experimental Safety Checklist

> [!CAUTION]
> Deploying to Mainnet puts real funds at risk. Do not deploy without reviewing the TEAL code.

Before Mainnet deployment:
- [ ] Set `ALLOW_MAINNET_DEPLOY=true` in environment.
- [ ] Set `DEPLOYER_MNEMONIC`, `ATTESTER_1_MNEMONIC`, `ATTESTER_2_MNEMONIC`, `ATTESTER_3_MNEMONIC`.
- [ ] Confirm typed prompt: `DEPLOY_TREX_MAINNET`.
- [ ] Ensure the USDC ASA ID is `31566704`.
- [ ] Verify maximum capital limits are respected.

Run:
```bash
python deploy.py --network mainnet
```

## Protocol Details

- **Threshold**: $t=2$ of $n=3$ attesters required for settlement or attested refund.
- **USDC Asset ID**: 31566704
- **Nonce**: 32-byte cryptographically secure nonce to prevent replays.
- **Opcode Budget**: Settlement and refund operations utilize OpUp inner transactions (pooling fee budget) to accommodate multiple `Ed25519Verify` calls within the AVM cost limits.

## Disclaimers
This implementation is for experimental/research purposes. It has **not** been externally audited. Use at your own risk.
