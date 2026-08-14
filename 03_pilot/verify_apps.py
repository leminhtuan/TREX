import requests
import base64

def get_app_info(app_id):
    url = f"https://testnet-api.algonode.cloud/v2/applications/{app_id}"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        print(f"App {app_id} EXISTS.")
        params = data.get("params", {})
        apap = params.get("approval-program", "")
        apsu = params.get("clear-state-program", "")
        print(f"  Creator: {params.get('creator')}")
        print(f"  Approval len: {len(base64.b64decode(apap)) if apap else 0}")
        print(f"  Clear len: {len(base64.b64decode(apsu)) if apsu else 0}")
        return apap, apsu
    else:
        print(f"App {app_id} DOES NOT EXIST or Error: {resp.status_code}")
        return None, None

def main():
    a1, c1 = get_app_info(769241061)
    a2, c2 = get_app_info(769248116)
    
    if a1 and a2:
        if a1 == a2 and c1 == c2:
            print("Both apps have EXACTLY the same bytecode.")
        else:
            print("Apps have DIFFERENT bytecode.")

if __name__ == '__main__':
    main()
