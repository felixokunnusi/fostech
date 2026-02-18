import requests

PAYSTACK_BANKS_URL = "https://api.paystack.co/bank"


def fetch_banks(secret_key: str):
    headers = {"Authorization": f"Bearer {secret_key}"}

    r = requests.get(PAYSTACK_BANKS_URL, headers=headers, timeout=30)
    data = r.json()

    if not r.ok or not data.get("status"):
        raise Exception("Failed to fetch banks")

    # return only active Nigerian banks
    banks = [
        {
            "name": b["name"],
            "code": b["code"]
        }
        for b in data["data"]
        if b.get("active") and b.get("currency") == "NGN"
    ]

    # sort alphabetically
    banks.sort(key=lambda x: x["name"].lower())
    return banks
