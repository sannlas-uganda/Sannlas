from flask import Blueprint, request, jsonify, render_template
import random, time, os, json, re
from datetime import datetime
from collections import defaultdict

orders_bp = Blueprint('orders_bp', __name__)

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
        if DATABASE_URL:
            conn = get_conn()
            try:
                from psycopg.rows import dict_row
                cur = conn.cursor(row_factory=dict_row)
                if file == 'products.json':
                    cur.execute("SELECT data FROM products ORDER BY id ASC"); rows = cur.fetchall(); cur.close(); conn.close()
                    return [r['data'] if not isinstance(r['data'], str) else json.loads(r['data']) for r in rows]
                else:
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                    if not row: return default
                    d=row['data']; return d if not isinstance(d,str) else json.loads(d)
            except:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                if file == 'products.json':
                    cur.execute("SELECT data FROM products ORDER BY id ASC"); rows = cur.fetchall(); cur.close(); conn.close()
                    return [r['data'] if not isinstance(r['data'],str) else json.loads(r['data']) for r in rows]
                else:
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                    if not row: return default
                    d=row['data']; return d if not isinstance(d,str) else json.loads(d)
        else:
            path=f'data/{file}'
            if os.path.exists(path):
                return json.load(open(path))
            return default
    except:
        return default

def save_db(file, data):
    if DATABASE_URL:
        try:
            conn = get_conn(); cur = conn.cursor()
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
        except Exception as e: print("SAVE ERROR", e)
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

def get_orders(): return load_db('orders.json', [])
def save_orders(d): save_db('orders.json', d)
def gen_tracking(): return f"SN-{random.randint(100000, 999999)}"
def clean_slug(s): return re.sub(r'[^a-z0-9]+','-',str(s or '').lower()).strip('-') or 'shop'

# ===== FIND REAL SELLER FROM PRODUCT + SHOP =====
def find_seller(product_id, item):
    # 1. Item already has seller?
    for k in ['real_seller_email','seller_email','shop_email','owner_email','email']:
        v = (item.get(k) or '').strip().lower()
        if v and '@' in v: 
            shop_name = item.get('real_shop_name') or item.get('shop_name') or item.get('business') or 'Sannlas'
            return v, shop_name
    # 2. Lookup in products.json by ID
    pid = str(product_id or item.get('product_id') or item.get('id') or '').strip()
    if pid:
        for p in load_db('products.json', []):
            if not isinstance(p, dict): continue
            if str(p.get('id')) == pid or str(p.get('product_id')) == pid:
                em = (p.get('seller_email') or p.get('shop_email') or p.get('owner_email') or '').lower().strip()
                nm = p.get('business') or p.get('shop_name') or p.get('business_name') or 'Sannlas'
                # Enrich item with real product data - FIX UGX 0!
                if not item.get('name'): item['name'] = p.get('name') or p.get('title') or ''
                if not item.get('product_name'): item['product_name'] = p.get('name') or p.get('title') or ''
                if not item.get('price') or float(item.get('price') or 0)==0:
                    item['price'] = p.get('discount_price') or p.get('price') or 0
                if not item.get('image'): item['image'] = p.get('image') or ''
                if em: return em, nm
                # No email in product? Try shop_slug -> shops.json
                slug = p.get('shop_slug') or clean_slug(nm)
                for s in load_db('shops.json', []):
                    if clean_slug(s.get('shop_slug') or s.get('business_name')) == clean_slug(slug):
                        if s.get('owner_email'): return s['owner_email'].lower().strip(), s.get('business_name') or nm
                return "", nm
    # 3. Lookup by shop_slug in shops.json
    slug = item.get('shop_slug') or clean_slug(item.get('shop_name') or item.get('business'))
    if slug:
        for s in load_db('shops.json', []):
            if clean_slug(s.get('shop_slug') or s.get('business_name')) == clean_slug(slug):
                if s.get('owner_email'): return s['owner_email'].lower().strip(), s.get('business_name') or 'Sannlas'
    return "admin@sannlas.com", item.get('shop_name') or item.get('business') or 'Sannlas'

# ===== PAGE - FIX NOT FOUND =====
@orders_bp.route('/my-orders')
def my_orders_page():
    return render_template('my-orders.html')

