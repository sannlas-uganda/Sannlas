from flask import Blueprint, request, jsonify, render_template
import os, json, time, uuid

cart_bp = Blueprint('cart_bp', __name__)

# ===== FIXED: SUPPORT POSTGRES LIKE app.py =====
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL:
        raise Exception("No DATABASE_URL")
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def ensure_tables():
    if not DATABASE_URL: return
    try:
        conn = get_conn(); cur = conn.cursor()
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
                cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
                row = cur.fetchone(); cur.close(); conn.close()
                if not row: return default
                d = row['data']
                if isinstance(d,str):
                    try: d=json.loads(d)
                    except: pass
                return d
            except:
                try:
                    import psycopg2.extras
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
                    row = cur.fetchone(); cur.close(); conn.close()
                    if not row: return default
                    d = row['data']
                    if isinstance(d,str):
                        try: d=json.loads(d)
                        except: pass
                    return d
                except:
                    try: conn.close()
                    except: pass
                    return default
        else:
            path = f'data/{file}'
            if os.path.exists(path):
                try: return json.load(open(path))
                except: return default
            return default
    except: return default

def save_db(file, data):
    if DATABASE_URL:
        try:
            ensure_tables(); conn = get_conn(); cur = conn.cursor()
            try:
                from psycopg.types.json import Jsonb
                cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, Jsonb(data)))
            except ImportError:
                cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, json.dumps(data)))
            conn.commit(); cur.close(); conn.close(); return
        except Exception as e:
            print("save_db error:", e)
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

# === SPEED CACHE - ADDED FOR FAST CART ===
_cache = {}
_cache_time = {}

def cached_load(key, default, ttl=15):
    import time as _time
    now = _time.time()
    if key in _cache and (now - _cache_time.get(key,0) < ttl):
        return _cache[key]
    data = load_db(key, default)
    _cache[key] = data
    _cache_time[key] = now
    return data

def cached_save(key, data):
    import time as _time
    _cache[key] = data
    _cache_time[key] = _time.time()
    save_db(key, data)

def get_carts(): 
    return cached_load('carts.json', [], ttl=10)

def save_carts(c): 
    cached_save('carts.json', c)
@cart_bp.route('/cart')
def cart_page():
    return render_template('cart.html')

@cart_bp.route('/api/cart', methods=['GET'])
def api_get_cart():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    carts = get_carts()
    user_cart = None
    for c in carts:
        c_email = (c.get('email') or '').lower().strip()
        c_phone = (c.get('phone') or '').strip()
        if (email and c_email == email) or (phone and c_phone == phone and phone != ''):
            user_cart = c
            break
    if not user_cart:
        return jsonify({"items": [], "total": 0, "count": 0})
    items = sorted(user_cart.get('items', []), key=lambda x: x.get('added_at',0), reverse=True)
    total = sum(float(i.get('price',0)) * int(i.get('qty',1)) for i in items)
    return jsonify({"items": items, "total": total, "count": len(items)})

