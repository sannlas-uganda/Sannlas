from flask import Blueprint, request, jsonify
import random, time, os, json
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

def ensure_tables():
    if not DATABASE_URL: return
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, data JSONB NOT NULL);")
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, data JSONB NOT NULL);")
        conn.commit(); cur.close(); conn.close()
    except: pass

def load_db(file, default):
    try:
        if DATABASE_URL:
            ensure_tables(); conn = get_conn()
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
    except Exception as e:
        print("LOAD ERROR", e)
        return default

def save_db(file, data):
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
        except Exception as e: print("SAVE ERROR", e)
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

def get_carts(): return load_db('carts.json', [])
def save_carts(c): save_db('carts.json', c)

PRODUCT_CACHE = {"data": None, "time": 0}
SHOP_CACHE = {"data": None, "time": 0}
ORDERS_CACHE = {"data": None, "time": 0}

def clear_all_caches():
    PRODUCT_CACHE["data"]=None
    SHOP_CACHE["data"]=None
    ORDERS_CACHE["data"]=None

def get_orders_fresh(): return load_db('orders.json', [])
def get_orders():
    now=time.time()
    if ORDERS_CACHE["data"] is not None and (now-ORDERS_CACHE["time"]<15):
        return ORDERS_CACHE["data"]
    data=load_db('orders.json', [])
    ORDERS_CACHE["data"]=data; ORDERS_CACHE["time"]=now
    return data

def save_orders(data):
    ORDERS_CACHE["data"]=data; ORDERS_CACHE["time"]=time.time()
    save_db('orders.json', data)

def get_orders_v2_fresh(): return load_db('orders_v2.json', [])
def gen_tracking_id(): return f"SN-{random.randint(100000, 999999)}"
def get_cached_products_fresh(): return load_db('products.json', [])
def get_cached_shops_fresh(): return load_db('shops.json', [])

def get_product_owner(product_id):
    pid = str(product_id).lower().strip()
    if not pid: return "", ""
    try:
        products = get_cached_products_fresh()
        for p in products:
            if not isinstance(p, dict): continue
            p_id = str(p.get('id') or p.get('product_id') or '').lower()
            if p_id == pid or p_id in pid or pid in p_id:
                owner = p.get('seller_email') or p.get('shop_email') or p.get('owner_email') or p.get('email') or ''
                if owner: return owner.lower().strip(), p.get('business') or p.get('business_name') or p.get('shop_name') or 'Sannlas'
                if p.get('shop_slug'):
                    shops = get_cached_shops_fresh()
                    sh = next((s for s in shops if s.get('shop_slug')==p.get('shop_slug')), None)
                    if sh and sh.get('owner_email'): return sh['owner_email'].lower().strip(), sh.get('business_name','Sannlas')
                return "", p.get('business') or 'Sannlas'
    except Exception as e: print(f"OWNER LOOKUP ERROR {e}")
    return "", ""

