# sannlas_sell.py - SELL WITH COMMISSION FOR PROMOTERS - FINAL
from flask import Blueprint, Response, request, jsonify
import os, json, uuid, time
from datetime import datetime
from werkzeug.utils import secure_filename
import cloudinary.uploader

sannlas_sell_bp = Blueprint('sannlas_sell_bp', __name__)

def load_db(file, default):
    try:
        if os.path.exists(f'data/{file}'): return json.load(open(f'data/{file}'))
        if os.path.exists(file): return json.load(open(file))
        return default
    except: return default

def save_db(file, data):
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

def get_products(): return load_db('products.json', [])
def save_products(d): save_db('products.json', d)

COMBINED_SELL_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SELL - SANNLAS</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial;background:#c0392b;padding-bottom:80px}.navbar{background:#000;color:#fff;padding:10px;display:flex;justify-content:space-between;position:sticky;top:0;z-index:12}.btn{background:#000;color:#FFCC02;border:2px solid #FFCC02;padding:10px;border-radius:20px;font-weight:bold;cursor:pointer;width:100%}.btn-yellow{background:#FFCC02;color:#000}.search-bar{background:#111;padding:10px;display:flex;gap:6px;position:sticky;top:50px;z-index:11}.search-bar input,.search-bar select{padding:10px;border-radius:20px;border:none;flex:1}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;padding:10px}.card{background:#fff;border-radius:12px;overflow:hidden;cursor:pointer}.card img{width:100%;height:150px;object-fit:cover}.card-body{padding:8px}.sell-form{background:#fff;border-radius:12px;padding:15px;margin:10px;border:3px solid #FFCC02}.sell-form input,.sell-form textarea,.sell-form select{width:100%;padding:12px;margin:6px 0;border-radius:10px;border:1px solid #ddd}.hidden{display:none!important}</style>
</head><body>
<div class="navbar"><div><a href="/" style="color:#FFCC02;text-decoration:none;font-weight:bold">SANNLAS</a> | SELL</div><div><button onclick="showView('list')" style="background:#FFCC02;border:none;padding:6px 10px;border-radius:10px;font-weight:bold">Shop</button> <button onclick="showView('form')" style="background:#00FF00;border:none;padding:6px 10px;border-radius:10px;font-weight:bold">+ Sell</button></div></div>
<div id="listView"><div class="search-bar"><input id="q" placeholder="Search..." oninput="loadProducts()"><select id="cat" onchange="loadProducts()"><option value="">All</option><option>Electronics</option><option>Fashion</option><option>Home</option><option>Vehicles</option></select><select id="sort" onchange="loadProducts()"><option value="newest">Newest</option><option value="price_low">Low</option><option value="price_high">High</option></select></div><div style="background:#000;color:#FFCC02;padding:8px;text-align:center">MARKETPLACE - <span id="totalProducts">0</span> products</div><div id="productsGrid" class="grid"><p style="color:white;text-align:center;grid-column:1/-1;padding:30px">Loading...</p></div></div>

<div id="formView" class="hidden"><div class="sell-form"><h2 style="text-align:center">Sell Product (FREE)</h2>
<input id="pName" placeholder="Product Name *">
<textarea id="pDesc" placeholder="Description..." rows="3"></textarea>
<input id="pPrice" type="number" placeholder="Price UGX *">
<input id="pQty" type="number" value="1">
<select id="pCategory"><option>Electronics</option><option>Fashion</option><option>Home & Living</option><option>Vehicles</option><option>Property</option><option>Other</option></select>
<input id="pLocation" placeholder="Location">
<input id="pImage" type="file" accept="image/*">

<!-- 💰 COMMISSION FOR PROMOTERS - HERE ONLY, NOT IN REEL UPLOAD -->
<div style="background:#000;color:#FFCC02;padding:12px;border-radius:12px;margin:12px 0;border:2px solid #FFCC02">
  <b>💰 Commission for Promoters</b><br>
  <small style="color:#fff">How much promoter earns when they promote?</small><br><br>
  <select id="pPromoCoins" style="width:100%;padding:12px;border-radius:10px;font-weight:900;">
    <option value="0">No promotion - 0 coins</option>
    <option value="1">1 coin = 599 UGX</option>
    <option value="2">2 coins = 1,198 UGX</option>
    <option value="3" selected>3 coins = 1,797 UGX ⭐ Popular</option>
    <option value="5">5 coins = 2,995 UGX 🔥 Hot</option>
    <option value="10">10 coins = 5,990 UGX 👑 Boss</option>
  </select>
  <div id="promoPreview" style="margin-top:8px;font-size:12px;color:#00ff88">✅ Promoter will earn 3 coins = 1,797 UGX per sale</div>
  <div style="margin-top:6px;font-size:11px;color:#aaa">This creates PROMOTE button on reels automatically!</div>