@cart_bp.route('/api/cart/add', methods=['POST'])
def api_add_to_cart():
    data = request.get_json() or {}
    email = (data.get('email') or '').lower().strip()
    phone = (data.get('phone') or '').strip()
    product_id = str(data.get('product_id') or '').strip()
    name = data.get('name','Product')
    price = float(data.get('price',0) or 0)
    image = data.get('image','')
    shop_name = data.get('shop_name','')
    shop_slug = data.get('shop_slug','')
    seller_email = (data.get('seller_email') or data.get('shop_email') or '').lower().strip()
    size = data.get('size','')
    qty = int(data.get('qty',1) or 1)
    # If frontend didn't send seller_email, look it up from products table
    if not seller_email and product_id:
        try:
            _prods = load_db('products.json', []) or []
            for _p in _prods:
                if str(_p.get('id')) == product_id:
                    seller_email = str(_p.get('seller_email','')).lower().strip()
                    if not shop_slug: shop_slug = _p.get('shop_slug','')
                    if not shop_name: shop_name = _p.get('business','')
                    break
        except: pass

    if not product_id or product_id == 'None':
        return jsonify({"success": False, "message": "Invalid product ID Boss!"}), 400
    if price==0:
        return jsonify({"success": False, "message": "Price is 0 Boss! Can't add"}), 400
    if not email and not phone:
        return jsonify({"success": False, "message": "Please login first Boss!"}), 401

    carts = get_carts()
    user_cart = None
    for c in carts:
        c_email = (c.get('email') or '').lower().strip()
        c_phone = (c.get('phone') or '').strip()
        if (email and c_email == email) or (phone and c_phone == phone and phone != ''):
            user_cart = c
            break
    if not user_cart:
        user_cart = {"email": email, "phone": phone, "items": [], "created": time.time(), "id": str(uuid.uuid4())}
        carts.append(user_cart)

    existing = next((i for i in user_cart['items'] if str(i.get('product_id'))==product_id), None)
    if existing:
        existing['qty'] = int(existing.get('qty',1)) + qty
    else:
        user_cart['items'].append({
            "product_id": product_id,
            "name": name,
            "price": price,
            "image": image,
            "shop_name": shop_name,
            "shop_slug": shop_slug,
            "seller_email": seller_email,
            "size": size,
            "qty": qty,
            "added_at": time.time()
        })
    
    user_cart['items'] = sorted(user_cart['items'], key=lambda x: x.get('added_at',0), reverse=True)
    save_carts(carts)
    return jsonify({"success": True, "message": f"{name} added!", "count": len(user_cart['items'])})

@cart_bp.route('/api/cart/remove', methods=['POST'])
def api_remove():
    data = request.get_json() or {}
    email = (data.get('email') or '').lower().strip()
    phone = (data.get('phone') or '').strip()
    product_id = str(data.get('product_id') or '')
    carts = get_carts()
    for uc in carts:
        c_email = (uc.get('email') or '').lower().strip()
        c_phone = (uc.get('phone') or '').strip()
        if (email and c_email == email) or (phone and c_phone == phone and phone != ''):
            uc['items'] = [i for i in uc['items'] if str(i.get('product_id')) != product_id]
            break
    save_carts(carts)
    return jsonify({"success": True})

@cart_bp.route('/api/cart/clear', methods=['POST'])
def api_clear():
    data = request.get_json() or {}
    email = (data.get('email') or '').lower().strip()
    phone = (data.get('phone') or '').strip()
    carts = get_carts()
    for uc in carts:
        c_email = (uc.get('email') or '').lower().strip()
        c_phone = (uc.get('phone') or '').strip()
        if (email and c_email == email) or (phone and c_phone == phone and phone != ''):
            uc['items'] = []
            break
    save_carts(carts)
    return jsonify({"success": True})

@cart_bp.route('/api/cart/update', methods=['POST'])
def api_update_qty():
    data = request.get_json() or {}
    email = (data.get('email') or '').lower().strip()
    phone = (data.get('phone') or '').strip()
    product_id = str(data.get('product_id') or '')
    change = int(data.get('change', 0))  # +1 or -1

    if not email and not phone:
        return jsonify({"success": False, "message": "Login required"}), 401

    carts = get_carts()
    for uc in carts:
        c_email = (uc.get('email') or '').lower().strip()
        c_phone = (uc.get('phone') or '').strip()
        if (email and c_email == email) or (phone and c_phone == phone and phone != ''):
            # find item
            for item in uc['items']:
                if str(item.get('product_id')) == product_id:
                    new_qty = int(item.get('qty',1)) + change
                    if new_qty <= 0:
                        uc['items'] = [i for i in uc['items'] if str(i.get('product_id')) != product_id]
                    else:
                        item['qty'] = new_qty
                    break
            break

    save_carts(carts)
    return jsonify({"success": True, "message": f"Updated to {new_qty if new_qty>0 else 'removed'}"})

