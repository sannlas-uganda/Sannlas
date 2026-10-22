from flask import Blueprint, request, jsonify, render_template_string
import os, json, time, random
from datetime import datetime

live_bp = Blueprint('live_bp', __name__)

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

def get_lives(): return load_db('live_streams.json', [])
def save_lives(d): save_db('live_streams.json', d)

# ===== API: GO LIVE =====
@live_bp.route('/api/live/start', methods=['POST'])
def start_live():
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').lower().strip()
        title = data.get('title') or data.get('live_title') or 'Live Selling'
        category = data.get('category') or data.get('cat') or 'All Products'
        phone = data.get('phone') or ''
        user_name = data.get('name') or data.get('user_name') or 'Seller'

        if not title or not phone:
            return jsonify({"success": False, "message": "Title and Phone required"}), 400

        lives = get_lives()
        live = {
            "id": f"LIVE-{random.randint(10000,99999)}",
            "owner_email": email,
            "owner_name": user_name,
            "title": title,
            "category": category,
            "phone": phone,
            "status": "LIVE",
            "viewers": random.randint(5,50),
            "likes": 0,
            "products": [],
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time()),
            "stream_key": f"sannlas-{random.randint(100000,999999)}"
        }
        lives.insert(0, live)
        save_lives(lives)
        return jsonify({"success": True, "live": live, "share_link": f"https://sannlas.com/live/{live['id']}"})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ===== API: GET LIVE STREAMS (WATCH) =====
@live_bp.route('/api/live/all', methods=['GET'])
@live_bp.route('/api/live/active', methods=['GET'])
def get_active_lives():
    cat = request.args.get('category','').lower()
    lives = get_lives()
    # Filter only LIVE status
    active = [l for l in lives if l.get('status')=='LIVE']
    
    # Expire lives older than 4 hours (auto end)
    now = int(time.time())
    active = [l for l in active if now - l.get('timestamp',0) < 14400]
    
    if cat and cat!='all':
        active = [l for l in active if cat in l.get('category','').lower() or cat in l.get('title','').lower()]

    # Simulate viewer count growing
    for l in active:
        l['viewers'] = l.get('viewers',0) + random.randint(0,5)

    active.sort(key=lambda x: x.get('viewers',0), reverse=True)
    return jsonify({"lives": active[:50], "count": len(active), "success": True})

# ===== API: MY LIVES =====
@live_bp.route('/api/live/my', methods=['GET'])
def my_lives():
    email = request.args.get('email','').lower().strip()
    lives = get_lives()
    if email:
        lives = [l for l in lives if l.get('owner_email','').lower()==email]
    lives.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"lives": lives, "count": len(lives), "success": True})

# ===== API: END LIVE =====
@live_bp.route('/api/live/end/<live_id>', methods=['POST','DELETE'])
def end_live(live_id):
    lives = get_lives()
    for l in lives:
        if l.get('id')==live_id:
            l['status']='ENDED'
            l['ended_at']=datetime.now().isoformat()
    save_lives(lives)
    return jsonify({"success": True})

# ===== API: LIKE LIVE =====
@live_bp.route('/api/live/like/<live_id>', methods=['POST'])
def like_live(live_id):
    lives = get_lives()
    for l in lives:
        if l.get('id')==live_id:
            l['likes']=l.get('likes',0)+1
            l['viewers']=l.get('viewers',0)+1
    save_lives(lives)
    return jsonify({"success": True})

# ===== PAGE ROUTE =====
@live_bp.route('/live-shopping')
@live_bp.route('/live')
def live_page():
    return render_template_string(LIVE_HTML)

