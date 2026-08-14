.venv\Scripts\Activate.ps1
algokit localnet start
Start-Sleep -Seconds 30
algokit localnet status
pytest test_integration_authorize.py test_integration_settle.py test_integration_refund.py test_integration_invariants.py --cov=trex_escrow --cov-report=term-missing > coverage_report.txt
