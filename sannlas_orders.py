from flask import Blueprint, request, jsonify, render_template_string
from sannlas_cart import load_db, save_db, get_carts, save_carts
import random, time, os, json
from datetime import datetime

orders_bp = Blueprint('orders_bp', __name__)

# ===== SUPER FAST CACHE SYSTEM =====
PRODUCT_CACHE = {"data": None, "time": 0}
SHOP_CACHE = {"data": None, "time": 0}
ORDERS_CACHE = {"data": None, "time": 0}
ORDERS_V2_CACHE = {"data": None, "time": 0}
NOTIF_CACHE = {"data": None, "time": 0}  # NEW

def get_orders():
    now = time.time()
    if ORDERS_CACHE["data"] is not None and (now - ORDERS_CACHE["time"] < 60):
        return ORDERS_CACHE["data"]
    data = load_db('orders.json', [])
    ORDERS_CACHE["data"] = data
    ORDERS_CACHE["time"] = now
    return data

def save_orders(data):
    ORDERS_CACHE["data"] = data
    ORDERS_CACHE["time"] = time.time()
    save_db('orders.json', data)

def get_orders_v2():
    now = time.time()
    if ORDERS_V2_CACHE["data"] is not None and (now - ORDERS_V2_CACHE["time"] < 60):
        return ORDERS_V2_CACHE["data"]
    try:
        data = load_db('orders_v2.json', [])
    except:
        data = []
    ORDERS_V2_CACHE["data"] = data
    ORDERS_V2_CACHE["time"] = now
    return data

# ===== NEW: NOTIFICATION SYSTEM =====
def get_notifications():
    now = time.time()
    if NOTIF_CACHE["data"] is not None and (now - NOTIF_CACHE["time"] < 30):
        return NOTIF_CACHE["data"]
    data = load_db('notifications.json', [])
    NOTIF_CACHE["data"] = data
    NOTIF_CACHE["time"] = now
    return data

def save_notifications(data):
    NOTIF_CACHE["data"] = data
    NOTIF_CACHE["time"] = time.time()
    save_db('notifications.json', data)