# ===== CREATE ORDER - GOOD VERSION =====
@orders_bp.route('/api/orders/create', methods=['POST'])
@orders_bp.route('/api/orders/place', methods=['POST'])
def create_orders():
    try:
        data = request.get_json() or {}
        email = (data.get('email') or data.get('buyer_email') or '').lower().strip()
        buyer_name = data.get('buyer_name','').strip() or (data.get('buyer') or {}).get('name','').strip()
        buyer_phone = data.get('buyer_phone','').strip() or (data.get('buyer') or {}).get('phone','').strip()
        district = data.get('district','').strip() or (data.get('buyer') or {}).get('district','')
        address = data.get('address','').strip()
        if not buyer_name or not buyer_phone:
            b = data.get('buyer') or {}
            buyer_name = buyer_name or b.get('name','')
            buyer_phone = buyer_phone or b.get('phone','')
            email = email or b.get('email','').lower()
        if not buyer_name or not buyer_phone:
            return jsonify({"success": False, "message": "Name & Phone required"}), 400

        # --- GET ITEMS - FIX CART BUG ---
        direct = data.get('items') or []
        if direct:
            raw_items = direct
        else:
            raw_items = []
            carts = load_db('carts.json', [])
            for c in carts:
                if (c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone):
                    # Cart can be {items:[...]} OR single item itself
                    if isinstance(c.get('items'), list):
                        raw_items.extend(c['items'])
                    elif c.get('product_id') or c.get('id'):
                        raw_items.append(c)
                    break
            # Also try cart from sannlas_cart: carts = [{email, items}] already handled
        if not raw_items:
            return jsonify({"success": False, "message": "Cart empty"}), 400

        # --- NORMALIZE + GROUP BY SELLER ---
        shops = defaultdict(list)
        for it in raw_items:
            if not isinstance(it, dict): continue
            # Normalize fields
            pid = str(it.get('product_id') or it.get('id') or '').strip()
            name = it.get('name') or it.get('title') or it.get('product_name') or ''
            price = float(it.get('price') or it.get('discount_price') or 0)
            qty = int(it.get('qty') or it.get('quantity') or 1)
            if qty < 1: qty = 1
            # If price 0, try lookup from products.json NOW
            if price == 0 and pid:
                for p in load_db('products.json', []):
                    if str(p.get('id')) == pid:
                        price = float(p.get('discount_price') or p.get('price') or 0)
                        if not name: name = p.get('name') or p.get('title') or ''
                        if not it.get('image'): it['image'] = p.get('image') or ''
                        break
            seller_email, shop_name = find_seller(pid, it)
            clean_item = {
                "product_id": pid,
                "id": pid,
                "name": name,
                "product_name": name,
                "title": name,
                "price": price,
                "qty": qty,
                "quantity": qty,
                "image": it.get('image') or it.get('product_image') or '',
                "shop_slug": it.get('shop_slug') or clean_slug(shop_name),
                "shop_name": shop_name,
                "seller_email": seller_email,
                "real_seller_email": seller_email,
                "real_shop_name": shop_name,
                "size": it.get('size',''),
                "color": it.get('color',''),
            }
            shops[seller_email].append(clean_item)

        orders = get_orders()
        created = []
        for seller_email, items in shops.items():
            tid = gen_tracking()
            while any(o.get('tracking_id')==tid for o in orders): tid = gen_tracking()
            total = sum(float(i['price'])*int(i['qty']) for i in items)
            order = {
                "order_id": tid, "tracking_id": tid, "id": tid,
                "buyer_email": email, "buyer_name": buyer_name, "buyer_phone": buyer_phone,
                "district": district, "address": address,
                "full_address": f"{district}, {address}",
                "seller_email": seller_email, "shop_email": seller_email, "shop_owner_email": seller_email,
                "shop_key": seller_email, "shop_name": items[0]['real_shop_name'],
                "items": items,
                "product_name": items[0]['name'], "name": items[0]['name'],
                "image": items[0]['image'], "product_image": items[0]['image'],
                "price": items[0]['price'], "qty": sum(i['qty'] for i in items), "quantity": sum(i['qty'] for i in items),
                "total": total, "amount": total,
                "status": "PENDING",
                "broker_agent_phone": data.get('broker_agent_phone') or data.get('ref') or request.args.get('ref') or request.cookies.get('ref_code') or '',
                "created_at": datetime.now().isoformat(), "timestamp": int(time.time()), "time": int(time.time()),
            }
            orders.append(order); created.append(order)
            # Notification for seller
            try:
                notifs = load_db('notifications.json', [])
                notifs.append({"id": f"NTF-{random.randint(100000,999999)}","recipient_email": seller_email,"type": "NEW_ORDER","title": f"🔥 NEW ORDER! {tid}","message": f"New: {items[0]['name']} - {buyer_name} {buyer_phone} UGX {total}","order_id": tid,"is_read": False,"created_at": datetime.now().isoformat(),"timestamp": int(time.time())})
                save_db('notifications.json', notifs[-500:])
            except: pass

        save_orders(orders)
        # Clear cart
        if not direct:
            try:
                carts = load_db('carts.json', [])
                carts = [c for c in carts if not ((c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone))]
                save_db('carts.json', carts)
            except: pass
        # Commission
        try:
            from sannlas_commission import split_and_record
            for o in created:
                split_and_record("broker_sale", o['total'], o.get('broker_agent_phone') or None, o.get('shop_email'), meta={"order_id": o['tracking_id']})
        except Exception as e: print("Commission", e)
        return jsonify({"success": True, "orders": created, "tracking_ids": [o['tracking_id'] for o in created]})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ===== BUYER - MY ORDERS =====
