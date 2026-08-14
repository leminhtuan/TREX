import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "02_clients"))

import config
import buyer_agent
import seller_agent
import attester
import relayer

def main():
    print("Starting T-REX Mock E2E Test...")
    
    buyer = buyer_agent.BuyerAgent()
    seller = seller_agent.SellerAgent()
    a1 = attester.AttesterAgent(0, config.ATTESTER_1_SK)
    a2 = attester.AttesterAgent(1, config.ATTESTER_2_SK)
    r = relayer.RelayerAgent()
    
    # 1. Buyer Authorize
    params = buyer.client.suggested_params()
    deadline = params.first + 100
    
    print("\n--- 1. BUYER AUTHORIZE ---")
    try:
        buyer_out = buyer.authorize(config.SELLER_ADDR, 500000, 500000, deadline)
    except Exception as e:
        print("Authorize Failed. Likely because USDC asset 31566704 does not exist on Testnet.")
        print("Error:", e)
        return
        
    session_id = buyer_out["session_id"]
    H_q = buyer_out["H_q"]
    H_c = buyer_out["H_c"]
    nonce = buyer_out["nonce"]
    
    # 2. Seller Process
    print("\n--- 2. SELLER PROCESS ---")
    seller_out = seller.process_request(session_id, H_q, H_c, nonce)
    H_p = seller_out["H_p"]
    seller_sig = seller_out["seller_signature"]
    
    # 3. Attesters Evaluate
    print("\n--- 3. ATTESTERS EVALUATE ---")
    att1_out = a1.attest(session_id, nonce, H_q, H_c, H_p, verdict=1)
    att2_out = a2.attest(session_id, nonce, H_q, H_c, H_p, verdict=1)
    
    # 4. Relayer Settle
    print("\n--- 4. RELAYER SETTLE ---")
    r.settle(session_id, H_p, seller_sig, att1_out, att2_out)
    
    print("\nE2E Test Complete. Check results/pilot/transactions.csv")

if __name__ == "__main__":
    main()
