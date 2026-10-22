from flask import Blueprint, request, jsonify, render_template_string
import os, json, time, random
from datetime import datetime

calls_bp = Blueprint('calls_bp', __name__)

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

def get_calls(): return load_db('sannlas_calls.json', [])
def save_calls(d): save_db('sannlas_calls.json', d)
def get_sellers(): return load_db('sannlas_users.json', {})

# ===== API: MAKE CALL LOG =====
@calls_bp.route('/api/calls/make', methods=['POST'])
def make_call():
    try:
        data = request.get_json() or {}
        from_email = (data.get('from_email') or data.get('email') or '').lower().strip()
        to_number = data.get('to') or data.get('to_number') or data.get('phone') or ''
        call_type = data.get('type') or 'OUTGOING'

        if not to_number:
            return jsonify({"success": False, "message": "Number required"}), 400

        calls = get_calls()
        call = {
            "id": f"CALL-{random.randint(100000,999999)}",
            "from_email": from_email,
            "to_number": to_number,
            "to": to_number,
            "type": call_type,
            "status": "COMPLETED",
            "duration": f"{random.randint(10,300)}s",
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        calls.insert(0, call)
        # Keep only 200 calls
        save_calls(calls[:200])
        return jsonify({"success": True, "call": call})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ===== API: CALL HISTORY =====
@calls_bp.route('/api/calls/history', methods=['GET'])
def call_history():
    email = request.args.get('email','').lower().strip()
    calls = get_calls()
    if email:
        calls = [c for c in calls if c.get('from_email','').lower()==email or c.get('to_number','')==email]
    calls.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"calls": calls[:100], "count": len(calls), "success": True})

# ===== API: GET SELLERS FOR CALLS (contacts) =====
@calls_bp.route('/api/calls/sellers', methods=['GET'])
def get_sellers_for_calls():
    q = request.args.get('q','').lower()
    try:
        # Try to load users from Neon
        users_raw = load_db('users.json', {})
        sellers_raw = load_db('sellers.json', {})
        users = []
        # Normalize users dict to list
        if isinstance(users_raw, dict):
            for k,v in users_raw.items():
                if isinstance(v, dict):
                    v['email']=v.get('email',k)
                    users.append(v)
        elif isinstance(users_raw, list):
            users = users_raw
        
        if isinstance(sellers_raw, dict):
            for k,v in sellers_raw.items():
                if isinstance(v, dict):
                    v['email']=v.get('email',k)
                    users.append(v)

        # Deduplicate by email/phone
        seen=set()
        filtered=[]
        for u in users:
            email = (u.get('email','') or '').lower()
            phone = u.get('phone') or u.get('whatsapp') or ''
            name = u.get('name') or u.get('shop_name') or email.split('@')[0] or 'Seller'
            if not phone and not email: continue
            key = email or phone
            if key in seen: continue
            seen.add(key)
            if q and q not in name.lower() and q not in email.lower() and q not in str(phone).lower():
                continue
            filtered.append({
                "name": name,
                "email": email,
                "phone": phone,
                "shop_name": u.get('shop_name', name),
                "location": u.get('location') or u.get('district') or 'Uganda',
                "online": True
            })
        # If no users, return dummy
        if len(filtered)==0:
            filtered = [
                {"name":"Anita Bags Seller","phone":"0755123456","location":"Katwe","online":True},
                {"name":"Rider - Boda UBA 123A","phone":"0700123456","location":"Kampala","online":False}
            ]
            if q:
                filtered = [f for f in filtered if q in f['name'].lower()]

        return jsonify({"sellers": filtered[:50], "count": len(filtered), "success": True})
    except Exception as e:
        return jsonify({"sellers": [], "success": False, "message": str(e)})

# ===== API: DELETE CALL =====
@calls_bp.route('/api/calls/delete/<call_id>', methods=['POST','DELETE'])
def delete_call(call_id):
    calls = get_calls()
    new_calls = [c for c in calls if c.get('id')!=call_id]
    save_calls(new_calls)
    return jsonify({"success": True})

# ===== PAGE ROUTE =====
@calls_bp.route('/calls')
def calls_page():
    return render_template_string(CALLS_HTML)

