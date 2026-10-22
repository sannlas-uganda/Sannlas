from flask import Blueprint, request, jsonify, render_template_string
import os, json, time, random
from datetime import datetime

transport_bp = Blueprint('transport_bp', __name__)

# ===== NEON DB (STANDALONE - NO IMPORTS) =====
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

# ===== TRANSPORT LOGIC =====
def get_vehicles():
    return load_db('transport_vehicles.json', [])

def save_vehicles(data):
    save_db('transport_vehicles.json', data)

def get_rides():
    return load_db('transport_rides.json', [])

def save_rides(data):
    save_db('transport_rides.json', data)

# ===== API: ADD VEHICLE (OWNER) =====
@transport_bp.route('/api/transport/add', methods=['POST'])
def add_vehicle():
    try:
        data = request.get_json() or {}
        user_raw = data.get('user') or {}
        email = (data.get('email') or user_raw.get('email') or '').lower().strip()
        v_type = data.get('type') or data.get('vehicle_type') or 'Bus'
        plate = data.get('plate') or data.get('number_plate') or ''
        route = data.get('route') or data.get('route_name') or ''
        price = data.get('price') or data.get('price_per_seat') or 0
        phone = data.get('phone') or data.get('driver_phone') or ''
        seats = data.get('seats') or 14

        if not plate or not route:
            return jsonify({"success": False, "message": "Plate and Route required"}), 400

        vehicles = get_vehicles()
        vehicle = {
            "id": f"VEH-{random.randint(10000,99999)}",
            "owner_email": email,
            "type": v_type,
            "vehicle_type": v_type.lower(),
            "plate": plate.upper(),
            "number_plate": plate.upper(),
            "route": route,
            "route_name": route,
            "price": int(price) if str(price).isdigit() else price,
            "price_per_seat": price,
            "phone": phone,
            "driver_phone": phone,
            "seats": int(seats),
            "available_seats": int(seats),
            "status": "ONLINE",
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        vehicles.append(vehicle)
        save_vehicles(vehicles)
        return jsonify({"success": True, "vehicle": vehicle})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ===== API: GET MY VEHICLES (OWNER) =====
@transport_bp.route('/api/transport/my', methods=['GET'])
def my_vehicles():
    email = request.args.get('email','').lower().strip()
    vehicles = get_vehicles()
    if email:
        vehicles = [v for v in vehicles if v.get('owner_email','').lower()==email]
    vehicles.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"vehicles": vehicles, "count": len(vehicles), "success": True})

# ===== API: GET ALL VEHICLES / SEARCH =====
@transport_bp.route('/api/transport/vehicles', methods=['GET'])
@transport_bp.route('/api/transport/search', methods=['GET'])
def search_vehicles():
    v_type = request.args.get('type','').lower()
    from_loc = request.args.get('from','').lower()
    to_loc = request.args.get('to','').lower()
    route_q = request.args.get('route','').lower()

    vehicles = get_vehicles()
    filtered = vehicles

    if v_type and v_type!='all':
        filtered = [v for v in filtered if v_type in v.get('type','').lower() or v_type in v.get('vehicle_type','').lower()]
    if from_loc:
        filtered = [v for v in filtered if from_loc in v.get('route','').lower()]
    if to_loc:
        filtered = [v for v in filtered if to_loc in v.get('route','').lower()]
    if route_q:
        filtered = [v for v in filtered if route_q in v.get('route','').lower()]

    # Only ONLINE
    filtered = [v for v in filtered if v.get('status')=='ONLINE']

    filtered.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"vehicles": filtered[:50], "count": len(filtered), "success": True})