@orders_bp.route('/api/orders/my', methods=['GET'])
def my_orders_api():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    orders = get_orders()
    my = [o for o in orders if (email and str(o.get('buyer_email','')).lower()==email) or (phone and str(o.get('buyer_phone',''))==phone)]
    my.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": my[:50], "success": True})

# ===== SELLER - FOR SHOP PAGE /my-shop =====
@orders_bp.route('/api/orders/seller', methods=['GET'])
def seller_orders():
    shop_email = (request.args.get('shop_email','') or request.args.get('email','') or request.args.get('shop','')).lower().strip()
    slug = request.args.get('slug','').strip()
    orders = get_orders()
    if slug and not shop_email:
        for s in load_db('shops.json', []):
            if clean_slug(s.get('shop_slug') or s.get('business_name')) == clean_slug(slug):
                shop_email = (s.get('owner_email') or '').lower().strip()
                break
    filtered = []
    for o in orders:
        if not shop_email:
            filtered.append(o); continue
        if shop_email in [(o.get('seller_email','') or '').lower(), (o.get('shop_email','') or '').lower(), (o.get('shop_owner_email','') or '').lower(), (o.get('shop_key','') or '').lower()]:
            filtered.append(o); continue
        for it in o.get('items', []):
            if shop_email == (it.get('real_seller_email','') or it.get('seller_email','') or '').lower():
                filtered.append(o); break
    filtered.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": filtered[:100], "count": len(filtered), "success": True})

# ===== SHOP OWNER DASHBOARD - FOR shops.py owner panel =====
@orders_bp.route('/api/shop-owner/dashboard')
def shop_owner_dashboard():
    email = (request.args.get('email','') or '').lower().strip()
    slug = request.args.get('slug','').strip()
    shop_email = email
    if slug:
        for s in load_db('shops.json', []):
            if clean_slug(s.get('shop_slug') or s.get('business_name')) == clean_slug(slug):
                shop_email = (s.get('owner_email') or email).lower().strip()
                break
    orders = get_orders()
    my = [o for o in orders if shop_email in [(o.get('seller_email','') or '').lower(), (o.get('shop_email','') or '').lower()]]
    # Flatten for shops.py panel - it expects list of single-item orders
    flat = []
    for o in my:
        for it in o.get('items', []) or [{}]:
            flat.append({
                "id": o.get('tracking_id'), "tracking_id": o.get('tracking_id'),
                "product_name": it.get('name') or o.get('product_name'), "name": it.get('name') or o.get('product_name'),
                "image": it.get('image') or o.get('image'), "product_image": it.get('image') or o.get('image'),
                "total": float(it.get('price',0))*int(it.get('qty',1)) if o.get('items') else o.get('total',0),
                "price": it.get('price', o.get('total',0)), "qty": it.get('qty',1), "quantity": it.get('qty',1),
                "status": o.get('status','PENDING'), "buyer_name": o.get('buyer_name'), "buyer_phone": o.get('buyer_phone'),
                "created_at": o.get('created_at'), "buyer_email": o.get('buyer_email'),
            })
    flat.sort(key=lambda x: x.get('created_at',''), reverse=True)
    products = [p for p in load_db('products.json', []) if (p.get('seller_email','').lower()==shop_email)]
    return jsonify({"success": True, "orders": flat, "stats": {"total_orders": len(my), "total_products": len(products), "total_earnings": sum(o.get('total',0) for o in my if str(o.get('status','')).upper()=='DELIVERED'), "total_views": sum(int(p.get('views',0) or 0) for p in products), "total_likes": sum(int(p.get('likes',0) or 0) for p in products)}})

