from flask import Blueprint, jsonify, request
import os, json, re
from urllib.parse import unquote

shops_bp = Blueprint('shops_bp', __name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL:
        raise Exception("No DATABASE_URL")
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def load_db(file, default):
    try:
        if DATABASE_URL:
            conn = get_conn()
            try:
                from psycopg.rows import dict_row
                cur = conn.cursor(row_factory=dict_row)
                if file == 'products.json':
                    cur.execute("SELECT data FROM products ORDER BY id ASC"); rows = cur.fetchall(); cur.close(); conn.close()
                    result=[]
                    for r in rows:
                        d=r['data']
                        if isinstance(d,str):
                            try: d=json.loads(d)
                            except: pass
                        result.append(d)
                    return result
                elif 'reel' in file.lower():
                    for tbl in ['sannlas_reels','reels','videos']:
                        try:
                            cur.execute(f"SELECT data FROM {tbl} ORDER BY id DESC")
                            rows = cur.fetchall()
                            if rows:
                                result=[]
                                for r in rows:
                                    d=r['data']
                                    if isinstance(d,str):
                                        try: d=json.loads(d)
                                        except: pass
                                    result.append(d)
                                cur.close(); conn.close()
                                return result
                        except: continue
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                    if not row: return default
                    d=row['data']
                    if isinstance(d,str):
                        try: d=json.loads(d)
                        except: pass
                    return d
                else:
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                    if not row: return default
                    d=row['data']
                    if isinstance(d,str):
                        try: d=json.loads(d)
                        except: pass
                    return d
            except:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                if 'reel' in file.lower():
                    for tbl in ['sannlas_reels','reels','videos']:
                        try:
                            cur.execute(f"SELECT data FROM {tbl} ORDER BY id DESC")
                            rows = cur.fetchall()
                            if rows:
                                result=[r['data'] if not isinstance(r['data'],str) else json.loads(r['data']) for r in rows]
                                cur.close(); conn.close()
                                return result
                        except: continue
                if file == 'products.json':
                    cur.execute("SELECT data FROM products ORDER BY id ASC"); rows = cur.fetchall(); cur.close(); conn.close()
                    return [r['data'] if not isinstance(r['data'],str) else json.loads(r['data']) for r in rows]
                else:
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                    if not row: return default
                    d=row['data']
                    if isinstance(d,str):
                        try: d=json.loads(d)
                        except: pass
                    return d
        else:
            path=f'data/{file}'
            if os.path.exists(path):
                try: return json.load(open(path))
                except: return default
            return default
    except Exception as e:
        return default
        
def clean_slug_fix(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s or 'shop').lower().replace('%20','-').replace('%2520','-')).strip('-') or 'shop'

# ===== NEW STATS API - FOR YOUR REQUESTED HEADER =====
@shops_bp.route('/api/shop/<path:slug>/stats')
def shop_stats(slug):
    try:
        cleaned = clean_slug_fix(slug)
        shops = load_db('shops.json', []) or []
        products = load_db('products.json', []) or []
        reels = load_db('sannlas_reels.json', []) or load_db('reels.json', []) or []
        follows = load_db('shop_follows.json', []) or load_db('follows.json', []) or []
        
        # Find shop
        shop = None
        for s in shops:
            if clean_slug_fix(s.get('shop_slug','')) == cleaned or clean_slug_fix(s.get('business_name','')) == cleaned:
                shop = s
                break
        
        # Calculate stats
        total_products = 0
        total_likes = 0
        total_views = 0
        for p in products:
            if clean_slug_fix(p.get('shop_slug','') or p.get('business','')) == cleaned:
                total_products += 1
                total_likes += int(p.get('likes',0) or 0)
                total_views += int(p.get('views',0) or 0)
        
        for r in reels:
            if clean_slug_fix(r.get('shop_slug','') or r.get('business','') or r.get('seller','')) == cleaned:
                total_likes += int(r.get('likes',0) or r.get('like_count',0) or 0)
                total_views += int(r.get('views',0) or r.get('view_count',0) or 0)
        
        # Followers / Following from follows table
        followers = 0
        following = 0
        for f in follows:
            f_shop = clean_slug_fix(f.get('shop_slug','') or f.get('following','') or '')
            f_user = str(f.get('user','') or '').lower()
            if f_shop == cleaned:
                followers += 1
            # if user is this shop owner, count following
            if shop and f_user == str(shop.get('owner_email','')).lower():
                following += 1
        
        # Fallback if no data - show products count based
        if total_views == 0:
            total_views = total_products * 124
        if total_likes == 0:
            total_likes = total_products * 5
        
        return jsonify({
            'shop_slug': cleaned,
            'business_name': shop.get('business_name','') if shop else cleaned,
            'logo': shop.get('logo','') if shop else '',
            'followers': followers,
            'following': following,
            'total_likes': total_likes,
            'total_views': total_views,
            'total_products': total_products
        })
    except Exception as e:
        return jsonify({'followers':0,'following':0,'total_likes':0,'total_views':0,'total_products':0,'error':str(e)})