def push_seller_notification(seller_email, order, items):
    """This is what was missing - SELLER GETS MESSAGE NOW!"""
    try:
        notifications = get_notifications()
        total_items = len(items)
        first_product = items[0].get('title') or items[0].get('name') or 'Product'
        
        notif = {
            "id": f"NTF-{random.randint(100000,999999)}",
            "recipient_email": seller_email.lower().strip(),
            "type": "NEW_ORDER",
            "title": f"🔥 NEW ORDER! {order['tracking_id']}",
            "message": f"You have new order: {first_product} x{total_items} - Buyer: {order['buyer_name']} ({order['buyer_phone']}) - Total: UGX {order['total']} - Address: {order['full_address']}",
            "order_id": order['tracking_id'],
            "order_data": {
                "tracking_id": order['tracking_id'],
                "buyer_name": order['buyer_name'],
                "buyer_phone": order['buyer_phone'],
                "total": order['total'],
                "items_count": total_items,
                "address": order['full_address']
            },
            "is_read": False,
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        notifications.append(notif)
        save_notifications(notifications)
        
        # Keep only last 500 notifications to stay fast
        if len(notifications) > 500:
            notifications = notifications[-500:]
            save_notifications(notifications)
            
        print(f"✅ SELLER NOTIFIED: {seller_email} - Order {order['tracking_id']}")
        return True
    except Exception as e:
        print(f"❌ Notification error: {e}")
        import traceback
        traceback.print_exc()
        return False

def gen_tracking_id():
    return f"SN-{random.randint(100000, 999999)}"

def get_cached_products():
    now = time.time()
    if PRODUCT_CACHE["data"] and (now - PRODUCT_CACHE["time"] < 300):
        return PRODUCT_CACHE["data"]
    data = load_db('products.json', [])
    PRODUCT_CACHE["data"] = data
    PRODUCT_CACHE["time"] = now
    return data

def get_cached_shops():
    now = time.time()
    if SHOP_CACHE["data"] and (now - SHOP_CACHE["time"] < 300):
        return SHOP_CACHE["data"]
    data = load_db('shops.json', [])
    SHOP_CACHE["data"] = data
    SHOP_CACHE["time"] = now
    return data

def get_product_owner(product_id):
    pid = str(product_id).lower().strip()
    if not pid:
        return "", ""
    try:
        products = get_cached_products()
        for p in products:
            if not isinstance(p, dict): continue
            p_id = str(p.get('id') or p.get('product_id') or '').lower()
            if p_id == pid:
                owner = p.get('seller_email') or p.get('shop_email') or p.get('owner_email') or p.get('email') or p.get('user_email') or ''
                if owner:
                    return owner.lower().strip(), p.get('business') or p.get('shop_name') or p.get('business_name') or 'Sannlas Shop'
                if p.get('shop_slug'):
                    shops = get_cached_shops()
                    sh = next((s for s in shops if s.get('shop_slug') == p.get('shop_slug')), None)
                    if sh and sh.get('owner_email'):
                        return sh['owner_email'].lower().strip(), sh.get('business_name','Sannlas')
                return "", p.get('business') or p.get('shop_name') or 'Sannlas Shop'
    except Exception as e:
        print(f"Cache lookup error: {e}")
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
        
        try:
            carts = get_carts()
        except:
            carts = []
            
        direct_items = data.get('items', [])
        
        if direct_items:
            user_carts = direct_items
        else:
            user_carts = [c for c in carts if (c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone)]
        
        if not user_carts:
            return jsonify({"success": False, "message": "Cart empty"}), 400
            
        from collections import defaultdict
        shops = defaultdict(list)
        
        for item in user_carts:
            try:
                product_id = item.get('product_id') or item.get('id') or item.get('_id') or item.get('productId')
                final_seller = (item.get('shop_email') or item.get('seller_email') or item.get('real_seller_email') or item.get('shop_owner_email') or '').lower().strip()
                final_shop = item.get('shop_name') or item.get('real_shop_name') or 'Sannlas'
                
                if not final_seller:
                    owner_email, shop_from_product = get_product_owner(product_id) if product_id else ("","")
                    final_seller = owner_email or final_seller
                    final_shop = shop_from_product or final_shop
                
                if not final_seller:
                    final_seller = "admin@sannlas.com"
                
                item['real_seller_email'] = final_seller
                item['real_shop_name'] = final_shop
                item['real_product_id'] = product_id
                shops[final_seller].append(item)
            except Exception as e:
                item['real_seller_email'] = "admin@sannlas.com"
                item['real_shop_name'] = "Sannlas"
                shops["admin@sannlas.com"].append(item)

        orders = get_orders()
        created = []
        for shop_key, items in shops.items():
            tid = gen_tracking_id()
            while any(o.get('tracking_id')==tid for o in orders):
                tid = gen_tracking_id()
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
            orders.append(order)
            created.append(order)

            # ===== FIX: NOTIFY SELLER INSTANTLY =====
            push_seller_notification(shop_key, order, items)
            
        save_orders(orders)
        
        if not direct_items:
            try:
                remaining = [c for c in carts if not ((c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone))]
                save_carts(remaining)
            except:
                pass
                
        return jsonify({"success": True, "orders": created, "tracking_ids": [o['tracking_id'] for o in created]})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e), "error": str(e)}), 500

# ===== NEW ROUTES FOR SELLER NOTIFICATIONS =====
@orders_bp.route('/api/notifications/seller', methods=['GET'])
def seller_notifications():
    email = request.args.get('email','').lower().strip() or request.args.get('shop_email','').lower().strip()
    if not email:
        return jsonify({"notifications": [], "count": 0})
    
    notifs = get_notifications()
    my_notifs = [n for n in notifs if n.get('recipient_email','').lower() == email]
    my_notifs.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    
    unread = len([n for n in my_notifs if not n.get('is_read')])
    
    return jsonify({
        "notifications": my_notifs[:50],
        "count": len(my_notifs),
        "unread": unread,
        "success": True
    })

