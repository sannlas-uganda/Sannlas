# wants_list.py - WANTS LIST ONLY - SANNLAS
from flask import Blueprint, Response, request, jsonify
import time, json, os
from datetime import datetime, timedelta
import threading

wants_list_bp = Blueprint('wants_list_bp', __name__)

WANTS_FILE = 'wants.json'
OFFERS_FILE = 'offers.json'

def load_db(file, default):
    try:
        path = f'data/{file}'
        if os.path.exists(path):
            return json.load(open(path))
        if os.path.exists(file):
            return json.load(open(file))
        return default
    except:
        return default

def save_db(file, data):
    try:
        os.makedirs('data', exist_ok=True)
        json.dump(data, open(f'data/{file}','w'), indent=2)
    except Exception as e:
        print(e)

def get_wants_data(): return load_db(WANTS_FILE, [])
def save_wants_data(wants): save_db(WANTS_FILE, wants)
def get_offers_data(): return load_db(OFFERS_FILE, [])
def save_offers_data(offers): save_db(OFFERS_FILE, offers)

# AUTO-DELETE EXPIRED
def cleanup_expired_wants():
    while True:
        try:
            now = datetime.utcnow()
            wants_data = get_wants_data()
            original = len(wants_data)
            active = []
            for w in wants_data:
                exp = w.get('expires_at')
                if not exp:
                    active.append(w)
                else:
                    try:
                        if datetime.fromisoformat(str(exp).replace('Z','')) > now:
                            active.append(w)
                    except:
                        active.append(w)
            if len(active) != original:
                save_wants_data(active)
                print(f"[CLEANUP] Deleted {original-len(active)} expired wants")
        except Exception as e:
            print("Cleanup error", e)
        time.sleep(3600)

threading.Thread(target=cleanup_expired_wants, daemon=True).start()

