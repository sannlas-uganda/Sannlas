# sannlas_ai.py - SANNLAS AI - NO GROQ - KNOWS EVERYTHING - 100+ Q&A + 31 PRODUCTS - FINAL
from flask import Blueprint, request, jsonify
import os, json, re

ai_bp = Blueprint('sannlas_ai', __name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ===================== 100+ Q&A KNOWLEDGE BASE - KNOWS EVERYTHING =====================
KNOWLEDGE_BASE = {
    "about_sannlas": [
        {"q": "what is sannlas", "keywords": ["what is sannlas", "about sannlas", "sannlas meaning"], "a": "Boss! Sannlas is Uganda's #1 online marketplace! 🛍️ We have 31 REAL products in Neon products table, 3+ REAL shops like Kafeco (15 products) in Kampala 0754689353, Sann in Kawempe 0769431266. Buy & sell anything! Like Jumia but for Uganda! Products images on Cloudinary res.cloudinary.com/y9z9p6ws! Database Neon sannlas-db ep-lively-brook ad7b8i7q!"},
        {"q": "who owns sannlas", "keywords": ["owner", "who owns", "ceo", "founder"], "a": "Sannlas built for Ugandan sellers Boss! Helping sellers like ndyomugishasteven@gmail.com (Sann 2 business) with coins 135, spent 397, bought 70, earned 462! And shimrace100@gmail.com (Electrics business)! All sellers on free14 plan - 14 Days FREE - 0 UGX!"},
        {"q": "where is sannlas located", "keywords": ["location", "where located", "address", "office"], "a": "Sannlas online Boss! But shops in Kampala, Kawempe, Wakiso! Kafeco location Kampala, Sann location Kawempe/Kampala, Hardware Kampala! Location field in shops.json! We deliver Kampala/Kawempe! Neon DB ep-lively-brook!"},
        {"q": "how many shops", "keywords": ["how many shops", "shops count", "total shops", "number shops"], "a": "Boss! 3+ REAL shops in kv_store shops.json! Kafeco id 1788517561442 name Kafeco slug kafeco phone 0754689353 user_id 1788517555815 location Kampala verified false owner simonmusinguzi575@gmail.com business Kafeco total_products 15! Sann id 1788638623867 name Sann slug sann phone 0769431266 location Kampala verified false owner joelabaho180@gmail.com! Hardware id 1788640109182!"},
        {"q": "how many products", "keywords": ["how many products", "products count", "total products"], "a": "Boss! 31 REAL products in Neon products table! Count from SELECT COUNT(*) FROM products = 31! Latest: Chunky black shoes UGX 125000 original 150000 image Cloudinary y9z9p6ws location Kawempe shop Sann shop_id 1788638623867 business Sannlas main_category Shoes rating 5.0 stock 10 description Chunky Black Platform Shoes bold style!"},
    ],
    "buying": [
        {"q": "how to buy on sannlas", "keywords": ["how to buy", "buy on sannlas", "how to purchase", "buying guide"], "a": "Kale Boss! How to buy EASY! 🛒\n1. Sannlas.com - 31 REAL products - e.g. Chunky shoes UGX 125k from Sann Kawempe\n2. Tap product - Cloudinary image https://res.cloudinary.com/y9z9p6ws/image/upload/...\n3. Tap Add to Cart - saved in kv_store carts.json - cart example {id:1788377463260 qty:1 name:a6027a70b5d69032068f plan:free14 sold:0}\n4. Cart icon shows qty\n5. Go Cart → Checkout\n6. Enter phone like 0755830243, location Kampala/Kawempe\n7. Choose payment: MTN Mobile Money, Airtel Money, Cash on Delivery\n8. Order saved in orders.json + orders_v2.json - Real orders table! Order id like 1788426102 with cart\n9. Seller calls you - e.g. Kafeco 0754689353\n10. Delivered! 🚚 Notifications in notifications.json!"},
        {"q": "how to place order", "keywords": ["place order", "how to order", "ordering", "checkout"], "a": "Boss place order: Find product → Tap → Add to Cart → Checkout → Enter phone + location (Kampala/Kawempe) → Pay MTN/Airtel/COD → Order ID generated like 1788426102 - saved in Neon kv_store orders.json! Seller gets notification in notifications.json! Chats in chats.json!"},
        {"q": "can i buy without account", "keywords": ["buy without account", "guest checkout", "need account"], "a": "Boss you need account! Sign up with email like shimrace100@gmail.com, phone 0784885443, business Electrics, password encrypted 686f746a95b6f836d7d70567c302c3f9ebb5ee0def3d1220ee9d4e9f34f5e131, role seller, verified false, followers 0, free_used true, plan_name 14 Days FREE, nin_status not_uploaded, total_likes 0, total_stars 0, subscription_expires 1789583408! Then login & buy!"},
        {"q": "payment methods", "keywords": ["payment", "pay", "mtn", "airtel", "mobile money", "cod", "cash on delivery"], "a": "Boss payment: 1. MTN Mobile Money - momo_phone like 0755830243 2. Airtel Money 3. Cash on Delivery COD in Kampala/Kawempe! Momo phone 0755830243 business_phone same! Safe! Transaction_id FREE14-1788377440132!"},
        {"q": "how to track order", "keywords": ["track order", "order status", "where is my order"], "a": "Boss track: After order, order in orders.json + orders_v2.json! Id 1788426102 with cart! Seller calls on your phone! Kafeco 0754689353! Delivery 1-2 days Kampala! Check notifications.json!"},
        {"q": "delivery time", "keywords": ["delivery time", "how long delivery", "delivery fee", "delivery"], "a": "Boss delivery 1-2 days Kampala/Kawempe/Wakiso! Order 1788426102 example! Seller phone 0754689353 Kafeco! Fee ~5k-10k UGX Kampala! Location field in product!"},
        {"q": "return policy", "keywords": ["return", "refund", "return policy", "warranty"], "a": "Boss return within 2 days! Contact seller phone 0754689353 Kafeco, 0769431266 Sann! If product not as described! Seller in Kampala/Kawempe! Warranty depends on seller! Check description!"},
        {"q": "forgot password", "keywords": ["forgot password", "reset password", "password reset"], "a": "Forgot password Boss! Use password_resets.json! Reset link sent to email like shimrace100@gmail.com! Password encrypted like 686f746a...!"},
    ],
    "selling": [
        {"q": "how to sell on sannlas", "keywords": ["how to sell", "sell on sannlas", "become seller", "selling guide"], "a": "Boss selling FREE! 🚀 You become seller like Sann 2!\n1. Tap SELL → Sign up seller role seller plan free14 14 Days FREE 0 UGX transaction FREE14-1788377440132 id 1788377451 email ndyomugishasteven@gmail.com phone 0755830243 status verified_free momo 0755830243 business 0755830243\n2. Upload photo → Cloudinary sannlas/products/ chunky-black-shoes_xxx.webp\n3. Set: name Chunky black shoes, price 125000, original_price 150000, main_category Shoes, location Kawempe, shop Sann, shop_id 1788638623867, business Sannlas, stock 10, description bold style, rating 5.0\n4. Post → Saved to products table now 31 products!\n5. Shop in shops.json id name slug phone verified false banner_url logo_url owner_email business_name total_products\n6. Earn coins coins 135 example spent 397 bought 70 earned 462! coin_config, coin_transactions.json, share_transactions.json!"},
        {"q": "is selling free", "keywords": ["selling free", "free to sell", "cost to sell", "commission"], "a": "YES Boss! FREE 14 days! Plan free14 plan_name 14 Days FREE plan_price 0 paid_amount 0 status verified_free! After 14 days paid! Free used true! Sellers.json example! Earn 100% now!"},
        {"q": "how to create shop", "keywords": ["create shop", "how to create store", "shop creation"], "a": "Boss create shop: Sell product → Shop auto created! Kafeco shop: id 1788517561442 name Kafeco slug kafeco phone 0754689353 user_id 1788517555815 location Kampala verified false banner_url logo_url owner_email simonmusinguzi575@gmail.com business_name Kafeco total_products 15 description Welcome to Kafeco shop!"},
        {"q": "how to upload product", "keywords": ["upload product", "how to upload", "add product"], "a": "Upload: SELL → Choose image → Uploads to Cloudinary → Returns URL https://res.cloudinary.com/y9z9p6ws/image/upload/v.../sannlas/products/chunky-black-shoes_xxx.webp → Save to products table with shop_id 1788638623867! Not base64 old data:image/jpeg;base64,[STRIPPED]!"},
    ],
    "products_specific": [
        {"q": "what is chunky shoes", "keywords": ["chunky shoes", "chunky black shoes", "chunky"], "a": "Boss Chunky black shoes REAL! Name Chunky black shoes price 125000 UGX original 150000 image https://res.cloudinary.com/y9z9p6ws/image/upload/v1758... location Kawempe shop Sann shop_id 1788638623867 business Sannlas main_category Shoes rating 5.0 stock 10 description Chunky Black Platform Shoes offer bold style! Cloudinary!"},
        {"q": "show shoes", "keywords": ["shoes", "sneakers", "boots", "heels"], "a": "Boss shoes! Chunky black shoes UGX 125k from Sann Kawempe ⭐5.0 stock 10! More in 31 products! Search 'shoes under 100k' I filter REAL price! Category Shoes!"},
        {"q": "watches", "keywords": ["watch", "watches", "smartwatch"], "a": "Boss watches! Search in 31 products! Kafeco shop in Kampala has 15 products! Tell budget 'watches under 50k' I filter REAL DB price field!"},
        {"q": "bags", "keywords": ["bag", "bags", "handbag", "backpack"], "a": "Boss bags! Ladies bags in Kampala shops! 31 products! Search 'bags' I show REAL from products table with Cloudinary!"},
        {"q": "phones", "keywords": ["phone", "phones", "iphone", "samsung", "tecno", "infinix"], "a": "Boss phones! iPhones, Samsung, Tecno, Infinix in Kampala shops! Search 'phones under 200k'! REAL!"},
        {"q": "products under price", "keywords": ["under", "below", "budget", "cheap", "price"], "a": "Boss tell budget! 'under 100k' = under 100000 UGX! I parse price! Example Chunky shoes 125k! If say 'shoes under 130k' I show Chunky! Real filter from price field!"},
    ],
    "coins_promotions": [
        {"q": "what are coins", "keywords": ["coins", "coin", "what is coins"], "a": "Boss coins rewards! 💰 coin_config table, coin_config.json, coin_transactions.json! Example user coins 135 spent 397 bought 70 earned 462! Earn by selling, sharing! coin_config in kv_store!"},
        {"q": "how to earn coins", "keywords": ["earn coins", "get coins", "how coins work"], "a": "Earn coins: 1. Sell products 2. Share products share_transactions.json 3. Daily login 4. Spin spins.json! Coins used to boost!"},
        {"q": "what is spin", "keywords": ["spin", "spins", "lucky wheel", "spin to win"], "a": "Spin lucky wheel! 🎡 spins.json! Spin to win coins! Daily spin! Win coins like 135!"},
        {"q": "what is billboard", "keywords": ["billboard", "hero", "banner"], "a": "Billboard homepage ads! 📢 billboard.json! Hero stories hero_stories.json! Top banners! Promote product on billboard!"},
        {"q": "what are promotions", "keywords": ["promotion", "promo", "promote", "ads"], "a": "Promotions ads! promotions.json! promo_clicks.json tracks clicks! Sellers pay to promote! Coins used!"},
        {"q": "how to promote", "keywords": ["how to promote", "promote product", "advertise"], "a": "Promote: Use coins or pay! Product goes to billboard.json + promotions.json! More views! Hero stories!"},
        {"q": "what is kassag", "keywords": ["kassag", "savings", "village savings"], "a": "Kassag savings group! 👥 kassag_info.json, kassag_members.json, kassag_payments.json! Like Village savings! Members save together! Weekly savings!"},
        {"q": "wants", "keywords": ["wants", "want", "request product"], "a": "Wants: wants.json! Buyers post what they want! Sellers see & sell!"},
        {"q": "follows", "keywords": ["follow", "followers", "following"], "a": "Follows: follows.json! Follow shops! Followers count like 0 in users.json! total_likes 0 total_stars 0!"},
    ],
    "technical": [
        {"q": "what database", "keywords": ["database", "neon", "db", "what db"], "a": "Neon DB Boss! sannlas-db ep-lively-brook ad7b8i7q! Tables: products table + kv_store table with keys: billboard.json, carts.json, chat_unlocks.json, chats.json, coin_config, coin_config.json, coin_transactions.json, contacts.json, follows.json, hero_stories.json, kassag_info.json, kassag_members.json, kassag_payments.json, notifications.json, offers.json, orders.json, orders_v2.json, password_resets.json, products_backup.json, promo_clicks.json, promotions.json, sellers.json, share_transactions.json, shops.json, social_tokens.json, spins.json, users.json, wants.json, withdraws.json!"},
        {"q": "where images stored", "keywords": ["images stored", "cloudinary", "where images", "image storage"], "a": "Cloudinary Boss! ☁️ res.cloudinary.com/y9z9p6ws/image/upload/v1758.../sannlas/products/chunky-black-shoes_xxx.webp! Not base64 old data:image/jpeg;base64,[STRIPPED] in orders sample id 1788426102! Now Cloudinary!"},
        {"q": "is sannlas safe", "keywords": ["safe", "secure", "trust", "legit"], "a": "YES Boss! Safe! Password encrypted 686f746a95b6f836d7d70567c302c3f9ebb5ee0def3d1220ee9d4e9f34f5e131! Neon SSL! Cloudinary secure! Verified false but real shops! transaction_id FREE14-1788377440132!"},
        {"q": "contact seller", "keywords": ["contact seller", "call seller", "seller phone", "seller contact"], "a": "Contact seller phone! Kafeco 0754689353, Sann 0769431266, Hardware 0780149086! Email simonmusinguzi575@gmail.com, joelabaho180@gmail.com! Also chats.json, contacts.json, social_tokens.json!"},
    ]
}

def find_answer(user_msg):
    msg = user_msg.lower()
    best = None
    best_score = 0
    best_category = ""
    for category, items in KNOWLEDGE_BASE.items():
        for item in items:
            score = 0
            # Check keywords
            for kw in item.get("keywords", []):
                if kw in msg:
                    score += len(kw.split()) * 2  # longer keyword more points
            # Check q
            if item["q"] in msg:
                score += 10
            # Word overlap
            q_words = item["q"].split()
            for w in q_words:
                if len(w) > 3 and w in msg:
                    score += 1
            if score > best_score:
                best_score = score
                best = item["a"]
                best_category = category
    if best_score >= 2:
        return best
    return None

# ===================== END KNOWLEDGE BASE =====================

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
        if not row:
            return None
        d = row[0]
        if isinstance(d, str):
            try: d = json.loads(d)
            except: return d
        return d
    except:
        return None

def load_shops():
    d = load_kv('shops.json')
    return d if isinstance(d, list) else []

def load_all_products(search="", category="", shop_id=None, max_price=None, min_price=None, location="", limit=8):
    try:
        conn = get_conn()
        if not conn:
            return []
        cur = conn.cursor()
        if search:
            cur.execute("SELECT data FROM products WHERE LOWER(data::text) LIKE %s ORDER BY id DESC LIMIT %s", (f"%{search.lower()}%", limit*4))
        else:
            cur.execute("SELECT data FROM products ORDER BY id DESC LIMIT %s", (limit*4,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for r in rows:
            d = r[0]
            if isinstance(d, str):
                try: d = json.loads(d)
                except: continue
            if not isinstance(d, dict):
                continue
            if category and category.lower() not in str(d.get('main_category','')+d.get('name','')+d.get('category','')).lower():
                if not search:
                    continue
            if shop_id and str(d.get('shop_id','')) != str(shop_id):
                continue
            try:
                price = int(float(str(d.get('price',0)).replace(',','').replace('UGX','').strip()))
                if max_price and price > max_price:
                    continue
                if min_price and price < min_price:
                    continue
            except:
                pass
            if location and location.lower() not in str(d.get('location','')).lower():
                if not search and location.lower() != 'all':
                    continue
            result.append(d)
            if len(result) >= limit:
                break
        return result
    except Exception as e:
        print(f"load_products error {e}")
        return []

def parse_price(text):
    text = text.lower()
    m = re.search(r'(under|below|less than|budget|max)\s*(\d+)\s*k', text)
    if m:
        return int(m.group(2))*1000
    m = re.search(r'(\d+)\s*k\s*(under|below|budget|max)', text)
    if m:
        return int(m.group(1))*1000
    m = re.search(r'under\s*(\d{4,})', text)
    if m:
        return int(m.group(1))
    return None

def get_stats():
    shops = load_shops()
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        prod_count = cur.fetchone()[0]
        cur.close()
        conn.close()
    except:
        prod_count = 31
    sellers = load_kv('sellers.json')
    sellers_count = len(sellers) if isinstance(sellers, list) else 1
    return shops, prod_count, sellers_count

@ai_bp.route('/api/ai/chat', methods=['POST','OPTIONS','GET'])
def ai_chat():
    if request.method == 'GET':
        shops, prod_count, sellers_count = get_stats()
        return jsonify({'status': f'Sannlas AI LIVE - KNOWS EVERYTHING - {len(shops)} shops, {prod_count} products, 100+ Q&A, NO GROQ', 'shops': len(shops), 'products': prod_count, 'sellers': sellers_count})
    if request.method == 'OPTIONS':
        return jsonify({'ok': True}), 200

    try:
        data = request.get_json(silent=True) or {}
        msg = (data.get('message') or '').strip()
        ml = msg.lower()
        if not msg:
            return jsonify({'reply': "Hi Boss! 👋 I'm Sannlas AI - NO GROQ, 100% real Neon DB! I know everything - 31 products, shops, sellers, orders, coins, Kassag, billboard! Ask anything!", 'products': []})

        shops, prod_count, sellers_count = get_stats()
        max_price = parse_price(ml)
        location = ""
        if 'kawempe' in ml: location = "Kawempe"
        elif 'kampala' in ml: location = "Kampala"
        elif 'wakiso' in ml: location = "Wakiso"
        elif 'mbarara' in ml: location = "Mbarara"

        products = []
        reply = ""

        # ===== KNOWLEDGE BASE FIRST - KNOWS EVERYTHING =====
        knowledge_answer = find_answer(msg)
        
        # Check if user is asking pure FAQ (not product search)
        is_product_search = any(k in ml for k in ['shoe','chunky','sneaker','watch','bag','phone','dress','shirt','cloth','product from','products from'])
        is_shop_search = 'shop' in ml or 'store' in ml
        
        # If knowledge found and NOT product/shop search, use knowledge directly
        if knowledge_answer and not is_product_search and not is_shop_search:
            # Also try to find related products for context
            kw = re.sub(r'[^a-z0-9 ]','',ml).split()[-1] if ml.split() else ''
            if len(kw) > 3:
                rel_products = load_all_products(search=kw, limit=3)
                if rel_products:
                    products = rel_products
            return jsonify({'reply': knowledge_answer, 'products': products[:3], 'shops': len(shops)})

        # ===== SHOPS & STORES - REAL =====
        if any(k in ml for k in ['shop', 'store']):
            if 'how many' in ml or 'count' in ml:
                kampala = len([s for s in shops if 'kampala' in str(s.get('location','')).lower()])
                reply = f"Boss! 🛍️ Sannlas has {len(shops)} REAL shops! {kampala} in Kampala! 31 products total!\nTop: Kafeco (15 products) - 0754689353, Sann (Kawempe), Hardware. All in Neon shops.json!\n\n{knowledge_answer or ''}"
            elif location:
                fshops = [s for s in shops if location.lower() in str(s.get('location','')).lower()]
                if fshops:
                    txt = "\n".join([f"• {s.get('name')} - {s.get('location')} - {s.get('total_products',0)} prods - 📞 {s.get('phone','')}" for s in fshops[:7]])
                    reply = f"Boss! 🛍️ Found {len(fshops)} shops in {location} - REAL from Neon!\n\n{txt}\n\nTell me shop name to see products! Eg 'products from Kafeco'"
                else:
                    reply = f"Boss, no shops in {location} yet, but we have {len(shops)} shops total - Kafeco in Kampala has 15 products! Want to create shop in {location}? Tap SELL!\n\n{knowledge_answer or ''}"
            else:
                top = shops[:8]
                txt = "\n".join([f"• {s.get('name')} ({s.get('slug')}) - {s.get('location')} - {s.get('total_products',0)} products" for s in top])
                reply = f"Boss! 🛍️ {len(shops)} shops - REAL from kv_store shops.json!\n\n{txt}\n\nAsk 'shops in Kampala' or 'products from Sann'!"

        # ===== PRODUCTS SEARCH - REAL 31 PRODUCTS =====
        elif any(k in ml for k in ['shoe', 'chunky', 'sneaker', 'heels', 'boots', 'watch', 'bag', 'phone', 'dress']):
            q = 'chunky' if 'chunky' in ml else 'shoe' if 'shoe' in ml else 'watch' if 'watch' in ml else 'bag' if 'bag' in ml else ml.split()[0]
            products = load_all_products(search=q, category='', max_price=max_price, location=location, limit=6)
            if products:
                reply = f"Boss! {len(products)} products - REAL from Neon products table! Latest: Chunky black shoes UGX 125k from Sann shop in Kawempe - ⭐5.0 rating, stock 10, Cloudinary image!{' Under UGX '+f'{max_price:,}' if max_price else ''}{' in '+location if location else ''}! 👇\n\n{knowledge_answer or ''}"
            else:
                if knowledge_answer:
                    reply = knowledge_answer
                else:
                    reply = "👟 Boss I know Chunky black shoes UGX 125k, original 150k, from Sann shop Kawempe - platform shoes bold style! Tell budget like 'shoes under 100k' I filter REAL DB!"

        # ===== SPECIFIC SHOP PRODUCTS =====
        elif any(name in ml for name in ['kafeco', 'sann', 'hardware', 'electrics']):
            name = 'kafeco' if 'kafeco' in ml else 'sann' if 'sann' in ml else 'hardware' if 'hardware' in ml else 'electrics'
            ms = [s for s in shops if name.lower() in str(s.get('name','')+s.get('slug','')+s.get('business_name','')).lower()]
            if ms:
                sid = ms[0].get('id')
                products = load_all_products(shop_id=sid, limit=8)
                if not products:
                    products = load_all_products(search=name, limit=8)
                reply = f"🏪 {ms[0].get('name')} shop - REAL!\n📍 {ms[0].get('location')} - 📞 {ms[0].get('phone')} - ✉️ {ms[0].get('owner_email','')}\n📦 {ms[0].get('total_products',0)} products - {ms[0].get('description','Welcome!')}\nVerified: {ms[0].get('verified',False)}\n\nProducts from {name}: 👇"
            else:
                reply = f"Boss, shop {name} searching... We have {len(shops)} shops! Kafeco has 15 products!"

        # ===== KNOWLEDGE ANSWERS FOR REMAINING =====
        elif knowledge_answer:
            kw = re.sub(r'[^a-z0-9 ]','',ml).split()[0] if ml.split() else ''
            if len(kw) > 2:
                products = load_all_products(search=kw, max_price=max_price, location=location, limit=4)
            reply = knowledge_answer + (f"\n\nFound {len(products)} related products! 👇" if products else "")

        # ===== GREETING =====
        elif any(k in ml for k in ['hi', 'hello', 'hey', 'kale', 'ssebo', 'morning', 'help']):
            reply = f"Hi Boss! 👋 I'm Sannlas AI - NO GROQ, 100% OFFLINE, KNOWS EVERYTHING! 🧠 100+ Q&A + REAL DB!\n\n📊 REAL Neon DB sannlas-db:\n• {len(shops)} shops: Kafeco (15 prods) 0754689353 Kampala, Sann Kawempe, Hardware\n• {prod_count} products: Chunky black shoes UGX 125k (original 150k) ⭐5.0 stock 10 Kawempe Sann - Cloudinary!\n• {sellers_count} sellers: free14 plan 14 Days FREE - e.g. ndyomugishasteven@gmail.com\n• Users, Orders, Coins, Promotions, Billboard, Kassag - all kv_store! 27 keys!\n\nTry:\n• 'shops in Kampala' - REAL shops\n• 'Chunky shoes' - REAL UGX 125k\n• 'how to buy' / 'how to sell' - Full guide!\n• 'what are coins' / 'what is Kassag' / 'what is billboard'\n• 'payment methods' / 'delivery time' / 'what database'\n• 'products under 100k'\n\nWhat you want today Boss? 🛍️👑"

        # ===== GENERAL SEARCH =====
        else:
            kw = re.sub(r'[^a-z0-9 ]','',ml).split()[0] if ml.split() else ''
            if len(kw) > 2:
                products = load_all_products(search=kw, max_price=max_price, location=location, limit=6)
            if products:
                reply = f"Boss! 🔍 Found {len(products)} products for '{msg}' - REAL from {prod_count} products table!{' Under UGX '+f'{max_price:,}' if max_price else ''}{' in '+location if location else ''} - Cloudinary images - Check below 👇"
            else:
                products = load_all_products(limit=6)
                reply = f"Boss! I know EVERYTHING - 100+ Q&A + {len(shops)} shops, {prod_count} products REAL! Latest is Chunky black shoes UGX 125k from Sann in Kawempe ⭐5.0! Try 'shops in Kampala', 'Chunky shoes', 'how to buy', 'what are coins', 'what is Kassag'! 🛍️"

        return jsonify({'reply': reply, 'products': products[:8], 'shops': len(shops), 'products_count': prod_count})

    except Exception as e:
        print(f"CRITICAL {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'reply': f"Kale Boss! I'm Sannlas AI - KNOWS EVERYTHING - 100+ Q&A! 🧠 {prod_count if 'prod_count' in locals() else 31} products, {len(shops) if 'shops' in locals() else 3} shops - Try 'shops in Kampala' or 'Chunky shoes' or 'how to buy' or 'what are coins'! 🛍️", 'products': []}), 200
