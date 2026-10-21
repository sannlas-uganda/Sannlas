from flask import Blueprint, request, jsonify, render_template_string
from sannlas_cart import load_db, save_db, get_carts, save_carts
import random, time, os, json
from datetime import datetime

orders_bp = Blueprint('orders_bp', __name__)

def get_orders():
    return load_db('orders.json', [])

def save_orders(data):
    save_db('orders.json', data)

def gen_tracking_id():
    return f"SN-{random.randint(100000, 999999)}"

def get_product_owner(product_id):
    # Find seller by product ID
    files = ['data/products.json','data/sannlas_products.json','products.json','sannlas_products.json']
    pid = str(product_id).lower().strip()
    for fp in files:
        try:
            if os.path.exists(fp):
                with open(fp,'r',encoding='utf-8') as f:
                    prods = json.loads(f.read())
                    if isinstance(prods, dict):
                        prods = list(prods.values())
                    for p in prods:
                        if not isinstance(p, dict): continue
                        p_id = str(p.get('id') or p.get('product_id') or p.get('_id') or '').lower()
                        if p_id == pid:
                            owner = p.get('seller_email') or p.get('shop_email') or p.get('owner_email') or p.get('email') or ''
                            shop = p.get('shop_name') or 'Sannlas Shop'
                            return owner.lower().strip(), shop
        except:
            continue
    return "", ""