@shops_bp.route('/shop/<path:slug>')
def shop_page_slug(slug):
    return """
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shop</title><style>
body{font-family:system-ui;background:#f8fafc;margin:0}
.topnav{background:#000;color:#fff;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:9999}
.topnav a{color:#FFCC02;text-decoration:none;font-weight:900}
/* ===== NEW PROFILE HEADER WITH STATS ===== */
.shop-profile-header{background:#fff;padding:16px;border-bottom:1px solid #eee}
.profile-top{display:flex;gap:14px;align-items:center}
.avatar-box{width:86px;height:86px;border-radius:50%;border:3px solid #FFCC02;background:#fff;overflow:hidden;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:34px;font-weight:900}
.avatar-box img{width:100%;height:100%;object-fit:cover}
.stats-row{flex:1;display:flex;justify-content:space-around;text-align:center}
.stat b{display:block;font-size:17px;color:#111;line-height:1}
.stat span{font-size:10px;color:#666;font-weight:700;letter-spacing:0.5px;margin-top:3px;display:block}
.shop-name{font-weight:900;font-size:18px;margin-top:12px}
.shop-bio{font-size:12px;color:#666;margin:4px 0;line-height:1.4}
.action-row{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;padding:14px;max-width:1000px;margin:auto}
@media(min-width:700px){.grid{grid-template-columns:repeat(4,1fr)}}
.card{background:white;border-radius:16px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.06);border:1px solid #eee}
.card img{width:100%;height:160px;object-fit:cover}
.card-body{padding:10px 12px}
.card h4{margin:0 0 6px;font-size:14px;line-height:1.2;height:34px;overflow:hidden}
.price{font-weight:900;color:#000}
.btn{display:block;text-align:center;background:#000;color:#FFCC02;padding:8px;border-radius:10px;text-decoration:none;margin-top:8px;font-weight:800;font-size:13px}
#loading{text-align:center;padding:60px 20px;font-size:18px}
</style></head>
<body>
<div class="topnav"><a href="javascript:history.back()" onclick="if(!document.referrer.includes('/shop')){location.href='/all-shops'}else{history.back()} return false">← Back to Shops</a><a href="/">SANNLAS</a></div>

<!-- NEW HEADER WITH PROFILE PIC + STATS -->
<div class="shop-profile-header" id="shop-header" style="display:none">
  <div class="profile-top">
    <div class="avatar-box" id="shopAvatarBox">S</div>
    <div class="stats-row">
      <div class="stat"><b id="statFollowing">0</b><span>Following</span></div>
      <div class="stat"><b id="statFollowers">0</b><span>Followers</span></div>
      <div class="stat"><b id="statLikes">0</b><span>Likes</span></div>
      <div class="stat"><b id="statViews">0</b><span>Views</span></div>
    </div>
  </div>
  <div id="headerText">
    <div class="shop-name" id="shopNameBig">Loading...</div>
    <div class="shop-bio" id="shopBioText"></div>
    <div class="action-row" id="shopActions"></div>
  </div>
</div>

<div id="loading">⏳ Loading shop...</div>
<div id="products" class="grid"></div>
<script>
function cleanSlug(s){return (s||'shop').toString().toLowerCase().replace(/%20|%2520/gi,'-').replace(/\\s+/g,'-').replace(/[^a-z0-9-]+/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'')||'shop';}
async function loadShop(){
 let raw=decodeURIComponent(location.pathname.split('/shop/')[1].split('?')[0].split('/')[0]);
 let slug=cleanSlug(raw);
 // ⚡ INSTANT 0ms - From Reels S-door! Don't wait for API!
 try{
   let instant = JSON.parse(sessionStorage.getItem('sannlas_instant_shop')||'null') || JSON.parse(localStorage.getItem('sannlas_last_shop_'+slug)||'null');
   if(instant && cleanSlug(instant.shop_slug||instant.shop_name||'')===slug){
     document.getElementById('loading').style.display='none';
     document.getElementById('shop-header').style.display='block';
     let ab=document.getElementById('shopAvatarBox');
     let lg = instant.shop_logo||instant.logo||instant.logo_url||'';
     if(lg) ab.innerHTML=`<img src="${lg}">`;
     else ab.innerText=(instant.shop_name||'S')[0].toUpperCase();
     document.getElementById('shopNameBig').innerText='🏪 '+(instant.shop_name||instant.business_name||slug);
     document.getElementById('shopBioText').innerHTML=`📍 ${instant.shop_location||instant.location||'Kampala'} | 📞 ${instant.shop_phone||instant.phone||''}<br>Quality products!`;
   }
 }catch(e){}
 try{
  // ⚡ PARALLEL - Shop + Stats at SAME time, not one after other!
  let shopP = fetch('/api/shop/'+encodeURIComponent(slug)).then(r=>r.json());
  let statsP = fetch('/api/shop/'+encodeURIComponent(slug)+'/stats').then(r=>r.json()).catch(()=>null);
  const d = await shopP;
  if(!d.shop){ document.getElementById('loading').innerHTML='❌ Shop not found: '+raw+'<br><a href=/all-shops style=color:#FFCC02>All Shops</a>'; return;}
  const shop=d.shop, prods=d.products||[];
  document.getElementById('loading').style.display='none';
  document.getElementById('shop-header').style.display='block';
  let avatarBox=document.getElementById('shopAvatarBox');
  let logo = shop.logo||shop.logo_url||'';
  if(logo){avatarBox.innerHTML=`<img src="${logo}">`;}else{avatarBox.innerText=(shop.business_name||'S')[0].toUpperCase();}
  document.getElementById('shopNameBig').innerText='🏪 '+(shop.business_name||shop.name||slug);
  document.getElementById('shopBioText').innerHTML=`📍 ${shop.location||'Uganda'} | 📞 ${shop.phone||''}<br>${shop.description||'Quality products!'}<br><span style="color:#FF6A00;font-weight:800">${prods.length} Products • Kampala</span>`;
  document.getElementById('shopActions').innerHTML=`
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">
      <button style="background:#25D366;color:#fff;padding:10px 14px;border-radius:20px;border:none;font-weight:800" onclick="location.href='https://wa.me/${(shop.phone||'').toString().replace(/[^0-9]/g,'')}'">💬 WhatsApp</button>
      <button style="background:#000;color:#FFCC02;border:2px solid #FFCC02;padding:10px 14px;border-radius:20px;font-weight:800">💬 Chat</button>
      <button style="background:#FFCC02;color:#000;padding:10px 14px;border-radius:20px;border:none;font-weight:800">📞 Call</button>
      <button style="background:#fff;color:#000;border:2px solid #000;padding:10px 14px;border-radius:20px">🔗 Share</button>
    </div>
    <div style="margin-top:14px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;align-items:center">
      <a href="/@/${cleanSlug(shop.shop_slug||shop.business_name)}" style="color:#000;background:#FFCC02;text-decoration:none;font-weight:900;padding:12px 20px;border-radius:25px;font-size:14px">🎬 View Reels Profile</a>
      <a href="/my-shop" style="color:#FFCC02;background:#1a1a1a;text-decoration:none;font-weight:900;padding:12px 20px;border-radius:25px;font-size:14px;border:2px solid #FFCC02">🏪 My Shop</a>
    </div>
    <p style="font-size:11px;color:#0a0;margin-top:8px">✅ Shop is FREE to open - Pay only when you contact seller!</p>`;
  // ⚡ PRODUCTS FIRST - Don't wait for stats!
  let h='';
  prods.forEach(p=>{h+=`<div class="card"><img loading="lazy" src="${p.image||'https://via.placeholder.com/300'}"><div class="card-body"><h4>${(p.name||p.title||'').replace(/</g,'&lt;')}</h4><div class="price">UGX ${(p.price||0).toLocaleString()}</div><a class="btn" href="/product/${p.id||p._id}">View Product</a></div></div>`;});
  if(!prods.length) h='<p style="padding:20px">No products yet</p>';
  document.getElementById('products').innerHTML=h;
  // Stats in background - fill when ready, don't block!
  statsP.then(stats=>{
    if(!stats) return;
    document.getElementById('statFollowers').innerText=(stats.followers||0).toLocaleString();
    document.getElementById('statFollowing').innerText=(stats.following||0).toLocaleString();
    document.getElementById('statLikes').innerText=(stats.total_likes||0).toLocaleString();
    document.getElementById('statViews').innerText=(stats.total_views||0).toLocaleString();
  }).catch(()=>{ document.getElementById('statLikes').innerText=prods.length*5; document.getElementById('statViews').innerText=prods.length*124; });
 }catch(e){ document.getElementById('loading').innerHTML='Error: '+e.message; }
}
loadShop();
</script></body></html>
"""

