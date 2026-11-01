# sannlas_ai.py - 5 LANGUAGES UGANDA + SMART C - UPGRADED FROM YOUR FILE
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

# ===== 5 LANGUAGES UGANDA + SMART SYNONYMS - UPGRADED =====
TRANSLATIONS = {
    "shoes": {"en": "shoes", "lg": "engatto", "sw": "viatu", "nyn": "engatto", "lus": "engatto"},
    "watches": {"en": "watches", "lg": "saawa", "sw": "saa", "nyn": "saawa", "lus": "saawa"},
    "bags": {"en": "bags", "lg": "ensawo", "sw": "mifuko", "nyn": "ensawo", "lus": "ensawo"},
    "phones": {"en": "phones", "lg": "essimu", "sw": "simu", "nyn": "essimu", "lus": "essimu"},
    "groceries": {"en": "groceries", "lg": "ebyokulya", "sw": "vyakula", "nyn": "ebyokulya", "lus": "ebyokulya"},
}

# ===== SMART C + 5 LANGUAGES - YOUR OLD MAP + UGANDA ADDED =====
SMART_SYNONYMS = {
    "shoes": ["shoes", "shoe", "foot wear", "footwear", "sneakers", "sneaker", "kicks", "boots", "heels", "chunky", "trainers", "loafers", "engatto", "viatu"],
    "watches": ["watches", "watch", "timepiece", "clock", "wristwatch", "saawa", "saa"],
    "bags": ["bags", "bag", "handbag", "backpack", "purse", "luggage", "tote", "ensawo", "mifuko"],
    "phones": ["phones", "phone", "mobile", "smartphone", "cellphone", "cell phone", "iphone", "samsung", "tecno", "infinix", "essimu", "simu"],
    "clothes": ["clothes", "dress", "shirt", "cloth", "fashion", "apparel", "wear"],
    "groceries": ["groceries", "grocery", "food", "royco", "flour", "rice", "maize", "tiv", "cooking", "seasoning", "ebyokulya", "vyakula"],
    "price": ["price", "cost", "how much", "rate", "amount", "fee", "charge", "sente meka", "sente zingahi", "bei gani"],
    "buy": ["buy", "purchase", "order", "get", "want", "need", "shop", "acquire", "okugula", "kununua", "nsaba", "njagala"],
    "sell": ["sell", "selling", "sale", "vendor", "shop", "post", "list", "okutunda", "kuuza"],
    "delivery": ["delivery", "deliver", "ship", "shipping", "transport", "bring", "send", "okutwala"],
    "location": ["location", "where", "place", "area", "kampala", "kawempe", "wakiso"],
    "hello": ["hello", "hi", "hey", "hola", "kale", "ssebo", "oli otya", "howdy", "habari", "orire ota", "wasuze otya"],
}

def detect_language(text):
    tl = text.lower()
    if any(w in tl for w in ["oli otya", "engatto", "ensawo", "sente meka", "ssebo", "kale", "nsaba", "njagala", "wasuze"]):
        return "lg"
    if any(w in tl for w in ["habari", "viatu", "bei gani", "simu", "mifuko", "karibu", "bei"]):
        return "sw"
    if any(w in tl for w in ["orire ota", "sente zingahi"]):
        return "nyn"
    if "lusoga" in tl:
        return "lus"
    return "en"

MULTI_REPLIES = {
    "greeting": {
        "en": "Hi Boss! 👋 Welcome to Sannlas! 🛍️ What do you want to buy today? Try: shoes, phones, watches, bags, Royco...",
        "lg": "Wasuze otya Boss! 👋 Karibu ku Sannlas! 🛍️ Oyagala kugula ki leero? Gezaako: engatto, essimu, saawa, Royco... (Sente meka?)",
        "sw": "Habari Boss! 👋 Karibu Sannlas! 🛍️ Unataka kununua nini leo? Jaribu: viatu, simu, saa, Royco...",
        "nyn": "Oririre ota Boss! 👋 Karibu Sannlas! 🛍️ Noki orikwenda kushara hati? Gezaako: engatto, essimu, saawa...",
        "lus": "Oli otya Boss! 👋 Karibu ku Sannlas! 🛍️ Oyenda kugula ki? Gezaako: engatto, essimu, saawa..."
    },
    "found": {
        "en": "Found {count} {product} for you! 👇",
        "lg": "Nzudde {count} {product} gyo! 👇",
        "sw": "Nimepata {count} {product} kwako! 👇",
        "nyn": "Nayine {count} {product} ahabwawe! 👇",
        "lus": "Nzudde {count} {product} gyo! 👇"
    }
}

def expand_with_synonyms(text):
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
    for item in knowledge:
        q = item.get('question','').lower().strip()
        if q == ml:
            return item.get('answer')
    for main_word in found_syns:
        for item in knowledge:
            q = item.get('question','').lower()
            cat = item.get('category','').lower()
            keywords = [k.lower() for k in item.get('keywords',[])]
            if main_word in q or main_word in cat or main_word in keywords:
                q_expanded, _ = expand_with_synonyms(q)
                if any(syn in ml for syn in SMART_SYNONYMS.get(main_word, [])):
                    return item.get('answer')
    for item in knowledge:
        q = item.get('question','').lower().strip()
        if q in ml or ml in q:
            if len(q) > 2:
                return item.get('answer')
    best = None
    best_score = 0
    for item in knowledge:
        score = 0
        q = item.get('question','').lower()
        q_expanded, _ = expand_with_synonyms(q)
        for word in q.split():
            if len(word) > 2 and word in ml:
                score += 2
        for word in q_expanded.split():
            if len(word) > 2 and word in ml_expanded:
                score += 1.5
        for kw in item.get('keywords', []):
            kw_low = kw.lower()
            if kw_low in ml:
                score += 2
            for main, syns in SMART_SYNONYMS.items():
                if kw_low in syns and any(s in ml for s in syns):
                    score += 2.5
        for syn_word in found_syns:
            if syn_word in q_expanded:
                score += 3
        if score > best_score:
            best_score = score
            best = item.get('answer')
    if best_score >= 1.5:
        return best
    return None

