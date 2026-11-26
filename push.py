import os, json
from pywebpush import webpush, WebPushException

SUBS_FILE = "subscriptions.json"

def load_subs():
    if not os.path.exists(SUBS_FILE):
        return []
    try:
        with open(SUBS_FILE) as f:
            return json.load(f)
    except:
        return []

def save_sub(sub):
    subs = load_subs()
    if sub not in subs:
        subs.append(sub)
        with open(SUBS_FILE, "w") as f:
            json.dump(subs, f)
    return subs

def send_to_all(title, body, url="/"):
    subs = load_subs()
    print(f"Sending to {len(subs)} devices...")
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=os.getenv("VAPID_PRIVATE_KEY"),
                vapid_claims={"sub": os.getenv("VAPID_CLAIM_EMAIL")}
            )
        except WebPushException as e:
            print("Failed:", e)
            if e.response and e.response.status_code in [404, 410]:
                subs.remove(sub)
                with open(SUBS_FILE, "w") as f:
                    json.dump(subs, f)
