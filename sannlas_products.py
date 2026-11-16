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

# ✅ FIX 1: Run ensure_tables ONCE, not every request
_TABLES_DONE = False

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
    global _TABLES_DONE
    if _TABLES_DONE:  # ✅ SKIP if already done!
        return
    if not DATABASE_URL: return
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, data JSONB NOT NULL);")
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, data JSONB NOT NULL);")
        # ✅ Speed index for sorting by created date stored inside JSONB
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_products_created ON products (((data->>'created')::float8) DESC);")
        except: pass
        conn.commit(); cur.close(); conn.close()
        _TABLES_DONE = True
    except Exception as e:
        print("ensure_tables:", e)

def _parse_row_data(d):
    if isinstance(d, str):
        try: return json.loads(d)
        except: return d
    return d

def load_db(file, default):
    try:
        if DATABASE_URL:
            ensure_tables(); conn = get_conn()
            try:
                from psycopg.rows import dict_row
                cur = conn.cursor(row_factory=dict_row)
                if file == 'products.json':
                    cur.execute("SELECT data FROM products ORDER BY id ASC"); rows = cur.fetchall(); cur.close(); conn.close()
                    return [_parse_row_data(r['data']) for r in rows]
                else:
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                    if not row: return default
                    return _parse_row_data(row['data'])
            except:
                try:
                    import psycopg2.extras
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    if file == 'products.json':
                        cur.execute("SELECT data FROM products ORDER BY id ASC"); rows = cur.fetchall(); cur.close(); conn.close()
                        return [_parse_row_data(r['data']) for r in rows]
                    else:
                        cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                        if not row: return default
                        return _parse_row_data(row['data'])
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

# ✅ FIX 2: FAST Neon helpers - SQL does paging, not Python
def get_all_products_neon():
    return load_db('products.json', [])

def get_products_page_neon(limit=20, offset=0, shop_slug=None, q_words=None):
    """FAST: Neon returns only `limit` rows, sorted by created DESC. No loading all products!"""
    if not DATABASE_URL:
        # Local fallback
        products = load_db('products.json', [])
        products = sorted(products, key=lambda x: x.get('created', 0), reverse=True)
        return products[offset:offset+limit]
    # If search/shop filter present, we need to filter in Python (JSONB search is slow without index)
    # But for normal browse (no filter) - use fast SQL path!
    if not shop_slug and not q_words:
        try:
            ensure_tables(); conn = get_conn()
            try:
                from psycopg.rows import dict_row
                cur = conn.cursor(row_factory=dict_row)
                # ✅ Neon sorts + pages - only 20 rows travel over network!
                cur.execute("SELECT data FROM products ORDER BY (data->>'created')::float8 DESC NULLS LAST, id DESC LIMIT %s OFFSET %s", (limit, offset))
                rows = cur.fetchall(); cur.close(); conn.close()
                return [_parse_row_data(r['data']) for r in rows]
            except:
                try:
                    import psycopg2.extras
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    cur.execute("SELECT data FROM products ORDER BY (data->>'created')::float8 DESC NULLS LAST, id DESC LIMIT %s OFFSET %s", (limit, offset))
                    rows = cur.fetchall(); cur.close(); conn.close()
                    return [_parse_row_data(r['data']) for r in rows]
                except:
                    try: conn.close()
                    except: pass
                    return get_all_products_neon()[offset:offset+limit]
        except Exception as e:
            print("get_products_page:", e)
            return get_all_products_neon()[offset:offset+limit]
    # Filtered path: use cache, filter in Python
    now = time.time()
    if PRODUCTS_CACHE["data"] and (now - PRODUCTS_CACHE["time"] < 30):
        products = PRODUCTS_CACHE["data"]
    else:
        products = get_all_products_neon()
        PRODUCTS_CACHE["data"] = products
        PRODUCTS_CACHE["time"] = now
    filtered = products
    if q_words:
        def match(p):
            hay = f"{p.get('name','')} {p.get('business','')} {p.get('main_category','')} {p.get('category','')} {p.get('description','')} {p.get('desc','')} {p.get('smart_keywords','')}".lower()
            return any(w in hay for w in q_words)
        filtered = [p for p in filtered if match(p)]
    if shop_slug:
        exact = [p for p in filtered if p.get('shop_slug') == shop_slug]
        if exact: filtered = exact
    filtered = sorted(filtered, key=lambda x: x.get('created', 0), reverse=True)
    return filtered[offset:offset+limit]

