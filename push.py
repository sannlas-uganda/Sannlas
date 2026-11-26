import os, json, threading

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL: raise Exception("No DATABASE_URL")
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def load_db(file, default):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
        row = cur.fetchone(); cur.close(); conn.close()
        if not row: return default
        d = row[0]
        return d if not isinstance(d, str) else json.loads(d)
    except:
        return default

def save_db(file, data):
    try:
        conn = get_conn(); cur = conn.cursor()
        try:
            from psycopg.types.json import Jsonb
            cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, Jsonb(data)))
        except:
            cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, json.dumps(data)))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print("push save error", e)

# --- NEW: SAVE WITH EMAIL ---
def save_sub(email, sub):
    subs = load_db('push_subs.json', [])
    email = (email or '').lower().strip()
    endpoint = sub.get('endpoint', '')
    # Remove old entry for same phone + same email
    subs = [s for s in subs if not (s.get('email')==email and s.get('subscription',{}).get('endpoint')==endpoint)]
    subs.append({"email": email, "subscription": sub})
    save_db('push_subs.json', subs)
    print(f"Push saved for {email}")
    return True

# --- NEW: SEND ONLY TO ONE USER (Seller / Buyer) ---
def send_to_email(email, title, body, url="/my-shop"):
    def _send():
        try:
            from pywebpush import webpush
            subs = load_db('push_subs.json', [])
            target = (email or '').lower().strip()
            mine = [s for s in subs if s.get('email')==target]
            print(f"Push to {target}: {len(mine)} devices - {title}")
            for s in mine:
                try:
                    webpush(subscription_info=s['subscription'], data=json.dumps({"title": title, "body": body, "url": url}), vapid_private_key=os.getenv("VAPID_PRIVATE_KEY"), vapid_claims={"sub": os.getenv("VAPID_CLAIM_EMAIL")})
                except Exception as e:
                    print("Push fail:", e)
                    # If expired, remove it
                    if '410' in str(e) or 'Gone' in str(e):
                        subs.remove(s)
                        save_db('push_subs.json', subs)
        except Exception as e:
            print("Push error:", e)
    threading.Thread(target=_send, daemon=True).start()

# Keep old for compatibility - but we won't use it for orders
def send_to_all(title, body, url="/"):
    def _send():
        try:
            from pywebpush import webpush
            subs = load_db('push_subs.json', [])
            for s in subs:
                try:
                    sub = s.get('subscription', s)
                    webpush(subscription_info=sub, data=json.dumps({"title": title, "body": body, "url": url}), vapid_private_key=os.getenv("VAPID_PRIVATE_KEY"), vapid_claims={"sub": os.getenv("VAPID_CLAIM_EMAIL")})
                except Exception as e:
                    print("Push fail:", e)
        except Exception as e:
            print("Push error:", e)
    threading.Thread(target=_send, daemon=True).start()