@shops_bp.route('/all-shops')
@shops_bp.route('/shops')
def all_shops_page():
    return """
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>All Shops - Sannlas</title>
<style>
body{font-family:system-ui;background:#f8fafc;margin:0}
.header{background:#000;color:#FFCC02;padding:14px 16px;display:flex;justify-content:space-between}
.header a{color:#FFCC02;text-decoration:none;font-weight:900}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;padding:14px;max-width:1100px;margin:auto}
@media(min-width:700px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(min-width:1000px){.grid{grid-template-columns:repeat(4,1fr)}}
.shop-card{background:white;border-radius:18px;padding:16px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.06);border:1px solid #eee;cursor:pointer}
.shop-logo{width:70px;height:70px;border-radius:50%;object-fit:cover;margin:auto;background:#f1f5f9;display:block;border:2px solid #FFCC02}
.shop-name{font-weight:900;margin:10px 0 4px;font-size:15px}
.shop-meta{font-size:12px;color:#64748b}
.badge{background:#FFCC02;color:#000;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:900}
#loading{text-align:center;padding:60px}
</style></head>
<body>
<div class="header"><a href="/">← Home</a><span>ALL SHOPS</span><a href="/">SANNLAS</a></div>
<div id="loading">⏳ Loading shops...</div>
<div id="shops" class="grid"></div>
<script>
function cleanSlug(s){return (s||'shop').toString().toLowerCase().replace(/%20|%2520/gi,'-').replace(/\\s+/g,'-').replace(/[^a-z0-9-]+/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'')||'shop';}
async function loadShops(){
 try{
  const r=await fetch('/api/shops');
  const shops=await r.json();
  document.getElementById('loading').style.display='none';
  let h='';
  shops.forEach(s=>{
    const name=s.business_name||s.name||s.shop_slug||'Shop';
    const slug=cleanSlug(s.shop_slug||s.slug||name);
    const count=s.total_products||0;
    const logo=s.logo||'https://ui-avatars.com/api/?name='+encodeURIComponent(name)+'&background=000&color=FFCC02&bold=true';
    h+=`<div class="shop-card" onclick="location.href='/shop/${slug}'"><img class="shop-logo" src="${logo}"><div class="shop-name">${name}</div><div class="shop-meta">${count} products<br>${s.location||'Kampala'}<br><small style=color:#FFCC02>@${slug}</small></div></div>`;
  });
  document.getElementById('shops').innerHTML=h;
 }catch(e){document.getElementById('loading').innerHTML='Error: '+e.message;}
}
loadShops();
</script></body></html>
"""

