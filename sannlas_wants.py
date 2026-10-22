# sannlas_wants.py - ONE FILE - FIXED - SANNLAS
from flask import Blueprint, Response, request, jsonify
import os, json, uuid, time
from datetime import datetime, timedelta
import threading

sannlas_wants_bp = Blueprint('sannlas_wants_bp', __name__)

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

def get_wants():
    return load_db('wants.json', [])

def save_wants(d):
    save_db('wants.json', d)

def get_offers():
    return load_db('offers.json', [])

def save_offers(d):
    save_db('offers.json', d)

def cleanup():
    while True:
        try:
            now = datetime.utcnow()
            wants = get_wants()
            alive = []
            for w in wants:
                exp = w.get('expires_at')
                if not exp:
                    alive.append(w)
                else:
                    try:
                        if datetime.fromisoformat(str(exp).replace('Z','')) > now:
                            alive.append(w)
                    except:
                        alive.append(w)
            if len(alive) != len(wants):
                save_wants(alive)
        except:
            pass
        time.sleep(3600)

threading.Thread(target=cleanup, daemon=True).start()

COMBINED_HTML = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>WANTS - Reverse Auction | SANNLAS</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial;background:#c0392b;padding-bottom:80px}
.navbar{background:#000;color:#fff;padding:10px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:12}
.btn{background:#000;color:#FFCC02;border:2px solid #FFCC02;padding:8px 14px;border-radius:20px;font-weight:bold;cursor:pointer;width:100%}
.btn-yellow{background:#FFCC02;color:#000;border-color:#000}
.search-bar{background:#111;padding:10px;display:flex;gap:6px;position:sticky;top:50px;z-index:11}
.search-bar input,.search-bar select{padding:10px;border-radius:20px;border:none;flex:1}
.wants-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;padding:10px}
.want-card{background:#fff;border-radius:12px;overflow:hidden;border-left:5px solid #00FF00;cursor:pointer}
.want-card .top{padding:10px;display:flex;justify-content:space-between}
.badge-live{background:#00FF00;color:#000;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold}
.price-box{background:#000;color:#FFCC02;padding:8px 10px;border-radius:8px;text-align:center;font-weight:bold}
.offer-count{background:#FFCC02;color:#000;padding:3px 8px;border-radius:10px;font-size:11px}
.card{background:#fff;border-radius:12px;padding:15px;margin:10px}
.offer-row{display:flex;justify-content:space-between;align-items:center;padding:10px;border-bottom:1px solid #eee}
.offer-row.winner{background:#00FF0011;border:2px solid #00FF00;border-radius:10px}
.rank{width:30px;height:30px;background:#000;color:#FFCC02;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold}
.rank.first{background:#FFD700;color:#000}
.hidden{display:none!important}
</style>
</head>
<body>
<div class="navbar">
<div><a href="/" style="color:#FFCC02;text-decoration:none;font-weight:bold">SANNLAS</a> | <a href="/wants" style="color:#FFCC02;text-decoration:none" id="navText">WANTS AUCTION</a></div>
<div><button class="btn btn-yellow" onclick="location.href='/'" style="width:auto">Home</button></div>
</div>
<div id="listView">
<div class="search-bar">
<input id="q" placeholder="Search wants..." oninput="loadWants()">
<select id="district" onchange="loadWants()"><option value="">All Districts</option><option>Kampala</option><option>Wakiso</option><option>Mukono</option><option>Mbarara</option><option>Gulu</option></select>
<select id="sort" onchange="loadWants()"><option value="newest">Newest</option><option value="most_offers">Most Offers</option><option value="lowest_budget">Low Budget</option></select>
</div>
<div style="background:#000;color:#FFCC02;padding:8px;text-align:center;font-weight:bold;border-bottom:3px solid #FFCC02">REVERSE AUCTION - Sellers compete, lowest wins! <span id="totalWants">0</span> open wants</div>
<div id="wantsGrid" class="wants-grid"><p style="color:white;text-align:center;grid-column:1/-1;padding:30px">Loading...</p></div>
</div>
<div id="detailView" class="hidden">
<div style="background:#000;padding:8px"><a href="/wants" style="color:#FFCC02;text-decoration:none">Back to Wants</a></div>
<div id="wantBox" class="card">Loading...</div>
<div class="card" style="background:#000;border:3px solid #FFCC02">
<h3 style="color:#FFCC02;text-align:center">Place Your Offer (1 coin)</h3>
<input id="offerPrice" type="number" placeholder="Your Price UGX" style="width:100%;padding:12px;margin:8px 0;border-radius:8px;border:2px solid #FFCC02;background:#111;color:#FFCC02;font-weight:bold">
<input id="offerDelivery" placeholder="Delivery" style="width:100%;padding:10px;margin:6px 0;border-radius:8px;border:none">
<input id="offerWarranty" placeholder="Warranty" style="width:100%;padding:10px;margin:6px 0;border-radius:8px;border:none">
<textarea id="offerMsg" placeholder="Message" rows="2" style="width:100%;padding:10px;margin:6px 0;border-radius:8px;border:none"></textarea>
<button class="btn btn-yellow" onclick="placeOffer()">Place Offer (1 Coin)</button>
<p id="offerStatus" style="color:#FFCC02;text-align:center;margin-top:8px"></p>
</div>
<div class="card"><h3>Live Ranking - Lowest First</h3><div id="offersList"><p>No offers yet</p></div></div>
</div>
<script>
let parts=location.pathname.split('/').filter(Boolean); let WID=(parts.length>=2&&parts[0]=='wants')?parts[1]:null;
let currentUser=JSON.parse(localStorage.getItem('sannlas_user')||'{}');
if(WID){document.getElementById('listView').classList.add('hidden');document.getElementById('detailView').classList.remove('hidden');}else{document.getElementById('detailView').classList.add('hidden');document.getElementById('listView').classList.remove('hidden');}
async function loadWants(){let q=document.getElementById('q').value;let district=document.getElementById('district').value;let sort=document.getElementById('sort').value;let url=`/api/wants?q=${encodeURIComponent(q)}&district=${encodeURIComponent(district)}&sort=${sort}`;try{let r=await fetch(url);let wants=await r.json();if(!Array.isArray(wants))wants=[];wants.sort((a,b)=>{let ta=new Date(a.created_at||0).getTime();let tb=new Date(b.created_at||0).getTime();if(sort==='most_offers')return(b.offers_count||0)-(a.offers_count||0);if(sort==='lowest_budget')return(a.max_budget||9999999999)-(b.max_budget||9999999999);return tb-ta;});document.getElementById('totalWants').innerText=wants.length;if(wants.length==0){document.getElementById('wantsGrid').innerHTML='<p style="color:white;grid-column:1/-1;text-align:center;padding:30px">No wants - be first!</p>';return;}document.getElementById('wantsGrid').innerHTML=wants.map(w=>{let lowest=w.lowest_offer?`UGX ${Number(w.lowest_offer).toLocaleString()}`:'No offers';let expireSec=w.expires_at?(typeof w.expires_at==='number'?w.expires_at:new Date(w.expires_at).getTime()/1000):0;let expire=expireSec?Math.max(0,Math.floor((expireSec*1000-Date.now())/3600000)):'--';return `<div class="want-card" onclick="location.href='/wants/${w.id}'"><div class="top"><div><b>${w.title||w.item}</b><br><small>${w.quantity||'1'} | ${w.district} | ${expire}h left</small></div><div style="text-align:right"><span class="badge-live">LIVE</span><br><span class="offer-count">${w.offers_count||0} offers</span></div></div><div style="display:flex;justify-content:space-between;padding:8px;background:#FFF9C4"><div><small>Budget:</small><br><b>${w.max_budget?`UGX ${Number(w.max_budget).toLocaleString()}`:'Negotiable'}</b></div><div class="price-box">Lowest:<br>${lowest}</div></div></div>`;}).join('');}catch(e){document.getElementById('wantsGrid').innerHTML='<p style="color:red;text-align:center">Failed: '+e.message+'</p>';}}
async function loadDetail(){let r=await fetch(`/api/wants/${WID}`);let w=await r.json();if(!w.id){document.getElementById('wantBox').innerHTML='Not found';return;}let exp=w.expires_at?Math.max(0,Math.floor((w.expires_at*1000-Date.now())/3600000)):0;document.getElementById('wantBox').innerHTML=`<div style="display:flex;justify-content:space-between"><h2>${w.title||w.item}</h2><span style="background:${w.status=='open'?'#00FF00':'red'};color:#000;padding:4px 10px;border-radius:10px;font-size:12px">${w.status.toUpperCase()}</span></div><p>Qty: ${w.quantity} | ${w.district} | ${exp}h left</p><p style="background:#FFF9C4;padding:10px;border-radius:8px;border-left:4px solid #FFCC02">${w.description||''}</p><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px"><div style="background:#000;color:#FFCC02;padding:10px;border-radius:8px;text-align:center">Budget<br><b>UGX ${Number(w.max_budget||0).toLocaleString()}</b></div><div style="background:#111;color:#00FF00;padding:10px;border-radius:8px;text-align:center">Lowest<br><b>${w.lowest_offer?'UGX '+Number(w.lowest_offer).toLocaleString():'No offers'}</b></div></div>`;let ol=document.getElementById('offersList');if(!w.offers||!w.offers.length){ol.innerHTML='<p style="text-align:center">No offers yet</p>';}else{w.offers.sort((a,b)=>(a.price||999999999)-(b.price||999999999));ol.innerHTML=w.offers.map((o,i)=>`<div class="offer-row ${i==0?'winner':''}"><div style="display:flex;gap:10px"><div class="rank ${i==0?'first':''}">${i==0?'*':i+1}</div><div><b>UGX ${Number(o.price).toLocaleString()}</b><br><small>${o.shop_slug||'Seller'}</small></div></div><div>${w.phone==currentUser.phone?`<button onclick="acceptOffer(${o.id})" style="background:#00FF00;color:#000;border:none;padding:8px 12px;border-radius:20px;font-weight:bold">Accept</button>`:''}</div></div>`).join('');}}
async function placeOffer(){let price=document.getElementById('offerPrice').value;if(!price){alert('Enter price');return;}if(!currentUser.phone){alert('Login first');return;}document.getElementById('offerStatus').innerText='Placing...';let r=await fetch(`/api/wants/${WID}/offers`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({price:parseInt(price),delivery_time:document.getElementById('offerDelivery').value,warranty:document.getElementById('offerWarranty').value,message:document.getElementById('offerMsg').value,phone:currentUser.phone,email:currentUser.email,shop_slug:currentUser.shop_slug||''})});let d=await r.json();document.getElementById('offerStatus').innerText=d.message;if(d.success){loadDetail();}}
async function acceptOffer(oid){if(!confirm('Accept?'))return;let r=await fetch(`/api/offers/${oid}/accept`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone:currentUser.phone,email:currentUser.email})});let d=await r.json();alert(d.message);if(d.success)loadDetail();}
if(WID){loadDetail();}else{loadWants();setInterval(loadWants,15000);}
</script>
</body>
</html>
'''

@sannlas_wants_bp.route('/wants')
@sannlas_wants_bp.route('/wants/<path:wid>')
def wants_page(wid=None):
    return Response(COMBINED_HTML, mimetype='text/html')

@sannlas_wants_bp.route('/api/wants')
def api_list():
    q = request.args.get('q','').lower()
    district = request.args.get('district','').lower()
    sort = request.args.get('sort','newest')
    wants = get_wants()
    offers = get_offers()
    filtered = [w for w in wants if w.get('status','open') == 'open']
    if q:
        filtered = [w for w in filtered if q in str(w.get('title','')).lower() or q in str(w.get('description','')).lower()]
    if district:
        filtered = [w for w in filtered if district in str(w.get('district','')).lower()]
    for w in filtered:
        wo = [o for o in offers if str(o.get('want_id')) == str(w['id'])]
        w['offers_count'] = len(wo)
        w['lowest_offer'] = min([o['price'] for o in wo], default=None)
    if sort == 'most_offers':
        filtered = sorted(filtered, key=lambda x: x.get('offers_count',0), reverse=True)
    elif sort == 'lowest_budget':
        filtered = sorted(filtered, key=lambda x: int(x.get('max_budget',0) or 999999999))
    else:
        filtered = sorted(filtered, key=lambda x: x.get('created_at',''), reverse=True)
    return jsonify(filtered[:150])

@sannlas_wants_bp.route('/api/wants/<path:wid>')
def api_single(wid):
    wants = get_wants()
    offers = get_offers()
    want = next((w for w in wants if str(w['id']) == str(wid)), None)
    if not want:
        return jsonify({'success':False}),404
    wo = sorted([o for o in offers if str(o.get('want_id')) == str(wid)], key=lambda x: x.get('price',999999999))
    want['offers'] = wo
    want['offers_count'] = len(wo)
    if wo:
        want['lowest_offer'] = wo[0]['price']
    return jsonify(want)

@sannlas_wants_bp.route('/api/wants', methods=['POST'])
def api_create():
    data = request.get_json() or {}
    want = {}
    want['id'] = str(uuid.uuid4())
    want['title'] = data.get('title') or data.get('item') or 'Want'
    want['item'] = data.get('item') or data.get('title')
    want['quantity'] = data.get('quantity','1')
    want['district'] = data.get('district','Kampala')
    want['phone'] = data.get('phone')
    want['email'] = data.get('email','')
    want['min_budget'] = data.get('min_budget','0')
    want['max_budget'] = data.get('max_budget','0')
    want['description'] = data.get('description') or ''
    want['category'] = data.get('category','')
    want['status'] = 'open'
    want['expires_at'] = (datetime.utcnow() + timedelta(hours=int(data.get('expiry_hours',24)))).isoformat()
    want['created_at'] = datetime.utcnow().isoformat()
    want['created'] = time.time()
    wants = get_wants()
    wants.append(want)
    save_wants(wants)
    return jsonify({"success":True,"want":want})

@sannlas_wants_bp.route('/api/wants/<path:wid>/offers', methods=['POST'])
def api_offer(wid):
    data = request.get_json() or {}
    price = int(data.get('price',0))
    phone = data.get('phone','')
    email = data.get('email','').lower().strip()
    if price <= 0:
        return jsonify({'success':False,'message':'Enter price'}),400
    users = load_db('users.json', [])
    seller = None
    for u in users:
        if (phone and u.get('phone') == phone) or (email and u.get('email','').lower() == email):
            seller = u
            break
    if not seller or int(seller.get('coins',0)) < 1:
        return jsonify({'success':False,'message':'Need 1 coin'}),402
    seller['spent'] = int(seller.get('spent',0)) + 1
    seller['coins'] = int(seller.get('bought',0)) + int(seller.get('earned',0)) - int(seller['spent'])
    save_db('users.json', users)
    offers = get_offers()
    new_offer = {}
    new_offer['id'] = int(time.time()*1000)
    new_offer['want_id'] = wid
    new_offer['seller_phone'] = phone
    new_offer['seller_email'] = email
    new_offer['shop_slug'] = data.get('shop_slug','')
    new_offer['price'] = price
    new_offer['delivery_time'] = data.get('delivery_time','Same day')
    new_offer['message'] = data.get('message','')
    new_offer['warranty'] = data.get('warranty','')
    new_offer['status'] = 'pending'
    new_offer['created'] = time.time()
    offers.append(new_offer)
    save_offers(offers)
    return jsonify({'success':True,'message':'Offer placed!','offer':new_offer})

@sannlas_wants_bp.route('/api/offers/<int:oid>/accept', methods=['POST'])
def api_accept(oid):
    wants = get_wants()
    offers = get_offers()
    offer = next((o for o in offers if o['id'] == oid), None)
    if not offer:
        return jsonify({'success':False}),404
    want = next((w for w in wants if str(w['id']) == str(offer.get('want_id'))), None)
    for o in offers:
        if str(o.get('want_id')) == str(want['id']):
            o['status'] = 'accepted' if o['id'] == oid else 'outbid'
    want['status'] = 'closed'
    save_offers(offers)
    save_wants(wants)
    return jsonify({'success':True,'message':f"Accepted! {offer.get('seller_phone')} will call you"})

@sannlas_wants_bp.route('/api/my-wants')
def api_my_wants():
    phone = request.args.get('phone','')
    email = request.args.get('email','').lower().strip()
    wants = get_wants()
    result = [w for w in wants if (phone and w.get('phone') == phone) or (email and w.get('email','').lower() == email)]
    return jsonify(result[::-1])

@sannlas_wants_bp.route('/api/my-offers')
def api_my_offers():
    phone = request.args.get('phone','')
    email = request.args.get('email','').lower().strip()
    offers = get_offers()
    result = [o for o in offers if (phone and o.get('seller_phone') == phone) or (email and o.get('seller_email','').lower() == email)]
    return jsonify(result[::-1])
