from flask import Blueprint, request, jsonify, render_template_string
import random, time, os, json
from datetime import datetime
from collections import defaultdict

orders_bp = Blueprint('orders_bp', __name__)

# ===== STANDALONE NEON DB (no import from sannlas_cart) =====
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
    except Exception as e: print(e)

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
    except: return default

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

# ===== CACHE =====
PRODUCT_CACHE = {"data": None, "time": 0}
SHOP_CACHE = {"data": None, "time": 0}
ORDERS_CACHE = {"data": None, "time": 0}
ORDERS_V2_CACHE = {"data": None, "time": 0}
NOTIF_CACHE = {"data": None, "time": 0}

def get_orders():
    now = time.time()
    if ORDERS_CACHE["data"] is not None and (now - ORDERS_CACHE["time"] < 60):
        return ORDERS_CACHE["data"]
    data = load_db('orders.json', [])
    ORDERS_CACHE["data"] = data; ORDERS_CACHE["time"] = now
    return data

def save_orders(data):
    ORDERS_CACHE["data"] = data; ORDERS_CACHE["time"] = time.time()
    save_db('orders.json', data)

def get_orders_v2():
    now = time.time()
    if ORDERS_V2_CACHE["data"] is not None and (now - ORDERS_V2_CACHE["time"] < 60):
        return ORDERS_V2_CACHE["data"]
    data = load_db('orders_v2.json', [])
    ORDERS_V2_CACHE["data"] = data; ORDERS_V2_CACHE["time"] = now
    return data

def get_notifications():
    now = time.time()
    if NOTIF_CACHE["data"] is not None and (now - NOTIF_CACHE["time"] < 30):
        return NOTIF_CACHE["data"]
    data = load_db('notifications.json', [])
    NOTIF_CACHE["data"] = data; NOTIF_CACHE["time"] = now
    return data

def save_notifications(data):
    NOTIF_CACHE["data"] = data; NOTIF_CACHE["time"] = time.time()
    save_db('notifications.json', data)