@orders_bp.route('/api/notifications/mark-read', methods=['POST'])
def mark_read():
    data = request.get_json() or {}
    notif_id = data.get('id') or data.get('notif_id')
    email = data.get('email','').lower().strip()
    
    notifs = get_notifications()
    for n in notifs:
        if notif_id and n.get('id') == notif_id:
            n['is_read'] = True
        elif email and n.get('recipient_email','').lower() == email:
            # mark all as read if email provided
            if not data.get('id'):
                n['is_read'] = True
    save_notifications(notifs)
    return jsonify({"success": True})

@orders_bp.route('/api/notifications/seller/count', methods=['GET'])
def seller_notif_count():
    email = request.args.get('email','').lower().strip() or request.args.get('shop_email','').lower().strip()
    if not email:
        return jsonify({"count": 0, "unread": 0})
    notifs = get_notifications()
    unread = len([n for n in notifs if n.get('recipient_email','').lower() == email and not n.get('is_read')])
    return jsonify({"count": unread, "unread": unread, "new_notifications": unread})

@orders_bp.route('/api/orders/my', methods=['GET'])
def my_orders():
    email = request.args.get('email','').lower()
    if not email:
        return jsonify({"orders": []})
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
        except:
            pass
    if not order:
        return jsonify({"success": False}), 404
    return jsonify({"success": True, "order": order})

@orders_bp.route('/api/orders/seller', methods=['GET'])
def seller_orders():
    shop_email = (request.args.get('shop_email','').lower() or request.args.get('email','').lower() or request.args.get('shop','').lower()).strip()
    orders = get_orders()
    if shop_email:
        try:
            v2_orders = get_orders_v2()
            for o in v2_orders:
                if 'tracking_id' not in o:
                    o['tracking_id'] = str(o.get('id'))
            orders = orders + v2_orders
        except:
            pass
    
    if not shop_email:
        return jsonify({"orders": orders[::-1][:50], "count": len(orders)})
    
    filtered = []
    for o in orders:
        o_seller = (o.get('seller_email','') or o.get('shop_email','') or '').lower()
        if shop_email == o_seller:
            filtered.append(o)
            continue
        for it in o.get('items',[]):
            real_seller = (it.get('real_seller_email','') or '').lower()
            if shop_email == real_seller:
                filtered.append(o)
                break
    
    filtered.sort(key=lambda x: x.get('timestamp',0) or 0, reverse=True)
    return jsonify({"orders": filtered[:30], "count": len(filtered), "success": True})

@orders_bp.route('/api/orders/seller/count', methods=['GET'])
def seller_count():
    shop_email = (request.args.get('shop_email','').lower() or request.args.get('email','').lower()).strip()
    if not shop_email:
        return jsonify({"count": 0, "new_orders": 0})
    orders = get_orders()
    count = 0
    for o in orders:
        if o.get('status','').upper() != 'PENDING': continue
        if (o.get('seller_email','') or '').lower() == shop_email:
            count += 1
    if count==0:
        try:
            v2 = get_orders_v2()
            for o in v2:
                if o.get('status','').upper() != 'PENDING': continue
                if (o.get('seller_email','') or '').lower() == shop_email:
                    count += 1
        except:
            pass
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
                ORDERS_V2_CACHE["data"]=v2
                ORDERS_V2_CACHE["time"]=time.time()
                return jsonify({"success": True, "order": o})
    except:
        pass
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
                            o['seller_email'] = email.lower()
                            o['shop_email'] = email.lower()
                            fixed += 1
                            break
                        if prod.get('shop_slug'):
                            sh = next((s for s in shops if s.get('shop_slug')==prod.get('shop_slug')), None)
                            if sh and sh.get('owner_email'):
                                o['seller_email'] = sh['owner_email'].lower()
                                o['shop_email'] = sh['owner_email'].lower()
                                fixed += 1
                                break
    if fixed>0:
        save_orders(orders)
    return jsonify({'success': True, 'fixed_orders': fixed, 'total': len(orders)})

