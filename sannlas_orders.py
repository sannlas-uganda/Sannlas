from flask import Blueprint, request, jsonify
from sannlas_cart import load_db, save_db, get_carts, save_carts
import random, time
from datetime import datetime

orders_bp = Blueprint('orders_bp', __name__)

def get_orders():
    return load_db('orders.json', [])

def save_orders(data):
    save_db('orders.json', data)

def gen_tracking_id():
    return f"SN-{random.randint(100000, 999999)}"

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
    
    # Group by shop - SPLIT PER SHOP
    from collections import defaultdict
    shops = defaultdict(list)
    for item in user_carts:
        shop_key = item.get('shop_email') or item.get('shop_name') or 'Sannlas'
        shops[shop_key].append(item)
    
    orders = get_orders()
    created_orders = []
    
    for shop_key, items in shops.items():
        tracking_id = gen_tracking_id()
        total = sum([float(i.get('price',0)) * int(i.get('qty',1)) for i in items])
        shop_name = items[0].get('shop_name','Sannlas')
        shop_email = items[0].get('shop_email','')
        
        order = {
            "order_id": tracking_id,
            "tracking_id": tracking_id,
            "buyer_email": email,
            "buyer_name": buyer_name,
            "buyer_phone": buyer_phone,
            "district": district,
            "address": address,
            "full_address": f"{district}, {address}",
            "shop_key": shop_key,
            "shop_name": shop_name,
            "shop_email": shop_email,
            "items": items,
            "total": total,
            "status": "PENDING",
            "delivery_man_name": "",
            "delivery_man_phone": "",
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        orders.append(order)
        created_orders.append(order)
    
    save_orders(orders)
    
    # Clear cart after order
    remaining = [c for c in carts if not ((c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone))]
    save_carts(remaining)
    
    return jsonify({"success": True, "orders": created_orders, "message": f"{len(created_orders)} order(s) created!"})

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
        return jsonify({"success": False, "message": "Order not found"}), 404
    return jsonify({"success": True, "order": order})

# ===== STEP 2: SELLER INBOX + ASSIGN RIDER =====
@orders_bp.route('/api/orders/seller', methods=['GET'])
def seller_orders():
    shop_email = request.args.get('shop_email','').lower()
    shop_name = request.args.get('shop_name','')
    orders = get_orders()
    filtered = []
    for o in orders:
        if shop_email and (o.get('shop_email','').lower()==shop_email or o.get('shop_key','').lower()==shop_email):
            filtered.append(o)
        elif shop_name and o.get('shop_name','')==shop_name:
            filtered.append(o)
        elif not shop_email and not shop_name:
            filtered.append(o)
    filtered.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": filtered})

@orders_bp.route('/api/orders/seller/<tracking_id>/status', methods=['POST'])
def update_status(tracking_id):
    data = request.get_json()
    new_status = data.get('status','')
    rider_name = data.get('delivery_man_name','')
    rider_phone = data.get('delivery_man_phone','')
    
    orders = get_orders()
    for o in orders:
        if o.get('tracking_id')==tracking_id:
            if new_status: o['status']=new_status
            if rider_name: o['delivery_man_name']=rider_name
            if rider_phone: o['delivery_man_phone']=rider_phone
            save_orders(orders)
            return jsonify({"success": True, "order": o})
    return jsonify({"success": False, "message": "Not found"}), 404

@orders_bp.route('/track/<tracking_id>')
def track_page(tracking_id):
    return f"""
<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>Track {tracking_id} - Sannlas</title>
<style>
body{{font-family:system-ui;background:#FFF7ED;margin:0;padding:15px}}
.card{{background:white;border-radius:20px;padding:18px;max-width:500px;margin:0 auto;box-shadow:0 4px 20px rgba(0,0,0,0.08)}}
.step{{display:flex;gap:12px;padding:12px 0;border-left:3px solid #eee;margin-left:12px;padding-left:20px;position:relative}}
.step.active{{border-left-color:#FF6A00}} .step.done{{border-left-color:#00AA00}}
.dot{{width:28px;height:28px;border-radius:50%;background:#eee;display:flex;align-items:center;justify-content:center;position:absolute;left:-15px;top:10px;font-size:14px}}
.dot.done{{background:#00AA00;color:white}} .dot.active{{background:#FF6A00;color:white}}
.badge{{padding:6px 14px;border-radius:20px;font-weight:900;font-size:12px}}
</style></head><body>
<div class="card">
<h2 style="margin:0">📦 Tracking <span style="color:#FF6A00">{tracking_id}</span></h2>
<div id="info">Loading...</div>
<div id="timeline" style="margin-top:20px"></div>
<div id="rider" style="margin-top:16px;display:none;background:#FFF7ED;padding:12px;border-radius:12px"></div>
<div style="margin-top:20px;display:flex;gap:8px">
<button onclick="location.href='/'" style="flex:1;padding:14px;border-radius:12px;border:none;background:#000;color:#FFCC02;font-weight:900">🏠 Home</button>
<button onclick="location.href='/my-orders.html'" style="flex:1;padding:14px;border-radius:12px;border:none;background:#fff;border:2px solid #000;font-weight:900">📦 My Orders</button>
</div>
</div>
<script>
let TID = "{tracking_id}";
async function loadTrack(){{
  let r = await fetch('/api/orders/track/'+TID);
  let res = await r.json();
  if(!res.success){{ document.getElementById('info').innerHTML='<p>Order not found! Check ID</p>'; return; }}
  let o = res.order;
  document.getElementById('info').innerHTML = `
    <div style="margin-top:12px;line-height:1.6;font-size:14px">
      <span class="badge" style="background:${{getColor(o.status)}};color:white">${{o.status}}</span><br><br>
      <b>Buyer:</b> ${{o.buyer_name}} - ${{o.buyer_phone}}<br>
      <b>Shop:</b> ${{o.shop_name}}<br>
      <b>Address:</b> ${{o.full_address}}<br>
      <b>Total:</b> UGX ${{Number(o.total).toLocaleString()}}<br>
      <small style="color:#666">${{new Date(o.created_at).toLocaleString()}}</small>
      <details style="margin-top:8px"><summary>View Items (${{o.items.length}})</summary>${{o.items.map(i=>`• ${{i.name||i.title}} x${{i.qty||1}}`).join('<br>')}}</details>
    </div>`;
  
  let steps = ['PENDING','CONFIRMED','PACKED','SHIPPED','DELIVERED'];
  let icons = {{'PENDING':'📝','CONFIRMED':'✅','PACKED':'📦','SHIPPED':'🚚','DELIVERED':'🎉'}};
  let currentIdx = steps.indexOf(o.status);
  let html='';
  steps.forEach((s,i)=>{{
    let cls = i < currentIdx ? 'done' : (i==currentIdx ? 'active' : '');
    let done = i <= currentIdx;
    html+=`<div class="step ${{cls}}"><div class="dot ${{done?'done':''}} ${{i==currentIdx?'active':''}}">${{done?'✓':i+1}}</div><div><b>${{icons[s]}} ${{s}}</b><br><small style="color:#666">${{getDesc(s)}}</small></div></div>`;
  }});
  document.getElementById('timeline').innerHTML=html;
  
  if(o.delivery_man_name){{
    document.getElementById('rider').style.display='block';
    document.getElementById('rider').innerHTML=`<b>🛵 Rider Assigned</b><br>👤 ${{o.delivery_man_name}}<br>📞 <a href="tel:${{o.delivery_man_phone}}" style="color:#00AA00;font-weight:900;font-size:16px">${{o.delivery_man_phone}}</a><br><a href="tel:${{o.delivery_man_phone}}" style="display:block;margin-top:8px;background:#25D366;color:white;padding:10px;border-radius:10px;text-align:center;text-decoration:none;font-weight:900">📞 Call Rider</a>`;
  }}
}}
function getColor(s){{ return {{'PENDING':'#F59E0B','CONFIRMED':'#3B82F6','PACKED':'#8B5CF6','SHIPPED':'#FF6A00','DELIVERED':'#10B981'}}[s]||'#999'; }}
function getDesc(s){{ return {{'PENDING':'Order received, shop will confirm','CONFIRMED':'Shop confirmed your order','PACKED':'Packed ready for pickup','SHIPPED':'On the way with rider','DELIVERED':'Delivered! Enjoy!'}}[s]||s; }}
loadTrack(); setInterval(loadTrack, 5000);
</script></body></html>
    """

@orders_bp.route('/my-orders')
def my_orders_page():
    return """
<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>My Orders - Sannlas</title>
<style>body{font-family:Arial;background:#f5f5f5;margin:0;padding:12px} .order{background:white;border-radius:16px;padding:14px;margin-bottom:12px;box-shadow:0 2px 10px rgba(0,0,0,0.06)} .badge{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:800;color:white} .PENDING{background:#F59E0B} .CONFIRMED{background:#3B82F6} .PACKED{background:#8B5CF6} .SHIPPED{background:#FF6A00} .DELIVERED{background:#10B981} .btn{padding:12px;border-radius:12px;border:none;background:#000;color:#FFCC02;font-weight:900;width:100%;margin-top:10px;cursor:pointer}</style>
</head><body>
<h2 style="font-weight:900">📦 My Orders</h2>
<div id="emailShow" style="font-size:12px;color:#666;margin-bottom:8px"></div>
<div id="list">Loading...</div>
<script>
async function load(){
  try{
    let raw = localStorage.getItem('sannlas_user')||localStorage.getItem('user')||'{}';
    let user = JSON.parse(raw);
    let email = (user.email||'').toLowerCase().trim();
    document.getElementById('emailShow').innerText = 'Email: ' + (email||'NOT FOUND');
    if(!email){ document.getElementById('list').innerHTML='<p style=background:white;padding:15px;border-radius:12px>⚠️ Login first!<br><br><button onclick="location.href=\\'/\\'" class=btn>Go Home & Login</button></p>'; return; }
    let r = await fetch('/api/orders/my?email='+encodeURIComponent(email));
    let txt = await r.text();
    let res = JSON.parse(txt);
    let html='';
    if(!res.orders || res.orders.length==0) html='<p style=background:white;padding:15px;border-radius:12px>No orders yet. Email: '+email+'</p>';
    else {
      res.orders.forEach(o=>{
        let tid = o.tracking_id;
        html+= '<div class="order"><div style="display:flex;justify-content:space-between"><b style="color:#FF6A00">'+tid+'</b><span class="badge '+o.status+'">'+o.status+'</span></div><div style="margin-top:6px;font-size:13px">🛍️ '+(o.shop_name||'')+'<br>💰 UGX '+Number(o.total).toLocaleString()+' - '+(o.items?o.items.length:0)+' items<br>📍 '+(o.full_address||'')+'<br><small>'+new Date(o.created_at).toLocaleString()+'</small></div><button onclick="goTrack(\\''+tid+'\\')" class="btn">🔍 Track Order</button></div>';
      });
    }
    document.getElementById('list').innerHTML=html;
  }catch(e){
    document.getElementById('list').innerHTML='<div style=background:#ffcccc;padding:12px;border-radius:10px>Error: '+e.message+'</div>';
    console.error(e);
  }
}
function goTrack(id){ location.href='/track/'+id; }
load();
</script></body></html>
    """

@orders_bp.route('/delivery')
def delivery_dashboard():
    return """
<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width, initial-scale=1'><title>Delivery Dashboard - Sannlas</title>
<style>body{font-family:Arial;background:#f0fdf4;margin:0;padding:12px} .card{background:white;border-radius:16px;padding:14px;margin-bottom:12px;box-shadow:0 2px 10px rgba(0,0,0,0.08)} input{width:100%;padding:14px;border-radius:12px;border:2px solid #ddd;margin:6px 0} .btn{padding:12px;border:none;border-radius:12px;font-weight:900;width:100%;margin-top:8px;cursor:pointer}</style>
</head><body>
<h2 style="font-weight:900">🛵 Delivery Dashboard</h2>
<div class="card">
<input id="riderPhone" placeholder="Enter your phone (rider phone)">
<button onclick="loadDelivery()" style="background:#000;color:#FFCC02" class="btn">🔍 My Assigned Orders</button>
<input id="trackInput" placeholder="Or enter Tracking ID like SN-123456">
<button onclick="trackSingle()" style="background:#fff;border:2px solid #000" class="btn">📦 Track Single Order</button>
</div>
<div id="list">Enter phone to see your deliveries</div>
<script>
async function loadDelivery(){
  let phone = document.getElementById('riderPhone').value.trim();
  if(!phone){ alert('Enter phone'); return; }
  localStorage.setItem('rider_phone', phone);
  let r = await fetch('/api/orders/delivery?phone='+encodeURIComponent(phone));
  let res = await r.json();
  render(res.orders);
}
async function trackSingle(){
  let tid = document.getElementById('trackInput').value.trim().toUpperCase();
  if(!tid){ alert('Enter Tracking ID'); return; }
  let r = await fetch('/api/orders/track/'+tid);
  let res = await r.json();
  if(!res.success){ document.getElementById('list').innerHTML='<p>Not found</p>'; return; }
  render([res.order]);
}
function render(orders){
  if(orders.length==0){ document.getElementById('list').innerHTML='<p>No orders assigned yet</p>'; return; }
  let html='';
  orders.forEach(o=>{
    let tid = o.tracking_id;
    let buyerPhone = (o.buyer_phone||'').replace(/[^0-9]/g,'');
    html+='<div class="card"><div style="display:flex;justify-content:space-between"><b style="color:#FF6A00">'+tid+'</b><span style="background:#FF6A00;color:white;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:800">'+o.status+'</span></div><div style="margin-top:8px;font-size:14px;line-height:1.6">👤 Buyer: <b>'+o.buyer_name+'</b><br>📞 <a href="tel:'+o.buyer_phone+'" style="color:#00AA00;font-weight:800">'+o.buyer_phone+'</a><br>📍 <b>'+o.full_address+'</b><br>🏪 Shop: '+(o.shop_name||'')+'<br>💰 UGX '+Number(o.total).toLocaleString()+'<br><small>'+new Date(o.created_at).toLocaleString()+'</small></div><div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap"><button onclick="updateStatus(\\''+tid+'\\',\\'SHIPPED\\')" style="background:#FEF3C7;padding:8px 12px;border-radius:10px;border:none;font-weight:700">🚚 Picked Up</button><button onclick="updateStatus(\\''+tid+'\\',\\'DELIVERED\\')" style="background:#D1FAE5;padding:8px 12px;border-radius:10px;border:none;font-weight:700">✅ Delivered</button><a href="https://wa.me/'+buyerPhone+'" target="_blank" style="background:#25D366;color:white;padding:8px 12px;border-radius:10px;text-decoration:none;font-weight:700">💬 WhatsApp</a><a href="tel:'+o.buyer_phone+'" style="background:#000;color:#FFCC02;padding:8px 12px;border-radius:10px;text-decoration:none;font-weight:700">📞 Call</a></div><button onclick="goTrack(\\''+tid+'\\')" style="margin-top:8px;background:#fff;border:2px solid #000;width:100%" class="btn">🔍 View Tracking</button></div>';
  });
  document.getElementById('list').innerHTML=html;
}
async function updateStatus(id,status){
  if(!confirm('Mark as '+status+'?')) return;
  await fetch('/api/orders/seller/'+id+'/status', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({status:status})});
  let phone = localStorage.getItem('rider_phone');
  if(phone) loadDelivery(); else trackSingle();
}
function goTrack(id){ location.href='/track/'+id; }
let saved = localStorage.getItem('rider_phone');
if(saved) document.getElementById('riderPhone').value=saved;
</script></body></html>
    """

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
        if rp and (rp==p or rp.endswith(p[-9:]) or p.endswith(rp[-9:])):
            filtered.append(o)
    filtered.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": filtered})
