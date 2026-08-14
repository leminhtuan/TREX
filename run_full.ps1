cd c:\Users\lemin\OneDrive\Desktop\trex-experiments\01_contracts
.\.venv\Scripts\python.exe compile.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
.\.venv\Scripts\python.exe deploy.py --network testnet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
.\.venv\Scripts\python.exe opt_in_contract.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

cd ..\03_pilot
..\01_contracts\.venv\Scripts\python.exe run_pilot.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