def push_seller_notification(seller_email, order, items):
    try:
        notifications = get_notifications()
        notif = {
            "id": f"NTF-{random.randint(100000,999999)}",
            "recipient_email": seller_email.lower().strip(),
            "type": "NEW_ORDER",
            "title": f"🔥 NEW ORDER! {order['tracking_id']}",
            "message": f"You have new order: {items[0].get('title') or items[0].get('name') or 'Product'} x{len(items)} - Buyer: {order['buyer_name']} ({order['buyer_phone']}) - UGX {order['total']}",
            "order_id": order['tracking_id'],
            "order_data": {
                "tracking_id": order['tracking_id'],
                "buyer_name": order['buyer_name'],
                "buyer_phone": order['buyer_phone'],
                "total": order['total'],
                "items_count": len(items),
                "address": order['full_address']
            },
            "is_read": False,
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        notifications.append(notif)
        if len(notifications) > 500: notifications = notifications[-500:]
        save_notifications(notifications)
        print(f"✅ SELLER NOTIFIED: {seller_email} - {order['tracking_id']}")
        return True
    except Exception as e:
        print(f"❌ Notification error: {e}")
        return False

def gen_tracking_id(): return f"SN-{random.randint(100000, 999999)}"

def get_cached_products():
    now = time.time()
    if PRODUCT_CACHE["data"] and (now - PRODUCT_CACHE["time"] < 300):
        return PRODUCT_CACHE["data"]
    data = load_db('products.json', [])
    PRODUCT_CACHE["data"] = data; PRODUCT_CACHE["time"] = now
    return data

def get_cached_shops():
    now = time.time()
    if SHOP_CACHE["data"] and (now - SHOP_CACHE["time"] < 300):
        return SHOP_CACHE["data"]
    data = load_db('shops.json', [])
    SHOP_CACHE["data"] = data; SHOP_CACHE["time"] = now
    return data

def get_product_owner(product_id):
    pid = str(product_id).lower().strip()
    if not pid: return "", ""
    try:
        products = get_cached_products()
        for p in products:
            p_id = str(p.get('id') or '').lower()
            if p_id == pid:
                owner = p.get('seller_email') or p.get('shop_email') or p.get('owner_email') or ''
                if owner: return owner.lower().strip(), p.get('business') or 'Sannlas Shop'
                if p.get('shop_slug'):
                    shops = get_cached_shops()
                    sh = next((s for s in shops if s.get('shop_slug') == p.get('shop_slug')), None)
                    if sh and sh.get('owner_email'): return sh['owner_email'].lower().strip(), sh.get('business_name','Sannlas')
                return "", p.get('business') or 'Sannlas Shop'
    except: pass
    return "", ""

@orders_bp.route('/api/orders/create', methods=['POST'])
@orders_bp.route('/api/orders/place', methods=['POST'])
def create_orders():
    try:
        data = request.get_json() or {}
        email = (data.get('email') or data.get('buyer_email') or '').lower().strip()
        buyer_name = data.get('buyer_name','').strip()
        buyer_phone = data.get('buyer_phone','').strip()
        district = data.get('district','').strip()
        address = data.get('address','').strip()
        full_address = data.get('full_address') or f"{district}, {address}"
        if not email or not buyer_name or not buyer_phone:
            return jsonify({"success": False, "message": "Name & Phone required"}), 400
        try: carts = get_carts()
        except: carts = []
        direct_items = data.get('items', [])
        if direct_items: user_carts = direct_items
        else: user_carts = [c for c in carts if (c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone)]
        if not user_carts: return jsonify({"success": False, "message": "Cart empty"}), 400
        shops = defaultdict(list)
        for item in user_carts:
            product_id = item.get('product_id') or item.get('id')
            final_seller = (item.get('shop_email') or item.get('seller_email') or item.get('real_seller_email') or '').lower().strip()
            final_shop = item.get('shop_name') or item.get('real_shop_name') or 'Sannlas'
            if not final_seller:
                owner_email, shop_from_product = get_product_owner(product_id) if product_id else ("","")
                final_seller = owner_email or final_seller
                final_shop = shop_from_product or final_shop
            if not final_seller: final_seller = "admin@sannlas.com"
            item['real_seller_email'] = final_seller
            item['real_shop_name'] = final_shop
            shops[final_seller].append(item)
        orders = get_orders()
        created = []
        for shop_key, items in shops.items():
            tid = gen_tracking_id()
            while any(o.get('tracking_id')==tid for o in orders): tid = gen_tracking_id()
            total = sum([float(i.get('price',0)) * int(i.get('qty',1) or 1) for i in items])
            order = {
                "order_id": tid, "tracking_id": tid,
                "buyer_email": email, "buyer_name": buyer_name,
                "buyer_phone": buyer_phone, "district": district,
                "address": address, "full_address": full_address,
                "shop_key": shop_key, "shop_name": items[0].get('real_shop_name','Sannlas'),
                "shop_email": items[0].get('real_seller_email',''), "seller_email": items[0].get('real_seller_email',''),
                "shop_owner_email": items[0].get('real_seller_email',''),
                "items": items, "total": total, "status": "PENDING",
                "delivery_man_name": "", "delivery_man_phone": "",
                "created_at": datetime.now().isoformat(), "timestamp": int(time.time())
            }
            orders.append(order); created.append(order)
            push_seller_notification(shop_key, order, items)
        save_orders(orders)
        if not direct_items:
            try:
                remaining = [c for c in carts if not ((c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone))]
                save_carts(remaining)
            except: pass
        return jsonify({"success": True, "orders": created, "tracking_ids": [o['tracking_id'] for o in created]})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@orders_bp.route('/api/notifications/seller', methods=['GET'])
def seller_notifications():
    email = request.args.get('email','').lower().strip() or request.args.get('shop_email','').lower().strip()
    if not email: return jsonify({"notifications": [], "count": 0})
    notifs = get_notifications()
    my_notifs = [n for n in notifs if n.get('recipient_email','').lower() == email]
    my_notifs.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    unread = len([n for n in my_notifs if not n.get('is_read')])
    return jsonify({"notifications": my_notifs[:50], "count": len(my_notifs), "unread": unread, "success": True})

@orders_bp.route('/api/notifications/mark-read', methods=['POST'])
def mark_read():
    data = request.get_json() or {}
    notif_id = data.get('id')
    email = data.get('email','').lower().strip()
    notifs = get_notifications()
    for n in notifs:
        if notif_id and n.get('id') == notif_id: n['is_read'] = True
        elif email and n.get('recipient_email','').lower() == email and not notif_id: n['is_read'] = True
    save_notifications(notifs)
    return jsonify({"success": True})

@orders_bp.route('/api/notifications/seller/count', methods=['GET'])
def seller_notif_count():
    email = request.args.get('email','').lower().strip() or request.args.get('shop_email','').lower().strip()
    if not email: return jsonify({"count": 0, "unread": 0})
    notifs = get_notifications()
    unread = len([n for n in notifs if n.get('recipient_email','').lower() == email and not n.get('is_read')])
    return jsonify({"count": unread, "unread": unread})

@orders_bp.route('/api/orders/my', methods=['GET'])
def my_orders():
    email = request.args.get('email','').lower()
    if not email: return jsonify({"orders": []})
    orders = get_orders()
    my = [o for o in orders if o.get('buyer_email','').lower()==email]
    my.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": my[:20]})

@orders_bp.route('/api/orders/track/<tracking_id>', methods=['GET'])
def track_order(tracking_id):
    orders = get_orders()
    order = next((o for o in orders if o.get('tracking_id')==tracking_id), None)
    if not order:
        try:
            v2 = get_orders_v2()
            order = next((o for o in v2 if str(o.get('id'))==tracking_id or str(o.get('tracking_id'))==tracking_id), None)
        except: pass
    if not order: return jsonify({"success": False}), 404
    return jsonify({"success": True, "order": order})

@orders_bp.route('/api/orders/seller', methods=['GET'])
def seller_orders():
    shop_email = (request.args.get('shop_email','').lower() or request.args.get('email','').lower() or request.args.get('shop','').lower()).strip()
    orders = get_orders()
    if shop_email:
        try:
            v2_orders = get_orders_v2()
            for o in v2_orders:
                if 'tracking_id' not in o: o['tracking_id'] = str(o.get('id'))
            orders = orders + v2_orders
        except: pass
    if not shop_email: return jsonify({"orders": orders[::-1][:50], "count": len(orders)})
    filtered = []
    for o in orders:
        o_seller = (o.get('seller_email','') or o.get('shop_email','') or '').lower()
        if shop_email == o_seller:
            filtered.append(o); continue
        for it in o.get('items',[]):
            if shop_email == (it.get('real_seller_email','') or '').lower():
                filtered.append(o); break
    filtered.sort(key=lambda x: x.get('timestamp',0) or 0, reverse=True)
    return jsonify({"orders": filtered[:30], "count": len(filtered), "success": True})

@orders_bp.route('/api/orders/seller/count', methods=['GET'])
def seller_count():
    shop_email = (request.args.get('shop_email','').lower() or request.args.get('email','').lower()).strip()
    if not shop_email: return jsonify({"count": 0, "new_orders": 0})
    orders = get_orders()
    count = sum(1 for o in orders if o.get('status','').upper()=='PENDING' and (o.get('seller_email','') or '').lower()==shop_email)
    return jsonify({"count": count, "new_orders": count})

@orders_bp.route('/api/orders/seller/<tracking_id>/status', methods=['POST'])
def update_status(tracking_id):
    data = request.get_json() or {}
    orders = get_orders()
    for o in orders:
        if o.get('tracking_id')==tracking_id or str(o.get('id'))==str(tracking_id):
            if data.get('status'): o['status']=data.get('status').upper()
            if data.get('delivery_man_name'): o['delivery_man_name']=data.get('delivery_man_name')
            if data.get('delivery_man_phone'): o['delivery_man_phone']=data.get('delivery_man_phone')
            o['updated_at'] = datetime.now().isoformat()
            save_orders(orders)
            return jsonify({"success": True, "order": o})
    try:
        v2 = get_orders_v2()
        for o in v2:
            if str(o.get('id'))==str(tracking_id) or str(o.get('tracking_id'))==str(tracking_id):
                if data.get('status'): o['status']=data.get('status').upper()
                if data.get('delivery_man_name'): o['delivery_man_name']=data.get('delivery_man_name')
                if data.get('delivery_man_phone'): o['delivery_man_phone']=data.get('delivery_man_phone')
                save_db('orders_v2.json', v2)
                return jsonify({"success": True, "order": o})
    except: pass
    return jsonify({"success": False}), 404

@orders_bp.route('/api/orders/fix-all')
def fix_all_orders():
    orders = get_orders()
    products = get_cached_products()
    shops = get_cached_shops()
    fixed = 0
    for o in orders:
        if not o.get('seller_email') and not o.get('shop_email'):
            for it in o.get('items',[]):
                pid = it.get('product_id') or it.get('id') or it.get('real_product_id')
                if pid:
                    prod = next((p for p in products if str(p.get('id'))==str(pid)), None)
                    if prod:
                        email = prod.get('seller_email') or prod.get('shop_email') or prod.get('owner_email')
                        if email:
                            o['seller_email'] = email.lower(); o['shop_email'] = email.lower(); fixed+=1; break
                        if prod.get('shop_slug'):
                            sh = next((s for s in shops if s.get('shop_slug')==prod.get('shop_slug')), None)
                            if sh and sh.get('owner_email'):
                                o['seller_email'] = sh['owner_email'].lower(); o['shop_email'] = sh['owner_email'].lower(); fixed+=1; break
    if fixed>0: save_orders(orders)
    return jsonify({'success': True, 'fixed_orders': fixed, 'total': len(orders)})

@orders_bp.route('/api/orders/delivery')
def delivery_orders():
    phone = request.args.get('phone','').strip()
    if not phone: return jsonify({"orders": []})
    orders = get_orders()
    filtered = [o for o in orders if phone[-9:] in o.get('delivery_man_phone','').replace(' ','').replace('+','')[-9:]]
    filtered.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": filtered[:30]})

@orders_bp.route('/track/<tracking_id>')
def track_page(tracking_id):
    return render_template_string(TRACK_HTML, tracking_id=tracking_id)

@orders_bp.route('/my-orders')
def my_orders_page():
    return render_template_string(MY_ORDERS_HTML)
        
@orders_bp.route('/delivery')
def delivery_dashboard():
    return render_template_string(DELIVERY_HTML)

TRACK_HTML = """<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>Track {{tracking_id}}</title><style>body{font-family:Arial;background:#FFF7ED;margin:0;padding:15px}.card{background:white;border-radius:20px;padding:18px;max-width:500px;margin:0 auto}.step{display:flex;gap:12px;padding:12px 0;border-left:3px solid #eee;margin-left:12px;padding-left:20px;position:relative}.step.done{border-left-color:#00AA00}.step.active{border-left-color:#FF6A00}.dot{width:28px;height:28px;border-radius:50%;background:#eee;display:flex;align-items:center;justify-content:center;position:absolute;left:-15px;top:10px}.dot.done{background:#00AA00;color:white}.dot.active{background:#FF6A00;color:white}.badge{padding:6px 14px;border-radius:20px;font-weight:900;color:white}</style></head><body><div class="card"><h2>📦 Tracking <span style="color:#FF6A00">{{tracking_id}}</span></h2><div id="info">Loading...</div><div id="timeline" style="margin-top:20px"></div><div id="rider" style="margin-top:16px;display:none;background:#FFF7ED;padding:12px;border-radius:12px"></div></div><script>let TID="{{tracking_id}}";async function loadTrack(){let r=await fetch('/api/orders/track/'+TID);let res=await r.json();if(!res.success){document.getElementById('info').innerHTML='Not found';return;}let o=res.order;document.getElementById('info').innerHTML=`<span class="badge" style="background:#F59E0B">${o.status}</span><br><br>Buyer: ${o.buyer_name}<br>Shop: ${o.shop_name}<br>Address: ${o.full_address}<br>Total: UGX ${Number(o.total).toLocaleString()}`;let steps=['PENDING','CONFIRMED','PACKED','SHIPPED','DELIVERED'];let cur=steps.indexOf(o.status);let html='';steps.forEach((s,i)=>{let done=i<=cur;html+=`<div class="step ${done?'done':''} ${i==cur?'active':''}"><div class="dot ${done?'done':''} ${i==cur?'active':''}">${done?'✓':i+1}</div><b>${s}</b></div>`;});document.getElementById('timeline').innerHTML=html;if(o.delivery_man_name){document.getElementById('rider').style.display='block';document.getElementById('rider').innerHTML=`Rider: ${o.delivery_man_name} - ${o.delivery_man_phone}`;}}loadTrack();setInterval(loadTrack,15000);</script></body></html>"""
MY_ORDERS_HTML = """<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>My Orders</title><style>body{font-family:Arial;background:#f5f5f5;margin:0;padding:12px}.order{background:white;border-radius:16px;padding:14px;margin-bottom:12px}.badge{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:800;color:white}.PENDING{background:#F59E0B}.CONFIRMED{background:#3B82F6}.PACKED{background:#8B5CF6}.SHIPPED{background:#FF6A00}.DELIVERED{background:#10B981}.btn{padding:12px;border-radius:12px;border:none;background:#000;color:#FFCC02;font-weight:900;width:100%;margin-top:10px}</style></head><body><h2>📦 My Orders</h2><div id="list">Loading...</div><script>async function load(){let raw=localStorage.getItem('sannlas_user')||'{}';let user=JSON.parse(raw);let email=(user.email||'').toLowerCase().trim();if(!email){document.getElementById('list').innerHTML='Login first!';return;}let r=await fetch('/api/orders/my?email='+encodeURIComponent(email));let res=await r.json();let html=res.orders&&res.orders.length?res.orders.map(o=>`<div class="order"><b style="color:#FF6A00">${o.tracking_id}</b> <span class="badge ${o.status}">${o.status}</span><br>Shop: ${o.shop_name}<br>Total: UGX ${Number(o.total).toLocaleString()}<br><button onclick="location.href='/track/${o.tracking_id}'" class="btn">Track</button></div>`).join(''):'No orders yet';document.getElementById('list').innerHTML=html;}load();</script></body></html>"""
DELIVERY_HTML = """<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>Delivery</title><style>body{font-family:Arial;background:#f0fdf4;margin:0;padding:12px}.card{background:white;border-radius:16px;padding:14px;margin-bottom:12px}input{width:100%;padding:14px;border-radius:12px;border:2px solid #ddd;margin:6px 0}.btn{padding:12px;border:none;border-radius:12px;font-weight:900;width:100%;margin-top:8px}</style></head><body><h2>🛵 Delivery</h2><div class="card"><input id="riderPhone" placeholder="Rider phone"><button onclick="loadDelivery()" style="background:#000;color:#FFCC02" class="btn">My Orders</button></div><div id="list"></div><script>async function loadDelivery(){let phone=document.getElementById('riderPhone').value.trim();if(!phone){alert('Enter phone');return;}let r=await fetch('/api/orders/delivery?phone='+encodeURIComponent(phone));let res=await r.json();let html=res.orders.length?res.orders.map(o=>`<div class="card"><b>${o.tracking_id}</b> - ${o.status}<br>Buyer: ${o.buyer_name}<br><button onclick="updateStatus('${o.tracking_id}','DELIVERED')" style="background:#D1FAE5;padding:8px;border-radius:10px">Delivered</button></div>`).join(''):'No orders';document.getElementById('list').innerHTML=html;}async function updateStatus(id,status){await fetch('/api/orders/seller/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:status})});loadDelivery();}</script></body></html>"""
