from flask import Blueprint, request, jsonify, render_template_string
import os, json, time, random
from datetime import datetime

manufacturers_bp = Blueprint('manufacturers_bp', __name__)

# ===== NEON DB STANDALONE =====
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
                cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
                row = cur.fetchone(); cur.close(); conn.close()
                if not row: return default
                d=row['data']; return d if not isinstance(d,str) else json.loads(d)
            except:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
                row = cur.fetchone(); cur.close(); conn.close()
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
                cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, Jsonb(data)))
            except ImportError:
                cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, json.dumps(data)))
            conn.commit(); cur.close(); conn.close(); return
        except Exception as e: print("SAVE ERROR", e)
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

def get_factories(): return load_db('manufacturers.json', [])
def save_factories(d): save_db('manufacturers.json', d)
def get_requests(): return load_db('manufacture_requests.json', [])
def save_requests(d): save_db('manufacture_requests.json', d)

# ===== API: ADD FACTORY =====
@manufacturers_bp.route('/api/manufacturers/add', methods=['POST'])
def add_factory():
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').lower().strip()
        name = data.get('name') or data.get('factory_name') or ''
        category = data.get('category') or data.get('cat') or 'Custom'
        location = data.get('location') or data.get('loc') or ''
        capacity = data.get('capacity') or data.get('cap') or ''
        min_order = data.get('min_order') or data.get('min') or ''
        price = data.get('price') or data.get('price_per_pc') or 0
        phone = data.get('phone') or data.get('factory_phone') or ''

        if not name:
            return jsonify({"success": False, "message": "Factory name required"}), 400

        factories = get_factories()
        factory = {
            "id": f"FACT-{random.randint(10000,99999)}",
            "owner_email": email,
            "name": name,
            "factory_name": name,
            "category": category,
            "cat": category,
            "location": location,
            "loc": location,
            "capacity": capacity,
            "min_order": min_order,
            "price": price,
            "price_per_pc": price,
            "phone": phone,
            "factory_phone": phone,
            "status": "VERIFIED",
            "verified": True,
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        factories.append(factory)
        save_factories(factories)
        return jsonify({"success": True, "factory": factory})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ===== API: MY FACTORIES =====
@manufacturers_bp.route('/api/manufacturers/my', methods=['GET'])
def my_factories():
    email = request.args.get('email','').lower().strip()
    factories = get_factories()
    if email:
        factories = [f for f in factories if f.get('owner_email','').lower()==email]
    factories.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"factories": factories, "count": len(factories), "success": True})

# ===== API: SEARCH FACTORIES (BUYER) =====
@manufacturers_bp.route('/api/manufacturers/search', methods=['GET'])
def search_factories():
    q = request.args.get('q','').lower()
    cat = request.args.get('category','').lower()
    district = request.args.get('district','').lower()

    factories = get_factories()
    filtered = factories

    if cat and cat!='all':
        filtered = [f for f in filtered if cat in f.get('category','').lower() or cat in f.get('cat','').lower()]
    if q:
        filtered = [f for f in filtered if q in f.get('name','').lower() or q in f.get('category','').lower() or q in f.get('location','').lower()]
    if district:
        filtered = [f for f in filtered if district in f.get('location','').lower() or district in f.get('loc','').lower()]

    filtered.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"factories": filtered[:50], "count": len(filtered), "success": True})

