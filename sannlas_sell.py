# sannlas_sell.py - ONE FILE = SELL LIST + UPLOAD + DETAIL + ALL APIS - FINAL FIXED
from flask import Blueprint, Response, request, jsonify
import os, json, uuid, time, base64
from datetime import datetime
from werkzeug.utils import secure_filename
import cloudinary.uploader

sannlas_sell_bp = Blueprint('sannlas_sell_bp', __name__)

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

def get_products():
    return load_db('products.json', [])

def save_products(d):
    save_db('products.json', d)

COMBINED_SELL_HTML = '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SELL - SANNLAS</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial;background:#c0392b;padding-bottom:80px}.navbar{background:#000;color:#fff;padding:10px;display:flex;justify-content:space-between;position:sticky;top:0;z-index:12}.btn{background:#000;color:#FFCC02;border:2px solid #FFCC02;padding:10px;border-radius:20px;font-weight:bold;cursor:pointer;width:100%}.btn-yellow{background:#FFCC02;color:#000}.search-bar{background:#111;padding:10px;display:flex;gap:6px;position:sticky;top:50px;z-index:11}.search-bar input,.search-bar select{padding:10px;border-radius:20px;border:none;flex:1}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;padding:10px}.card{background:#fff;border-radius:12px;overflow:hidden;cursor:pointer}.card img{width:100%;height:150px;object-fit:cover}.card-body{padding:8px}.upload-box{background:#fff;border-radius:12px;padding:15px;margin:10px;border:3px solid #FFCC02}.upload-box input,.upload-box textarea,.upload-box select{width:100%;padding:12px;margin:6px 0;border-radius:10px;border:1px solid #ddd}.hidden{display:none!important}</style>
</head><body>
<div class="navbar"><div><a href="/" style="color:#FFCC02;text-decoration:none;font-weight:bold">SANNLAS</a> | <span id="navText">SELL</span></div><div><button onclick="showView('sell')" style="background:#FFCC02;border:none;padding:6px 10px;border-radius:10px;font-weight:bold">Shop</button> <button onclick="showView('upload')" style="background:#00FF00;border:none;padding:6px 10px;border-radius:10px;font-weight:bold">+ Sell</button></div></div>
<div id="sellView"><div class="search-bar"><input id="q" placeholder="Search products..." oninput="loadProducts()"><select id="cat" onchange="loadProducts()"><option value="">All</option><option>Electronics</option><option>Fashion</option><option>Home</option></select><select id="sort" onchange="loadProducts()"><option value="newest">Newest</option><option value="price_low">Low Price</option><option value="price_high">High Price</option></select></div><div style="background:#000;color:#FFCC02;padding:8px;text-align:center;font-weight:bold">MARKETPLACE - <span id="totalProducts">0</span> products</div><div id="productsGrid" class="grid"><p style="color:white;text-align:center;grid-column:1/-1;padding:30px">Loading...</p></div></div>
<div id="uploadView" class="hidden"><div class="upload-box"><h2 style="text-align:center">Sell Product (FREE)</h2><input id="pName" placeholder="Product Name"><textarea id="pDesc" placeholder="Description..." rows="3"></textarea><input id="pPrice" type="number" placeholder="Price UGX"><input id="pQty" type="number" placeholder="Quantity" value="1"><select id="pCategory"><option>Electronics</option><option>Fashion</option><option>Home & Living</option><option>Vehicles</option><option>Property</option><option>Other</option></select><input id="pLocation" placeholder="Location e.g. Kampala"><input id="pImage" type="file" accept="image/*" multiple><p id="imgPreview" style="display:flex;gap:5px;flex-wrap:wrap"></p><label><input type="checkbox" id="pNegotiable" checked> Negotiable</label><br><br><button class="btn btn-yellow" onclick="uploadProduct()">Upload Product Now</button><p id="uploadStatus" style="text-align:center;margin-top:8px;font-weight:bold"></p></div></div>
<div id="detailView" class="hidden"><div style="background:#000;padding:8px"><a href="javascript:showView('sell')" style="color:#FFCC02;text-decoration:none">Back to Shop</a></div><div id="productBox" class="card" style="margin:10px;padding:0"><p style="padding:20px">Loading...</p></div></div>
<script>
let currentUser=JSON.parse(localStorage.getItem('sannlas_user')||'{}');let view='sell';
function showView(v){document.getElementById('sellView').classList.toggle('hidden',v!=='sell');document.getElementById('uploadView').classList.toggle('hidden',v!=='upload');document.getElementById('detailView').classList.toggle('hidden',v!=='detail');view=v;if(v=='sell')loadProducts();}
let parts=location.pathname.split('/').filter(Boolean);if(parts[0]=='sell'&&parts[1]){loadProductDetail(parts[1]);}else{showView('sell');}
async function loadProducts(){let q=document.getElementById('q').value;let cat=document.getElementById('cat').value;let sort=document.getElementById('sort').value;let url=`/api/products?q=${encodeURIComponent(q)}&category=${encodeURIComponent(cat)}&sort=${sort}`;try{let r=await fetch(url);let prods=await r.json();if(!Array.isArray(prods))prods=[];prods.sort((a,b)=>{if(sort=='price_low')return(a.price||0)-(b.price||0);if(sort=='price_high')return(b.price||0)-(a.price||0);return(b.created||0)-(a.created||0);});document.getElementById('totalProducts').innerText=prods.length;if(prods.length==0){document.getElementById('productsGrid').innerHTML='<p style="color:white;grid-column:1/-1;text-align:center">No products yet - be first to sell!</p>';return;}document.getElementById('productsGrid').innerHTML=prods.map(p=>`<div class="card" onclick="location.href='/sell/${p.id}'"><img src="${p.image||'https://via.placeholder.com/200'}"><div class="card-body"><b style="font-size:13px">${(p.name||'').slice(0,30)}</b><br><small>${p.location||'Kampala'}</small><br><b style="color:#c0392b">UGX ${Number(p.price||0).toLocaleString()}</b></div></div>`).join('');}catch(e){document.getElementById('productsGrid').innerHTML='<p style="color:red">Failed: '+e.message+'</p>';}}
async function loadProductDetail(id){showView('detail');let r=await fetch(`/api/products/${id}`);let p=await r.json();if(!p.id){document.getElementById('productBox').innerHTML='Not found';return;}document.getElementById('productBox').innerHTML=`<img src="${p.image||'https://via.placeholder.com/400'}" style="width:100%;height:300px;object-fit:cover"><div style="padding:15px"><h2>${p.name}</h2><p>${p.description||''}</p><h3 style="color:#c0392b">UGX ${Number(p.price||0).toLocaleString()}</h3><p>${p.location} | ${p.quantity} | ${p.phone}</p><button class="btn btn-yellow" onclick="contactSeller('${p.phone}')">Contact Seller</button></div>`;}
async function uploadProduct(){let name=document.getElementById('pName').value;let price=document.getElementById('pPrice').value;if(!name||!price){alert('Enter name and price!');return;}if(!currentUser.phone){alert('Login first!');location.href='/';return;}document.getElementById('uploadStatus').innerText='Uploading...';let fd=new FormData();fd.append('name',name);fd.append('description',document.getElementById('pDesc').value);fd.append('price',price);fd.append('quantity',document.getElementById('pQty').value);fd.append('category',document.getElementById('pCategory').value);fd.append('location',document.getElementById('pLocation').value);fd.append('negotiable',document.getElementById('pNegotiable').checked);fd.append('phone',currentUser.phone);fd.append('email',currentUser.email);fd.append('business',currentUser.business||'');let files=document.getElementById('pImage').files;for(let i=0;i<files.length;i++){fd.append('images',files[i]);}try{let r=await fetch('/api/products/create',{method:'POST',body:fd});let d=await r.json();document.getElementById('uploadStatus').innerText=d.message||'Done!';if(d.success){setTimeout(()=>{location.href='/sell/'+d.product.id},800);}}catch(e){document.getElementById('uploadStatus').innerText='Error: '+e.message;}}
function contactSeller(phone){if(phone)window.open('https://wa.me/'+phone.replace(/[^0-9]/g,''),'_blank');}
loadProducts();
</script>
</body></html>
'''

@sannlas_sell_bp.route('/sell')
@sannlas_sell_bp.route('/sell/<path:pid>')
@sannlas_sell_bp.route('/upload')
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
def api_product_single(pid):
    products = get_products()
    prod = next((p for p in products if str(p.get('id')) == str(pid)), None)
    if not prod:
        return jsonify({'success':False}),404
    return jsonify(prod)

@sannlas_sell_bp.route('/api/products/create', methods=['POST'])
def api_create_product():
    name = request.form.get('name','').strip()
    description = request.form.get('description','')
    price = request.form.get('price','0')
    quantity = request.form.get('quantity','1')
    category = request.form.get('category','Other')
    location = request.form.get('location','Kampala')
    phone = request.form.get('phone','')
    email = request.form.get('email','')
    business = request.form.get('business','')
    negotiable = request.form.get('negotiable','true')

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
            except Exception as e:
                image_url = ""

    prod = {}
    prod['id'] = str(uuid.uuid4())[:8]
    prod['name'] = name
    prod['title'] = name
    prod['description'] = description
    prod['price'] = float(price)
    prod['quantity'] = quantity
    prod['category'] = category
    prod['location'] = location
    prod['district'] = location
    prod['phone'] = phone
    prod['seller_email'] = email.lower() if email else ''
    prod['email'] = email.lower() if email else ''
    prod['business'] = business
    prod['negotiable'] = negotiable
    prod['image'] = image_url
    prod['images'] = [image_url] if image_url else []
    prod['created'] = time.time()
    prod['created_at'] = datetime.utcnow().isoformat()
    prod['views'] = 0
    prod['sold'] = 0
    prod['shop_slug'] = business.lower().replace(' ','-') if business else 'shop'

    products = get_products()
    products.append(prod)
    save_products(products)

    return jsonify({'success':True,'message':'Product uploaded FREE!','product':prod})

@sannlas_sell_bp.route('/api/my-products')
def api_my_products():
    phone = request.args.get('phone','')
    email = request.args.get('email','').lower().strip()
    products = get_products()
    result = [p for p in products if (phone and p.get('phone')==phone) or (email and p.get('seller_email','').lower()==email)]
    return jsonify(result[::-1])