def add_product_neon(prod):
    """✅ FAST: 1 INSERT, not DELETE ALL + re-insert ALL!"""
    global PRODUCTS_CACHE
    PRODUCTS_CACHE["data"] = None
    if not DATABASE_URL:
        products = load_db('products.json', [])
        found = False
        for i, p in enumerate(products):
            if str(p.get('id')) == str(prod.get('id')):
                products[i] = prod; found = True; break
        if not found: products.append(prod)
        save_db('products.json', products)
        return prod
    try:
        ensure_tables(); conn = get_conn(); cur = conn.cursor()
        try:
            from psycopg.types.json import Jsonb
            # If same ID exists, update it, else insert
            cur.execute("SELECT id FROM products WHERE (data->>'id') = %s LIMIT 1", (str(prod.get('id')),))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE products SET data = %s WHERE id = %s", (Jsonb(prod), row[0]))
            else:
                cur.execute("INSERT INTO products (data) VALUES (%s)", [Jsonb(prod)])
        except ImportError:
            import json as js
            cur.execute("SELECT id FROM products WHERE (data->>'id') = %s LIMIT 1", (str(prod.get('id')),))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE products SET data = %s WHERE id = %s", (js.dumps(prod), row[0]))
            else:
                cur.execute("INSERT INTO products (data) VALUES (%s)", [js.dumps(prod)])
        conn.commit(); cur.close(); conn.close()
        return prod
    except Exception as e:
        print("add_product_neon:", e)
        # Fallback to old slow method if fast fails
        products = load_db('products.json', [])
        products.append(prod)
        save_db('products.json', products)
        return prod

def delete_product_neon(pid):
    """✅ FAST: 1 DELETE, not DELETE ALL + re-insert ALL!"""
    global PRODUCTS_CACHE
    PRODUCTS_CACHE["data"] = None
    if not DATABASE_URL:
        products = load_db('products.json', [])
        products = [p for p in products if str(p.get('id')) != str(pid)]
        save_db('products.json', products)
        return
    try:
        ensure_tables(); conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE (data->>'id') = %s", (str(pid),))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print("delete_product_neon:", e)

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
        return jsonify(get_all_products_neon())
    except Exception as e:
        print(e)
        return jsonify([])

@products_bp.route('/api/products')
def get_products():
    try:
        q = request.args.get('q','').lower()
        q_expanded = expand_search_query(q) if q else ""
        shop_slug = request.args.get('shop') or request.args.get('shop_slug')
        limit = int(request.args.get('limit', 20))  # ✅ Changed 200 -> 20 default!
        offset = int(request.args.get('offset', 0))
        limit = min(limit, 50)  # ✅ Never allow 200 at once!
        q_words = q_expanded.split() if q_expanded else None
        shop_val = shop_slug.strip() if shop_slug else None
        # ✅ FIX 2: Neon does LIMIT/OFFSET + sorting
        chunk = get_products_page_neon(limit=limit, offset=offset, shop_slug=shop_val, q_words=q_words)
        return jsonify(chunk)
    except Exception as e:
        print(f"Products API error: {e}")
        return jsonify([])

@products_bp.route('/api/my-products')
def my_products_compat():
    phone = request.args.get('phone','').strip()
    email = request.args.get('email','').lower().strip()
    products = get_all_products_neon()
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
    add_product_neon(prod)
    PRODUCTS_CACHE["data"] = None
    PRODUCTS_CACHE["time"] = 0
    return jsonify({'success':True,'message':f'Product added! Seller {user_email} will receive orders!'})

@products_bp.route('/api/delete-product/<int:pid>', methods=['DELETE'])
def delete_prod(pid):
    delete_product_neon(pid)
    PRODUCTS_CACHE["data"] = None
    return jsonify({'success':True})

@products_bp.route('/api/fix-slugs')
def fix_slugs():
    products = get_all_products_neon()
    for p in products:
        b = p.get('business') or ''
        if b:
            p['shop_slug'] = make_shop_slug(b)
            add_product_neon(p)
    PRODUCTS_CACHE["data"] = None
    return jsonify({'success':True,'message':'Fixed in Neon'})

@products_bp.route('/api/fix-all-old-products')
def fix_all_old():
    products = get_all_products_neon()
    shops = load_db('shops.json', [])
    users = load_db('users.json', [])
    fixed = 0
    for p in products:
        if not p.get('seller_email'):
            shop = next((s for s in shops if s.get('shop_slug') == p.get('shop_slug')), None)
            if shop and shop.get('owner_email'):
                p['seller_email'] = shop['owner_email'].lower()
                p['shop_email'] = p['seller_email']
                p['owner_email'] = p['seller_email']
                p['email'] = p['seller_email']
                p['user_email'] = p['seller_email']
                add_product_neon(p)
                fixed += 1
            else:
                ph = p.get('phone')
                u = next((x for x in users if x.get('phone') == ph), None)
                if u and u.get('email'):
                    p['seller_email'] = u['email'].lower()
                    p['shop_email'] = u['email'].lower()
                    p['owner_email'] = u['email'].lower()
                    p['email'] = u['email'].lower()
                    p['user_email'] = u['email'].lower()
                    add_product_neon(p)
                    fixed += 1
    PRODUCTS_CACHE["data"] = None
    return jsonify({'success': True, 'fixed': fixed, 'total': len(products), 'message': f'Fixed {fixed} old products!'})
