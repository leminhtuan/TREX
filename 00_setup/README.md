# T-REX Experiments Setup

This directory contains the necessary setup files and configuration for the T-REX experiments.

## 1. Getting Mnemonics from Pera Wallet
To export your account mnemonic from Pera Wallet:
1. Open the Pera Wallet app.
2. Tap on the account you want to export.
3. Tap the three dots (More options) in the top right corner.
4. Select "View Passphrase".
5. Write down the 25 words carefully. Update the `config.yaml` or `.env` files with these mnemonics.

## 2. Funding Accounts
Before running the pilot or simulation, ensure your accounts are funded:
- **ALGO**: Required for transaction fees and minimum balance requirements.
- **USDC**: Required for test transactions (ASA ID: `31566704`).
- Transfer ALGO and USDC from an exchange or another wallet to your test accounts.

## 3. Mainnet Safety Checklist
> [!CAUTION]
> You are operating on Mainnet. Real funds are at risk.
- [ ] Verify that `MAX_CAPITAL_AT_RISK_USD` is set to an acceptable limit (e.g., $10).
- [ ] Verify that `MAX_TOTAL_COST_USD` is properly configured.
- [ ] Ensure that only the required amount of ALGO and USDC is available in the test accounts to minimize potential loss.
- [ ] Double-check the network configuration is indeed pointing to `mainnet`.
- [ ] Review all smart contract code before deploying.

## 4. Checking Balances
To check account balances during the experiment, you can use any Algorand block explorer (e.g., [AlgoExplorer](https://algoexplorer.io/) or [Allo](https://allo.info/)) by searching for your account address.
