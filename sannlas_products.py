from flask import Blueprint, request, jsonify, render_template, Response, make_response
import os, json, time, re, uuid, random
from datetime import datetime
import cloudinary
import cloudinary.uploader

products_bp = Blueprint('products_bp', __name__)

# ===== CONFIG =====
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

PRODUCTS_CACHE = {"data": None, "time": 0}

def get_conn():
    if not DATABASE_URL:
        raise Exception("No DATABASE_URL")
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except Exception as e:
        try:
            import psycopg2
            return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
        except Exception as e2:
            raise Exception("DB connection failed")

def ensure_tables():
    if not DATABASE_URL: return
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, data JSONB NOT NULL);")
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, data JSONB NOT NULL);")
        conn.commit(); cur.close(); conn.close()
    except Exception as e: 
        print("ensure_tables:", e)

def load_db(file, default):
    try:
        if DATABASE_URL:
            ensure_tables(); conn = get_conn()
            try:
                from psycopg.rows import dict_row
                cur = conn.cursor(row_factory=dict_row)
                if file == 'products.json':
                    cur.execute("SELECT data FROM products ORDER BY id ASC"); rows = cur.fetchall(); cur.close(); conn.close()
                    result=[]
                    for r in rows:
                        d=r['data']
                        if isinstance(d,str):
                            try: d=json.loads(d)
                            except: pass
                        result.append(d)
                    return result
                else:
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                    if not row: return default
                    d=row['data']
                    if isinstance(d,str):
                        try: d=json.loads(d)
                        except: pass
                    return d
            except:
                try:
                    import psycopg2.extras
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    if file == 'products.json':
                        cur.execute("SELECT data FROM products ORDER BY id ASC"); rows = cur.fetchall(); cur.close(); conn.close()
                        result=[]
                        for r in rows:
                            d=r['data']
                            if isinstance(d,str):
                                try: d=json.loads(d)
                                except: pass
                            result.append(d)
                        return result
                    else:
                        cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                        if not row: return default
                        d=row['data']
                        if isinstance(d,str):
                            try: d=json.loads(d)
                            except: pass
                        return d
                except:
                    try: conn.close()
                    except: pass
                    return default
        else:
            path=f'data/{file}'
            if os.path.exists(path):
                try: return json.load(open(path))
                except: return default
            return default
    except: return default

def save_db(file, data):
    global PRODUCTS_CACHE
    if file in ('products.json','users.json','shops.json'):
        PRODUCTS_CACHE["data"] = None
    if DATABASE_URL:
        try:
            ensure_tables(); conn = get_conn(); cur = conn.cursor()
            try:
                from psycopg.types.json import Jsonb
                if file == 'products.json':
                    cur.execute("DELETE FROM products")
                    for item in data: cur.execute("INSERT INTO products (data) VALUES (%s)", [Jsonb(item)])
                else:
                    cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, Jsonb(data)))
            except ImportError:
                import json as js
                if file == 'products.json':
                    cur.execute("DELETE FROM products")
                    for item in data: cur.execute("INSERT INTO products (data) VALUES (%s)", [js.dumps(item)])
                else:
                    cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, js.dumps(data)))
            conn.commit(); cur.close(); conn.close(); return
        except Exception as e: print(e)
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

# ===== CATEGORY MAP =====
CATEGORY_MAP = {
    "Fashion & Clothing": ["t-shirt","tshirt","shirt","trouser","jeans","dress","skirt","suit","jacket","coat","sweater","hoodie","shorts","tracksuit","uniform","underwear","socks","fabric","textile","cloth","kitenge","gomesi","kanzu"],
    "Shoes": ["shoe","shoes","sneaker","sneakers","boot","boots","heels","sandal","sandals","loafer","trainer","nike","adidas","jordan","puma","air force","air max"],
    "Bags": ["bag","bags","handbag","backpack","purse","wallet","school bag","laptop bag"],
    "Jewelry & Watches": ["watch","rolex","smartwatch","necklace","bracelet","ring","earring","jewelry","casio","clock"],
    "Electronics": ["tv","television","radio","speaker","headphone","earphone","camera","lens","drone","game console","controller","smart devices"],
    "Computers & Technology": ["laptop","desktop","computer","monitor","keyboard","mouse","ram","ssd","hard drive","flash disk","memory card","router","modem","printer","scanner","projector","server","webcam"],
    "Phones & Accessories": ["phone","iphone","samsung","tecno","infinix","xiaomi","oppo","huawei","nokia","itel","smartphone","phone case","screen protector","power bank"],
    "Home & Furniture": ["sofa","bed","mattress","wardrobe","table","chair","desk","cabinet","shelf","tv stand","curtain","carpet","rug","pillow","blanket","mirror","lamp"],
    "Home Appliances": ["fridge","freezer","cooker","oven","microwave","blender","kettle","washing machine","vacuum","fan","air conditioner","iron"],
    "Construction & Building": ["cement","sand","gravel","brick","block","paver","steel","roofing","timber","door","window","tile","paint","pipe","tap","toilet","sink","excavator","mixer","helmet","safety boot"],
    "Vehicles & Transport": ["electric bike","e-bike","ebike","bike","bicycle","motorcycle","motorbike","scooter","electric scooter","car","pickup","van","truck","bus","tractor","trailer","tyre","battery","engine","gearbox","brake","car radio","gps","oil","lubricant"],
}
CATEGORY_PRIORITY = ["Vehicles & Transport", "Tools & Hardware", "Electrical & Solar", "Construction & Building", "Electronics", "Phones & Accessories", "Computers & Technology", "Shoes", "Fashion & Clothing"]