# ===== API: FIND RIDE (PASSENGER) =====
@transport_bp.route('/api/transport/find-ride', methods=['POST'])
def find_ride():
    try:
        data = request.get_json() or {}
        from_loc = data.get('from','').lower()
        to_loc = data.get('to','').lower()
        v_type = data.get('type','').lower()

        vehicles = get_vehicles()
        results = []
        for v in vehicles:
            if v.get('status')!='ONLINE': continue
            if v_type and v_type not in v.get('vehicle_type','').lower() and v_type not in v.get('type','').lower(): continue
            route_lower = v.get('route','').lower()
            if from_loc and from_loc not in route_lower: continue
            if to_loc and to_loc not in route_lower: continue
            results.append(v)

        return jsonify({"success": True, "rides": results[:20], "count": len(results)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ===== API: BOOK RIDE =====
@transport_bp.route('/api/transport/book', methods=['POST'])
def book_ride():
    try:
        data = request.get_json() or {}
        vehicle_id = data.get('vehicle_id')
        passenger_email = data.get('email','').lower()
        passenger_name = data.get('name','')
        passenger_phone = data.get('phone','')
        from_loc = data.get('from','')
        to_loc = data.get('to','')

        vehicles = get_vehicles()
        vehicle = next((v for v in vehicles if v.get('id')==vehicle_id), None)
        if not vehicle:
            return jsonify({"success": False, "message": "Vehicle not found"}), 404

        rides = get_rides()
        booking = {
            "id": f"RIDE-{random.randint(100000,999999)}",
            "vehicle_id": vehicle_id,
            "vehicle": vehicle,
            "passenger_email": passenger_email,
            "passenger_name": passenger_name,
            "passenger_phone": passenger_phone,
            "from": from_loc,
            "to": to_loc,
            "status": "PENDING",
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        rides.append(booking)
        save_rides(rides)

        return jsonify({"success": True, "booking": booking, "message": "Ride booked! Driver will contact you."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ===== API: DELETE VEHICLE =====
@transport_bp.route('/api/transport/delete/<vehicle_id>', methods=['POST','DELETE'])
def delete_vehicle(vehicle_id):
    vehicles = get_vehicles()
    new_vehicles = [v for v in vehicles if v.get('id')!=vehicle_id]
    save_vehicles(new_vehicles)
    return jsonify({"success": True})

# ===== PAGE ROUTE =====
@transport_bp.route('/transport')
def transport_page():
    return render_template_string(TRANSPORT_HTML)

TRANSPORT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Transport - Sannlas</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>.tab-active{border-bottom:3px solid #00FF88;color:#00FF88}.no-scrollbar::-webkit-scrollbar{display:none}</style>
</head>
<body class="bg-black text-white min-h-screen">
<div class="sticky top-0 z-10 bg-black/80 backdrop-blur p-4 flex items-center gap-3 border-b border-white/10">
  <a href="/" class="text-xl"><i class="fas fa-arrow-left"></i></a>
  <h1 class="font-bold text-lg">Transport</h1>
  <span class="ml-auto text-xs bg-[#00FF88] text-black px-2 py-1 rounded-full">UGANDA</span>
</div>
<div class="flex bg-zinc-900 sticky top-[57px] z-10">
  <button id="btn-passenger" onclick="switchTab('passenger')" class="flex-1 py-4 font-bold text-sm tab-active"><i class="fas fa-user mr-2"></i> I NEED A RIDE</button>
  <button id="btn-owner" onclick="switchTab('owner')" class="flex-1 py-4 font-bold text-sm text-zinc-400"><i class="fas fa-bus mr-2"></i> MY TRANSPORT</button>
</div>
<div id="passenger-view" class="p-4">
  <div class="flex gap-2 mb-5 overflow-x-auto no-scrollbar pb-2">
    <button onclick="selectType(this,'bus')" class="type-btn bg-white text-black px-5 py-3 rounded-full font-bold text-sm flex items-center gap-2"><i class="fas fa-bus"></i> Bus</button>
    <button onclick="selectType(this,'taxi')" class="type-btn bg-zinc-800 px-5 py-3 rounded-full font-bold text-sm flex items-center gap-2"><i class="fas fa-taxi"></i> Taxi</button>
    <button onclick="selectType(this,'boda')" class="type-btn bg-zinc-800 px-5 py-3 rounded-full font-bold text-sm flex items-center gap-2"><i class="fas fa-motorcycle"></i> Boda</button>
  </div>
  <div class="bg-zinc-900 rounded-2xl p-4 space-y-4">
    <div class="space-y-2"><label class="text-xs text-zinc-400">FROM</label><div class="flex items-center bg-black rounded-xl px-3"><i class="fas fa-circle-dot text-[#00FF88] text-xs"></i><input id="from" class="w-full bg-black p-3 outline-none text-sm" placeholder="Enter pickup location"></div></div>
    <div class="space-y-2"><label class="text-xs text-zinc-400">TO</label><div class="flex items-center bg-black rounded-xl px-3"><i class="fas fa-location-dot text-red-500 text-xs"></i><input id="to" class="w-full bg-black p-3 outline-none text-sm" placeholder="Enter destination"></div></div>
    <div class="grid grid-cols-2 gap-3"><input id="date" type="date" class="bg-black p-3 rounded-xl text-sm w-full"><input id="time" type="time" class="bg-black p-3 rounded-xl text-sm w-full"></div>
    <button onclick="findRide()" class="w-full bg-[#00FF88] text-black font-black py-4 rounded-xl">FIND RIDE NOW</button>
  </div>
  <div id="results" class="mt-5 space-y-3"></div>
</div>
<div id="owner-view" class="p-4 hidden">
  <div class="bg-zinc-900 rounded-2xl p-4">
    <h3 class="font-bold mb-4">Register Your Vehicle</h3>
    <div class="grid grid-cols-3 gap-2 mb-4"><select id="o-type" class="bg-black p-3 rounded-xl text-sm"><option>Bus</option><option>Taxi</option><option>Boda Boda</option></select><input id="o-plate" class="bg-black p-3 rounded-xl text-sm col-span-2" placeholder="Number Plate"></div>
    <input id="o-route" class="w-full bg-black p-3 rounded-xl text-sm mb-3" placeholder="Route (e.g. Kampala - Jinja)"><input id="o-price" class="w-full bg-black p-3 rounded-xl text-sm mb-3" placeholder="Price per seat (UGX)"><input id="o-phone" class="w-full bg-black p-3 rounded-xl text-sm mb-3" placeholder="Driver Phone (WhatsApp)"><button onclick="addVehicle()" class="w-full bg-white text-black font-bold py-3 rounded-xl">ADD VEHICLE +</button>
  </div>
  <div class="mt-5"><h3 class="font-bold text-sm mb-3">MY VEHICLES <span id="count" class="bg-zinc-800 px-2 py-1 rounded-full text-xs">0</span></h3><div id="owner-list" class="space-y-3"><p class="text-center text-zinc-500 text-sm py-10">No vehicles yet. Add one above.</p></div></div>
</div>
<script>
let selectedType='bus';
let myUser=JSON.parse(localStorage.getItem('sannlas_user')||localStorage.getItem('user')||'{}');
let myEmail=(myUser.email||'').toLowerCase();
function switchTab(tab){
  document.getElementById('passenger-view').classList.toggle('hidden', tab!=='passenger');
  document.getElementById('owner-view').classList.toggle('hidden', tab!=='owner');
  document.getElementById('btn-passenger').className=tab==='passenger'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';
  document.getElementById('btn-owner').className=tab==='owner'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';
  if(tab==='owner') loadMyVehicles();
}
function selectType(el,type){
  selectedType=type;
  document.querySelectorAll('.type-btn').forEach(b=>b.className='type-btn bg-zinc-800 px-5 py-3 rounded-full font-bold text-sm flex items-center gap-2');
  el.className='type-btn bg-white text-black px-5 py-3 rounded-full font-bold text-sm flex items-center gap-2';
}
async function findRide(){
  const from=document.getElementById('from').value||'';
  const to=document.getElementById('to').value||'';
  const resultsDiv=document.getElementById('results');
  resultsDiv.innerHTML='<p class="text-center text-zinc-500">Searching rides...</p>';
  try{
    let r=await fetch(`/api/transport/search?type=${selectedType}&from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
    let data=await r.json();
    let vehicles=data.vehicles||[];
    if(vehicles.length==0){
      resultsDiv.innerHTML=`<div class="bg-zinc-900 rounded-2xl p-6 text-center"><p class="text-zinc-400 text-sm">No ${selectedType} found for ${from||'any'} -> ${to||'any'}</p><p class="text-xs text-zinc-600 mt-2">Try different route or type</p></div>`;
      return;
    }
    resultsDiv.innerHTML=vehicles.map(v=>`
      <div class="bg-zinc-900 rounded-2xl p-4 flex justify-between items-center">
        <div><p class="font-bold text-sm">${v.route} - ${v.plate}</p><p class="text-xs text-zinc-400">${v.type} • ${v.seats} seats • UGX ${v.price}</p><p class="text-xs text-[#00FF88]">${v.status} ●</p></div>
        <button onclick="bookRide('${v.id}','${v.phone}')" class="bg-[#00FF88] text-black px-4 py-2 rounded-full font-bold text-xs">BOOK</button>
      </div>`).join('');
  }catch(e){ resultsDiv.innerHTML='Error: '+e.message; }
}
async function bookRide(vehicleId, phone){
  if(!myEmail){ alert('Login first!'); return; }
  let from=document.getElementById('from').value||'Kampala';
  let to=document.getElementById('to').value||'Jinja';
  let r=await fetch('/api/transport/book',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({vehicle_id:vehicleId,email:myEmail,name:myUser.name||'',phone:myUser.phone||'',from:from,to:to})});
  let res=await r.json();
  if(res.success){
    alert('✅ Booked! Driver will call you!');
    if(phone) window.open(`https://wa.me/${phone.replace(/[^0-9]/g,'')}?text=Hi, I booked ${from} -> ${to} on Sannlas`, '_blank');
  } else alert(res.message);
}
async function addVehicle(){
  if(!myEmail){ alert('Login first as owner!'); return; }
  const payload={
    email:myEmail,
    type:document.getElementById('o-type').value,
    plate:document.getElementById('o-plate').value,
    route:document.getElementById('o-route').value,
    price:document.getElementById('o-price').value,
    phone:document.getElementById('o-phone').value
  };
  if(!payload.plate || !payload.route){ alert('Add plate and route'); return; }
  let r=await fetch('/api/transport/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  let res=await r.json();
  if(res.success){ alert('✅ Vehicle Added!'); document.getElementById('o-plate').value=''; document.getElementById('o-route').value=''; loadMyVehicles(); }
  else alert(res.message);
}
async function loadMyVehicles(){
  if(!myEmail) return;
  let r=await fetch('/api/transport/my?email='+encodeURIComponent(myEmail));
  let data=await r.json();
  let vehicles=data.vehicles||[];
  document.getElementById('count').innerText=vehicles.length;
  if(vehicles.length==0){ document.getElementById('owner-list').innerHTML='<p class="text-center text-zinc-500 text-sm py-10">No vehicles yet. Add one above.</p>'; return; }
  document.getElementById('owner-list').innerHTML=vehicles.map(x=>`
    <div class="bg-zinc-900 rounded-2xl p-4 flex justify-between items-center">
      <div><p class="font-bold text-sm">${x.type} - ${x.plate}</p><p class="text-xs text-zinc-400">${x.route} • UGX ${x.price}</p></div>
      <div class="flex gap-2"><span class="text-[#00FF88] text-xs font-bold">${x.status} ●</span><button onclick="deleteVeh('${x.id}')" class="text-red-500 text-xs">🗑️</button></div>
    </div>`).join('');
}
async function deleteVeh(id){
  if(!confirm('Delete vehicle?')) return;
  await fetch('/api/transport/delete/'+id,{method:'POST'});
  loadMyVehicles();
}
loadMyVehicles();
</script>
</body>
</html>"""
