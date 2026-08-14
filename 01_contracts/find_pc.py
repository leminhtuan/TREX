import json
from algosdk.v2client import algod
import config

client = algod.AlgodClient("", config.ALGONODE_URL)

with open("approval.teal", "r") as f:
    teal_code = f.read()

res = client.compile(teal_code, source_map=True)
sourcemap_b64 = res.get("sourcemap")

import base64
sourcemap_raw = base64.b64decode(sourcemap_b64)

# Sourcemap is a JSON-like structure (Wait, no, sourcemap mapping format is v3 JSON)
sourcemap = json.loads(sourcemap_raw)
mapping = sourcemap["mapping"]

# It uses standard sourcemap format. A simpler way is to just use pyteal.
# Or better, we can just disassemble the bytecode!
# Wait, goal clerk disassemble is not available?