@cart_bp.route('/api/orders/create', methods=['POST'])
def api_create_order():
    data = request.get_json() or {}
    email = (data.get('email') or data.get('buyer_email') or '').lower().strip()
    phone = (data.get('phone') or data.get('buyer_phone') or '').strip()
    buyer_name = data.get('buyer_name') or data.get('name') or email or 'Customer'
    district = data.get('district') or ''
    address = data.get('address') or data.get('delivery_address') or ''
    items = data.get('items') or []
    # FALLBACK: If frontend didn't send items (old cart.html), load from saved cart
    if not items:
        carts = get_carts()
        for c in carts:
            c_email = (c.get('email') or '').lower().strip()
            c_phone = (c.get('phone') or '').strip()
            if (email and c_email == email) or (phone and c_phone == phone and phone != ''):
                items = c.get('items', [])
                break
    if not items:
        return jsonify({"success": False, "message": "Cart is empty Boss!"}), 400
    # Enrich missing seller_email from products
    try:
        _prods = load_db('products.json', []) or []
        _map = {str(_p.get('id')): _p for _p in _prods}
        for it in items:
            if not it.get('seller_email'):
                _p = _map.get(str(it.get('product_id')))
                if _p:
                    it['seller_email'] = str(_p.get('seller_email','')).lower().strip()
                    it['shop_slug'] = it.get('shop_slug') or _p.get('shop_slug','')
                    it['shop_name'] = it.get('shop_name') or _p.get('business','')
    except: pass
    orders = load_db('orders_v2.json', []) or []
    if not isinstance(orders, list): orders = []
    created = []
    for it in items:
        seller_email = str(it.get('seller_email') or '').lower().strip()
        if not seller_email:
            continue  # Can't deliver order without seller - skip
        tracking = f"SN-{int(time.time())}-{len(orders)+1}"
        qty = int(it.get('qty') or it.get('quantity') or 1)
        price = float(it.get('price') or 0)
        new_o = {
            'id': tracking,
            'tracking_id': tracking,
            'product_id': str(it.get('product_id') or ''),
            'product_name': it.get('name') or 'Product',
            'name': it.get('name') or 'Product',
            'image': it.get('image') or '',
            'product_image': it.get('image') or '',
            'price': price,
            'total': price * qty,
            'qty': qty,
            'quantity': qty,
            'size': it.get('size') or '',
            'seller_email': seller_email,
            'shop_slug': it.get('shop_slug') or '',
            'business': it.get('shop_name') or '',
            'shop_name': it.get('shop_name') or '',
            'buyer_email': email,
            'buyer_name': buyer_name,
            'buyer_phone': phone,
            'customer_name': buyer_name,
            'phone': phone,
            'district': district,
            'address': address,
            'delivery_address': address,
            'status': 'new',
            'created_at': time.time(),
            'created': time.time()
        }
        orders.append(new_o); created.append(new_o)
    if not created:
        return jsonify({"success": False, "message": "No seller found for these products - re-add to cart"}), 400
    save_db('orders_v2.json', orders)
    # Clear cart after order
    carts = get_carts()
    for c in carts:
        c_email = (c.get('email') or '').lower().strip()
        c_phone = (c.get('phone') or '').strip()
        if (email and c_email == email) or (phone and c_phone == phone and phone != ''):
            c['items'] = []
            break
    save_carts(carts)
    return jsonify({"success": True, "orders": created, "count": len(created)})

@cart_bp.route('/api/my-orders', methods=['GET'])
def api_my_orders():
    email = request.args.get('email','').lower().strip()
    orders = load_db('orders_v2.json', []) or []
    mine = [o for o in orders if str(o.get('buyer_email','')).lower() == email]
    return jsonify({"orders": sorted(mine, key=lambda x: x.get('created_at',0), reverse=True)})
