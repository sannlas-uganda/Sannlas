# sannlas_agency.py - AGENCY DASHBOARD FOR OPTION 1 - FINAL
# Ties: sannlas_permissions.py + sannlas_promotion.py + sannlas_commission.py
from flask import Blueprint, Response, request, jsonify
import os, json, time

sannlas_agency_bp = Blueprint('sannlas_agency_bp', __name__)

def load_db(file, default):
    try:
        from app import load_db as main_load
        return main_load(file, default)
    except:
        path = f'data/{file}'
        if os.path.exists(path):
            try: return json.load(open(path))
            except: return default
        return default

def save_db(file, data):
    try:
        from app import save_db as main_save
        return main_save(file, data)
    except:
        os.makedirs('data', exist_ok=True)
        json.dump(data, open(f'data/{file}','w'), indent=2)

# Import your security check
try:
    from sannlas_permissions import can_agent_do, get_permissions, save_permissions
except:
    # Fallback
    def can_agent_do(agent_phone, shop_slug, action):
        perms = load_db('sannlas_permissions.json', [])
        perm = next((x for x in perms if x['agent_phone']==agent_phone and x['shop_slug'].lower()==shop_slug.lower() and x['status']=='active'), None)
        if not perm: return False, "No permission"
        if action not in perm.get('scopes',[]): return False, f"Scope {action} denied"
        return True, "Allowed"

