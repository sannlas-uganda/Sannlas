# sannlas_ai.py - FIXED - ADMIN Q&A FIRST PRIORITY - FINAL
from flask import Blueprint, request, jsonify
import os, json, re

ai_bp = Blueprint('sannlas_ai', __name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL: return None
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=8)
    except:
        try:
            import psycopg2
            return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=8)
        except: return None

def load_admin_knowledge():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT data FROM kv_store WHERE key='ai_knowledge.json' LIMIT 1")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row: return []
        d = row[0]
        if isinstance(d, str):
            try: d = json.loads(d)
            except: return []
        return d if isinstance(d, list) else []
    except: return []

def find_from_admin_knowledge(msg):
    ml = msg.lower().strip()
    knowledge = load_admin_knowledge()
    # FIRST - Exact match (highest priority)
    for item in knowledge:
        q = item.get('question','').lower().strip()
        if q == ml:
            return item.get('answer')
    # SECOND - Contains match
    for item in knowledge:
        q = item.get('question','').lower().strip()
        if q in ml or ml in q:
            if len(q) > 2:  # avoid too short
                return item.get('answer')
    # THIRD - Keyword match
    best = None
    best_score = 0
    for item in knowledge:
        score = 0
        q = item.get('question','').lower()
        # keywords
        for word in q.split():
            if len(word) > 2 and word in ml:
                score += 1
        for kw in item.get('keywords', []):
            if kw.lower() in ml and len(kw) > 2:
                score += 1
        if score > best_score:
            best_score = score
            best = item.get('answer')
    if best_score >= 1:  # LOW threshold - to catch "hello"
        return best
    return None

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
            if location and location.lower() not in str(d.get('location','')).lower(): continue
            result.append({
                "name": d.get("name"),
                "price": d.get("price"),
                "location": d.get("location","Kampala"),
                "image": d.get("image",""),
            })
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
        k = load_admin_knowledge()
        return jsonify({'status': f'AI LIVE - {len(k)} Q&A from admin', 'knowledge_count': len(k), 'sample': k[:1] if k else []})
    if request.method == 'OPTIONS':
        return jsonify({'ok': True}), 200

    try:
        data = request.get_json(silent=True) or {}
        msg = (data.get('message') or '').strip()
        ml = msg.lower()
        if not msg:
            return jsonify({'reply': "Hi Boss! 👋 Welcome to Sannlas! What do you want to buy? 🛍️", 'products': []})

        # ===== STEP 1: ADMIN Q&A FIRST - HIGHEST PRIORITY! =====
        admin_answer = find_from_admin_knowledge(msg)
        if admin_answer:
            # If admin has answer, use it! No other checks!
            print(f"FOUND ADMIN ANSWER for '{msg}': {admin_answer}")
            return jsonify({'reply': admin_answer, 'products': []})

        # ===== STEP 2: Products & other logic =====
        max_price = parse_price(ml)
        location = "Kawempe" if 'kawempe' in ml else "Kampala" if 'kampala' in ml else ""
        products = []
        is_search = any(k in ml for k in ['shoe','chunky','watch','bag','phone','royco','flour','rice','show','find','search','tiv','dress'])

        if is_search or 'shop' in ml:
            q = ml.split()[-1] if ml.split() else ""
            if 'shoe' in ml: q = 'shoe'
            if 'watch' in ml: q = 'watch'
            if 'bag' in ml: q = 'bag'
            if len(q) > 2:
                products = load_products(search=q, max_price=max_price, location=location, limit=6)
            if products:
                return jsonify({'reply': f"Found {len(products)} for '{q}'! 👇", 'products': products[:6]})
            else:
                products = load_products(limit=4)
                return jsonify({'reply': f"Searching '{q}'... Try 'shoes', 'Royco'! 🛍️", 'products': products[:4]})

        # ===== STEP 3: Default greeting (only if no admin answer) =====
        if any(k in ml for k in ['hi','hello','hey','kale','ssebo','help']):
            # This only runs if NO admin answer found!
            products = load_products(limit=4)
            return jsonify({'reply': "Hi Boss! 👋 Welcome to Sannlas! 🛍️ What do you want to buy today?", 'products': products[:4]})

        # Fallback
        products = load_products(search=ml.split()[0] if ml.split() else "", limit=4)
        return jsonify({'reply': "Got it Boss! 🔍 Found products for you! 👇" if products else "Hi Boss! Tell me what you want - e.g. 'shoes', 'Royco'! 🛍️", 'products': products[:6]})

    except Exception as e:
        print(f"ERROR {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'reply': "Hi Boss! Welcome to Sannlas! 🛍️", 'products': []}), 200