def get_smart_category(text):
    if not text: return "Other / Miscellaneous"
    t = text.lower().strip()
    matches = []
    for cat, keywords in CATEGORY_MAP.items():
        for kw in sorted(keywords, key=len, reverse=True):
            if kw in t:
                matches.append((cat, kw, len(kw)))
    if not matches: return "Other / Miscellaneous"
    for priority_cat in CATEGORY_PRIORITY:
        for cat, kw, l in matches:
            if cat == priority_cat: return cat
    matches.sort(key=lambda x: x[2], reverse=True)
    return matches[0][0]

def expand_search_query(q):
    if not q: return ""
    synonyms = {"phone": "phone smartphone mobile","bike": "bike bicycle motorcycle electric bike","tv": "tv television","fridge": "fridge freezer"}
    q_lower = q.lower()
    expanded = q_lower
    for key, vals in synonyms.items():
        if key in q_lower: expanded += " " + vals
    return expanded

def make_shop_slug(business):
    if not business: return 'shop'
    base = re.sub(r'[^a-z0-9]+', '-', business.lower()).strip('-')
    if not base: base = 'shop'
    return base[:50]

def get_biz_key(name):
    if not name: return ''
    return re.sub(r'[^a-z0-9]+', '', name.lower())

def ensure_shop_for_user(user):
    shops = load_db('shops.json', [])
    biz = (user.get('business') or '').strip()
    if not biz: biz = 'Shop'
    biz_key = get_biz_key(biz)
    slug = make_shop_slug(biz)
    email = (user.get('email') or '').lower()
    for s in shops:
        s_biz = s.get('business_name') or s.get('name') or ''
        if get_biz_key(s_biz) == biz_key and biz_key:
            s['shop_slug'] = slug
            s['slug'] = slug
            s['business_name'] = biz
            s['name'] = biz
            if email: s['owner_email'] = email
            if user.get('phone'): s['phone'] = user.get('phone')
            save_db('shops.json', shops)
            return s
    existing = next((s for s in shops if (s.get('shop_slug')==slug or s.get('slug')==slug)), None)
    if existing:
        existing['business_name'] = biz
        existing['name'] = biz
        existing['shop_slug'] = slug
        existing['slug'] = slug
        save_db('shops.json', shops)
        return existing
    shop = {"id": int(time.time()*1000),"user_id": user.get('id'),"business_name": biz,"name": biz,"shop_slug": slug,"slug": slug,"phone": user.get('phone',''),"owner_email": email,"location": "Kampala","description": "Welcome to " + biz + " shop!","logo_url": "","banner_url": "","verified": False,"total_products": 0,"product_count": 0,"created_at": time.time()}
    shops.append(shop)
    save_db('shops.json', shops)
    return shop

# ===== ROUTES =====
@products_bp.route('/products')
def products_page():
    return render_template('products.html')

@products_bp.route('/product/<pid>')
def product_link(pid):
    ref = request.args.get('ref','')
    promo = request.args.get('promo','')
    try:
        clicks = load_db('promo_clicks.json',[])
        clicks.append({'product_id':pid,'ref':ref,'promo':promo,'time':time.time(),'ip':request.remote_addr})
        save_db('promo_clicks.json', clicks)
    except: pass
    return render_template('index.html')

@products_bp.route('/p/<pid>')
def product_short(pid):
    return product_link(pid)

@products_bp.route('/api/all-products')
def api_all_products():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM products ORDER BY id DESC")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]
        cur.close(); conn.close()
        return jsonify(data)
    except Exception as e:
        print(e)
        products = load_db('products.json', [])
        return jsonify(products)