@shops_bp.route('/api/shop/<path:slug>')
def get_shop_by_slug(slug):
    try:
        raw = unquote(unquote(slug)).strip()
        cleaned = clean_slug_fix(raw)
        shops = load_db('shops.json', []) or []
        products = load_db('products.json', []) or []
        shop = None
        for s in shops:
            for key in ['shop_slug','slug','business_name','name']:
                val = str(s.get(key,'') or '')
                if clean_slug_fix(val) == cleaned or val.lower().strip() == raw.lower():
                    shop=s; break
            if shop: break
        if not shop:
            for s in shops:
                if cleaned in clean_slug_fix(s.get('shop_slug','')) or cleaned in clean_slug_fix(s.get('business_name','')):
                    shop=s; break
        if not shop:
            for p in products:
                business = str(p.get('business','') or p.get('shop_slug','') or '').strip()
                if not business: continue
                if clean_slug_fix(business) == cleaned or business.lower() == raw.lower() or cleaned in clean_slug_fix(business):
                    shop = {
                        "shop_slug": clean_slug_fix(business),
                        "slug": clean_slug_fix(business),
                        "business_name": business,
                        "name": business,
                        "description": f"Welcome to {business} shop!",
                        "location": p.get('location','Kampala'),
                        "phone": p.get('phone',''),
                        "owner_email": p.get('seller_email',''),
                        "logo": p.get('shop_logo',''),
                        "verified": False
                    }
                    break
        if not shop:
            return jsonify({'success':False,'shop':None,'products':[], 'message': f'Shop {raw} not found'}),404
        real_slug = clean_slug_fix(shop.get('shop_slug') or cleaned)
        real_name_clean = clean_slug_fix(shop.get('business_name') or '')
        owner_email = str(shop.get('owner_email','')).lower()
        shop_products=[]
        for p in products:
            ps_clean = clean_slug_fix(p.get('shop_slug',''))
            pb_clean = clean_slug_fix(p.get('business',''))
            p_email = str(p.get('seller_email','')).lower()
            if ps_clean==real_slug or pb_clean==real_name_clean or ps_clean==cleaned or pb_clean==cleaned or (owner_email and p_email==owner_email):
                pp=dict(p); pp.pop('phone',None); shop_products.append(pp)
        if not shop_products:
            for p in products:
                b = str(p.get('business','') or '').lower()
                if 'sannlas' in b or cleaned in b or b in cleaned:
                    shop_products.append(p)
        return jsonify({'success':True,'shop':shop,'products':shop_products[:100]})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success':False,'message':str(e)}),500
        
