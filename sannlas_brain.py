# sannlas_brain.py - ONE BRAIN FOR GOOGLE + SANNLAS AI
# Add product once -> Google knows + AI knows. AUTOMATIC!
import os, json

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL:
        return None
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=8)
    except:
        try:
            import psycopg2
            return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=8)
        except:
            return None

# ===== STATIC KNOWLEDGE - What SANNLAS is =====
BRAIN_KNOWLEDGE = [
    {"key": "what_is_sannlas", "keywords": ["what is sannlas", "about sannlas", "who are you", "sannlas"],
     "answer": "SANNLAS is Uganda's #1 Reels Shopping App in Kampala! Buy, Sell, Request (Want), Book Transport, Find Manufacturers. All in ONE app at sannlas.store"},
    {"key": "how_to_sell", "keywords": ["how to sell", "sell", "create shop", "open shop", "okutunda", "kuuza"],
     "answer": "To SELL FREE on SANNLAS: 1) Create account 2) Click Create Shop FREE 3) Upload product + photo + price 4) Upload Reel. Buyers will find you! Listing is FREE."},
    {"key": "how_to_buy", "keywords": ["how to buy", "buy", "purchase", "order", "okugula", "kununua"],
     "answer": "To BUY: Browse Reels or Shops on sannlas.store, click Buy, chat seller, arrange delivery in Kampala. Pay on delivery or Mobile Money."},
    {"key": "what_is_want", "keywords": ["want", "request", "cant find"],
     "answer": "WANT = Request. Can't find it? Post a WANT FREE! Example: 'I want iPhone 13, 1.2M, Kampala'. Sellers send you offers. Cheapest wins!"},
    {"key": "transport", "keywords": ["transport", "boda", "taxi", "bus", "ride", "delivery"],
     "answer": "SANNLAS Transport: Book Boda Boda, Taxi, Bus in Kampala. Go to Transport on sannlas.store, pick Boda/Taxi/Bus, enter location. Fast & cheap!"},
    {"key": "agency", "keywords": ["agency", "earn", "400"],
     "answer": "SANNLAS AGENCY: Earn 400 UGX per shop you bring! Help shops join Sannlas FREE, you earn. Join Agency on sannlas.store"},
    {"key": "payment", "keywords": ["pay", "payment", "momo", "mobile money", "cash"],
     "answer": "Pay with MTN MoMo, Airtel Money, or Cash on Delivery in Kampala. Safe & easy."},
    {"key": "is_free", "keywords": ["free", "cost", "charge"],
     "answer": "YES! Buying FREE, Posting Want FREE, Creating Shop FREE, Uploading Product FREE. Sannlas is FREE to start!"},
    {"key": "manufacturer", "keywords": ["manufacturer", "factory", "wholesale"],
     "answer": "Find Manufacturers in Uganda on SANNLAS! Buy direct from factory, no middleman. Go to Manufacturers, search cement, furniture, clothes."},
    {"key": "location", "keywords": ["where", "location", "kampala", "address"],
     "answer": "SANNLAS is in Kampala, Uganda. We deliver all over Uganda. Main areas: Kampala, Wakiso, Kawempe, Mukono, Jinja, Mbarara."},
]

# ===== LIVE DATA - Reads your REAL database =====
def get_live_products(limit=1000):
    try:
        conn = get_conn()
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute("SELECT data FROM products ORDER BY id DESC LIMIT %s", (limit,))
        out = []
        for r in cur.fetchall():
            d = r[0]
            if isinstance(d, str):
                try:
                    d = json.loads(d)
                except:
                    continue
            if isinstance(d, dict):
                out.append(d)
        cur.close()
        conn.close()
        return out
    except:
        return []

def get_live_shops(limit=500):
    try:
        conn = get_conn()
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute("SELECT data FROM shops ORDER BY id DESC LIMIT %s", (limit,))
        out = []
        for r in cur.fetchall():
            d = r[0]
            if isinstance(d, str):
                try:
                    d = json.loads(d)
                except:
                    continue
            if isinstance(d, dict):
                out.append(d)
        cur.close()
        conn.close()
        return out
    except:
        return []

def get_live_admin_knowledge():
    try:
        conn = get_conn()
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute("SELECT data FROM kv_store WHERE key='ai_knowledge.json' LIMIT 1")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return []
        d = row[0]
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except:
                return []
        return d if isinstance(d, list) else []
    except:
        return []

# ===== SYNONYMS =====
SYNONYMS = {
    "shoes": ["shoes", "shoe", "sneakers", "kicks", "boots", "heels", "engatto", "viatu"],
    "phones": ["phones", "phone", "mobile", "smartphone", "iphone", "samsung", "tecno", "infinix", "essimu", "simu"],
    "laptops": ["laptop", "computer", "macbook", "hp", "dell"],
    "bags": ["bags", "bag", "handbag", "backpack", "ensawo", "mifuko"],
    "watches": ["watches", "watch", "saawa", "saa"],
    "furniture": ["furniture", "sofa", "chair", "table", "bed"],
    "hair": ["hair", "wig", "weave", "braids"],
    "groceries": ["groceries", "food", "royco", "rice", "flour", "ebyokulya"],
    "clothes": ["clothes", "dress", "shirt", "gomesi", "kitenge"],
}

def search_brain(query, max_price=None, location=""):
    q = query.lower()
    products = get_live_products()
    found = []
    for p in products:
        name = str(p.get("name", "")).lower()
        cat = str(p.get("category", "")).lower()
        match = False
        for main, syns in SYNONYMS.items():
            if main in q and any(s in name or s in cat for s in syns):
                match = True
        if q.split() and q.split()[0] in name:
            match = True
        if match:
            try:
                price = int(float(str(p.get("price", 0)).replace(",", "").replace("UGX", "").strip()))
                if max_price and price > max_price:
                    continue
            except:
                pass
            if location and location.lower() not in str(p.get("location", "")).lower():
                continue
            found.append({"name": p.get("name"), "price": p.get("price"), "location": p.get("location", "Kampala"), "image": p.get("image", "")})
        if len(found) >= 6:
            break
    return {"answer": None, "products": found}

# ===== SMART ADMIN - YOUR ADMIN Q&A IS BOSS HERE! =====
# This keeps your old find_from_admin_knowledge logic EXACTLY!
def find_brain_answer(query):
    q = query.lower().strip()
    admin_list = get_live_admin_knowledge()
    # 1. Exact match - your admin Q&A first!
    for item in admin_list:
        if item.get('question', '').lower().strip() == q:
            return item.get('answer')
    # 2. Score match - smart like before
    best = None
    best_score = 0
    for item in admin_list:
        score = 0
        qq = item.get('question', '').lower()
        for word in qq.split():
            if len(word) > 2 and word in q:
                score += 2
        for kw in item.get('keywords', []):
            if kw.lower() in q:
                score += 2
        if score > best_score:
            best_score = score
            best = item.get('answer')
    if best_score >= 1.5:
        return best
    # 3. Contains match
    for item in admin_list:
        qq = item.get('question', '').lower().strip()
        if qq and (qq in q or q in qq) and len(qq) > 2:
            return item.get('answer')
    # 4. Static Brain - only if Admin has no answer
    for item in BRAIN_KNOWLEDGE:
        if any(k in q for k in item["keywords"]):
            return item["answer"]
    return None