AGENCY_HTML = """
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agency Dashboard - Sannlas</title>
<style>
body{font-family:Arial;background:#f5f5f5;margin:0;padding:15px;padding-bottom:90px}
.card{background:#fff;border-radius:14px;padding:16px;margin-bottom:12px;box-shadow:0 2px 10px rgba(0,0,0,0.08)}
.btn{padding:12px 16px;border:none;border-radius:10px;font-weight:bold;cursor:pointer;margin:6px 0}
.btn-black{background:#000;color:#FFCC02;border:2px solid #FFCC02;width:100%}
.btn-green{background:#00c853;color:#fff;width:100%}
.btn-outline{background:#fff;border:2px solid #000;width:100%}
input,select{width:100%;padding:12px;border:1px solid #ccc;border-radius:10px;margin:8px 0;box-sizing:border-box}
.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:bold}
.badge-green{background:#e8f5e9;color:#2e7d32}
.badge-yellow{background:#fff8e1;color:#f57f17}
.shop-card{border-left:4px solid #FFCC02}
.stat{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #eee}
.nav{position:fixed;bottom:0;left:0;right:0;background:#fff;display:flex;justify-content:space-around;padding:12px;border-top:1px solid #ddd}
.nav a{text-decoration:none;color:#666;font-size:12px;text-align:center}
.nav a.active{color:#ff6f00;font-weight:bold}
.small{font-size:12px;color:#666}
h2,h3{margin:8px 0}
</style></head><body>

<h2>🧠 Agency Dashboard</h2>
<div class="card">
<div style="display:flex;gap:8px">
<div style="flex:1;background:#000;color:#FFCC02;padding:12px;border-radius:10px;text-align:center"><b id="statShops">0</b><br><small>Shops</small></div>
<div style="flex:1;background:#fff;border:2px solid #000;padding:12px;border-radius:10px;text-align:center"><b id="statProducts">0</b><br><small>Uploads</small></div>
<div style="flex:1;background:#00c853;color:#fff;padding:12px;border-radius:10px;text-align:center"><b id="statEarn">0</b><br><small>UGX Earned</small></div>
</div>
</div>

<div class="card">
<h3>🔀 Active Shop Context</h3>
<select id="shopSwitch" onchange="switchShop()"><option>Loading shops...</option></select>
<small class="small">You are now working AS this shop. Uploads will be credited to them.</small>
<div id="contextInfo" class="small" style="margin-top:8px"></div>
</div>

<div class="card">
<h3>📤 Quick Actions (As Selected Shop)</h3>
<button class="btn-black" onclick="goUpload()">➕ Upload Product for Shop</button>
<button class="btn-black" onclick="goPromote()">🚀 Promote Product for Shop</button>
<button class="btn-outline" onclick="loadMyClients()">🔄 Refresh</button>
</div>

<div class="card">
<h3>🏪 My Clients - Shops I Manage</h3>
<div id="myClients">Loading...</div>
</div>

<div class="card">
<h3>👥 My Helpers - People Helping ME</h3>
<small class="small">If you are also a shop owner</small>
<div style="display:flex;gap:6px;margin:10px 0">
<input id="helperPhone" placeholder="Helper phone e.g 0772123456">
<select id="helperPerm"><option value="upload_only">Upload Only (Safe)</option><option value="upload_and_promote" selected>Upload + Promote</option><option value="full_access">Full Access (Orders)</option></select>
</div>
<button class="btn-green" onclick="inviteHelper()">📩 Invite Helper</button>
<div id="myHelpers" style="margin-top:12px">Loading helpers...</div>
</div>

<div class="card">
<h3>💰 Recent Commissions</h3>
<div id="commissions">Loading...</div>
</div>

<div class="nav">
<a href="/">🏠 Home</a><a href="/agency" class="active">🧠 Agency</a><a href="/promote">🚀 Promote</a><a href="/balance">💰 Balance</a>
</div>

<script>
let user=JSON.parse(localStorage.getItem('sannlas_user')||'{}'); if(user.user) user=user.user;
let myPhone=user.phone||user.phone_number||''; let myEmail=(user.email||'').toLowerCase();
let activeShop=null;

async function loadMyClients(){
 let res=await fetch(`/api/agency/my-clients?phone=${myPhone}&email=${myEmail}`);
 let data=await res.json();
 let shops=data.shops||[];
 document.getElementById('statShops').innerText=shops.length;
 let totalProd=0,totalEarn=0;
 let html=''; let options='<option value="">-- Select Shop --</option>';
 if(!shops.length){ html='<small>No shops yet. Ask shop owner to add you as helper at /my-shop/collaborators</small>'; }
 else{
  shops.forEach(item=>{
   let perm=item.permission||item; let shop=item.shop||{};
   totalProd+=perm.products_uploaded||0; totalEarn+=perm.total_earned||0;
   let name=perm.shop_name||perm.shop_slug;
   options+=`<option value="${perm.shop_slug}" ${activeShop==perm.shop_slug?'selected':''}>${name} (${perm.shop_slug}) - ${perm.scopes.join(', ')}</option>`;
   html+=`<div class="card shop-card"><b>${name}</b> <span class="badge badge-green">${perm.status}</span><br><small>Slug: ${perm.shop_slug} | Scopes: ${perm.scopes.join(', ')}<br>Uploaded: ${perm.products_uploaded||0} | Earned: ${perm.total_earned||0} UGX | Per Upload: ${perm.commission_per_upload||400} UGX</small><br><button class="btn-black" onclick="selectShop('${perm.shop_slug}')">Switch to this shop</button></div>`;
  });
 }
 document.getElementById('myClients').innerHTML=html;
 document.getElementById('shopSwitch').innerHTML=options;
 document.getElementById('statProducts').innerText=totalProd;
 document.getElementById('statEarn').innerText=totalEarn;
 if(!activeShop && shops.length) selectShop(shops[0].permission.shop_slug);
 loadCommissions();
 loadMyHelpers();
}

function selectShop(slug){
 activeShop=slug; localStorage.setItem('sannlas_active_shop', slug);
 document.getElementById('contextInfo').innerHTML=`✅ Active: <b>${slug}</b> - All uploads now go to this shop`;
 document.getElementById('shopSwitch').value=slug;
 // Switch API
 fetch('/api/agency/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_phone:myPhone, shop_slug:slug})});
}

function switchShop(){
 let slug=document.getElementById('shopSwitch').value;
 if(slug) selectShop(slug);
}

function goUpload(){
 if(!activeShop){ alert('Select shop first!'); return; }
 // Redirect to your existing upload page with shop context
 window.location.href=`/upload?as_shop=${activeShop}&agent=${myPhone}`;
}

function goPromote(){
 if(!activeShop){ alert('Select shop first!'); return; }
 window.location.href=`/promote?as_shop=${activeShop}`;
}

async function loadMyHelpers(){
 let res=await fetch(`/api/agency/my-helpers?owner_phone=${myPhone}&email=${myEmail}`);
 let data=await res.json();
 let perms=data.permissions||[];
 let html='';
 if(!perms.length) html='<small>No helpers yet</small>';
 else perms.forEach(p=>{
  html+=`<div style="padding:10px;border-bottom:1px solid #eee"><b>${p.agent_name||p.agent_phone}</b> - ${p.agent_phone}<br><small>${p.scopes.join(', ')} | Uploaded: ${p.products_uploaded} | Status: ${p.status}</small><br><button onclick="revoke('${p.shop_slug}','${p.agent_phone}')" style="background:#ff1744;color:#fff;border:none;padding:6px 10px;border-radius:6px;margin-top:6px">Revoke</button></div>`;
 });
 document.getElementById('myHelpers').innerHTML=html;
}

async function inviteHelper(){
 let phone=document.getElementById('helperPhone').value.trim();
 let perm=document.getElementById('helperPerm').value;
 if(!phone){ alert('Enter helper phone'); return; }
 // Need shop_slug - use activeShop or first shop owned
 let shopSlug=activeShop || prompt('Enter your Shop Slug (e.g fashion-hub):');
 if(!shopSlug){ alert('Shop slug needed'); return; }
 let scopes=["upload_product","view_products","edit_own_product"];
 if(perm=='upload_and_promote') scopes=["upload_product","view_products","edit_own_product","view_orders"];
 if(perm=='full_access') scopes=["upload_product","view_products","view_orders","edit_own_product","delete_own_product"];
 
 let res=await fetch('/api/permissions/invite',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({shop_slug:shopSlug, owner_phone:myPhone, owner_email:myEmail, agent_phone:phone, scopes:scopes})});
 let d=await res.json(); alert(d.message); loadMyHelpers();
}

async function revoke(shop_slug, agent_phone){
 if(!confirm('Revoke access?')) return;
 let res=await fetch('/api/permissions/revoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({shop_slug:shop_slug, agent_phone:agent_phone, owner_phone:myPhone})});
 let d=await res.json(); alert(d.message); loadMyHelpers(); loadMyClients();
}

async function loadCommissions(){
 let res=await fetch(`/api/commission/list?agent_phone=${myPhone}`);
 let data=await res.json();
 let html='';
 if(!data.length) html='<small>No commissions yet</small>';
 else data.slice(0,10).forEach(c=>{
  html+=`<div class="stat"><span>${c.type} - ${c.shop_slug} <small>${new Date(c.time*1000).toLocaleDateString()}</small></span><b>${c.agent_amount} UGX</b></div>`;
 });
 document.getElementById('commissions').innerHTML=html;
}

loadMyClients();
</script></body></html>
"""