# ===== HTML PAGE =====
WANTS_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>WANTS - Reverse Auction | SANNLAS</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial;background:#c0392b;padding-bottom:80px}
.navbar{background:#000;color:#fff;padding:10px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:12}
.btn{background:#000;color:#FFCC02;border:2px solid #FFCC02;padding:8px 14px;border-radius:20px;font-weight:bold;cursor:pointer}
.btn-yellow{background:#FFCC02;color:#000;border-color:#000}
.search-bar{background:#111;padding:10px;display:flex;gap:6px;position:sticky;top:50px;z-index:11}
.search-bar input, .search-bar select{padding:10px;border-radius:20px;border:none;flex:1}
.wants-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;padding:10px}
.want-card{background:#fff;border-radius:12px;overflow:hidden;border-left:5px solid #00FF00;cursor:pointer}
.want-card .top{padding:10px;display:flex;justify-content:space-between}
.badge-live{background:#00FF00;color:#000;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold}
.price-box{background:#000;color:#FFCC02;padding:8px 10px;border-radius:8px;text-align:center;font-weight:bold}
.offer-count{background:#FFCC02;color:#000;padding:3px 8px;border-radius:10px;font-size:11px}
</style>
</head>
<body>
<div class="navbar"><div><a href="/" style="color:#FFCC02;text-decoration:none;font-weight:bold">🛍️ SANNLAS</a> | 🔥 WANTS AUCTION</div><div><button class="btn btn-yellow" onclick="location.href='/'">Home</button></div></div>
<div class="search-bar"><input id="q" placeholder="Search wants... e.g. iPhone, maize" oninput="loadWants()"><select id="district" onchange="loadWants()"><option value="">All Districts</option><option>Kampala</option><option>Wakiso</option><option>Mukono</option><option>Mbarara</option><option>Gulu</option></select><select id="sort" onchange="loadWants()"><option value="newest">Newest</option><option value="most_offers">Most Offers 🔥</option><option value="lowest_budget">Low Budget</option></select></div>
<div style="background:#000;color:#FFCC02;padding:8px;text-align:center;font-weight:bold;border-bottom:3px solid #FFCC02">🔥 REVERSE AUCTION - Sellers compete, lowest price wins! <span id="totalWants">0</span> open wants</div>
<div id="wantsGrid" class="wants-grid"><p style="color:white;text-align:center;grid-column:1/-1;padding:30px">⏳ Loading auction wants...</p></div>
<script>
async function loadWants(){
 let q=document.getElementById('q').value; let district=document.getElementById('district').value; let sort=document.getElementById('sort').value;
 let url=`/api/wants?q=${encodeURIComponent(q)}&district=${encodeURIComponent(district)}&sort=${sort}`;
 try{
   let r=await fetch(url); let wants=await r.json(); if(!Array.isArray(wants)) wants=[];
   wants.sort((a,b)=>{ let ta = new Date(a.created_at || a.created || 0).getTime(); let tb = new Date(b.created_at || b.created || 0).getTime(); if(sort==='most_offers') return (b.offers_count||0) - (a.offers_count||0); if(sort==='lowest_budget') return (a.max_budget||9999999999) - (b.max_budget||9999999999); return tb - ta; });
   document.getElementById('totalWants').innerText=wants.length;
   if(wants.length==0){ document.getElementById('wantsGrid').innerHTML='<p style="color:white;grid-column:1/-1;text-align:center;padding:30px">No wants matching - be first to post! 🎯<br><a href="/" style="color:#FFCC02">Post Want on Home</a></p>'; return; }
   document.getElementById('wantsGrid').innerHTML=wants.map(w=>{
     let lowest = w.lowest_offer ? `UGX ${Number(w.lowest_offer).toLocaleString()}` : 'No offers yet';
     let expireSec = w.expires_at ? (typeof w.expires_at === 'number' ? w.expires_at : new Date(w.expires_at).getTime()/1000) : 0;
     let expire = expireSec ? Math.max(0, Math.floor((expireSec*1000 - Date.now())/3600000)) : '--';
     return `<div class="want-card" onclick="location.href='/wants/${w.id}'"><div class="top"><div><b>🎯 ${w.title||w.item}</b><br><small>📦 ${w.quantity||'1'} | 📍 ${w.district} | ⏰ ${expire}h left</small><br><small style="color:#666">${(w.description||w.note||'').slice(0,60)}</small></div><div style="text-align:right"><span class="badge-live">LIVE AUCTION</span><br><div style="margin-top:5px"><span class="offer-count">💬 ${w.offers_count||0} offers</span></div></div></div><div style="display:flex;justify-content:space-between;padding:8px;background:#FFF9C4"><div><small>Budget:</small><br><b>${w.min_budget?`UGX ${Number(w.min_budget).toLocaleString()}`:''} - ${w.max_budget?`UGX ${Number(w.max_budget).toLocaleString()}`:'Negotiable'}</b></div><div class="price-box">Lowest:<br>${lowest}</div></div></div>`;
   }).join('');
 }catch(e){ document.getElementById('wantsGrid').innerHTML='<p style="color:red;grid-column:1/-1;text-align:center;padding:20px">⚠️ Failed to load: '+e.message+'</p>'; }
}
loadWants(); setInterval(loadWants,15000);
</script>
</body>
</html>"""

@wants_list_bp.route('/wants')
def wants_page():
    return Response(WANTS_HTML, mimetype='text/html')

@wants_list_bp.route('/api/wants')
def get_wants_api():
    q = request.args.get('q','').lower()
    district = request.args.get('district','').lower()
    category = request.args.get('category','').lower()
    budget_min = request.args.get('budget_min','')
    sort = request.args.get('sort','newest')
    wants = get_wants_data()
    offers = get_offers_data()
    now = datetime.utcnow()
    live = []
    for w in wants:
        exp = w.get('expires_at')
        if not exp:
            live.append(w)
        else:
            try:
                dt = datetime.fromisoformat(str(exp).replace('Z',''))
                if dt > now:
                    live.append(w)
            except:
                live.append(w)
    wants = live
    filtered = [w for w in wants if w.get('status','open') == 'open']
    if q:
        filtered = [w for w in filtered if q in str(w.get('title','')).lower() or q in str(w.get('description','')).lower() or q in str(w.get('category','')).lower() or q in str(w.get('item','')).lower()]
    if district:
        filtered = [w for w in filtered if district in str(w.get('district','')).lower()]
    if category and category!= 'all':
        filtered = [w for w in filtered if category in str(w.get('category','')).lower()]
    if budget_min:
        try:
            bm = int(budget_min)
            filtered = [w for w in filtered if int(w.get('max_budget',0) or 0) >= bm]
        except: pass
    for w in filtered:
        w_offers = [o for o in offers if str(o.get('want_id')) == str(w['id'])]
        w['offers_count'] = len(w_offers)
        w['lowest_offer'] = min([o['price'] for o in w_offers], default=None)
    if sort == 'lowest_budget':
        filtered = sorted(filtered, key=lambda x: int(x.get('max_budget',0) or 999999999))
    elif sort == 'most_offers':
        filtered = sorted(filtered, key=lambda x: x.get('offers_count',0), reverse=True)
    else:
        def get_time(x):
            try:
                return datetime.fromisoformat(str(x.get('created_at','')).replace('Z',''))
            except:
                return datetime.fromtimestamp(x.get('created',0) or 0)
        filtered = sorted(filtered, key=get_time, reverse=True)
    return jsonify(filtered[:150])
