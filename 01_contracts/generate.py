from algosdk import account, mnemonic

keys = [account.generate_account() for _ in range(4)]
env = f'DEPLOYER_MNEMONIC="{mnemonic.from_private_key(keys[0][0])}"\n' \
      f'ATTESTER_1_MNEMONIC="{mnemonic.from_private_key(keys[1][0])}"\n' \
      f'ATTESTER_2_MNEMONIC="{mnemonic.from_private_key(keys[2][0])}"\n' \
      f'ATTESTER_3_MNEMONIC="{mnemonic.from_private_key(keys[3][0])}"\n'

with open('.env', 'w') as f:
    f.write(env)

print('Deployer Address:', keys[0][1])