@sannlas_agency_bp.route('/agency')
@sannlas_agency_bp.route('/my-clients')
@sannlas_agency_bp.route('/agency-dashboard')
def agency_page():
    return Response(AGENCY_HTML, mimetype='text/html')

# ===== API: MY CLIENTS (Shops where I am helper) - wrapper for your permissions =====
@sannlas_agency_bp.route('/api/agency/my-clients')
def my_clients():
    phone = request.args.get('phone','').strip()
    email = request.args.get('email','').lower().strip()
    if not phone and not email:
        return jsonify({"success":False,"message":"Login first"}),401
    
    perms = load_db('sannlas_permissions.json', [])
    # filter active where agent_phone == my phone
    my_perms = [p for p in perms if (p.get('agent_phone')==phone) and p.get('status')=='active']
    
    shops_db = load_db('shops.json', [])
    result=[]
    for perm in my_perms:
        shop = next((s for s in shops_db if s.get('shop_slug','').lower()==perm['shop_slug'].lower() or s.get('slug','').lower()==perm['shop_slug'].lower()), None)
        result.append({"permission": perm, "shop": shop})
    
    return jsonify({"success":True,"shops":result})

# ===== API: MY HELPERS (People helping me) =====
@sannlas_agency_bp.route('/api/agency/my-helpers')
def my_helpers():
    owner_phone = request.args.get('owner_phone','').strip()
    email = request.args.get('email','').lower().strip()
    
    perms = load_db('sannlas_permissions.json', [])
    if owner_phone:
        filtered = [p for p in perms if p.get('owner_phone')==owner_phone and p.get('status')=='active']
    else:
        filtered = []
    
    return jsonify({"success":True,"permissions":filtered})

# ===== API: SWITCH CONTEXT =====
@sannlas_agency_bp.route('/api/agency/switch', methods=['POST'])
def switch_context():
    data=request.json or {}
    agent_phone=data.get('agent_phone','').strip()
    shop_slug=data.get('shop_slug','').lower().strip()
    
    if not agent_phone or not shop_slug:
        return jsonify({"success":False,"message":"agent_phone and shop_slug required"}),400
    
    allowed, reason = can_agent_do(agent_phone, shop_slug, "view_products")
    if not allowed:
        return jsonify({"success":False,"message":reason}),403
    
    return jsonify({"success":True,"message":f"Switched to {shop_slug}","active_shop":shop_slug})