CALLS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Calls - Sannlas</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>.tab-active{border-bottom:3px solid #00FF00;color:#00FF00}.call-btn:active{transform:scale(0.95)}</style>
</head>
<body class="bg-black text-white min-h-screen flex flex-col">
<div class="sticky top-0 z-10 bg-black/90 p-4 flex items-center gap-3 border-b border-white/10">
  <a href="/" class="text-xl"><i class="fas fa-arrow-left"></i></a>
  <h1 class="font-black text-lg">📞 Sannlas <span class="text-[#00FF00]">CALLS</span></h1>
  <span class="ml-auto bg-[#00FF00] text-black px-3 py-1 rounded-full text-xs font-black">FREE CALLS</span>
</div>
<div class="flex bg-zinc-900 sticky top-[57px] z-10">
  <button id="btn-dial" onclick="switchTab('dial')" class="flex-1 py-4 font-bold text-sm tab-active"><i class="fas fa-phone mr-2"></i>DIAL</button>
  <button id="btn-history" onclick="switchTab('history')" class="flex-1 py-4 font-bold text-sm text-zinc-400"><i class="fas fa-clock mr-2"></i>RECENT</button>
  <button id="btn-contacts" onclick="switchTab('contacts')" class="flex-1 py-4 font-bold text-sm text-zinc-400"><i class="fas fa-users mr-2"></i>SELLERS</button>
</div>
<div id="dial-view" class="p-4 flex-1 flex flex-col">
  <div class="bg-zinc-900 rounded-2xl p-4 mb-4">
    <input id="phone-display" class="w-full bg-black p-4 rounded-xl text-2xl font-bold tracking-widest text-center outline-none border border-[#00FF00]" placeholder="0755 123 456">
    <p class="text-[10px] text-zinc-500 text-center mt-2">Enter seller / buyer number to call free via Sannlas</p>
  </div>
  <div class="grid grid-cols-3 gap-4 max-w-[280px] mx-auto w-full mb-6">
    <button onclick="addDigit('1')" class="call-btn bg-zinc-900 h-16 rounded-full text-2xl font-bold">1</button>
    <button onclick="addDigit('2')" class="call-btn bg-zinc-900 h-16 rounded-full text-2xl font-bold">2<span class="block text-[10px] text-zinc-400">ABC</span></button>
    <button onclick="addDigit('3')" class="call-btn bg-zinc-900 h-16 rounded-full text-2xl font-bold">3<span class="block text-[10px] text-zinc-400">DEF</span></button>
    <button onclick="addDigit('4')" class="call-btn bg-zinc-900 h-16 rounded-full text-2xl font-bold">4<span class="block text-[10px] text-zinc-400">GHI</span></button>
    <button onclick="addDigit('5')" class="call-btn bg-zinc-900 h-16 rounded-full text-2xl font-bold">5<span class="block text-[10px] text-zinc-400">JKL</span></button>
    <button onclick="addDigit('6')" class="call-btn bg-zinc-900 h-16 rounded-full text-2xl font-bold">6<span class="block text-[10px] text-zinc-400">MNO</span></button>
    <button onclick="addDigit('7')" class="call-btn bg-zinc-900 h-16 rounded-full text-2xl font-bold">7<span class="block text-[10px] text-zinc-400">PQRS</span></button>
    <button onclick="addDigit('8')" class="call-btn bg-zinc-900 h-16 rounded-full text-2xl font-bold">8<span class="block text-[10px] text-zinc-400">TUV</span></button>
    <button onclick="addDigit('9')" class="call-btn bg-zinc-900 h-16 rounded-full text-2xl font-bold">9<span class="block text-[10px] text-zinc-400">WXYZ</span></button>
    <button onclick="addDigit('*')" class="call-btn bg-zinc-900 h-16 rounded-full text-xl">*</button>
    <button onclick="addDigit('0')" class="call-btn bg-zinc-900 h-16 rounded-full text-2xl font-bold">0</button>
    <button onclick="addDigit('#')" class="call-btn bg-zinc-900 h-16 rounded-full text-xl">#</button>
  </div>
  <div class="flex justify-center gap-6 mt-auto pb-4">
    <button onclick="clearPhone()" class="w-14 h-14 bg-zinc-800 rounded-full flex items-center justify-center"><i class="fas fa-backspace"></i></button>
    <button onclick="makeCall()" class="w-20 h-20 bg-[#00FF00] rounded-full flex items-center justify-center text-black text-2xl shadow-lg shadow-green-500/30"><i class="fas fa-phone"></i></button>
    <button onclick="openWA()" class="w-14 h-14 bg-[#FFCC02] rounded-full flex items-center justify-center text-black"><i class="fab fa-whatsapp text-xl"></i></button>
  </div>
</div>
<div id="history-view" class="p-4 hidden">
  <div id="call-history" class="space-y-2"><p class="text-center text-zinc-500 text-sm py-10">Loading calls...</p></div>
</div>
<div id="contacts-view" class="p-4 hidden">
  <input id="search-sellers" oninput="loadSellers()" class="w-full bg-zinc-900 p-3 rounded-xl text-sm mb-4" placeholder="🔍 Search sellers, buyers, riders...">
  <div id="sellers-list" class="space-y-3"><p class="text-center text-zinc-500 py-10">Loading sellers...</p></div>
</div>
<script>
let myUser=JSON.parse(localStorage.getItem('sannlas_user')||localStorage.getItem('user')||'{}');
let myEmail=(myUser.email||'').toLowerCase();
function switchTab(t){
  document.getElementById('dial-view').classList.toggle('hidden',t!=='dial');
  document.getElementById('history-view').classList.toggle('hidden',t!=='history');
  document.getElementById('contacts-view').classList.toggle('hidden',t!=='contacts');
  document.getElementById('btn-dial').className=t==='dial'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';
  document.getElementById('btn-history').className=t==='history'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';
  document.getElementById('btn-contacts').className=t==='contacts'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';
  if(t==='history') loadHistory(); if(t==='contacts') loadSellers();
}
function addDigit(d){document.getElementById('phone-display').value+=d}
function clearPhone(){let el=document.getElementById('phone-display');el.value=el.value.slice(0,-1)}
function openWA(){let num=document.getElementById('phone-display').value.replace(/[^0-9]/g,''); if(!num){alert('Enter number');return;} window.open('https://wa.me/'+num,'_blank');}
async function makeCall(){
  let num=document.getElementById('phone-display').value.trim();
  if(!num) return alert('Enter number Boss!');
  try{
    await fetch('/api/calls/make',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({from_email:myEmail,to:num})});
  }catch{}
  loadHistory();
  if(confirm('📞 Calling '+num+' via Sannlas Free Call!\\nOpen phone dialer?')) window.open('tel:'+num);
}
function callContact(n){document.getElementById('phone-display').value=n;switchTab('dial')}
async function loadHistory(){
  try{
    let r=await fetch('/api/calls/history?email='+encodeURIComponent(myEmail)); let d=await r.json(); let calls=d.calls||[];
    if(calls.length==0){ document.getElementById('call-history').innerHTML='<p class="text-center text-zinc-500 text-sm py-10">No recent calls</p>'; return; }
    document.getElementById('call-history').innerHTML=calls.map(c=>`
      <div class="bg-zinc-900 rounded-2xl p-3 flex justify-between items-center">
        <div><p class="text-sm font-bold">${c.to_number||c.to}</p><p class="text-xs text-zinc-400">${new Date(c.created_at).toLocaleString()} • ${c.duration||''} • ${c.type}</p></div>
        <div class="flex gap-2"><i class="fas fa-phone text-[#00FF00]"></i><button onclick="delCall('${c.id}')" class="text-red-500 text-xs ml-2">✕</button></div>
      </div>`).join('');
  }catch(e){ document.getElementById('call-history').innerHTML='Error '+e.message; }
}
async function loadSellers(){
  let q=document.getElementById('search-sellers')?.value||'';
  try{
    let r=await fetch('/api/calls/sellers?q='+encodeURIComponent(q)); let d=await r.json(); let sellers=d.sellers||[];
    if(sellers.length==0){ document.getElementById('sellers-list').innerHTML='<p class="text-center text-zinc-500 py-10">No sellers found</p>'; return; }
    document.getElementById('sellers-list').innerHTML=sellers.map(s=>`
      <div class="bg-zinc-900 rounded-2xl p-3 flex justify-between items-center">
        <div class="flex gap-3 items-center"><div class="w-10 h-10 bg-[#FFCC02] rounded-full flex items-center justify-center font-bold text-black">${(s.name||'A')[0].toUpperCase()}</div><div><p class="text-sm font-bold">${s.name}</p><p class="text-xs ${s.online?'text-[#00FF00]':'text-zinc-400'}">${s.online?'● Online':'○ Offline'} • ${s.location||''}</p></div></div>
        <button onclick="callContact('${s.phone||s.email}')" class="w-10 h-10 bg-[#00FF00] rounded-full text-black"><i class="fas fa-phone"></i></button>
      </div>`).join('');
  }catch(e){ document.getElementById('sellers-list').innerHTML='Error '+e.message; }
}
async function delCall(id){ await fetch('/api/calls/delete/'+id,{method:'POST'}); loadHistory(); }
loadHistory(); loadSellers();
</script>
</body>
</html>"""