LIVE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Live Shopping - Sannlas</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>.tab-active{border-bottom:3px solid #ff0000;color:#ff0000}.live-dot{animation:blink 1s infinite}@keyframes blink{0%,100%{opacity:1}50%{opacity:0}}</style>
</head>
<body class="bg-black text-white min-h-screen">
<div class="sticky top-0 z-10 bg-black/90 backdrop-blur p-4 flex items-center gap-3 border-b border-white/10">
  <a href="/" class="text-xl"><i class="fas fa-arrow-left"></i></a>
  <h1 class="font-black text-lg">🔴 LIVE <span class="text-[#ff0000]">SHOPPING</span></h1>
  <span id="live-count" class="ml-auto bg-[#ff0000] text-white px-3 py-1 rounded-full text-xs font-black flex items-center gap-1"><span class="w-2 h-2 bg-white rounded-full live-dot"></span> <span id="cnt">0 LIVE</span></span>
</div>
<div class="flex bg-zinc-900 sticky top-[57px] z-10">
  <button id="btn-watch" onclick="switchTab('watch')" class="flex-1 py-4 font-bold text-sm tab-active"><i class="fas fa-eye mr-2"></i>WATCH LIVE</button>
  <button id="btn-go" onclick="switchTab('go')" class="flex-1 py-4 font-bold text-sm text-zinc-400"><i class="fas fa-video mr-2"></i>GO LIVE</button>
</div>
<div id="watch-view" class="p-3">
  <div id="live-grid" class="grid grid-cols-2 gap-3"><p class="col-span-2 text-center text-zinc-500 py-10 text-sm">Loading lives...</p></div>
  <button onclick="loadLives()" class="w-full bg-zinc-900 py-3 rounded-xl mt-4 text-sm font-bold">🔄 Refresh Lives</button>
</div>
<div id="go-view" class="p-4 hidden">
  <div class="bg-zinc-900 rounded-2xl p-5 text-center">
    <div class="w-20 h-20 bg-[#ff0000] rounded-full flex items-center justify-center mx-auto mb-4"><i class="fas fa-video text-white text-2xl"></i></div>
    <h2 class="font-black text-lg">START LIVE SELLING</h2>
    <p class="text-xs text-zinc-400 mb-5">Sell directly to viewers, earn instantly</p>
    <input id="l-title" class="w-full bg-black p-3 rounded-xl text-sm mb-3" placeholder="Live Title e.g. Shoes 50% OFF Live">
    <select id="l-cat" class="w-full bg-black p-3 rounded-xl text-sm mb-3"><option>Shoes</option><option>Bags</option><option>Electronics</option><option>Fashion</option><option>All Products</option></select>
    <input id="l-phone" class="w-full bg-black p-3 rounded-xl text-sm mb-4 border border-[#ff0000]" placeholder="Your WhatsApp 0755...">
    <button onclick="startLive()" class="w-full bg-[#ff0000] text-white font-black py-4 rounded-xl">🔴 GO LIVE NOW</button>
    <p class="text-[10px] text-zinc-500 mt-3">By going live you agree to Sannlas terms. No adult content.</p>
  </div>
  <div class="mt-5 bg-zinc-900 rounded-2xl p-4">
    <h3 class="font-bold text-sm mb-2">MY PREVIOUS LIVES</h3>
    <div id="my-lives"><p class="text-xs text-zinc-500 text-center py-6">No lives yet. Go live to start selling!</p></div>
  </div>
</div>
<script>
let myUser=JSON.parse(localStorage.getItem('sannlas_user')||localStorage.getItem('user')||'{}');
let myEmail=(myUser.email||'').toLowerCase();
function switchTab(t){
  document.getElementById('watch-view').classList.toggle('hidden',t!=='watch');
  document.getElementById('go-view').classList.toggle('hidden',t!=='go');
  document.getElementById('btn-watch').className=t==='watch'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';
  document.getElementById('btn-go').className=t==='go'?'flex-1 py-4 font-bold text-sm tab-active':'flex-1 py-4 font-bold text-sm text-zinc-400';
  if(t==='watch') loadLives(); else loadMyLives();
}
async function loadLives(){
  try{
    let r=await fetch('/api/live/active'); let d=await r.json(); let lives=d.lives||[];
    document.getElementById('cnt').innerText=lives.length+' LIVE'; document.getElementById('live-count').style.display='flex';
    if(lives.length==0){ document.getElementById('live-grid').innerHTML='<p class="col-span-2 text-center text-zinc-500 py-10 text-sm">No live now. Be first to go live!</p>'; return; }
    document.getElementById('live-grid').innerHTML=lives.map(l=>`
      <div class="bg-zinc-900 rounded-2xl overflow-hidden border border-white/10">
        <div class="relative h-48 bg-zinc-800 flex items-center justify-center">
          <span class="absolute top-2 left-2 bg-red-600 text-white text-[10px] px-2 py-1 rounded-full font-black flex items-center gap-1"><span class="w-2 h-2 bg-white rounded-full live-dot"></span> LIVE • ${l.viewers||0}</span>
          <span class="absolute bottom-2 left-2 bg-black/70 text-white text-[10px] px-2 py-1 rounded-full">${(l.category||'Live').substring(0,20)}</span>
          <i class="fas fa-video text-zinc-600 text-3xl"></i>
        </div>
        <div class="p-2"><p class="text-xs font-bold truncate">${l.title}</p><p class="text-[10px] text-zinc-400 truncate">${l.owner_name||'Seller'} • ${l.viewers||0} watching</p><button onclick="joinLive('${l.id}','${l.phone}')" class="w-full bg-[#ff0000] text-white text-[10px] py-2 rounded-full mt-2 font-bold">JOIN LIVE</button></div>
      </div>`).join('');
  }catch(e){ document.getElementById('live-grid').innerHTML='Error: '+e.message; }
}
function joinLive(id,phone){
  alert('Joining live '+id);
  if(phone) window.open(`https://wa.me/${phone.replace(/[^0-9]/g,'')}?text=Hi, I am watching your live on Sannlas!`,'_blank');
  fetch('/api/live/like/'+id,{method:'POST'});
}
async function startLive(){
  if(!myEmail){ alert('Login first!'); return; }
  let title=document.getElementById('l-title').value||'Live Selling';
  let cat=document.getElementById('l-cat').value;
  let phone=document.getElementById('l-phone').value;
  if(!phone){ alert('Add WhatsApp'); return; }
  let r=await fetch('/api/live/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:myEmail,name:myUser.name||'Seller',title:title,category:cat,phone:phone})});
  let res=await r.json();
  if(res.success){
    alert('🔴 LIVE STARTED Boss!\\nShare link: '+res.share_link+'\\nViewers will join now!');
    document.getElementById('l-title').value=''; loadMyLives(); switchTab('watch');
  } else alert(res.message);
}
async function loadMyLives(){
  if(!myEmail) return;
  let r=await fetch('/api/live/my?email='+encodeURIComponent(myEmail)); let d=await r.json(); let lives=d.lives||[];
  if(lives.length==0){ document.getElementById('my-lives').innerHTML='<p class="text-xs text-zinc-500 text-center py-6">No lives yet. Go live to start selling!</p>'; return; }
  document.getElementById('my-lives').innerHTML=lives.map(l=>`
    <div class="bg-black rounded-xl p-3 flex justify-between items-center mb-2"><div><p class="text-xs font-bold">${l.title}</p><p class="text-[10px] text-zinc-400">${l.status} • ${l.viewers||0} viewers • ${new Date(l.created_at).toLocaleDateString()}</p></div><button onclick="endMyLive('${l.id}')" class="text-[10px] bg-zinc-800 px-3 py-1 rounded-full">${l.status=='LIVE'?'END':''}</button></div>`).join('');
}
async function endMyLive(id){
  await fetch('/api/live/end/'+id,{method:'POST'}); loadMyLives(); loadLives();
}
loadLives();
</script>
</body>
</html>"""