@orders_bp.route('/api/orders/create', methods=['POST'])
def create_orders():
    data = request.get_json()
    email = data.get('email','').lower().strip()
    buyer_name = data.get('buyer_name','').strip()
    buyer_phone = data.get('buyer_phone','').strip()
    district = data.get('district','').strip()
    address = data.get('address','').strip()
    if not email or not buyer_name or not buyer_phone:
        return jsonify({"success": False, "message": "Name & Phone required"}), 400
    carts = get_carts()
    user_carts = [c for c in carts if (c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone)]
    if not user_carts:
        return jsonify({"success": False, "message": "Cart empty"}), 400
    from collections import defaultdict
    shops = defaultdict(list)
    for item in user_carts:
        product_id = item.get('product_id') or item.get('id') or item.get('_id')
        owner_email, shop_from_product = get_product_owner(product_id)
        final_seller = owner_email or item.get('shop_email') or item.get('seller_email') or ''
        final_shop = shop_from_product or item.get('shop_name') or 'Sannlas'
        item['real_seller_email'] = final_seller
        item['real_shop_name'] = final_shop
        item['real_product_id'] = product_id
        shops[final_seller or final_shop].append(item)
        print(f"PRODUCT {product_id} -> SELLER {final_seller}")
    orders = get_orders()
    created = []
    for shop_key, items in shops.items():
        tid = gen_tracking_id()
        total = sum([float(i.get('price',0)) * int(i.get('qty',1)) for i in items])
        order = {
            "order_id": tid,
            "tracking_id": tid,
            "buyer_email": email,
            "buyer_name": buyer_name,
            "buyer_phone": buyer_phone,
            "district": district,
            "address": address,
            "full_address": f"{district}, {address}",
            "shop_key": shop_key,
            "shop_name": items[0].get('real_shop_name','Sannlas'),
            "shop_email": items[0].get('real_seller_email',''),
            "seller_email": items[0].get('real_seller_email',''),
            "shop_owner_email": items[0].get('real_seller_email',''),
            "items": items,
            "total": total,
            "status": "PENDING",
            "delivery_man_name": "",
            "delivery_man_phone": "",
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        orders.append(order)
        created.append(order)
    save_orders(orders)
    remaining = [c for c in carts if not ((c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone))]
    save_carts(remaining)
    return jsonify({"success": True, "orders": created})

@orders_bp.route('/api/orders/my', methods=['GET'])
def my_orders():
    email = request.args.get('email','').lower()
    if not email:
        return jsonify({"orders": []})
    orders = get_orders()
    my = [o for o in orders if o.get('buyer_email','').lower()==email]
    my.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": my})

@orders_bp.route('/api/orders/track/<tracking_id>', methods=['GET'])
def track_order(tracking_id):
    orders = get_orders()
    order = next((o for o in orders if o.get('tracking_id')==tracking_id), None)
    if not order:
        return jsonify({"success": False}), 404
    return jsonify({"success": True, "order": order})

@orders_bp.route('/api/orders/seller', methods=['GET'])
def seller_orders():
    shop_email = request.args.get('shop_email','').lower() or request.args.get('email','').lower()
    orders = get_orders()
    if not shop_email:
        return jsonify({"orders": orders[::-1]})
    filtered = []
    for o in orders:
        o_seller = (o.get('seller_email','') or o.get('shop_email','') or '').lower()
        if shop_email == o_seller or shop_email in o_seller:
            filtered.append(o)
        else:
            for it in o.get('items',[]):
                if shop_email == (it.get('real_seller_email','') or '').lower():
                    filtered.append(o)
                    break
    filtered.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": filtered})

@orders_bp.route('/api/orders/seller/count', methods=['GET'])
def seller_count():
    shop_email = request.args.get('shop_email','').lower() or request.args.get('email','').lower()
    orders = get_orders()
    count = 0
    for o in orders:
        if o.get('status') != 'PENDING': continue
        o_seller = (o.get('seller_email','') or '').lower()
        if o_seller == shop_email:
            count += 1
        else:
            for it in o.get('items',[]):
                if (it.get('real_seller_email','') or '').lower() == shop_email:
                    count += 1
                    break
    return jsonify({"count": count, "new_orders": count})

@orders_bp.route('/api/orders/seller/<tracking_id>/status', methods=['POST'])
def update_status(tracking_id):
    data = request.get_json()
    orders = get_orders()
    for o in orders:
        if o.get('tracking_id')==tracking_id:
            if data.get('status'): o['status']=data.get('status')
            if data.get('delivery_man_name'): o['delivery_man_name']=data.get('delivery_man_name')
            if data.get('delivery_man_phone'): o['delivery_man_phone']=data.get('delivery_man_phone')
            save_orders(orders)
            return jsonify({"success": True, "order": o})
    return jsonify({"success": False}), 404

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
    return jsonify({"orders": filtered})

@orders_bp.route('/track/<tracking_id>')
def track_page(tracking_id):
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
    return render_template_string(DELIVERY_HTML)

TRACK_HTML = """<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>Track {{tracking_id}}</title><style>body{font-family:Arial;background:#FFF7ED;margin:0;padding:15px}.card{background:white;border-radius:20px;padding:18px;max-width:500px;margin:0 auto}.step{display:flex;gap:12px;padding:12px 0;border-left:3px solid #eee;margin-left:12px;padding-left:20px;position:relative}.step.done{border-left-color:#00AA00}.step.active{border-left-color:#FF6A00}.dot{width:28px;height:28px;border-radius:50%;background:#eee;display:flex;align-items:center;justify-content:center;position:absolute;left:-15px;top:10px}.dot.done{background:#00AA00;color:white}.dot.active{background:#FF6A00;color:white}.badge{padding:6px 14px;border-radius:20px;font-weight:900;color:white}</style></head><body><div class="card"><h2>📦 Tracking <span style="color:#FF6A00">{{tracking_id}}</span></h2><div id="info">Loading...</div><div id="timeline" style="margin-top:20px"></div><div id="rider" style="margin-top:16px;display:none;background:#FFF7ED;padding:12px;border-radius:12px"></div></div><script>let TID="{{tracking_id}}";async function loadTrack(){let r=await fetch('/api/orders/track/'+TID);let res=await r.json();if(!res.success){document.getElementById('info').innerHTML='Not found';return;}let o=res.order;document.getElementById('info').innerHTML=`<span class="badge" style="background:#F59E0B">${o.status}</span><br><br>Buyer: ${o.buyer_name}<br>Shop: ${o.shop_name}<br>Address: ${o.full_address}<br>Total: UGX ${Number(o.total).toLocaleString()}`;let steps=['PENDING','CONFIRMED','PACKED','SHIPPED','DELIVERED'];let cur=steps.indexOf(o.status);let html='';steps.forEach((s,i)=>{let done=i<=cur;html+=`<div class="step ${done?'done':''} ${i==cur?'active':''}"><div class="dot ${done?'done':''} ${i==cur?'active':''}">${done?'✓':i+1}</div><b>${s}</b></div>`;});document.getElementById('timeline').innerHTML=html;if(o.delivery_man_name){document.getElementById('rider').style.display='block';document.getElementById('rider').innerHTML=`Rider: ${o.delivery_man_name} - ${o.delivery_man_phone}`;}}loadTrack();setInterval(loadTrack,5000);</script></body></html>"""
MY_ORDERS_HTML = """<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>My Orders</title><style>body{font-family:Arial;background:#f5f5f5;margin:0;padding:12px}.order{background:white;border-radius:16px;padding:14px;margin-bottom:12px}.badge{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:800;color:white}.PENDING{background:#F59E0B}.CONFIRMED{background:#3B82F6}.PACKED{background:#8B5CF6}.SHIPPED{background:#FF6A00}.DELIVERED{background:#10B981}.btn{padding:12px;border-radius:12px;border:none;background:#000;color:#FFCC02;font-weight:900;width:100%;margin-top:10px}</style></head><body><h2>📦 My Orders</h2><div id="emailShow"></div><div id="list">Loading...</div><script>async function load(){let raw=localStorage.getItem('sannlas_user')||localStorage.getItem('user')||'{}';let user=JSON.parse(raw);let email=(user.email||'').toLowerCase().trim();document.getElementById('emailShow').innerText='Email: '+(email||'NOT FOUND');if(!email){document.getElementById('list').innerHTML='Login first!';return;}let r=await fetch('/api/orders/my?email='+encodeURIComponent(email));let res=await r.json();let html='';if(!res.orders||res.orders.length==0) html='No orders yet';else res.orders.forEach(o=>{let tid=o.tracking_id;html+='<div class="order"><b style="color:#FF6A00">'+tid+'</b> <span class="badge '+o.status+'">'+o.status+'</span><br>Shop: '+(o.shop_name||'')+'<br>Total: UGX '+Number(o.total).toLocaleString()+'<br><button onclick="location.href=\\'/track/'+tid+'\\'" class="btn">Track</button></div>';});document.getElementById('list').innerHTML=html;}load();</script></body></html>"""
DELIVERY_HTML = """<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>Delivery</title><style>body{font-family:Arial;background:#f0fdf4;margin:0;padding:12px}.card{background:white;border-radius:16px;padding:14px;margin-bottom:12px}input{width:100%;padding:14px;border-radius:12px;border:2px solid #ddd;margin:6px 0}.btn{padding:12px;border:none;border-radius:12px;font-weight:900;width:100%;margin-top:8px}</style></head><body><h2>🛵 Delivery</h2><div class="card"><input id="riderPhone" placeholder="Rider phone"><button onclick="loadDelivery()" style="background:#000;color:#FFCC02" class="btn">My Orders</button><input id="trackInput" placeholder="SN-123456"><button onclick="trackSingle()" class="btn">Track Single</button></div><div id="list"></div><script>async function loadDelivery(){let phone=document.getElementById('riderPhone').value.trim();if(!phone){alert('Enter phone');return;}localStorage.setItem('rider_phone',phone);let r=await fetch('/api/orders/delivery?phone='+encodeURIComponent(phone));let res=await r.json();render(res.orders);}async function trackSingle(){let tid=document.getElementById('trackInput').value.trim().toUpperCase();if(!tid){alert('Enter ID');return;}let r=await fetch('/api/orders/track/'+tid);let res=await r.json();if(!res.success){document.getElementById('list').innerHTML='Not found';return;}render([res.order]);}function render(orders){if(orders.length==0){document.getElementById('list').innerHTML='No orders';return;}let html='';orders.forEach(o=>{let tid=o.tracking_id;html+='<div class="card"><b>'+tid+'</b> - '+o.status+'<br>Buyer: '+o.buyer_name+'<br>Phone: '+o.buyer_phone+'<br>Address: '+o.full_address+'<br><button onclick="updateStatus(\\''+tid+'\\',\\'DELIVERED\\')" style="background:#D1FAE5;padding:8px;border-radius:10px">Delivered</button></div>';});document.getElementById('list').innerHTML=html;}async function updateStatus(id,status){if(!confirm('Mark '+status+'?')) return;await fetch('/api/orders/seller/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:status})});loadDelivery();}
</script>
</body>
</html>"""