@orders_bp.route('/api/orders/delivery')
def delivery_orders():
    phone = request.args.get('phone','').strip()
    if not phone:
        return jsonify({"orders": []})
    orders = get_orders()
    filtered = []
    for o in orders:
        rp = o.get('delivery_man_phone','').replace(' ','').replace('+','')
        p = phone.replace(' ','').replace('+','')
        if rp and (rp==p or rp.endswith(p[-9:])):
            filtered.append(o)
    filtered.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": filtered[:30]})

@orders_bp.route('/track/<tracking_id>')
def track_page(tracking_id):
    try:
        from flask import render_template
        return render_template('track.html', tracking_id=tracking_id)
    except:
        return render_template_string(TRACK_HTML, tracking_id=tracking_id)

@orders_bp.route('/my-orders')
def my_orders_page():
    try:
        from flask import render_template
        return render_template('my-orders.html')
    except:
        return render_template_string(MY_ORDERS_HTML)
        
@orders_bp.route('/delivery')
def delivery_dashboard():
    try:
        from flask import render_template
        return render_template('delivery.html')
    except:
        return render_template_string(DELIVERY_HTML)
        
TRACK_HTML = """<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>Track {{tracking_id}}</title><style>body{font-family:Arial;background:#FFF7ED;margin:0;padding:15px}.card{background:white;border-radius:20px;padding:18px;max-width:500px;margin:0 auto}.step{display:flex;gap:12px;padding:12px 0;border-left:3px solid #eee;margin-left:12px;padding-left:20px;position:relative}.step.done{border-left-color:#00AA00}.step.active{border-left-color:#FF6A00}.dot{width:28px;height:28px;border-radius:50%;background:#eee;display:flex;align-items:center;justify-content:center;position:absolute;left:-15px;top:10px}.dot.done{background:#00AA00;color:white}.dot.active{background:#FF6A00;color:white}.badge{padding:6px 14px;border-radius:20px;font-weight:900;color:white}</style></head><body><div class="card"><h2>📦 Tracking <span style="color:#FF6A00">{{tracking_id}}</span></h2><div id="info">Loading...</div><div id="timeline" style="margin-top:20px"></div><div id="rider" style="margin-top:16px;display:none;background:#FFF7ED;padding:12px;border-radius:12px"></div></div><script>let TID="{{tracking_id}}";async function loadTrack(){let r=await fetch('/api/orders/track/'+TID);let res=await r.json();if(!res.success){document.getElementById('info').innerHTML='Not found';return;}let o=res.order;document.getElementById('info').innerHTML=`<span class="badge" style="background:#F59E0B">${o.status}</span><br><br>Buyer: ${o.buyer_name}<br>Shop: ${o.shop_name}<br>Address: ${o.full_address}<br>Total: UGX ${Number(o.total).toLocaleString()}`;let steps=['PENDING','CONFIRMED','PACKED','SHIPPED','DELIVERED'];let cur=steps.indexOf(o.status);let html='';steps.forEach((s,i)=>{let done=i<=cur;html+=`<div class="step ${done?'done':''} ${i==cur?'active':''}"><div class="dot ${done?'done':''} ${i==cur?'active':''}">${done?'✓':i+1}</div><b>${s}</b></div>`;});document.getElementById('timeline').innerHTML=html;if(o.delivery_man_name){document.getElementById('rider').style.display='block';document.getElementById('rider').innerHTML=`Rider: ${o.delivery_man_name} - ${o.delivery_man_phone}`;}}loadTrack();setInterval(loadTrack,15000);</script></body></html>"""
MY_ORDERS_HTML = """<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>My Orders</title><style>body{font-family:Arial;background:#f5f5f5;margin:0;padding:12px}.order{background:white;border-radius:16px;padding:14px;margin-bottom:12px}.badge{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:800;color:white}.PENDING{background:#F59E0B}.CONFIRMED{background:#3B82F6}.PACKED{background:#8B5CF6}.SHIPPED{background:#FF6A00}.DELIVERED{background:#10B981}.btn{padding:12px;border-radius:12px;border:none;background:#000;color:#FFCC02;font-weight:900;width:100%;margin-top:10px}</style></head><body><h2>📦 My Orders</h2><div id="emailShow"></div><div id="list">Loading...</div><script>async function load(){let raw=localStorage.getItem('sannlas_user')||localStorage.getItem('user')||'{}';let user=JSON.parse(raw);let email=(user.email||'').toLowerCase().trim();document.getElementById('emailShow').innerText='Email: '+(email||'NOT FOUND');if(!email){document.getElementById('list').innerHTML='Login first!';return;}let r=await fetch('/api/orders/my?email='+encodeURIComponent(email));let res=await r.json();let html='';if(!res.orders||res.orders.length==0) html='No orders yet';else res.orders.forEach(o=>{let tid=o.tracking_id;html+='<div class="order"><b style="color:#FF6A00">'+tid+'</b> <span class="badge '+o.status+'">'+o.status+'</span><br>Shop: '+(o.shop_name||'')+'<br>Total: UGX '+Number(o.total).toLocaleString()+'<br><button onclick="location.href=\\'/track/'+tid+'\\'" class="btn">Track</button></div>';});document.getElementById('list').innerHTML=html;}load();</script></body></html>"""
DELIVERY_HTML = """<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>Delivery</title><style>body{font-family:Arial;background:#f0fdf4;margin:0;padding:12px}.card{background:white;border-radius:16px;padding:14px;margin-bottom:12px}input{width:100%;padding:14px;border-radius:12px;border:2px solid #ddd;margin:6px 0}.btn{padding:12px;border:none;border-radius:12px;font-weight:900;width:100%;margin-top:8px}</style></head><body><h2>🛵 Delivery</h2><div class="card"><input id="riderPhone" placeholder="Rider phone"><button onclick="loadDelivery()" style="background:#000;color:#FFCC02" class="btn">My Orders</button><input id="trackInput" placeholder="SN-123456"><button onclick="trackSingle()" class="btn">Track Single</button></div><div id="list"></div><script>async function loadDelivery(){let phone=document.getElementById('riderPhone').value.trim();if(!phone){alert('Enter phone');return;}localStorage.setItem('rider_phone',phone);let r=await fetch('/api/orders/delivery?phone='+encodeURIComponent(phone));let res=await r.json();render(res.orders);}async function trackSingle(){let tid=document.getElementById('trackInput').value.trim().toUpperCase();if(!tid){alert('Enter ID');return;}let r=await fetch('/api/orders/track/'+tid);let res=await r.json();if(!res.success){document.getElementById('list').innerHTML='Not found';return;}render([res.order]);}function render(orders){if(orders.length==0){document.getElementById('list').innerHTML='No orders';return;}let html='';orders.forEach(o=>{let tid=o.tracking_id;html+='<div class="card"><b>'+tid+'</b> - '+o.status+'<br>Buyer: '+o.buyer_name+'<br>Phone: '+o.buyer_phone+'<br>Address: '+o.full_address+'<br><button onclick="updateStatus(\\''+tid+'\\',\\'DELIVERED\\')" style="background:#D1FAE5;padding:8px;border-radius:10px">Delivered</button></div>';});document.getElementById('list').innerHTML=html;}async function updateStatus(id,status){if(!confirm('Mark '+status+'?')) return;await fetch('/api/orders/seller/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:status})});loadDelivery();}</script></body></html>"""
