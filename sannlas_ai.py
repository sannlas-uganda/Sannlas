# sannlas_ai.py - SMART C - UNDERSTANDS MEANING LIKE ME! - FINAL
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

# ===== SMART C - SYNONYMS MAP - UNDERSTANDS MEANING! =====
SMART_SYNONYMS = {
    "shoes": ["shoes", "shoe", "foot wear", "footwear", "sneakers", "sneaker", "kicks", "boots", "heels", "chunky", "trainers", "loafers"],
    "watches": ["watches", "watch", "timepiece", "clock", "wristwatch"],
    "bags": ["bags", "bag", "handbag", "backpack", "purse", "luggage", "tote"],
    "phones": ["phones", "phone", "mobile", "smartphone", "cellphone", "cell phone", "iphone", "samsung", "tecno", "infinix"],
    "clothes": ["clothes", "dress", "shirt", "cloth", "fashion", "apparel", "wear"],
    "groceries": ["groceries", "grocery", "food", "royco", "flour", "rice", "maize", "tiv", "cooking", "seasoning"],
    "price": ["price", "cost", "how much", "rate", "amount", "fee", "charge"],
    "buy": ["buy", "purchase", "order", "get", "want", "need", "shop", "acquire"],
    "sell": ["sell", "selling", "sale", "vendor", "shop", "post", "list"],
    "delivery": ["delivery", "deliver", "ship", "shipping", "transport", "bring", "send"],
    "location": ["location", "where", "place", "area", "kampala", "kawempe", "wakiso"],
    "hello": ["hello", "hi", "hey", "hola", "kale", "ssebo", "oli otya", "howdy"],
}

def expand_with_synonyms(text):
    """Convert any synonym to main keyword - like me!"""
    text = text.lower()
    expanded = text
    found_keywords = []
    for main_word, syn_list in SMART_SYNONYMS.items():
        for syn in syn_list:
            if syn in text:
                if main_word not in found_keywords:
                    found_keywords.append(main_word)
                expanded += " " + main_word
                break
    return expanded.lower(), found_keywords

def find_from_admin_knowledge(msg):
    ml = msg.lower().strip()
    ml_expanded, found_syns = expand_with_synonyms(ml)
    
    knowledge = load_admin_knowledge()
    # FIRST - Exact match
    for item in knowledge:
        q = item.get('question','').lower().strip()
        if q == ml:
            return item.get('answer')
    
    # SECOND - Smart synonym contains
    # If user said "foot wear" -> we check for "shoes"
    for main_word in found_syns:
        for item in knowledge:
            q = item.get('question','').lower()
            cat = item.get('category','').lower()
            keywords = [k.lower() for k in item.get('keywords',[])]
            # If Q&A is about shoes and user said footwear -> match!
            if main_word in q or main_word in cat or main_word in keywords:
                # Check synonyms of that Q&A too
                q_expanded, _ = expand_with_synonyms(q)
                if any(syn in ml for syn in SMART_SYNONYMS.get(main_word, [])):
                    return item.get('answer')
    
    # THIRD - Contains match
    for item in knowledge:
        q = item.get('question','').lower().strip()
        if q in ml or ml in q:
            if len(q) > 2:
                return item.get('answer')
    
    # FOURTH - Smart keyword scoring with synonyms
    best = None
    best_score = 0
    for item in knowledge:
        score = 0
        q = item.get('question','').lower()
        q_expanded, _ = expand_with_synonyms(q)
        
        # Direct words
        for word in q.split():
            if len(word) > 2 and word in ml:
                score += 2
        # Expanded meaning - BIG BONUS
        for word in q_expanded.split():
            if len(word) > 2 and word in ml_expanded:
                score += 1.5
        # Keywords
        for kw in item.get('keywords', []):
            kw_low = kw.lower()
            if kw_low in ml:
                score += 2
            # Synonym match - e.g., kw=shoes, msg=footwear
            for main, syns in SMART_SYNONYMS.items():
                if kw_low in syns and any(s in ml for s in syns):
                    score += 2.5
        # Synonyms found bonus
        for syn_word in found_syns:
            if syn_word in q_expanded:
                score += 3
        
        if score > best_score:
            best_score = score
            best = item.get('answer')
    
    if best_score >= 1.5:  # Smart threshold
        return best
    return None

def load_products(search="", max_price=None, location="", limit=6):
    try:
        # SMART SEARCH - expand synonyms for product search too!
        search_expanded, found_syns = expand_with_synonyms(search.lower())
        # If search is "foot wear", convert to "shoes"
        actual_search = search
        for main_word in found_syns:
            if main_word in ["shoes","watches","bags","phones","groceries","clothes"]:
                actual_search = main_word
                break
        
        conn = get_conn()
        if not conn: return []
        cur = conn.cursor()
        
        if actual_search:
            # Search for main word AND its synonyms
            synonyms_to_search = SMART_SYNONYMS.get(actual_search.lower(), [actual_search.lower()])
            # Build LIKE query with OR
            like_conditions = " OR ".join(["LOWER(data::text) LIKE %s" for _ in synonyms_to_search])
            params = [f"%{syn}%" for syn in synonyms_to_search] + [limit*3]
            cur.execute(f"SELECT data FROM products WHERE {like_conditions} ORDER BY id DESC LIMIT %s", params)
        else:
            cur.execute("SELECT data FROM products ORDER BY id DESC LIMIT %s", (limit*3,))
        
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
    except Exception as e:
        print(f"load_products error {e}")
        return []