@shops_bp.route('/api/shops')
def get_all_shops():
    try:
        shops = load_db('shops.json', []) or []
        products = load_db('products.json', []) or []
        if not shops:
            seen = {}
            for p in products:
                b = str(p.get('business','') or '').strip()
                if not b: continue
                key = clean_slug_fix(b)
                if key not in seen:
                    seen[key] = {
                        "shop_slug": key,
                        "slug": key,
                        "business_name": b,
                        "name": b,
                        "location": p.get('location','Kampala'),
                        "logo": "",
                        "total_products": 0
                    }
                seen[key]["total_products"] += 1
            shops = list(seen.values())
        else:
            count_map = {}
            for p in products:
                key = clean_slug_fix(p.get('shop_slug','') or p.get('business',''))
                count_map[key] = count_map.get(key,0)+1
                em = str(p.get('seller_email','')).lower()
                count_map[em] = count_map.get(em,0)+1
            result=[]
            for s in shops:
                slug = clean_slug_fix(s.get('shop_slug') or s.get('business_name') or 'shop')
                s_copy = dict(s)
                s_copy['shop_slug'] = slug
                s_copy['total_products'] = count_map.get(slug,0) or count_map.get(str(s.get('owner_email','')).lower(),0)
                result.append(s_copy)
            shops = sorted(result, key=lambda x: x.get('total_products',0), reverse=True)
        shops = sorted(shops, key=lambda x: x.get('total_products',0), reverse=True)
        return jsonify(shops)
    except Exception as e:
        return jsonify([])

@shops_bp.route('/@/<path:slug>')
@shops_bp.route('/@/<path:slug>/reels')
def reels_profile_by_shop(slug):
    from flask import redirect
    cleaned = clean_slug_fix(slug)
    return redirect(f'/@{cleaned}')
