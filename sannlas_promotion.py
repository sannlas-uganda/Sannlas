# sannlas_promotion.py - ONE FILE = PROMOTION / PROMOTE - FINAL
from flask import Blueprint, Response, request, jsonify
import os, json, time, random, string

sannlas_promotion_bp = Blueprint('sannlas_promotion_bp', __name__)

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

# ===== SIMPLE PROMOTION HTML (You don't have file, so I create one for you) =====
PROMOTION_HTML = """
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Promote & Earn - Sannlas</title>
<style>
body{font-family:Arial;background:#f5f5f5;margin:0;padding:15px;padding-bottom:80px}
.card{background:#fff;border-radius:12px;padding:15px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.btn{width:100%;padding:12px;border:none;border-radius:10px;font-weight:bold;cursor:pointer;margin:6px 0}
.btn-black{background:#000;color:#FFCC02;border:2px solid #FFCC02}
.btn-green{background:#00c853;color:#fff}
input{width:100%;padding:12px;border:1px solid #ccc;border-radius:8px;margin:8px 0;box-sizing:border-box}
.item{padding:12px;border-bottom:1px solid #eee}
.small{font-size:12px;color:#666}
h2{margin:0 0 10px}
.nav{position:fixed;bottom:0;left:0;right:0;background:#fff;display:flex;justify-content:space-around;padding:10px;border-top:1px solid #ddd}
.nav a{text-decoration:none;color:#666;font-size:12px;text-align:center}
.nav a.active{color:#ff6f00;font-weight:bold}
.link-box{background:#000;color:#FFCC02;padding:10px;border-radius:8px;word-break:break-all;margin:8px 0}
</style></head><body>
<h2>🚀 Promote & Earn Coins</h2>
<div class="card">
<b>How it works:</b><br>
<small>1. Pick product to promote<br>2. Get your unique link<br>3. Share link - when someone buys, you earn coins!<br>4. Commission = product owner sets (3-10 coins per sale)</small>
</div>
<div class="card">
<h3>📦 My Promotion Links</h3>
<div id="myPromos">Loading...</div>
</div>
<div class="card">
<h3>📥 Requests For My Products</h3>
<small>People who want to promote your products</small>
<div id="requests">Loading...</div>
</div>
<div class="nav">
<a href="/">🏠 Home</a><a href="/promote" class="active">🚀 Promote</a><a href="/balance">💰 Balance</a><a href="/">🏪 Shops</a>
</div>
<script>
let myUser=JSON.parse(localStorage.getItem('sannlas_user')||'{}'); if(myUser.user) myUser=myUser.user;
async function loadMy(){
 let res=await fetch(`/api/promote/my?email=${myUser.email||''}&phone=${myUser.phone||''}`);
 let data=await res.json(); let html='';
 if(!data.length) html='No promotions yet. Go to a product > Click Promote & Earn button!';
 else data.forEach(p=>{
   let link=`https://sannlas.onrender.com/?promo=${p.promo_code}&product=${p.product_id}`;
   html+=`<div class=item><b>${p.product_name||p.product_id}</b><br><span class=small>Code: ${p.promo_code} | Commission: ${p.commission_coins} coins | Sales: ${p.sales||0} | Status: ${p.status}</span><div class=link-box>${link}</div><button class=btn-black onclick="navigator.clipboard.writeText('${link}');alert('Copied!')">📋 Copy Link</button><button class=btn-black onclick="share('${link}')">📤 Share WhatsApp</button></div>`;
 });
 document.getElementById('myPromos').innerHTML=html;
}
async function loadRequests(){
 let res=await fetch(`/api/promote/requests?email=${myUser.email||''}&phone=${myUser.phone||''}`);
 let data=await res.json(); let html='';
 if(!data.length) html='No requests yet';
 else data.forEach(p=>{
   html+=`<div class=item><b>${p.freelancer_phone} / ${p.freelancer_email}</b> wants to promote <b>${p.product_name}</b> for ${p.commission_coins} coins<br><span class=small>${new Date(p.created*1000).toLocaleString()} | ${p.promo_code} | Sales: ${p.sales}</span><br><button class=btn-green onclick="actionPromo(${p.id},'approved')">✅ Approve</button> <button class=btn-black onclick="actionPromo(${p.id},'rejected')">❌ Reject</button></div>`;
 });
 document.getElementById('requests').innerHTML=html;
}
async function actionPromo(id,act){
 let res=await fetch('/api/promote/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,action:act})});
 let d=await res.json(); alert(d.message); loadRequests();
}
function share(link){ window.open(`https://wa.me/?text=${encodeURIComponent('Check this product Boss! '+link)}`,'_blank');}
loadMy(); loadRequests();
</script></body></html>
"""