def push_notification(seller_email, order, items):
    try:
        notifs = load_db('notifications.json', [])
        notif = {
            "id": f"NTF-{random.randint(100000,999999)}",
            "recipient_email": seller_email.lower().strip(),
            "type": "NEW_ORDER",
            "title": f"🔥 NEW ORDER! {order['tracking_id']}",
            "message": f"New: {items[0].get('name') or items[0].get('title')} - {order['buyer_name']} {order['buyer_phone']} UGX {order['total']}",
            "order_id": order['tracking_id'],
            "is_read": False,
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        notifs.append(notif)
        if len(notifs)>500: notifs=notifs[-500:]
        save_db('notifications.json', notifs)
    except Exception as e: print(e)

def get_user_coins_balance(email, phone):
    users = load_db('users.json', [])
    u = next((x for x in users if (email and str(x.get('email','')).lower()==email.lower()) or (phone and str(x.get('phone',''))==phone)), None)
    if not u: return 0, None
    bought = int(u.get('bought',0)); earned = int(u.get('earned',0)); spent = int(u.get('spent',0))
    total = bought + earned - spent
    if total<0: total=0
    return total, u

def deduct_coins_balance(email, phone, amount):
    users = load_db('users.json', [])
    for u in users:
        if (email and str(u.get('email','')).lower()==email.lower()) or (phone and str(u.get('phone',''))==phone):
            u['spent'] = int(u.get('spent',0)) + amount
            u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
            if u['coins']<0: u['coins']=0
            save_db('users.json', users)
            return True, u
    return False, None

# ================= MAIN CREATE - CLEAN =================
@orders_bp.route('/api/orders/create', methods=['POST'])
@orders_bp.route('/api/orders/place', methods=['POST'])
def create_orders():
    try:
        data = request.get_json() or {}
        email = (data.get('email') or data.get('buyer_email') or '').lower().strip()
        buyer_name = data.get('buyer_name','').strip() or data.get('buyer',{}).get('name','').strip()
        buyer_phone = data.get('buyer_phone','').strip() or data.get('buyer',{}).get('phone','').strip()
        district = data.get('district','').strip() or data.get('buyer',{}).get('district','')
        address = data.get('address','').strip()
        full_address = data.get('full_address') or f"{district}, {address}"
        
        # Get broker ref from ANYWHERE - NEW!
        broker_ref = (data.get('broker_agent_phone') or data.get('ref') or request.args.get('ref') or request.cookies.get('ref_code') or '').strip()
        
        if not buyer_name or not buyer_phone:
            # Try nested buyer
            buyer = data.get('buyer',{})
            buyer_name = buyer.get('name','')
            buyer_phone = buyer.get('phone','')
            email = buyer.get('email','').lower() or email
            
        if not buyer_name or not buyer_phone:
            return jsonify({"success": False, "message": "Name & Phone required"}), 400
        
        carts = get_carts()
        direct_items = data.get('items', [])
        user_carts = direct_items if direct_items else [c for c in carts if (c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone)]
        if not user_carts:
            return jsonify({"success": False, "message": "Cart empty"}), 400
        
        shops = defaultdict(list)
        for item in user_carts:
            product_id = str(item.get('product_id') or item.get('id') or '').strip()
            final_seller = (item.get('real_seller_email') or item.get('shop_email') or item.get('seller_email') or item.get('owner_email') or '').lower().strip()
            final_shop = item.get('real_shop_name') or item.get('shop_name') or item.get('business') or 'Sannlas'
            
            if not final_seller and product_id:
                owner_email, shop_name = get_product_owner(product_id)
                if owner_email:
                    final_seller = owner_email
                    final_shop = shop_name
            
            if not final_seller and item.get('shop_slug'):
                shops_db = get_cached_shops_fresh()
                sh = next((s for s in shops_db if s.get('shop_slug')==item.get('shop_slug')), None)
                if sh and sh.get('owner_email'):
                    final_seller = sh['owner_email'].lower().strip()
                    final_shop = sh.get('business_name','Sannlas')
            
            if not final_seller:
                final_seller = "admin@sannlas.com"
            
            item['real_seller_email'] = final_seller
            item['real_shop_name'] = final_shop
            shops[final_seller].append(item)

        orders = get_orders_fresh()
        created=[]
        for shop_key, items in shops.items():
            tid = gen_tracking_id()
            while any(o.get('tracking_id')==tid for o in orders): tid = gen_tracking_id()
            total = sum([float(i.get('price',0))*int(i.get('qty',1) or 1) for i in items])
            order = {
                "order_id": tid, "tracking_id": tid,
                "buyer_email": email, "buyer_name": buyer_name,
                "buyer_phone": buyer_phone, "district": district,
                "address": address, "full_address": full_address,
                "shop_key": shop_key, "shop_name": items[0].get('real_shop_name','Sannlas'),
                "shop_email": shop_key, "seller_email": shop_key, "shop_owner_email": shop_key,
                "items": items, "total": total, "status": "PENDING",
                "delivery_man_name": "", "delivery_man_phone": "",
                "broker_agent_phone": broker_ref,
                "created_at": datetime.now().isoformat(), "timestamp": int(time.time())
            }
            orders.append(order); created.append(order)
            push_notification(shop_key, order, items)
        
        save_orders(orders)
        clear_all_caches()
        
        # ===== COMMISSION 94% / 4% / 2% =====
        try:
            from sannlas_commission import split_and_record
            for ord in created:
                total = ord.get('total',0)
                broker_phone = ord.get('broker_agent_phone','').strip()
                shop_slug = ord.get('shop_email','')
                if broker_phone and 'SANN-AGENT' in broker_phone:
                    agents_db = load_db('sannlas_agents.json',[])
                    ag = next((a for a in agents_db if a['agent_code']==broker_phone), None)
                    if ag: broker_phone = ag['phone']
                if broker_phone:
                    split_and_record("broker_sale", total, broker_phone, shop_slug, meta={"order_id":ord['tracking_id']})
                else:
                    split_and_record("broker_sale", total, None, shop_slug, meta={"order_id":ord['tracking_id']})
        except Exception as e:
            print("Commission error:", e)
        
        if not direct_items:
            try:
                remaining = [c for c in carts if not ((c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone))]
                save_carts(remaining)
            except: pass
        
        return jsonify({"success": True, "orders": created, "tracking_ids": [o['tracking_id'] for o in created]})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ================= SELLER ROUTES =================
@orders_bp.route('/api/orders/seller', methods=['GET'])
def seller_orders():
    shop_email = (request.args.get('shop_email','').lower() or request.args.get('email','').lower() or request.args.get('shop','').lower()).strip()
    orders = get_orders_fresh() + get_orders_v2_fresh()
    for o in orders:
        if 'tracking_id' not in o or not o['tracking_id']:
            o['tracking_id'] = str(o.get('id') or o.get('order_id') or f"ORD{random.randint(100000,999999)}")
        if 'status' not in o: o['status'] = 'PENDING'
    if not shop_email:
        orders.sort(key=lambda x: x.get('timestamp',0) or 0, reverse=True)
        return jsonify({"orders": orders[:50], "count": len(orders), "success": True})
    filtered=[]
    for o in orders:
        fields_to_check = [
            (o.get('seller_email','') or '').lower(),
            (o.get('shop_email','') or '').lower(),
            (o.get('shop_owner_email','') or '').lower(),
            (o.get('shop_key','') or '').lower(),
        ]
        matched = any(shop_email == f for f in fields_to_check if f)
        if matched:
            filtered.append(o); continue
        for it in o.get('items',[]):
            real = (it.get('real_seller_email','') or it.get('seller_email','') or it.get('shop_email','') or '').lower()
            if shop_email == real:
                filtered.append(o); break
    filtered.sort(key=lambda x: x.get('timestamp',0) or 0, reverse=True)
    return jsonify({"orders": filtered[:50], "count": len(filtered), "success": True})

@orders_bp.route('/api/orders/seller/count', methods=['GET'])
def seller_count():
    shop_email = (request.args.get('shop_email','').lower() or request.args.get('email','').lower()).strip()
    if not shop_email: return jsonify({"count": 0})
    orders = get_orders_fresh()
    count = sum(1 for o in orders if o.get('status','').upper()=='PENDING' and shop_email in [
        (o.get('seller_email','') or '').lower(),
        (o.get('shop_email','') or '').lower(),
    ])
    return jsonify({"count": count, "new_orders": count})

@orders_bp.route('/api/orders/my-sales')
def my_sales_orders():
    email=request.args.get('email','').lower().strip()
    phone=request.args.get('phone','').strip()
    orders = get_orders_fresh() + get_orders_v2_fresh()
    my = [o for o in orders if (email and str(o.get('seller_email','')).lower()==email) or (phone and str(o.get('seller_phone',''))==phone)]
    my.sort(key=lambda x: x.get('timestamp',0) or x.get('created_at',0), reverse=True)
    return jsonify(sorted(my, key=lambda x: x.get('created_at',0), reverse=True))

# ================= UNLOCK - 2 COINS =================
@orders_bp.route('/api/orders/unlock', methods=['POST'])
def unlock_order_view():
    data=request.json or {}
    order_id = data.get('order_id','').strip()
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    if not order_id: return jsonify({"success":False,"message":"Order ID required"}),400
    
    orders = get_orders_fresh()
    order = next((o for o in orders if str(o.get('tracking_id'))==str(order_id) or str(o.get('order_id'))==str(order_id)), None)
    v2_list = get_orders_v2_fresh()
    if not order:
        order = next((o for o in v2_list if str(o.get('id'))==str(order_id) or str(o.get('tracking_id'))==str(order_id)), None)
    
    if not order: return jsonify({"success":False,"message":"Order not found"}),404
    if order.get('paid_to_view'): return jsonify({"success":True,"order":order,"message":"Already unlocked"})

    bal, user = get_user_coins_balance(email, phone)
    if bal < 2:
        return jsonify({"success":False,"message":f"Need 2 coins! You have {bal}","need":2,"have":bal}),402

    ok, _ = deduct_coins_balance(email, phone, 2)
    if not ok: return jsonify({"success":False,"message":"Deduct failed"}),500

    for o in orders:
        if str(o.get('tracking_id'))==str(order_id) or str(o.get('order_id'))==str(order_id):
            o['paid_to_view'] = True; o['unlocked_at'] = time.time(); order = o; break
    save_orders(orders)
    
    # Also update v2 if needed
    for o in v2_list:
        if str(o.get('id'))==str(order_id):
            o['paid_to_view']=True; save_db('orders_v2.json', v2_list); break

    txs = load_db('coin_transactions.json', [])
    txs.append({"id": int(time.time()*1000), "email": email, "phone": phone, "coins": -2, "price": 0, "momo_code": f"ORDER-VIEW-{order_id[:8]}", "reason": f"Unlock buyer {order.get('buyer_phone')} for {order_id}", "time": time.time(), "status": "order_unlock"})
    save_db('coin_transactions.json', txs)

    return jsonify({"success":True,"order":order,"message":f"Unlocked! Buyer: {order.get('buyer_name')} {order.get('buyer_phone')}"})

@orders_bp.route('/api/notifications/seller/count', methods=['GET'])
def notif_count():
    email = (request.args.get('email','').lower() or request.args.get('shop_email','').lower()).strip()
    if not email: return jsonify({"unread": 0})
    notifs = load_db('notifications.json', [])
    unread = len([n for n in notifs if n.get('recipient_email','').lower()==email and not n.get('is_read')])
    return jsonify({"unread": unread, "count": unread})

@orders_bp.route('/api/notifications/mark-read', methods=['POST'])
def mark_read():
    data=request.get_json() or {}
    email=data.get('email','').lower()
    notifs=load_db('notifications.json', [])
    for n in notifs:
        if email and n.get('recipient_email','').lower()==email:
            n['is_read']=True
    save_db('notifications.json', notifs)
    return jsonify({"success": True})

@orders_bp.route('/api/orders/my', methods=['GET'])
def my_orders_route():
    email=request.args.get('email','').lower()
    orders=get_orders_fresh()
    my=[o for o in orders if o.get('buyer_email','').lower()==email]
    my.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": my[:30]})

@orders_bp.route('/api/orders/track/<tracking_id>', methods=['GET'])
def track_order(tracking_id):
    orders=get_orders_fresh()+get_orders_v2_fresh()
    order=next((o for o in orders if str(o.get('tracking_id'))==str(tracking_id) or str(o.get('id'))==str(tracking_id)), None)
    if not order: return jsonify({"success": False}), 404
    return jsonify({"success": True, "order": order})

@orders_bp.route('/api/orders/seller/<tracking_id>/status', methods=['POST'])
def update_status(tracking_id):
    data=request.get_json() or {}
    orders=get_orders_fresh()
    for o in orders:
        if str(o.get('tracking_id'))==str(tracking_id) or str(o.get('id'))==str(tracking_id):
            if data.get('status'): o['status']=data.get('status').upper()
            if data.get('delivery_man_name'): o['delivery_man_name']=data.get('delivery_man_name')
            if data.get('delivery_man_phone'): o['delivery_man_phone']=data.get('delivery_man_phone')
            o['updated_at']=datetime.now().isoformat()
            save_orders(orders)
            clear_all_caches()
            return jsonify({"success": True})
    v2=get_orders_v2_fresh()
    for o in v2:
        if str(o.get('id'))==str(tracking_id) or str(o.get('tracking_id'))==str(tracking_id):
            if data.get('status'): o['status']=data.get('status').upper()
            if data.get('delivery_man_name'): o['delivery_man_name']=data.get('delivery_man_name')
            if data.get('delivery_man_phone'): o['delivery_man_phone']=data.get('delivery_man_phone')
            save_db('orders_v2.json', v2)
            clear_all_caches()
            return jsonify({"success": True})
    return jsonify({"success": False}), 404

@orders_bp.route('/api/orders/fix-all')
def fix_all():
    orders=get_orders_fresh()
    products=get_cached_products_fresh()
    shops=get_cached_shops_fresh()
    fixed=0
    for o in orders:
        if not o.get('seller_email') or o.get('seller_email')=='admin@sannlas.com':
            for it in o.get('items',[]):
                pid=str(it.get('product_id') or it.get('id') or '')
                prod=next((p for p in products if str(p.get('id'))==pid), None)
                if prod:
                    em=prod.get('seller_email') or prod.get('shop_email') or ''
                    if em and em!='admin@sannlas.com':
                        o['seller_email']=em.lower(); o['shop_email']=em.lower(); fixed+=1; break
    if fixed>0: save_orders(orders); clear_all_caches()
    return jsonify({"fixed": fixed, "total": len(orders)})

@orders_bp.route('/api/orders/clear-cache')
def clear_cache_route():
    clear_all_caches()
    return jsonify({"success": True, "message": "Cache cleared!"})
