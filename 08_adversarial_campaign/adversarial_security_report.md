# T-REX Adversarial Security Matrix
**Artifact Version:** Final Replay-Hardened (App ID 772156663)

## Summary
- **Total Exploit Attempts:** 180
- **Successful Exploits:** 0 (100% rejection rate)

## Attack Matrix
- **Replay Auth (Released)**: 20 attempts, 0 exploits. Revert Mechanism: Assertion / SPENT Marker (`load 4; !; assert` pc=670)
- **Replay Auth (Refunded)**: 20 attempts, 0 exploits. Revert Mechanism: Assertion / SPENT Marker (`load 4; !; assert` pc=670)
- **Duplicate Terminal Group**: 20 attempts, 0 exploits. Revert Mechanism: Box Lookup / Session Not Found (`store 5; load 6; assert` pc=961)
- **Concurrent Auth Duplicate**: 20 attempts, 0 exploits. Revert Mechanism: Box Validation / ACTIVE Box Exists (`load 2; !; assert` pc=647)
- **Payload Tampering (H_p)**: 20 attempts, 0 exploits. Revert Mechanism: Signature Validation (`ed25519verify_bare; assert` pc=1104)
- **Bad Attester Signature**: 20 attempts, 0 exploits. Revert Mechanism: Signature Validation (`ed25519verify_bare; assert` pc=1167)
- **Deadline Tampering (r_dead)**: 20 attempts, 0 exploits. Revert Mechanism: Signature Validation (`ed25519verify_bare; assert` pc=1167)
- **Cross-User Replay**: 20 attempts, 0 exploits. Revert Mechanism: Buyer Address Assertion (`==; assert` pc=1009) & Domain Binding Signature Check (`ed25519verify_bare; assert` pc=1104)
- **Cross-Instance Replay**: 20 attempts, 0 exploits. Revert Mechanism: Domain Binding Signature Check (`ed25519verify_bare; assert` pc=1104)