@products_bp.route('/api/products')
def get_products():
    try:
        q = request.args.get('q','').lower()
        q_expanded = expand_search_query(q) if q else ""
        shop_slug = request.args.get('shop') or request.args.get('shop_slug')
        limit = int(request.args.get('limit', 200))
        offset = int(request.args.get('offset', 0))
        now = time.time()
        if PRODUCTS_CACHE["data"] and (now - PRODUCTS_CACHE["time"] < 30):
            products = PRODUCTS_CACHE["data"]
        else:
            products = load_db('products.json', [])
            PRODUCTS_CACHE["data"] = products
            PRODUCTS_CACHE["time"] = now
        filtered = products
        if q_expanded:
            q_words = q_expanded.split()
            def match(p):
                hay = f"{p.get('name','')} {p.get('business','')} {p.get('main_category','')} {p.get('category','')} {p.get('description','')} {p.get('desc','')} {p.get('smart_keywords','')}".lower()
                return any(w in hay for w in q_words)
            filtered = [p for p in filtered if match(p)]
        if shop_slug:
            sf = shop_slug.strip()
            exact = [p for p in filtered if p.get('shop_slug')==sf]
            if exact: filtered = exact
        filtered = sorted(filtered, key=lambda x:x.get('created',0), reverse=True)
        chunk = filtered[offset:offset+limit]
        return jsonify(chunk)
    except Exception as e:
        print(f"Products API error: {e}")
        return jsonify([])

@products_bp.route('/api/my-products')
def my_products_compat():
    phone = request.args.get('phone','').strip()
    email = request.args.get('email','').lower().strip()
    products = load_db('products.json', [])
    if not email and not phone:
        return jsonify([])
    result = []
    for p in products:
        p_email = (p.get('seller_email') or p.get('email') or p.get('user_email') or p.get('shop_email') or p.get('owner_email') or '').lower().strip()
        p_phone = (p.get('phone') or p.get('seller_phone') or '').strip()
        if email and p_email and p_email == email:
            result.append(p)
        elif phone and p_phone and p_phone == phone:
            result.append(p)
    return jsonify(result)

@products_bp.route('/api/sell', methods=['POST'])
def sell():
    name=request.form.get('name')
    price=int(request.form.get('price',0))
    original_price = int(request.form.get('original_price') or request.form.get('price',0))
    if original_price < price: original_price = price
    business=request.form.get('business')
    location=request.form.get('location')
    phone=request.form.get('phone')
    desc=request.form.get('desc','') or request.form.get('description','')
    raw_input = (request.form.get('main_category','') + " " + request.form.get('name','') + " " + (request.form.get('desc','') or request.form.get('description',''))).strip()
    smart_cat = get_smart_category(raw_input)
    main_cat = smart_cat
    smart_keywords = raw_input.lower() + " " + smart_cat.lower()
    stock=int(request.form.get('stock',10))
    promo_commission = int(request.form.get('promo_commission','3'))
    user_email=request.form.get('user_email','').lower().strip()
    users=load_db('users.json',[]); seller=next((u for u in users if u['phone']==phone or u['email']==user_email),None)
    if not seller: return jsonify({'success':False,'message':'Register first'}),402
    images=[]
    image_count = int(request.form.get('image_count','0') or '0')
    if image_count > 0:
        for i in range(4):
            key = f'image_{i}'
            f = request.files.get(key)
            if f and f.filename:
                result = cloudinary.uploader.upload(f, folder="sannlas/products", transformation=[{'width': 800, 'quality': 'auto'}])
                images.append(result['secure_url'])
    if not images:
        for key in request.files:
            f=request.files[key]
            if f and f.filename:
                result = cloudinary.uploader.upload(f, folder="sannlas/products", transformation=[{'width': 800, 'quality': 'auto'}])
                images.append(result['secure_url'])
    if not images: images=['https://via.placeholder.com/300']
    images = images[:4]
    shop_id=None; shop_slug=None
    try:
        shop = ensure_shop_for_user(seller); shop_id=shop.get('id'); shop_slug=shop.get('shop_slug')
    except: pass
    prod = {
        'id': int(time.time()*1000),
        'name': name,
        'price': price,
        'original_price': original_price,
        'business': business,
        'location': location,
        'phone': phone,
        'seller_email': user_email,
        'shop_email': user_email,
        'owner_email': user_email,
        'email': user_email,
        'user_email': user_email,
        'description': desc,
        'image': images[0],
        'images': images,
        'main_category': main_cat,
        'smart_keywords': smart_keywords,
        'stock': stock,
        'sold': 0,
        'rating': 5.0,
        'reviews': [],
        'created': time.time(),
        'shop_id': shop_id,
        'shop_slug': shop_slug,
        'promo_commission': promo_commission
    }
    products=load_db('products.json',[]); products.append(prod); save_db('products.json', products)
    PRODUCTS_CACHE["data"] = None
    PRODUCTS_CACHE["time"] = 0
    return jsonify({'success':True,'message':f'Product added! Seller {user_email} will receive orders!'})

@products_bp.route('/api/delete-product/<int:pid>', methods=['DELETE'])
def delete_prod(pid):
    products=load_db('products.json', []); products=[p for p in products if p['id']!=pid]; save_db('products.json', products)
    PRODUCTS_CACHE["data"] = None
    return jsonify({'success':True})

@products_bp.route('/api/fix-slugs')
def fix_slugs():
    products = load_db('products.json', [])
    for p in products:
        b = p.get('business') or ''
        if b: p['shop_slug'] = make_shop_slug(b)
    save_db('products.json', products)
    PRODUCTS_CACHE["data"] = None
    return jsonify({'success':True,'message':'Fixed'})
