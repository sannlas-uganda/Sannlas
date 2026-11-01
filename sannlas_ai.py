# sannlas_ai.py - CLEAN - SHORT - HUMAN - NO LEAKS - FINAL
from flask import Blueprint, request, jsonify
import os, json, re

ai_bp = Blueprint('sannlas_ai', __name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ===== CLEAN KNOWLEDGE - SHORT & HUMAN =====
KNOWLEDGE = {
    "what is sannlas": "Sannlas is Uganda's marketplace! 🛍️ Buy & sell anything - shoes, phones, watches, bags, groceries! Like Jumia for Uganda! Shops in Kampala & Kawempe.",
    "how to buy": "How to buy: 🛒\n1. Search product\n2. Tap it\n3. Add to Cart\n4. Checkout\n5. Pay with MTN/Airtel or Cash on Delivery\n6. We deliver in Kampala!",
    "how to sell": "How to sell - FREE 14 days! 🚀\n1. Tap SELL button\n2. Upload photo\n3. Set price & location\n4. Post! Customers will see it!",
    "payment": "Pay with: MTN Mobile Money, Airtel Money, or Cash on Delivery! 💰 Safe & easy!",
    "delivery": "Delivery 1-2 days in Kampala & Kawempe! 🚚 Fee ~5k-10k UGX. We call you before delivery!",
    "coins": "Coins are rewards! 💰 Earn by selling & sharing products. Use coins to boost your products!",
    "spin": "Spin the wheel daily to win coins! 🎡 Free coins every day!",
    "kassag": "Kassag is group savings! 👥 Save money together with friends weekly!",
    "billboard": "Billboard is top ads on homepage! 📢 Promote your product to get more views!",
    "promotion": "Promote your product to get more customers! Use coins to boost!",
    "return": "Return within 2 days if product not as described! Contact seller directly! 🔄",
    "contact": "Contact seller via phone on their shop page! 📞 Or chat with them!",
    "shops count": "We have shops in Kampala & Kawempe! Like Kafeco shop in Kampala! 🛍️",
    "products count": "We have many products - shoes, watches, bags, phones, food items like Royco, Maize Flour! 🔍 Tell me what you want!",
    "chunky shoes": "Chunky black shoes - Trendy platform shoes! UGX 125k! ⭐5.0 - Available in Kawempe!",
}

def find_answer(msg):
    ml = msg.lower()
    for key, ans in KNOWLEDGE.items():
        if key in ml:
            return ans
    # keyword match
    if "buy" in ml and ("how" in ml or "sannlas" in ml):
        return KNOWLEDGE["how to buy"]
    if "sell" in ml and "how" in ml:
        return KNOWLEDGE["how to sell"]
    if "pay" in ml or "mtn" in ml or "airtel" in ml or "cod" in ml:
        return KNOWLEDGE["payment"]
    if "deliver" in ml:
        return KNOWLEDGE["delivery"]
    if "coin" in ml:
        return KNOWLEDGE["coins"]
    if "spin" in ml:
        return KNOWLEDGE["spin"]
    if "kassag" in ml:
        return KNOWLEDGE["kassag"]
    if "billboard" in ml:
        return KNOWLEDGE["billboard"]
    if "promo" in ml:
        return KNOWLEDGE["promotion"]
    if "return" in ml or "refund" in ml:
        return KNOWLEDGE["return"]
    if "contact" in ml:
        return KNOWLEDGE["contact"]
    if "what is sannlas" in ml or "about sannlas" in ml:
        return KNOWLEDGE["what is sannlas"]
    return None

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

def load_kv(key):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT data FROM kv_store WHERE key=%s LIMIT 1", (key,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row: return None
        d = row[0]
        if isinstance(d, str):
            try: d = json.loads(d)
            except: return d
        return d
    except: return None

def load_shops():
    d = load_kv('shops.json')
    return d if isinstance(d, list) else []

def load_products(search="", max_price=None, location="", limit=6):
    try:
        conn = get_conn()
        if not conn: return []
        cur = conn.cursor()
        if search:
            cur.execute("SELECT data FROM products WHERE LOWER(data::text) LIKE %s ORDER BY id DESC LIMIT %s", (f"%{search.lower()}%", limit*2))
        else:
            cur.execute("SELECT data FROM products ORDER BY id DESC LIMIT %s", (limit*2,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for r in rows:
            d = r[0]
            if isinstance(d, str):
                try: d = json.loads(d)
                except: continue
            if not isinstance(d, dict): continue
            try:
                price = int(float(str(d.get('price',0)).replace(',','').replace('UGX','').strip()))
                if max_price and price > max_price: continue
            except: pass
            if location and location.lower() not in str(d.get('location','')).lower():
                continue
            result.append(d)
            if len(result) >= limit: break
        return result
    except: return []

def parse_price(text):
    m = re.search(r'(under|below|budget|max)\s*(\d+)\s*k', text.lower())
    if m: return int(m.group(2))*1000
    return None

@ai_bp.route('/api/ai/chat', methods=['POST','OPTIONS','GET'])
def ai_chat():
    if request.method == 'GET':
        return jsonify({'status': 'Sannlas AI LIVE - CLEAN'})
    if request.method == 'OPTIONS':
        return jsonify({'ok': True}), 200

    try:
        data = request.get_json(silent=True) or {}
        msg = (data.get('message') or '').strip()
        ml = msg.lower()
        if not msg:
            return jsonify({'reply': "Hi Boss! 👋 Welcome to Sannlas! What do you want to buy today? 🛍️", 'products': []})

        max_price = parse_price(ml)
        location = "Kawempe" if 'kawempe' in ml else "Kampala" if 'kampala' in ml else ""

        products = []
        reply = ""

        # FAQ FIRST - SHORT & CLEAN - NO PRODUCTS
        knowledge = find_answer(msg)
        is_search = any(k in ml for k in ['shoe','chunky','watch','bag','phone','dress','royco','flour','tiv','rice','show','find','search'])

        if knowledge and not is_search:
            # Pure FAQ - NO products, NO leaks!
            return jsonify({'reply': knowledge, 'products': []})

        # SHOPS
        if 'shop' in ml or 'store' in ml:
            shops = load_shops()
            if location:
                fshops = [s for s in shops if location.lower() in str(s.get('location','')).lower()]
                if fshops:
                    txt = "\n".join([f"• {s.get('name')} - {s.get('location')}" for s in fshops[:5]])
                    reply = f"Shops in {location} 🛍️:\n{txt}"
                else:
                    reply = f"No shops in {location} yet. Shops in Kampala available!"
            else:
                shops = load_shops()
                txt = "\n".join([f"• {s.get('name')} - {s.get('location')}" for s in shops[:5]])
                reply = f"Our shops 🛍️:\n{txt}\n\nTell me shop name to see products!"
            return jsonify({'reply': reply, 'products': []})

        # PRODUCTS SEARCH - CLEAN
        if is_search:
            q = ""
            if 'chunky' in ml or 'shoe' in ml: q = 'shoe'
            elif 'watch' in ml: q = 'watch'
            elif 'bag' in ml: q = 'bag'
            elif 'phone' in ml: q = 'phone'
            elif 'royco' in ml: q = 'royco'
            elif 'flour' in ml or 'maize' in ml: q = 'flour'
            elif 'tiv' in ml or 'rice' in ml: q = 'rice'
            else:
                # take last word as search
                q = ml.split()[-1] if len(ml.split())>0 else ""

            if len(q) > 2:
                products = load_products(search=q, max_price=max_price, location=location, limit=6)

            if products:
                reply = f"Found {len(products)} for '{q}'! 👇"
                if max_price:
                    reply = f"Found {len(products)} under UGX {max_price:,}! 👇"
            else:
                reply = f"Searching '{q}'... Try 'shoes', 'watches', 'Royco'! 🛍️"
                products = load_products(limit=6)

            return jsonify({'reply': reply, 'products': products[:6]})

        # HOW TO SELL / BUY with products
        if 'how to sell' in ml:
            products = load_products(limit=4)
            return jsonify({'reply': KNOWLEDGE["how to sell"], 'products': products[:4]})
        
        if 'how to buy' in ml:
            products = load_products(limit=4)
            return jsonify({'reply': KNOWLEDGE["how to buy"], 'products': products[:4]})

        # GREETING
        if any(k in ml for k in ['hi','hello','hey','kale','ssebo','help']):
            reply = "Hi Boss! 👋 Welcome to Sannlas! 🛍️\n\nI can help with:\n• Find products - e.g. 'Chunky shoes'\n• Shops in Kampala\n• How to buy/sell\n• Delivery & payment\n\nWhat do you need? 😊"
            products = load_products(limit=4)
            return jsonify({'reply': reply, 'products': products[:4]})

        # FALLBACK - SHORT
        products = load_products(search=ml.split()[0] if ml.split() else "", limit=4)
        reply = f"Got it Boss! 🔍 Found products for you! 👇" if products else "Hi Boss! Tell me what you want - e.g. 'shoes', 'watches', 'Royco'! 🛍️"
        return jsonify({'reply': reply, 'products': products[:6]})

    except Exception as e:
        print(f"ERROR {e}")
        return jsonify({'reply': "Hi Boss! Welcome to Sannlas! 🛍️ Tell me what you want to buy?", 'products': []}), 200