def parse_price(text):
    m = re.search(r'(under|below|budget|max)\s*(\d+)\s*k', text.lower())
    if m: return int(m.group(2))*1000
    m2 = re.search(r'(\d+)\s*k', text.lower())
    if m2 and any(w in text.lower() for w in ['under','below','less','cheap']):
        return int(m2.group(1))*1000
    return None

@ai_bp.route('/api/ai/chat', methods=['POST','OPTIONS','GET'])
def ai_chat():
    if request.method == 'GET':
        k = load_admin_knowledge()
        return jsonify({'status': f'AI LIVE SMART C - {len(k)} Q&A - Understands meaning!', 'knowledge_count': len(k), 'synonyms': list(SMART_SYNONYMS.keys()), 'sample': k[:1] if k else []})
    if request.method == 'OPTIONS':
        return jsonify({'ok': True}), 200

    try:
        data = request.get_json(silent=True) or {}
        msg = (data.get('message') or '').strip()
        ml = msg.lower()
        if not msg:
            return jsonify({'reply': "Hi Boss! 👋 Welcome to Sannlas! What do you want to buy? 🛍️ Try: shoes, phones, watches, bags, Royco...", 'products': []})

        # ===== STEP 1: ADMIN Q&A FIRST - WITH SMART MEANING! =====
        admin_answer = find_from_admin_knowledge(msg)
        if admin_answer:
            print(f"SMART C FOUND for '{msg}': {admin_answer[:50]}")
            return jsonify({'reply': admin_answer, 'products': []})

        # ===== STEP 2: Products with SMART search =====
        max_price = parse_price(ml)
        location = "Kawempe" if 'kawempe' in ml else "Kampala" if 'kampala' in ml else ""
        
        # Smart detect intent
        ml_expanded, found_syns = expand_with_synonyms(ml)
        is_search = len(found_syns) > 0 or any(k in ml for k in ['show','find','search','looking','want','need','buy','price'])
        
        # Detect product type via synonyms
        product_type = ""
        for p_type in ["shoes","watches","bags","phones","groceries","clothes"]:
            if p_type in found_syns:
                product_type = p_type
                break
        
        # Fallback detection
        if not product_type:
            if any(k in ml for k in ['shoe','chunky','sneaker','footwear','kicks','boots']): product_type = 'shoes'
            elif any(k in ml for k in ['watch','timepiece']): product_type = 'watches'
            elif any(k in ml for k in ['bag','handbag','backpack']): product_type = 'bags'
            elif any(k in ml for k in ['phone','mobile','smartphone','iphone','samsung','tecno']): product_type = 'phones'
            elif any(k in ml for k in ['royco','flour','rice','tiv','food','grocery']): product_type = 'groceries'

        if is_search or product_type or 'shop' in ml:
            search_q = product_type if product_type else ml.split()[0] if ml.split() else ""
            products = load_products(search=search_q, max_price=max_price, location=location, limit=6)
            if products:
                smart_msg = f"Found {len(products)} {product_type or 'products'} for you! 👇"
                if found_syns:
                    smart_msg += f" (Understood '{msg}' as {product_type or found_syns[0]}! 🧠)"
                return jsonify({'reply': smart_msg, 'products': products[:6]})
            else:
                products = load_products(limit=4)
                if product_type:
                    return jsonify({'reply': f"No {product_type} under {max_price}k, but check these! 🛍️", 'products': products[:4]})
                return jsonify({'reply': f"Searching '{msg}'... Try 'shoes', 'phones', 'watches', 'Royco'! 🛍️", 'products': products[:4]})

        # ===== STEP 3: Default with SMART greeting =====
        if any(k in ml_expanded for k in SMART_SYNONYMS['hello']) or any(k in ml for k in ['help','what']):
            products = load_products(limit=4)
            return jsonify({'reply': "Hi Boss! 👋 Welcome to Sannlas! 🛍️ I'm smart now - I understand meaning! Try: 'foot wear' = shoes, 'mobile' = phone, 'cheap watches under 100k'!", 'products': products[:4]})

        # Fallback
        search_term = product_type if product_type else (ml.split()[0] if ml.split() else "")
        products = load_products(search=search_term, limit=4)
        return jsonify({'reply': "Got it Boss! 🔍 I understand! Found products for you! 👇" if products else "Hi Boss! I now understand meanings! Try: 'foot wear', 'mobile', 'handbag', 'cheap phones under 100k'! 🛍️", 'products': products[:6]})

    except Exception as e:
        print(f"ERROR {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'reply': "Hi Boss! Welcome to Sannlas! 🛍️ SMART C LIVE!", 'products': []}), 200
