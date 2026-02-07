import requests
from flask import current_app

PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/"

def verify_paystack_payment(reference):
    headers = {
        "Authorization": f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
    }

    response = requests.get(
        PAYSTACK_VERIFY_URL + reference,
        headers=headers,
        timeout=15
    )

    if response.status_code != 200:
        return None

    data = response.json()
    if data.get("status") is True:
        return data["data"]

    return None