</div>

<button class="btn btn-yellow" onclick="createProduct()" style="margin-top:10px;padding:15px;font-size:16px">🚀 Post Product</button>
<p id="status" style="text-align:center;margin-top:8px;font-weight:bold"></p></div></div>

<div id="detailView" class="hidden"><div style="background:#000;padding:8px"><a href="javascript:showView('list')" style="color:#FFCC02;text-decoration:none">← Back</a></div><div id="productBox" style="background:#fff;border-radius:12px;margin:10px;overflow:hidden">Loading...</div></div>
<script>
let currentUser=JSON.parse(localStorage.getItem('sannlas_user')||'{}');
function showView(v){document.getElementById('listView').classList.toggle('hidden',v!=='list');document.getElementById('formView').classList.toggle('hidden',v!=='form');document.getElementById('detailView').classList.toggle('hidden',v!=='detail');if(v=='list')loadProducts();}
let parts=location.pathname.split('/').filter(Boolean);
if(parts[0]=='sell'&&parts[1]){loadDetail(parts[1]);}else{showView('list');}
async function loadProducts(){let q=document.getElementById('q').value;let cat=document.getElementById('cat').value;let sort=document.getElementById('sort').value;let url=`/api/products?q=${encodeURIComponent(q)}&category=${encodeURIComponent(cat)}&sort=${sort}`;try{let r=await fetch(url);let prods=await r.json();if(!Array.isArray(prods))prods=[];if(sort=='price_low')prods.sort((a,b)=>(a.price||0)-(b.price||0));else if(sort=='price_high')prods.sort((a,b)=>(b.price||0)-(a.price||0));else prods.sort((a,b)=>(b.created||0)-(a.created||0));document.getElementById('totalProducts').innerText=prods.length;if(prods.length==0){document.getElementById('productsGrid').innerHTML='<p style="color:white;grid-column:1/-1;text-align:center">No products</p>';return;}document.getElementById('productsGrid').innerHTML=prods.map(p=>`<div class="card" onclick="location.href='/sell/${p.id}'"><img src="${p.image||'https://via.placeholder.com/200'}"><div class="card-body"><b>${(p.name||'').slice(0,25)}</b><br><small>${p.location||''}</small><br><b style="color:#c0392b">UGX ${Number(p.price||0).toLocaleString()}</b><br><small style="color:#00aa00">${p.promo_coins?`💰 ${p.promo_coins} coins promo`:''}</small></div></div>`).join('');}catch(e){document.getElementById('productsGrid').innerHTML='Error: '+e.message;}}
async function loadDetail(id){showView('detail');let r=await fetch(`/api/products/${id}`);let p=await r.json();if(!p.id){document.getElementById('productBox').innerHTML='Not found';return;}document.getElementById('productBox').innerHTML=`<img src="${p.image||''}" style="width:100%;height:300px;object-fit:cover"><div style="padding:15px"><h2>${p.name}</h2><p>${p.description||''}</p><h3>UGX ${Number(p.price||0).toLocaleString()}</h3><p>${p.location} | Qty: ${p.quantity}</p><p style="color:green;font-weight:900">${p.promo_coins?`💰 Promo: ${p.promo_coins} coins = ${(p.promo_coins*599).toLocaleString()} UGX`:''}</p><button class="btn btn-yellow" onclick="window.open('https://wa.me/${(p.phone||'').replace(/[^0-9]/g,'')}')">Contact ${p.phone||''}</button></div>`;}
async function createProduct(){let name=document.getElementById('pName').value;let price=document.getElementById('pPrice').value;if(!name||!price){alert('Name and Price required');return;}if(!currentUser.phone){alert('Login first');return;}document.getElementById('status').innerText='⏳ Uploading...';let fd=new FormData();fd.append('name',name);fd.append('description',document.getElementById('pDesc').value);fd.append('price',price);fd.append('quantity',document.getElementById('pQty').value);fd.append('category',document.getElementById('pCategory').value);fd.append('location',document.getElementById('pLocation').value);fd.append('phone',currentUser.phone);fd.append('email',currentUser.email);
let promoCoins=document.getElementById('pPromoCoins').value;
fd.append('promo_coins',promoCoins);
fd.append('promo_commission',promoCoins);
fd.append('commission_percent',(promoCoins*1.2).toFixed(1)+'%');
let file=document.getElementById('pImage').files[0];if(file)fd.append('images',file);let r=await fetch('/api/products/create',{method:'POST',body:fd});let d=await r.json();document.getElementById('status').innerText=d.message;if(d.success)location.href='/sell/'+d.product.id;}

