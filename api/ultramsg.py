import requests

ID_INSTANCE = "7107621756"
API_TOKEN_INSTANCE = "06eb4a45e29a4c828619052b0843da80ddfbea077502471c89"

BASE_URL = f"https://7107.api.greenapi.com/waInstance{ID_INSTANCE}"


def send_whatsapp_message(phone, message):
    phone = str(phone).replace("+", "").replace(" ", "")

    if len(phone) == 10:
        phone = "91" + phone

    url = f"{BASE_URL}/sendMessage/{API_TOKEN_INSTANCE}"

    payload = {
        "chatId": f"{phone}@c.us",
        "message": message
    }

    response = requests.post(url, json=payload)
    print("GREEN API SEND:", response.text)

    return response.json()