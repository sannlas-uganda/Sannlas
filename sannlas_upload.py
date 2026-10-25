# sannlas_upload.py - ONE FILE = UPLOAD PAGE + REELS UPLOAD POST + MY PRODUCTS API - FINAL SEPARATED
from flask import Blueprint, Response, request, jsonify
import os, json, time, traceback, cloudinary, cloudinary.uploader
import psycopg2

sannlas_upload_bp = Blueprint('sannlas_upload_bp', __name__)

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

def get_conn():
    DATABASE_URL = os.getenv('DATABASE_URL')
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def ensure_reels_table():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_reels (
      id BIGSERIAL PRIMARY KEY, 
      user_email TEXT, user_name TEXT, shop_name TEXT, shop_slug TEXT,
      caption TEXT, description TEXT, price TEXT, promo_link TEXT,
      location TEXT, hashtags TEXT, video_url TEXT, product_link TEXT,
      product_id TEXT, likes INT DEFAULT 0, created TIMESTAMP DEFAULT NOW())""")
    conn.commit(); cur.close(); conn.close()

def load_db(file, default):
    try:
        if os.path.exists(f'data/{file}'):
            return json.load(open(f'data/{file}'))
        if os.path.exists(file):
            return json.load(open(file))
        return default
    except: return default

def save_db(file, data):
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

UPLOAD_HTML = """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1"><title>Upload Reel - Sannlas</title><style>*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,Arial}body{background:#fff;color:#111;min-height:100vh;padding-bottom:90px}.header{background:#000;padding:12px 15px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:99}.header a{color:#FFCC02;text-decoration:none;font-weight:900;font-size:14px}.header b{color:#FFCC02}.container{max-width:500px;margin:0 auto;padding:15px}.card{background:#fff;border-radius:16px;padding:15px;margin-bottom:15px;border:1px solid #eee;box-shadow:0 2px 8px rgba(0,0,0,.04)}label{display:block;font-size:12px;color:#111;font-weight:900;margin:14px 0 6px 2px}label:first-child{margin-top:0}input,textarea,select{width:100%;background:#fff;color:#111;border:1.5px solid #ddd;border-radius:12px;padding:13px 14px;font-size:14px;outline:none}input:focus,textarea:focus,select:focus{border-color:#000}.hint{font-size:11px;color:#888;margin-top:4px}.video-box{border:2px dashed #ccc;border-radius:16px;padding:20px;text-align:center;background:#fafafa;cursor:pointer;overflow:hidden}.video-box.has-video{border-color:#000;padding:0}.video-box video{width:100%;max-height:350px;display:block;border-radius:16px}.btn-post{width:100%;background:#000;color:#FFCC02;padding:16px;border:none;border-radius:30px;font-weight:900;font-size:16px;margin-top:20px;cursor:pointer}.btn-post:disabled{background:#ccc}.badge{background:#FFCC02;color:#000;padding:3px 8px;border-radius:10px;font-size:10px;font-weight:900}.new-field{background:#FFFBE6;border:1.5px solid #FFCC02 !important;}</style></head><body><div class="header"><a href="/">← Home</a><b>SANNLAS UPLOAD</b><a href="/reels">Reels</a></div><div class="container"><div class="card"><label>📹 UPLOAD VIDEO * <span class="badge">Required</span></label><div class="video-box" id="videoBox" onclick="document.getElementById('videoInput').click()"><div id="videoPlaceholder"><div style="font-size:40px">🎥</div><b>Tap to select video</b><br><span class="hint">MP4, MOV - Max 100MB</span></div><video id="videoPreview" style="display:none" controls playsinline muted></video></div><input type="file" id="videoInput" accept="video/*" style="display:none"><div class="hint" id="videoInfo"></div></div><div class="card"><label>🛍️ SELECT PRODUCT FROM YOUR SHOP * <span class="badge">ONLY YOUR SHOP</span></label><select id="productSelect" onchange="onProductSelected()"><option value="">⏳ Loading ONLY your products...</option></select><div class="hint" id="loadHint">Tap card below to go to MY SHOP page!</div><div id="selectedProductPreview" style="display:none;margin-top:12px;background:#f8fafc;border:1.5px solid #000;border-radius:12px;padding:10px;cursor:pointer" onclick="goToMyShop()"><div style="display:flex;gap:10px;align-items:center"><img id="selImg" src="" style="width:60px;height:60px;border-radius:12px;object-fit:cover"><div style="flex:1"><b id="selName">Product</b><br><span style="font-weight:900" id="selPrice">UGX 0</span> • <span id="selShop" style="font-size:12px"></span><div style="margin-top:6px"><span style="background:#000;color:#FFCC02;padding:6px 12px;border-radius:20px;font-size:11px;font-weight:900;display:inline-block">🏪 GO TO MY SHOP →</span></div></div><div style="font-size:20px">➡️</div></div></div><div style="margin-top:10px;display:flex;gap:8px"><button onclick="goToMyShop()" type="button" style="flex:1;background:#fff;border:1.5px solid #000;border-radius:12px;padding:12px;font-weight:900;font-size:13px">🏪 MY SHOP PAGE</button><button onclick="goToProduct()" id="viewProductBtn" type="button" style="flex:1;display:none;background:#FFCC02;border:1.5px solid #000;border-radius:12px;padding:12px;font-weight:900;font-size:13px">👁️ VIEW PRODUCT</button></div><label>🏪 SHOP NAME *</label><input type="text" id="shopName" placeholder="e.g. STEPH" readonly><label>📝 DESCRIPTION *</label><textarea id="description" rows="3" placeholder="Auto-filled from product"></textarea>

<!-- ✅✅ NEW - LINK SPACE - YOU ASKED FOR THIS BOSS! ✅✅ -->
<label>🔗 PROMO / AFFILIATE LINK <span class="badge" style="background:#000;color:#FFCC02">NEW</span></label>
<input type="text" id="promoLink" class="new-field" placeholder="Paste your link here - e.g. https://sannlas.com/product/123 or your YouTube, WhatsApp link">
<div class="hint">Leave empty = will use product link automatically. Put any link: your shop, WhatsApp, YouTube!</div>

<label>💰 EARN / COMMISSION <span style="color:#888;font-weight:400">(Optional)</span></label>
<input type="text" id="promoCommission" class="new-field" placeholder="e.g. 5000 or 10% - shows on PROMOTE & EARN button">
<div class="hint">This amount will show: 💸 PROMOTE & EARN 5,000</div>
<!-- ✅✅ END NEW FIELDS ✅✅ -->

<label>💬 CAPTION</label><textarea id="caption" rows="2" placeholder="e.g. New collection just landed! 🔥"></textarea><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><div><label>📍 LOCATION</label><input type="text" id="location" placeholder="Kampala"></div><div><label>💰 PRICE (Auto)</label><input type="number" id="price" placeholder="Auto" readonly style="background:#f1f5f9"></div></div><input type="hidden" id="productId"><input type="hidden" id="shopSlug"><button class="btn-post" id="postBtn" onclick="uploadReel()">🚀 POST REEL</button><div class="hint" style="text-align:center;margin-top:8px">Preview: <b id="previewBtn">UGX 0 - BUY NOW</b> + <b style="color:#000;background:#FFCC02;padding:2px 6px;border-radius:10px">💸 PROMOTE & EARN</b></div></div></div><script>
let videoFile=null;let user=JSON.parse(localStorage.getItem('sannlas_user')||localStorage.getItem('user')||'{}');if(user.user)user=user.user;let myProducts=[];document.getElementById('shopName').value=user.business_name||user.business||user.shop_name||'';document.getElementById('location').value=user.location||'Kampala';
function getShopSlug(){let slug=document.getElementById('shopSlug').value;if(slug)return slug;let name=document.getElementById('shopName').value||'';return name.toLowerCase().replace(/\\s+/g,'-').replace(/[^a-z0-9\\-]/g,'');}
function goToMyShop(){let slug=getShopSlug();if(!slug){alert('Select product first Boss!');return;}window.open('/shop/'+slug,'_blank');}
function goToProduct(){let pid=document.getElementById('productId').value;if(!pid){alert('Select product first');return;}window.open('/product/'+pid,'_blank');}
async function loadMyProducts(){try{let email=(user.email||'').toLowerCase();let phone=user.phone||'';let sel=document.getElementById('productSelect');let hint=document.getElementById('loadHint');if(!email&&!phone){sel.innerHTML='<option value="">❌ Not logged in! Login again</option>';return;}hint.innerText='Loading for: '+(email||phone)+' ...';let url='/api/my-products?email='+encodeURIComponent(email)+'&phone='+encodeURIComponent(phone)+'&t='+Date.now();let r=await fetch(url);let products=await r.json();if(email){products=products.filter(p=> (p.seller_email||p.email||p.user_email||'').toLowerCase().trim()===email);}myProducts=products;if(!products||products.length==0){sel.innerHTML='<option value="">❌ No products in YOUR shop - Upload product first</option>';hint.innerText='Found 0 for '+email;return;}sel.innerHTML='<option value="">-- Select from YOUR shop ('+products.length+') --</option>'+products.map(p=>{let pid=p.id;let name=(p.name||'Product').replace(/"/g,'');let price=p.price||0;let img=p.image||'';return '<option value="'+pid+'" data-price="'+price+'" data-name="'+name+'" data-shop="'+(p.shop_slug||'')+'" data-img="'+img+'" data-desc="'+(p.description||'').replace(/"/g,'')+'" data-business="'+(p.business||'').replace(/"/g,'')+'">'+name+' - UGX '+Number(price).toLocaleString()+'</option>';}).join('');hint.innerText='✅ Found '+products.length+' - ONLY YOUR SHOP - Tap card to go to My Shop!';}catch(e){document.getElementById('productSelect').innerHTML='<option>Error: '+e.message+'</option>';}}
loadMyProducts();
function onProductSelected(){let sel=document.getElementById('productSelect');let opt=sel.selectedOptions[0];if(!opt||!opt.value)return;let pid=opt.value;let price=opt.dataset.price;let name=opt.dataset.name;let shop=opt.dataset.shop||document.getElementById('shopName').value;let img=opt.dataset.img;let desc=opt.dataset.desc;let business=opt.dataset.business||shop;document.getElementById('productId').value=pid;document.getElementById('price').value=price;if(business)document.getElementById('shopName').value=business;let slug=(shop||business).toLowerCase().replace(/\\s+/g,'-').replace(/[^a-z0-9\\-]/g,'');document.getElementById('shopSlug').value=slug;document.getElementById('description').value=desc||name;
// AUTO FILL LINK - but now user can EDIT it!
let autoLink='/product/'+pid;
if(document.getElementById('promoLink').value.trim()==''){document.getElementById('promoLink').value=autoLink;}
document.getElementById('selectedProductPreview').style.display='block';document.getElementById('viewProductBtn').style.display='block';document.getElementById('selImg').src=img||'https://via.placeholder.com/60';document.getElementById('selName').innerText=name;document.getElementById('selPrice').innerText='UGX '+Number(price).toLocaleString();document.getElementById('selShop').innerText=business;document.getElementById('previewBtn').innerText='UGX '+Number(price).toLocaleString()+' - BUY NOW';}
document.getElementById('videoInput').addEventListener('change',function(e){let file=e.target.files[0];if(!file)return;if(file.size>100*1024*1024){alert('Too big! Max 100MB');return;}videoFile=file;let url=URL.createObjectURL(file);let v=document.getElementById('videoPreview');v.src=url;v.style.display='block';document.getElementById('videoPlaceholder').style.display='none';document.getElementById('videoBox').classList.add('has-video');document.getElementById('videoInfo').innerText=file.name+' ('+(file.size/1024/1024).toFixed(1)+' MB)';});
async function uploadReel(){let shopName=document.getElementById('shopName').value.trim();let description=document.getElementById('description').value.trim();let caption=document.getElementById('caption').value.trim();let location=document.getElementById('location').value.trim();let price=document.getElementById('price').value.trim();let productId=document.getElementById('productId').value.trim();let promoLink=document.getElementById('promoLink').value.trim();let promoCommission=document.getElementById('promoCommission').value.trim();if(!videoFile){alert('Select video first Boss!');return;}if(!productId){alert('SELECT PRODUCT FROM YOUR SHOP FIRST!');return;}if(!shopName){alert('Shop name missing');return;}let btn=document.getElementById('postBtn');btn.disabled=true;btn.innerText='⏳ Uploading...';try{let fd=new FormData();fd.append('video',videoFile);fd.append('shop_name',shopName);fd.append('business_name',shopName);fd.append('shop_slug',getShopSlug());fd.append('description',description);fd.append('caption',(description+'\\n'+caption).trim());fd.append('location',location);fd.append('price',price);fd.append('product_id',productId);fd.append('promo_link',promoLink);fd.append('promo_commission',promoCommission);fd.append('product_link',promoLink||'/product/'+productId);fd.append('user_email',user.email||'');fd.append('user_name',shopName);fd.append('user_id',user.email||shopName);let r=await fetch('/api/sannlas/reels/upload',{method:'POST',body:fd});let d=await r.json();if(!r.ok)throw new Error(d.error||d.message||'Upload failed');alert('✅ Posted! Link saved: '+(promoLink||'/product/'+productId));location.href='/reels';}catch(e){alert('❌ Failed: '+e.message);console.log(e);btn.disabled=false;btn.innerText='🚀 POST REEL';}}
</script></body></html>
"""

@sannlas_upload_bp.route('/upload')
@sannlas_upload_bp.route('/upload-reel')
@sannlas_upload_bp.route('/post-reel')
def upload_page():
    return Response(UPLOAD_HTML, mimetype='text/html')

@sannlas_upload_bp.route('/api/my-products')
def my_products():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    products = load_db('products.json', [])
    if not email and not phone: return jsonify([])
    filtered = []
    for p in products:
        seller_email = str(p.get('seller_email','') or p.get('email','') or p.get('user_email','')).lower().strip()
        seller_phone = str(p.get('phone','') or p.get('seller_phone','') or '').strip()
        if email and seller_email == email: filtered.append(p)
        elif phone and seller_phone == phone and not email: filtered.append(p)
    filtered = sorted(filtered, key=lambda x: x.get('created',0) or x.get('id',0), reverse=True)
    return jsonify(filtered)

@sannlas_upload_bp.route('/api/sannlas/reels/upload', methods=['POST'])
def upload_reel_post():
    try:
        print("=== REELS UPLOAD START - WITH LINK FIELD ===")
        video = request.files.get('video')
        if not video:
            return jsonify({'success':False, 'error':'No video file - Select video Boss!'}),400
        
        shop_name = request.form.get('shop_name') or request.form.get('business_name') or 'SANNLAS SHOP'
        shop_slug = (request.form.get('shop_slug') or shop_name).lower().replace(' ','-')
        description = request.form.get('description', '')
        caption = request.form.get('caption', description)
        price = request.form.get('price', '0')
        product_id = request.form.get('product_id', '')
        promo_link = request.form.get('promo_link', '') or request.form.get('product_link', '')
        promo_commission = request.form.get('promo_commission', '')  # NEW
        product_link = promo_link or f"/product/{product_id}" if product_id else f"/shop/{shop_slug}"
        location = request.form.get('location', 'Uganda')
        hashtags = request.form.get('hashtags', '')
        if promo_commission:
            hashtags = f"{hashtags} #earn{promo_commission}".strip()
        user_email = request.form.get('user_email','anon')
        user_name = shop_name
        
        print(f"Uploading: Shop={shop_name}, ProductID={product_id}, Link={promo_link}, Commission={promo_commission}")
        
        result = cloudinary.uploader.upload(
            video, 
            resource_type="video", 
            folder="sannlas_reels", 
            chunk_size=6000000, 
            timeout=120
        )
        video_url = result.get('secure_url')
        if not video_url:
            return jsonify({'success':False, 'error':'Cloudinary returned no URL'}),500
        
        ensure_reels_table()
        conn = get_conn(); cur = conn.cursor()
        # Save promo_link + commission in hashtags / promo_link field
        cur.execute("""
            INSERT INTO sannlas_reels 
            (user_email, user_name, shop_name, shop_slug, caption, description, price, promo_link, location, hashtags, video_url, product_link, product_id) 
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """,
            (user_email, user_name, shop_name, shop_slug, caption, description, price, promo_link, location, hashtags, video_url, product_link, product_id))
        new_id = cur.fetchone()[0]
        conn.commit(); cur.close(); conn.close()
        
        print(f"✅ REEL SAVED ID {new_id}: {video_url} LINK={promo_link}")
        return jsonify({'success':True, 'url': video_url, 'id': new_id, 'promo_link': promo_link})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success':False, 'error': str(e)}), 500