document.getElementById('pPromoCoins').addEventListener('change', function(){
  let c=this.value; let ugx=c*599;
  document.getElementById('promoPreview').innerHTML=c==0?'❌ No promotion':'✅ Promoter will earn '+c+' coins = '+ugx.toLocaleString()+' UGX per sale';
});
loadProducts();
</script>
</body></html>
"""

@sannlas_sell_bp.route('/sell')
@sannlas_sell_bp.route('/sell/<path:pid>')
def sell_page(pid=None):
    return Response(COMBINED_SELL_HTML, mimetype='text/html')

@sannlas_sell_bp.route('/api/products')
def api_products():
    q = request.args.get('q','').lower()
    category = request.args.get('category','').lower()
    sort = request.args.get('sort','newest')
    products = get_products()
    filtered = products[:]
    if q:
        filtered = [p for p in filtered if q in str(p.get('name','')).lower() or q in str(p.get('description','')).lower()]
    if category:
        filtered = [p for p in filtered if category in str(p.get('category','')).lower()]
    if sort == 'price_low':
        filtered = sorted(filtered, key=lambda x: float(x.get('price',0) or 0))
    elif sort == 'price_high':
        filtered = sorted(filtered, key=lambda x: float(x.get('price',0) or 0), reverse=True)
    else:
        filtered = sorted(filtered, key=lambda x: x.get('created',0), reverse=True)
    return jsonify(filtered[:150])

@sannlas_sell_bp.route('/api/products/<path:pid>')
def api_single(pid):
    products = get_products()
    prod = next((p for p in products if str(p.get('id')) == str(pid)), None)
    if not prod:
        return jsonify({'success':False}),404
    return jsonify(prod)

@sannlas_sell_bp.route('/api/products/create', methods=['POST'])
def api_create():
    name = request.form.get('name','').strip()
    description = request.form.get('description','')
    price = request.form.get('price','0')
    quantity = request.form.get('quantity','1')
    category = request.form.get('category','Other')
    location = request.form.get('location','Kampala')
    phone = request.form.get('phone','')
    email = request.form.get('email','')
    if not name or not price:
        return jsonify({'success':False,'message':'Name and price required'}),400
    image_url = ""
    files = request.files.getlist('images')
    if files and files[0].filename:
        try:
            res = cloudinary.uploader.upload(files[0], folder="sannlas/products")
            image_url = res['secure_url']
        except:
            try:
                filename = f"{int(time.time())}_{secure_filename(files[0].filename)}"
                os.makedirs('static/uploads', exist_ok=True)
                path = os.path.join('static/uploads', filename)
                files[0].save(path)
                image_url = f"/static/uploads/{filename}"
            except:
                image_url = ""
    prod = {}
    prod['id'] = str(uuid.uuid4())[:8]
    prod['name'] = name
    prod['description'] = description
    prod['price'] = float(price)
    prod['quantity'] = quantity
    prod['category'] = category
    prod['location'] = location
    prod['phone'] = phone
    prod['seller_email'] = email.lower() if email else ''
    prod['image'] = image_url
    prod['promo_coins'] = int(request.form.get('promo_coins', 0) or 0)
    prod['promo_commission'] = int(request.form.get('promo_commission', 0) or 0)
    prod['commission_percent'] = request.form.get('commission_percent','0%')
    prod['promo_link'] = f"/promotion/{prod['id']}?commission={prod['promo_coins']}"
    prod['buy_link'] = f"/product/{prod['id']}"
    prod['created'] = time.time()
    prod['created_at'] = datetime.utcnow().isoformat()
    prod['views'] = 0
    prod['sold'] = 0
    products = get_products()
    products.append(prod)
    save_products(products)
    return jsonify({'success':True,'message':'✅ Product posted with '+str(prod['promo_coins'])+' coins promo!','product':prod})

@sannlas_sell_bp.route('/api/my-products')
def api_my():
    phone = request.args.get('phone','')
    email = request.args.get('email','').lower().strip()
    products = get_products()
    result = [p for p in products if (phone and p.get('phone')==phone) or (email and p.get('seller_email','').lower()==email)]
    return jsonify(result[::-1])