@orders_bp.route('/api/shop-owner/update-order', methods=['POST'])
def shop_owner_update_order():
    data = request.get_json() or {}
    oid = str(data.get('id') or data.get('tracking_id') or '')
    status = (data.get('status') or '').upper()
    orders = get_orders()
    for o in orders:
        if str(o.get('tracking_id'))==oid or str(o.get('id'))==oid:
            o['status']=status; o['updated_at']=datetime.now().isoformat()
            save_orders(orders)
            return jsonify({"success": True})
    return jsonify({"success": False, "message": "Order not found"}), 404

@orders_bp.route('/api/orders/track/<tracking_id>')
def track_order(tracking_id):
    o = next((x for x in get_orders() if str(x.get('tracking_id'))==str(tracking_id)), None)
    if not o: return jsonify({"success": False}), 404
    return jsonify({"success": True, "order": o})

@orders_bp.route('/api/orders/seller/<tracking_id>/status', methods=['POST'])
def update_status(tracking_id):
    data = request.get_json() or {}
    orders = get_orders()
    for o in orders:
        if str(o.get('tracking_id'))==str(tracking_id):
            if data.get('status'): o['status']=data.get('status').upper()
            save_orders(orders)
            return jsonify({"success": True})
    return jsonify({"success": False}), 404

@orders_bp.route('/api/notifications/seller/count')
def notif_count():
    email = (request.args.get('email','') or request.args.get('shop_email','')).lower().strip()
    notifs = load_db('notifications.json', [])
    unread = len([n for n in notifs if n.get('recipient_email','').lower()==email and not n.get('is_read')])
    return jsonify({"unread": unread, "count": unread})

@orders_bp.route('/api/notifications/mark-read', methods=['POST'])
def mark_read():
    data = request.get_json() or {}
    email = data.get('email','').lower()
    notifs = load_db('notifications.json', [])
    for n in notifs:
        if n.get('recipient_email','').lower()==email: n['is_read']=True
    save_db('notifications.json', notifs)
    return jsonify({"success": True})

@orders_bp.route('/track/<tracking_id>')
def track_page(tracking_id):
    return render_template('track.html', tracking_id=tracking_id)

@orders_bp.route('/api/orders/seller')
@orders_bp.route('/api/seller/orders')
@orders_bp.route('/api/shop/orders')
def api_seller_orders():
    email = request.args.get('email','').lower().strip()
    shop_slug = request.args.get('shop_slug','').lower().strip()
    shop_name = request.args.get('shop_name','').lower().strip()
    orders = get_orders()
    mine = []
    for o in orders:
        o_seller = str(o.get('seller_email') or '').lower().strip()
        o_slug = str(o.get('shop_slug') or '').lower().strip()
        o_shop = str(o.get('shop_name') or o.get('business') or '').lower().strip()
        # Match ANY: email OR slug OR shop name - so Sann always sees it
        if email and o_seller == email:
            mine.append(o)
        elif shop_slug and o_slug == shop_slug:
            mine.append(o)
        elif shop_name and o_shop == shop_name:
            mine.append(o)
        elif not email and not shop_slug:
            mine.append(o)
    return jsonify({"orders": sorted(mine, key=lambda x: x.get('created_at',0), reverse=True), "count": len(mine)})
