# sannlas_delivery.py - ONE FILE = DELIVERY + TRACKING SYSTEM - FINAL
from flask import Blueprint, Response, request, jsonify
import os, json, time

sannlas_delivery_bp = Blueprint('sannlas_delivery_bp', __name__)

def load_db(file, default):
    try:
        if os.path.exists(f'data/{file}'):
            return json.load(open(f'data/{file}'))
        if os.path.exists(file):
            return json.load(open(file))
        return default
    except:
        return default

def save_db(file, data):
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

COMBINED_DELIVERY_HTML = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Delivery Tracking - Sannlas</title><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><style>.tab-active{border-bottom:3px solid #FFCC02;color:#FFCC02}.no-scrollbar::-webkit-scrollbar{display:none}</style></head><body class="bg-black text-white min-h-screen"><div class="sticky top-0 z-10 bg-black/80 backdrop-blur p-4 flex items-center gap-3 border-b border-white/10"><a href="/" class="text-xl"><i class="fas fa-arrow-left"></i></a><h1 class="font-bold text-lg">📦 Delivery Tracking</h1><span class="ml-auto text-xs bg-[#00FF88] text-black px-2 py-1 rounded-full font-black">LIVE TRACK</span></div><div class="flex bg-zinc-900 sticky top-[57px] z-10"><button id="btn-track" onclick="switchTab('track')" class="flex-1 py-4 font-bold text-sm tab-active"><i class="fas fa-search-location mr-2"></i>TRACK ORDER</button><button id="btn-rider" onclick="switchTab('rider')" class="flex-1 py-4 font-bold text-sm text-zinc-400"><i class="fas fa-motorcycle mr-2"></i>MY DELIVERIES</button></div><div id="track-view" class="p-4"><div class="bg-zinc-900 rounded-2xl p-5"><div class="text-center mb-5"><div class="w-16 h-16 bg-[#FFCC02] rounded-full flex items-center justify-center mx-auto mb-3"><i class="fas fa-box text-black text-2xl"></i></div><h2 class="font-black text-lg">TRACK YOUR PACKAGE</h2><p class="text-xs text-zinc-400">Enter code sent to your phone</p></div><div><label class="text-xs text-zinc-400">TRACKING CODE / ORDER ID</label><input id="t-code" class="w-full bg-black p-4 rounded-xl text-sm mt-1 outline-none border border-[#FFCC02] font-bold tracking-widest" placeholder="e.g. SN-123456"></div><div class="mt-3"><label class="text-xs text-zinc-400">PHONE NUMBER (Optional)</label><input id="t-phone" class="w-full bg-black p-3 rounded-xl text-sm mt-1" placeholder="0755..."></div><button onclick="doTrack()" class="w-full bg-[#FFCC02] text-black font-black py-4 rounded-xl mt-4">TRACK NOW 🔍</button></div><div id="track-result" class="mt-5 hidden"></div></div><div id="rider-view" class="p-4 hidden"><div class="bg-zinc-900 rounded-2xl p-4"><h3 class="font-bold mb-4">Rider Login</h3><input id="r-phone-login" class="w-full bg-black p-3 rounded-xl text-sm mb-3 border border-[#FFCC02]" placeholder="Your Phone 0755..."><button onclick="loadRiderOrders()" class="w-full bg-[#FFCC02] text-black font-black py-3 rounded-xl">MY DELIVERIES 📦</button><div class="mt-4 border-t border-zinc-800 pt-4"><h3 class="font-bold mb-2 text-sm">Register as Delivery Rider</h3><div class="grid grid-cols-2 gap-3 mb-3"><select id="r-type" class="bg-black p-3 rounded-xl text-sm"><option>Boda Boda</option><option>Tuk Tuk</option><option>Car</option><option>Van</option><option>Bicycle</option></select><input id="r-plate" class="bg-black p-3 rounded-xl text-sm" placeholder="Plate UBA 123A"></div><input id="r-name" class="w-full bg-black p-3 rounded-xl text-sm mb-3" placeholder="Your Name"></div></div><div class="mt-5"><h3 class="font-bold text-sm mb-3">ACTIVE DELIVERIES <span id="r-count" class="bg-[#00FF88] text-black px-2 py-1 rounded-full text-xs">0</span></h3><div id="rider-list" class="space-y-3"><p class="text-center text-zinc-500 text-sm py-10">Enter phone to see assigned orders.</p></div></div></div><script>
function switchTab(t){document.getElementById('track-view').classList.toggle('hidden',t!=='track');document.getElementById('rider-view').classList.toggle('hidden',t!=='rider');document.getElementById('btn-track').className=t==='track'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';document.getElementById('btn-rider').className=t==='rider'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';}
async function doTrack(){let code=document.getElementById('t-code').value.trim().toUpperCase();if(!code)return alert('Enter tracking code');let resultDiv=document.getElementById('track-result');resultDiv.classList.remove('hidden');resultDiv.innerHTML='<p class="text-center py-6">Loading...</p>';try{let r=await fetch('/api/orders/track/'+encodeURIComponent(code));let res=await r.json();if(!res.success){resultDiv.innerHTML='<div class="bg-red-900 rounded-2xl p-4 text-center">Order not found! Check code: '+code+'</div>';return;}let o=res.order;let steps=['PENDING','CONFIRMED','PACKED','SHIPPED','DELIVERED'];let cur=steps.indexOf(o.status);let timeline=steps.map((s,i)=>{let done=i<=cur;let active=i==cur;return `<div class="flex gap-3"><div class="w-3 h-3 ${done?'bg-[#00FF88]':'bg-zinc-600'} ${active?'animate-pulse':''} rounded-full mt-1"></div><div><p class="text-xs font-bold ${done?'text-white':'text-zinc-500'}">${s} ${done?'✓':''}</p><p class="text-[10px] text-zinc-400">${i==cur?'Current status':i<cur?'Done':'Pending'}</p></div></div>`;}).join('');resultDiv.innerHTML=`<div class="bg-zinc-900 rounded-2xl p-4"><div class="flex justify-between items-center mb-4"><p class="font-bold text-sm">${o.tracking_id} • ${o.shop_name||'Order'}</p><span class="bg-[#00FF88] text-black text-xs px-3 py-1 rounded-full font-black">${o.status}</span></div><div class="text-xs text-zinc-300 mb-3">Buyer: ${o.buyer_name} - ${o.buyer_phone}<br>Address: ${o.full_address}<br>Total: UGX ${Number(o.total).toLocaleString()}</div><div class="space-y-3 relative">${timeline}</div>${o.delivery_man_name?`<div class="mt-4 bg-black rounded-xl p-3 text-xs">🛵 Rider: ${o.delivery_man_name}<br>📞 ${o.delivery_man_phone}<br><a href="tel:${o.delivery_man_phone}" class="block mt-2 bg-[#FFCC02] text-black text-center py-2 rounded-xl font-black">CALL RIDER</a></div>`:''}</div>`;resultDiv.scrollIntoView({behavior:'smooth'});}catch(e){resultDiv.innerHTML='Error: '+e.message;}}
async function loadRiderOrders(){let phone=document.getElementById('r-phone-login').value.trim();if(!phone){alert('Enter phone');return;}localStorage.setItem('rider_phone',phone);let list=document.getElementById('rider-list');list.innerHTML='<p class="text-center py-6">Loading...</p>';try{let r=await fetch('/api/orders/delivery?phone='+encodeURIComponent(phone));let res=await r.json();document.getElementById('r-count').innerText=res.orders.length;if(res.orders.length==0){list.innerHTML='<p class="text-center text-zinc-500 text-sm py-10">No deliveries assigned to '+phone+'</p>';return;}list.innerHTML=res.orders.map(o=>`<div class="bg-zinc-900 rounded-2xl p-4"><div class="flex justify-between"><b class="text-sm text-[#FFCC02]">${o.tracking_id}</b><span class="bg-[#FFCC02] text-black text-xs px-2 py-1 rounded-full font-black">${o.status}</span></div><p class="text-xs mt-2">👤 ${o.buyer_name} - ${o.buyer_phone}</p><p class="text-xs text-zinc-400">📍 ${o.full_address}</p><p class="text-xs">💰 UGX ${Number(o.total).toLocaleString()}</p><div class="flex gap-2 mt-3"><button onclick="updateStatus('${o.tracking_id}','SHIPPED')" class="flex-1 bg-zinc-800 py-2 rounded-xl text-xs">🚚 Picked</button><button onclick="updateStatus('${o.tracking_id}','DELIVERED')" class="flex-1 bg-[#00FF88] text-black py-2 rounded-xl text-xs font-black">✅ Delivered</button></div><a href="tel:${o.buyer_phone}" class="block mt-2 bg-white text-black text-center py-2 rounded-xl text-xs font-bold">📞 Call Buyer</a></div>`).join('');}catch(e){list.innerHTML='Error '+e.message;}}
async function updateStatus(id,status){if(!confirm('Mark '+status+'?'))return;await fetch('/api/orders/seller/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});loadRiderOrders();}
let saved=localStorage.getItem('rider_phone');if(saved)document.getElementById('r-phone-login').value=saved;
</script></body></html>
"""

@sannlas_delivery_bp.route('/delivery')
def delivery_page():
    return Response(COMBINED_DELIVERY_HTML, mimetype='text/html')

# ============ API: TRACK ORDER BY CODE ============
@sannlas_delivery_bp.route('/api/orders/track/<tracking_code>')
def track_order(tracking_code):
    tracking_code = tracking_code.strip().upper()
    orders = load_db('orders.json', [])
    order = next((o for o in orders if str(o.get('tracking_id','')).upper()==tracking_code or str(o.get('id','')).upper()==tracking_code or str(o.get('order_id','')).upper()==tracking_code), None)
    if not order:
        return jsonify({'success':False,'error':'Order not found!'}),404
    return jsonify({'success':True,'order':order})

# ============ API: GET RIDER DELIVERIES ============
@sannlas_delivery_bp.route('/api/orders/delivery')
def rider_deliveries():
    phone = request.args.get('phone','').strip()
    if not phone:
        return jsonify({'success':False,'orders':[],'message':'Phone required'}),400
    orders = load_db('orders.json', [])
    # Find orders assigned to this rider phone OR where delivery_man_phone matches
    my_orders = [o for o in orders if str(o.get('delivery_man_phone','')).strip()==phone or str(o.get('rider_phone','')).strip()==phone or str(o.get('assigned_rider','')).strip()==phone]
    # If no assigned, also show all PENDING/SHIPPED orders for demo (so rider can pick)
    if len(my_orders)==0:
        my_orders = [o for o in orders if o.get('status') in ['CONFIRMED','PACKED','SHIPPED']][:20]
    my_orders = sorted(my_orders, key=lambda x: x.get('time',0), reverse=True)
    return jsonify({'success':True,'orders':my_orders,'count':len(my_orders)})

# ============ API: SELLER UPDATE STATUS ============
@sannlas_delivery_bp.route('/api/orders/seller/<tracking_id>/status', methods=['POST'])
def update_order_status(tracking_id):
    data = request.json or {}
    new_status = data.get('status','').upper().strip()
    if not new_status:
        return jsonify({'success':False,'error':'Status required'}),400
    
    valid_status = ['PENDING','CONFIRMED','PACKED','SHIPPED','DELIVERED','CANCELLED']
    if new_status not in valid_status:
        return jsonify({'success':False,'error':f'Invalid status! Use {valid_status}'}),400

    orders = load_db('orders.json', [])
    found = False
    for o in orders:
        if str(o.get('tracking_id','')).upper()==tracking_id.upper() or str(o.get('id','')).upper()==tracking_id.upper():
            o['status'] = new_status
            o['updated_at'] = time.time()
            o['status_history'] = o.get('status_history',[])
            o['status_history'].append({'status':new_status,'time':time.time()})
            found = True
            break
    
    if not found:
        return jsonify({'success':False,'error':'Order not found!'}),404
    
    save_db('orders.json', orders)
    return jsonify({'success':True,'message':f'✅ Order {tracking_id} marked as {new_status}','status':new_status})

# ============ API: REQUEST DELIVERY (CREATE ORDER) ============
@sannlas_delivery_bp.route('/api/delivery/request', methods=['POST'])
def request_delivery():
    data = request.json or {}
    orders = load_db('orders.json', [])
    
    tracking_id = f"SN-{int(time.time())%1000000:06d}"
    
    new_order = {
        'id': tracking_id,
        'tracking_id': tracking_id,
        'order_id': tracking_id,
        'buyer_name': data.get('buyer_name','Customer'),
        'buyer_phone': data.get('buyer_phone',''),
        'buyer_email': data.get('buyer_email',''),
        'full_address': data.get('address','') or data.get('full_address',''),
        'shop_name': data.get('shop_name','Sannlas Shop'),
        'total': data.get('total',0),
        'items': data.get('items',[]),
        'status': 'PENDING',
        'time': time.time(),
        'created_at': time.time(),
        'delivery_man_name': '',
        'delivery_man_phone': '',
        'status_history': [{'status':'PENDING','time':time.time()}]
    }
    orders.append(new_order)
    save_db('orders.json', orders)
    return jsonify({'success':True,'message':'Delivery requested!','tracking_id':tracking_id,'order':new_order})

# ============ API: MY DELIVERIES (BUYER) ============
@sannlas_delivery_bp.route('/api/delivery/my-deliveries')
def my_deliveries():
    phone = request.args.get('phone','').strip()
    email = request.args.get('email','').lower().strip()
    orders = load_db('orders.json', [])
    my = [o for o in orders if (phone and str(o.get('buyer_phone','')).strip()==phone) or (email and str(o.get('buyer_email','')).lower()==email)]
    my = sorted(my, key=lambda x: x.get('time',0), reverse=True)
    return jsonify({'success':True,'orders':my,'count':len(my)})

# ============ API: ASSIGN RIDER ============
@sannlas_delivery_bp.route('/api/delivery/assign', methods=['POST'])
def assign_rider():
    data = request.json or {}
    tracking_id = data.get('tracking_id','').upper().strip()
    rider_name = data.get('rider_name','').strip()
    rider_phone = data.get('rider_phone','').strip()
    
    orders = load_db('orders.json', [])
    for o in orders:
        if str(o.get('tracking_id','')).upper()==tracking_id:
            o['delivery_man_name'] = rider_name
            o['delivery_man_phone'] = rider_phone
            o['rider_phone'] = rider_phone
            o['status'] = 'SHIPPED'
            o['status_history'].append({'status':'SHIPPED','time':time.time(),'rider':rider_name})
            save_db('orders.json', orders)
            return jsonify({'success':True,'message':f'Rider {rider_name} assigned to {tracking_id}'})
    
    return jsonify({'success':False,'error':'Order not found!'}),404
