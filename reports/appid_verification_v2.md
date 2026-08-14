# Application ID Forensic Verification Report

## 1. Overview
This audit verifies the exact Application ID invoked by each transaction during the pilot phase.
Two Application IDs were investigated:
- App Old: 769241061
- App Final: 769248116

## 2. Transaction Audits
Total TXIDs analyzed: 24
- VERIFIED (App Old): 0
- VERIFIED (App Final): 24
- NOT_FOUND/NOT_VERIFIABLE: 0

## 3. Session Consistency
- Sessions consistently using App Final: 18
- Sessions with mixed or unknown Apps: 0

## 4. Deployment Forensics
`json
{
  "769241061": {
    "creation_txid": "VXOCPHFBCMIE3M4MWJZLTIBGBFXG3YAOPD6FVTT7LV3GC6KTIO7A",
    "creation_round": 66297187,
    "approval_program_len": 2020,
    "approval_program_sha256": "25d92141526f0013213d5f5ff64764575d637af5373fca9cf8ac8099bea51461",
    "clear_program_len": 4,
    "clear_program_sha256": "d17be8c9ad6dedb5b4394a8fdc00273a4deb4725415ff8ce151a12544b4a280a"
  },
  "769248116": {
    "creation_txid": "BULKMXVYFO4RTF2GAYHDR343NLXEMQ3TTAVBEBIQLVMTKKMVCNHA",
    "creation_round": 66301515,
    "approval_program_len": 2048,
    "approval_program_sha256": "c51aa4a4c8affc932086248dd9d6de4af09b939aacaae1804ae391f9ddb32a28",
    "clear_program_len": 4,
    "clear_program_sha256": "d17be8c9ad6dedb5b4394a8fdc00273a4deb4725415ff8ce151a12544b4a280a"
  }
}
`

## 5. Conclusion
Based on strictly verifiable on-chain evidence:
a) Toan bo pilot dung app final (769248116).

(Note: No assumptions regarding OpUp were made without direct deployment bytecode evidence.)