@sannlas_promotion_bp.route('/promote')
@sannlas_promotion_bp.route('/promotion')
@sannlas_promotion_bp.route('/promote-and-earn')
def promote_page():
    return Response(PROMOTION_HTML, mimetype='text/html')

# ===== API: APPLY TO PROMOTE A PRODUCT =====
@sannlas_promotion_bp.route('/api/promote/apply', methods=['POST'])
def promote_apply():
    data=request.json or {}
    product_id=str(data.get('product_id','')).strip()
    phone=(data.get('phone') or '').strip()
    email=(data.get('email') or '').lower().strip()
    if not phone and not email:
        return jsonify({"success":False,"message":"Login first"}),401
    products=load_db('products.json',[])
    prod=next((p for p in products if str(p.get('id'))==product_id),None)
    if not prod:
        return jsonify({"success":False,"message":"Product not found"}),404
    promos=load_db('promotions.json',[])
    existing = next((p for p in promos if str(p.get('product_id'))==product_id and (p.get('freelancer_phone')==phone or p.get('freelancer_email','').lower()==email)), None)
    if existing:
        code = existing.get('promo_code')
        link = f"https://sannlas.onrender.com/?promo={code}&product={product_id}"
        return jsonify({"success":True,"message":f"Already applied!","promo":existing,"link":link,"promo_link":link,"code":code})
    code=f"PROMO{product_id[:3]}{phone[-3:]}{''.join(random.choices(string.ascii_uppercase+string.digits,k=3))}"
    new_promo={
        "id":int(time.time()*1000),
        "product_id":product_id,
        "product_name":prod.get('name'),
        "product_owner_phone":prod.get('phone'),
        "product_owner_email":(prod.get('seller_email') or '').lower(),
        "freelancer_phone":phone,
        "freelancer_email":email,
        "commission_coins":int(prod.get('promo_commission',3)),
        "promo_code":code,
        "status":"approved",
        "sales":0,
        "created":time.time()
    }
    promos.append(new_promo)
    save_db('promotions.json',promos)
    link = f"https://sannlas.onrender.com/?promo={code}&product={product_id}"
    return jsonify({"success":True,"message":f"Applied! Earn {new_promo['commission_coins']} coins per sale! Link: {link}","promo":new_promo,"link":link,"promo_link":link,"code":code})

# ===== API: MY PROMOTIONS (I am freelancer) =====
@sannlas_promotion_bp.route('/api/promote/my', methods=['GET'])
def my_promotions():
    phone=request.args.get('phone','').strip()
    email=request.args.get('email','').lower().strip()
    promos=load_db('promotions.json',[])
    result=[p for p in promos if (phone and p.get('freelancer_phone')==phone) or (email and p.get('freelancer_email','').lower()==email)]
    return jsonify(result[::-1])

# ===== API: REQUESTS FOR MY PRODUCTS (I am owner) =====
@sannlas_promotion_bp.route('/api/promote/requests', methods=['GET'])
def promote_requests():
    phone=request.args.get('phone','').strip()
    email=request.args.get('email','').lower().strip()
    promos=load_db('promotions.json',[])
    result=[p for p in promos if (phone and p.get('product_owner_phone')==phone) or (email and p.get('product_owner_email','').lower()==email)]
    return jsonify(result[::-1])

# ===== API: APPROVE / REJECT PROMOTER =====
@sannlas_promotion_bp.route('/api/promote/action', methods=['POST'])
def promote_action():
    data=request.json or {}
    pid=int(data.get('id',0))
    action=data.get('action','approved')
    promos=load_db('promotions.json',[])
    for p in promos:
        if int(p.get('id'))==pid:
            p['status']=action
            break
    save_db('promotions.json',promos)
    return jsonify({"success":True,"message":f"Promoter {action}!"})

# ===== API: PROMO CLICK TRACKING (Optional) =====
@sannlas_promotion_bp.route('/api/promote/click', methods=['POST'])
def promo_click():
    data=request.json or {}
    clicks=load_db('promo_clicks.json',[])
    clicks.append({'product_id':data.get('product_id'),'promo':data.get('promo'),'ref':data.get('ref'),'time':time.time(),'ip':request.remote_addr})
    save_db('promo_clicks.json', clicks)
    return jsonify({'success':True})

# ===== API: PRODUCT PROMOTERS LIST =====
@sannlas_promotion_bp.route('/api/promote/product/<product_id>')
def product_promoters(product_id):
    promos=load_db('promotions.json',[])
    result=[p for p in promos if str(p.get('product_id'))==str(product_id) and p.get('status')=='approved']
    return jsonify(result)