# ===== API: BUYER REQUEST MANUFACTURING =====
@manufacturers_bp.route('/api/manufacturers/request', methods=['POST'])
def request_manufacture():
    try:
        data = request.get_json() or {}
        need = data.get('need') or data.get('product') or ''
        qty = data.get('qty') or data.get('quantity') or ''
        budget = data.get('budget') or ''
        district = data.get('district') or ''
        phone = data.get('phone') or ''
        email = (data.get('email') or '').lower()
        category = data.get('category') or ''

        if not need or not phone:
            return jsonify({"success": False, "message": "Product and Phone required"}), 400

        requests = get_requests()
        req = {
            "id": f"REQ-{random.randint(100000,999999)}",
            "buyer_email": email,
            "product": need,
            "need": need,
            "quantity": qty,
            "qty": qty,
            "budget": budget,
            "district": district,
            "phone": phone,
            "category": category,
            "status": "OPEN",
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        requests.append(req)
        save_requests(requests)
        return jsonify({"success": True, "request": req})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ===== API: DELETE FACTORY =====
@manufacturers_bp.route('/api/manufacturers/delete/<fid>', methods=['POST','DELETE'])
def delete_factory(fid):
    factories = get_factories()
    new_fact = [f for f in factories if f.get('id')!=fid]
    save_factories(new_fact)
    return jsonify({"success": True})

# ===== PAGE ROUTE =====
@manufacturers_bp.route('/manufacturers')
def manufacturers_page():
    return render_template_string(MANUFACTURERS_HTML)

MANUFACTURERS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Manufacturers - Sannlas</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>.tab-active{border-bottom:3px solid #FFCC02;color:#FFCC02}.no-scrollbar::-webkit-scrollbar{display:none}</style>
</head>
<body class="bg-black text-white min-h-screen">
<div class="sticky top-0 z-10 bg-black/80 backdrop-blur p-4 flex items-center gap-3 border-b border-white/10">
  <a href="/" class="text-xl"><i class="fas fa-arrow-left"></i></a>
  <h1 class="font-bold text-lg">🏭 Manufacturers</h1>
  <span class="ml-auto text-xs bg-[#FFCC02] text-black px-2 py-1 rounded-full font-black">UGANDA</span>
</div>
<div class="flex bg-zinc-900 sticky top-[57px] z-10">
  <button id="btn-buyer" onclick="switchTab('buyer')" class="flex-1 py-4 font-bold text-sm tab-active"><i class="fas fa-shopping-cart mr-2"></i>I NEED FACTORY</button>
  <button id="btn-factory" onclick="switchTab('factory')" class="flex-1 py-4 font-bold text-sm text-zinc-400"><i class="fas fa-industry mr-2"></i>MY FACTORY</button>
</div>
<div id="buyer-view" class="p-4">
  <div class="flex gap-2 mb-5 overflow-x-auto no-scrollbar pb-2">
    <button onclick="selCat(this,'Shoes')" class="type-btn bg-white text-black px-4 py-2 rounded-full font-bold text-xs">Shoes</button>
    <button onclick="selCat(this,'Bags')" class="type-btn bg-zinc-800 px-4 py-2 rounded-full font-bold text-xs">Bags</button>
    <button onclick="selCat(this,'Clothes')" class="type-btn bg-zinc-800 px-4 py-2 rounded-full font-bold text-xs">Clothes</button>
    <button onclick="selCat(this,'Furniture')" class="type-btn bg-zinc-800 px-4 py-2 rounded-full font-bold text-xs">Furniture</button>
    <button onclick="selCat(this,'Custom')" class="type-btn bg-zinc-800 px-4 py-2 rounded-full font-bold text-xs">Custom</button>
  </div>
  <div class="bg-zinc-900 rounded-2xl p-4 space-y-3">
    <div><label class="text-xs text-zinc-400">WHAT PRODUCT TO MANUFACTURE?</label><input id="need" class="w-full bg-black p-3 rounded-xl text-sm mt-1 outline-none" placeholder="e.g. 500x School Bags, Leather"></div>
    <div class="grid grid-cols-2 gap-3">
      <div><label class="text-xs text-zinc-400">QUANTITY</label><input id="qty" class="w-full bg-black p-3 rounded-xl text-sm mt-1" placeholder="e.g. 1000 pcs"></div>
      <div><label class="text-xs text-zinc-400">BUDGET (UGX)</label><input id="budget" class="w-full bg-black p-3 rounded-xl text-sm mt-1" placeholder="e.g. 5M"></div>
    </div>
    <div><label class="text-xs text-zinc-400">DELIVERY DISTRICT</label><input id="district" class="w-full bg-black p-3 rounded-xl text-sm mt-1" placeholder="Kampala, Jinja..."></div>
    <div><label class="text-xs text-zinc-400">PHONE</label><input id="phone" class="w-full bg-black p-3 rounded-xl text-sm mt-1 border border-[#FFCC02]" placeholder="0755..."></div>
    <button onclick="findFactory()" class="w-full bg-[#FFCC02] text-black font-black py-4 rounded-xl mt-2">FIND MANUFACTURER NOW</button>
  </div>
  <div id="buyer-results" class="mt-5 space-y-3"></div>
</div>
<div id="factory-view" class="p-4 hidden">
  <div class="bg-zinc-900 rounded-2xl p-4">
    <h3 class="font-bold mb-4">Register Your Factory / Workshop</h3>
    <input id="f-name" class="w-full bg-black p-3 rounded-xl text-sm mb-3" placeholder="Factory Name e.g. Sannlas Shoes Ltd">
    <div class="grid grid-cols-2 gap-3 mb-3">
      <select id="f-cat" class="bg-black p-3 rounded-xl text-sm"><option>Shoes</option><option>Bags</option><option>Clothes</option><option>Furniture</option><option>Metal Work</option><option>Custom</option></select>
      <input id="f-loc" class="w-full bg-black p-3 rounded-xl text-sm" placeholder="Location e.g. Namanve">
    </div>
    <input id="f-cap" class="w-full bg-black p-3 rounded-xl text-sm mb-3" placeholder="Capacity / Day e.g. 200 bags per day">
    <input id="f-min" class="w-full bg-black p-3 rounded-xl text-sm mb-3" placeholder="Min Order e.g. 50 pcs">
    <input id="f-price" class="w-full bg-black p-3 rounded-xl text-sm mb-3" placeholder="Price per pc (UGX) e.g. 15000">
    <input id="f-phone" class="w-full bg-black p-3 rounded-xl text-sm mb-3 border border-[#FFCC02]" placeholder="Factory Phone (WhatsApp)">
    <button onclick="addFactory()" class="w-full bg-white text-black font-bold py-3 rounded-xl">ADD FACTORY +</button>
  </div>
  <div class="mt-5"><h3 class="font-bold text-sm mb-3">MY FACTORIES <span id="f-count" class="bg-zinc-800 px-2 py-1 rounded-full text-xs">0</span></h3><div id="factory-list" class="space-y-3"><p class="text-center text-zinc-500 text-sm py-10">No factory yet.</p></div></div>
</div>
<script>
let myUser=JSON.parse(localStorage.getItem('sannlas_user')||localStorage.getItem('user')||'{}');
let myEmail=(myUser.email||'').toLowerCase();
let selectedCat='Shoes';
function switchTab(t){
  document.getElementById('buyer-view').classList.toggle('hidden',t!=='buyer');
  document.getElementById('factory-view').classList.toggle('hidden',t!=='factory');
  document.getElementById('btn-buyer').className=t==='buyer'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';
  document.getElementById('btn-factory').className=t==='factory'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';
  if(t==='factory') loadMyFactories();
}
function selCat(el,cat){
  selectedCat=cat;
  document.querySelectorAll('.type-btn').forEach(b=>b.className='type-btn bg-zinc-800 px-4 py-2 rounded-full font-bold text-xs');
  el.className='type-btn bg-white text-black px-4 py-2 rounded-full font-bold text-xs';
}
async function findFactory(){
  let need=document.getElementById('need').value||'';
  let qty=document.getElementById('qty').value||'';
  let budget=document.getElementById('budget').value||'';
  let district=document.getElementById('district').value||'';
  let phone=document.getElementById('phone').value||'';
  let results=document.getElementById('buyer-results');
  if(!need){ alert('Enter what to manufacture'); return; }
  if(!phone){ alert('Enter phone'); return; }
  results.innerHTML='<p class="text-center text-zinc-500 text-sm">Searching factories...</p>';
  try{
    let r=await fetch(`/api/manufacturers/search?category=${encodeURIComponent(selectedCat)}&q=${encodeURIComponent(need)}&district=${encodeURIComponent(district)}`);
    let data=await r.json();
    let factories=data.factories||[];
    if(factories.length==0){
      results.innerHTML=`<div class="bg-zinc-900 rounded-2xl p-6 text-center"><p class="text-zinc-400 text-sm">No ${selectedCat} factories for ${need} yet</p><p class="text-xs text-zinc-600 mt-2">Your request saved, factories will contact you!</p></div>`;
      await fetch('/api/manufacturers/request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({need:need,qty:qty,budget:budget,district:district,phone:phone,email:myEmail,category:selectedCat})});
      return;
    }
    results.innerHTML=factories.map(f=>`
      <div class="bg-zinc-900 rounded-2xl p-4 flex justify-between items-center">
        <div><p class="font-bold text-sm">🏭 ${f.name}</p><p class="text-xs text-zinc-400">${f.category} • ${f.location} • ${f.price} UGX/pc</p><p class="text-xs text-[#00FF88]">● ${f.status} • Min: ${f.min_order||'50 pcs'}</p></div>
        <button onclick="window.open('https://wa.me/${(f.phone||'').replace(/[^0-9]/g,'')}?text=Hi ${f.name}, I need ${need} qty ${qty}, Budget ${budget} - from Sannlas','_blank')" class="bg-[#FFCC02] text-black px-4 py-2 rounded-full font-bold text-xs">CHAT</button>
      </div>`).join('');
  }catch(e){ results.innerHTML='Error: '+e.message; }
}
async function addFactory(){
  if(!myEmail){ alert('Login first!'); return; }
  let payload={
    email:myEmail,
    name:document.getElementById('f-name').value,
    category:document.getElementById('f-cat').value,
    location:document.getElementById('f-loc').value,
    capacity:document.getElementById('f-cap').value,
    min_order:document.getElementById('f-min').value,
    price:document.getElementById('f-price').value,
    phone:document.getElementById('f-phone').value
  };
  if(!payload.name){ alert('Add factory name'); return; }
  let r=await fetch('/api/manufacturers/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  let res=await r.json();
  if(res.success){ alert('✅ Factory Added!'); document.getElementById('f-name').value=''; loadMyFactories(); }
  else alert(res.message);
}
async function loadMyFactories(){
  if(!myEmail) return;
  let r=await fetch('/api/manufacturers/my?email='+encodeURIComponent(myEmail));
  let data=await r.json();
  let factories=data.factories||[];
  document.getElementById('f-count').innerText=factories.length;
  if(factories.length==0){ document.getElementById('factory-list').innerHTML='<p class="text-center text-zinc-500 text-sm py-10">No factory yet.</p>'; return; }
  document.getElementById('factory-list').innerHTML=factories.map(x=>`
    <div class="bg-zinc-900 rounded-2xl p-4 flex justify-between items-center"><div><p class="font-bold text-sm">${x.name}</p><p class="text-xs text-zinc-400">${x.category} • ${x.location} • ${x.price} UGX/pc • ${x.capacity}</p></div><div class="flex gap-2"><span class="text-[#FFCC02] text-xs font-bold">VERIFIED ●</span><button onclick="delFactory('${x.id}')" class="text-red-500 text-xs">🗑️</button></div></div>`).join('');
}
async function delFactory(id){
  if(!confirm('Delete factory?')) return;
  await fetch('/api/manufacturers/delete/'+id,{method:'POST'});
  loadMyFactories();
}
loadMyFactories();
</script>
</body>
</html>"""