# ===== API: AGENCY UPLOAD AS SHOP (Uses your permissions upload logic) =====
@sannlas_agency_bp.route('/api/agency/upload', methods=['POST'])
def agency_upload():
    data=request.json or {}
    shop_slug=data.get('shop_slug','').lower().strip()
    agent_phone=data.get('agent_phone','').strip()
    product=data.get('product',{})
    
    allowed, reason = can_agent_do(agent_phone, shop_slug, "upload_product")
    if not allowed:
        return jsonify({"success":False,"message":f"Permission denied: {reason}"}),403
    
    # Call your existing logic
    products=load_db('products.json', [])
    shops=load_db('shops.json', [])
    shop=next((s for s in shops if s.get('shop_slug','').lower()==shop_slug), None)
    if not shop:
        return jsonify({"success":False,"message":"Shop not found"}),404
    
    new_product={
        "id": int(time.time()*1000),
        "name": product.get('name',''),
        "price": product.get('price',0),
        "description": product.get('description',''),
        "image": product.get('image',''),
        "category": product.get('category','Other'),
        "shop_slug": shop_slug,
        "business": shop.get('business_name') or shop.get('name') or shop_slug,
        "seller_email": shop.get('owner_email',''),
        "phone": shop.get('phone',''),
        "uploaded_by_agent": agent_phone,
        "is_agent_upload": True,
        "created": time.time()
    }
    products.append(new_product)
    save_db('products.json', products)
    
    # Commission - Use your commission engine
    try:
        from sannlas_commission import split_and_record
        split_and_record("upload", 500, agent_phone, shop_slug, meta={"product_id":new_product['id'],"commission_per_upload":400})
    except:
        # Fallback
        comms=load_db('sannlas_commissions.json', [])
        comms.append({"id":int(time.time()*1000),"type":"upload","total_amount":500,"agent_phone":agent_phone,"shop_slug":shop_slug,"agent_amount":400,"sannlas_amount":100,"owner_amount":0,"time":time.time(),"status":"completed"})
        save_db('sannlas_commissions.json', comms)
    
    # Update permission stats
    perms=load_db('sannlas_permissions.json', [])
    for p in perms:
        if p['agent_phone']==agent_phone and p['shop_slug'].lower()==shop_slug.lower():
            p['products_uploaded']=p.get('products_uploaded',0)+1
            p['total_earned']=p.get('total_earned',0)+400
    save_db('sannlas_permissions.json', perms)
    
    return jsonify({"success":True,"message":"Product uploaded AS shop - Owner safe!","product":new_product})

# ===== API: AGENCY PROMOTE AS SHOP =====
@sannlas_agency_bp.route('/api/agency/promote-as-shop', methods=['POST'])
def agency_promote():
    """
    Helper promotes product on behalf of shop owner
    Uses promotion system but commission goes to shop owner, not helper?
    Or helper also earns? We make helper earn promo commission!
    """
    data=request.json or {}
    shop_slug=data.get('shop_slug','').lower().strip()
    agent_phone=data.get('agent_phone','').strip()
    product_id=str(data.get('product_id','')).strip()
    
    allowed, reason = can_agent_do(agent_phone, shop_slug, "view_products")
    if not allowed:
        return jsonify({"success":False,"message":reason}),403
    
    # Create promo link for agent - but sale still credits to shop owner, agent gets promo commission
    promos=load_db('promotions.json', [])
    import random, string
    code=f"AGENCY{product_id[:2]}{agent_phone[-3:]}{''.join(random.choices(string.ascii_uppercase+string.digits,k=3))}"
    
    products=load_db('products.json', [])
    prod=next((p for p in products if str(p.get('id'))==product_id), None)
    
    new_promo={
        "id":int(time.time()*1000),
        "product_id":product_id,
        "product_name":prod.get('name') if prod else product_id,
        "product_owner_phone":prod.get('phone') if prod else "",
        "shop_slug": shop_slug,
        "freelancer_phone": agent_phone,
        "freelancer_email": "",
        "is_agency_promo": True,
        "uploaded_by_agent": agent_phone,
        "commission_coins": int(prod.get('promo_commission',3)) if prod else 3,
        "promo_code": code,
        "status": "approved",
        "sales":0,
        "created": time.time()
    }
    promos.append(new_promo)
    save_db('promotions.json', promos)
    
    link=f"https://sannlas.onrender.com/?promo={code}&product={product_id}"
    return jsonify({"success":True,"message":"Agency promo link created!","promo":new_promo,"link":link})