def load_products(search="", max_price=None, location="", limit=6):
    try:
        search_expanded, found_syns = expand_with_synonyms(search.lower())
        actual_search = search
        for main_word in found_syns:
            if main_word in ["shoes","watches","bags","phones","groceries","clothes"]:
                actual_search = main_word
                break
        conn = get_conn()
        if not conn: return []
        cur = conn.cursor()
        if actual_search:
            synonyms_to_search = SMART_SYNONYMS.get(actual_search.lower(), [actual_search.lower()])
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
    if m2 and any(w in text.lower() for w in ['under','below','less','cheap','sente','bei']):
        return int(m2.group(1))*1000
    return None

@ai_bp.route('/api/ai/chat', methods=['POST','OPTIONS','GET'])
def ai_chat():
    if request.method == 'GET':
        k = load_admin_knowledge()
        return jsonify({'status': f'AI LIVE - 5 LANGUAGES UGANDA + SMART C - {len(k)} Q&A', 'languages': ['en - English', 'lg - Luganda 80% Kampala', 'sw - Swahili Traders', 'nyn - Runyankole Mbarara', 'lus - Lusoga Jinja'], 'knowledge_count': len(k), 'synonyms': list(SMART_SYNONYMS.keys())})
    if request.method == 'OPTIONS':
        return jsonify({'ok': True}), 200

    try:
        data = request.get_json(silent=True) or {}
        msg = (data.get('message') or '').strip()
        ml = msg.lower()
        lang = detect_language(msg)
        
        if not msg:
            reply = MULTI_REPLIES["greeting"][lang]
            return jsonify({'reply': reply, 'products': [], 'detected_lang': lang})

        admin_answer = find_from_admin_knowledge(msg)
        if admin_answer:
            print(f"SMART 5LANG FOUND for '{msg}' [{lang}]: {admin_answer[:50]}")
            return jsonify({'reply': admin_answer, 'products': [], 'detected_lang': lang})

        max_price = parse_price(ml)
        location = "Kawempe" if 'kawempe' in ml else "Kampala" if 'kampala' in ml else ""
        ml_expanded, found_syns = expand_with_synonyms(ml)
        is_search = len(found_syns) > 0 or any(k in ml for k in ['show','find','search','looking','want','need','buy','price','sente','bei','nsaba','njagala'])
        product_type = ""
        for p_type in ["shoes","watches","bags","phones","groceries","clothes"]:
            if p_type in found_syns:
                product_type = p_type
                break
        if not product_type:
            if any(k in ml for k in ['shoe','chunky','sneaker','footwear','kicks','boots','engatto','viatu']): product_type = 'shoes'
            elif any(k in ml for k in ['watch','timepiece','saawa','saa']): product_type = 'watches'
            elif any(k in ml for k in ['bag','handbag','backpack','ensawo','mifuko']): product_type = 'bags'
            elif any(k in ml for k in ['phone','mobile','smartphone','iphone','samsung','tecno','essimu','simu']): product_type = 'phones'
            elif any(k in ml for k in ['royco','flour','rice','tiv','food','grocery','ebyokulya','vyakula']): product_type = 'groceries'

        if is_search or product_type or 'shop' in ml:
            search_q = product_type if product_type else ml.split()[0] if ml.split() else ""
            products = load_products(search=search_q, max_price=max_price, location=location, limit=6)
            if products:
                prod_name = TRANSLATIONS.get(product_type, {}).get(lang, product_type or 'products') if product_type else 'products'
                base_reply = MULTI_REPLIES["found"][lang].format(count=len(products), product=prod_name)
                if lang == "lg":
                    base_reply += f" (Ntegedde '{msg}' nga {prod_name}! 🧠)"
                elif lang == "sw":
                    base_reply += f" (Nimeelewa '{msg}' kama {prod_name}! 🧠)"
                else:
                    base_reply += f" (Understood '{msg}' as {prod_name}! 🧠)"
                return jsonify({'reply': base_reply, 'products': products[:6], 'detected_lang': lang})
            else:
                products = load_products(limit=4)
                return jsonify({'reply': MULTI_REPLIES["greeting"][lang], 'products': products[:4], 'detected_lang': lang})

        if any(k in ml_expanded for k in SMART_SYNONYMS['hello']) or any(k in ml for k in ['help','what']):
            products = load_products(limit=4)
            return jsonify({'reply': MULTI_REPLIES["greeting"][lang], 'products': products[:4], 'detected_lang': lang})

        search_term = product_type if product_type else (ml.split()[0] if ml.split() else "")
        products = load_products(search=search_term, limit=4)
        return jsonify({'reply': MULTI_REPLIES["greeting"][lang], 'products': products[:6], 'detected_lang': lang})

    except Exception as e:
        print(f"ERROR {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'reply': "Hi Boss! / Oli otya Boss! / Habari Boss! Welcome to Sannlas! 🛍️", 'products': []}), 200
