from flask import Blueprint, jsonify, request
import os, json, re, time
from urllib.parse import unquote

shops_bp = Blueprint('shops_bp', __name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_SHOP_CACHE = {}
_SHOPS_LIST_CACHE = {"data": None, "time": 0}
_CACHE_TTL = 30

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

def get_shop_fast(cleaned, raw=""):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT data FROM kv_store WHERE key=%s", ('shops.json',))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            return None
        shops = row[0]
        if isinstance(shops, str):
            try: shops = json.loads(shops)
            except: shops = []
        if not isinstance(shops, list):
            return None
        for s in shops:
            for key in ['shop_slug','slug','business_name','name']:
                val = str(s.get(key,'') or '')
                if clean_slug_fix(val) == cleaned or val.lower().strip() == raw.lower():
                    return s
        for s in shops:
            if cleaned in clean_slug_fix(s.get('shop_slug','')) or cleaned in clean_slug_fix(s.get('business_name','')):
                return s
        return None
    except Exception as e:
        print("get_shop_fast err", e)
        return None

def get_shop_products_fast(cleaned, shop):
    try:
        conn = get_conn()
        cur = conn.cursor()
        biz = shop.get('business_name','') if shop else ''
        email = shop.get('owner_email','') if shop else ''
        cur.execute(
            "SELECT data FROM products WHERE data->>'shop_slug' = %s OR data->>'business' = %s OR data->>'seller_email' = %s LIMIT 100",
            (cleaned, biz, email)
        )
        rows = cur.fetchall()
        cur.close(); conn.close()
        out = []
        for r in rows:
            d = r[0]
            if isinstance(d, str):
                try: d = json.loads(d)
                except: continue
            if isinstance(d, dict):
                d.pop('phone', None)
                out.append(d)
        if out:
            return out
    except Exception as e:
        print("get_shop_products_fast err", e)
    try:
        products = load_db('products.json', []) or []
        real_name_clean = clean_slug_fix(shop.get('business_name','')) if shop else ''
        owner_email = str(shop.get('owner_email','')).lower() if shop else ''
        out = []
        for p in products:
            ps_clean = clean_slug_fix(p.get('shop_slug',''))
            pb_clean = clean_slug_fix(p.get('business',''))
            p_email = str(p.get('seller_email','')).lower()
            if ps_clean==cleaned or pb_clean==real_name_clean or ps_clean==clean_slug_fix(shop.get('shop_slug','')) if shop else False or pb_clean==cleaned or (owner_email and p_email==owner_email):
                pp=dict(p); pp.pop('phone',None); out.append(pp)
            if len(out) >= 100:
                break
        return out
    except:
        return []

# ===== ✅ NEW - LIVE FOLLOW COUNT - Fixes 0 Followers! =====
def get_live_follow_counts(shop_email, shop_slug):
    shop_email = (shop_email or '').lower().strip()
    shop_slug = (shop_slug or '').lower().strip()
    followers_set = set()
    following_set = set()
    # 1. From follows.json (kv_store) - NOT shop_follows.json!
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT data FROM kv_store WHERE key=%s", ('follows.json',))
        row = cur.fetchone(); cur.close(); conn.close()
        follows = row[0] if row else []
        if isinstance(follows, str):
            try: follows = json.loads(follows)
            except: follows = []
        for f in (follows or []):
            fe = (f.get('follower_email') or '').lower()
            te = (f.get('following_email') or '').lower()
            if shop_email and te == shop_email and fe:
                followers_set.add(fe)
            if shop_email and fe == shop_email and te:
                following_set.add(te)
            if shop_slug and te == shop_slug and fe:
                followers_set.add(fe)
    except Exception as e:
        print("live counts JSON fail:", e)
    # 2. From Postgres sannlas_follows (Reels follows!)
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS sannlas_follows (id BIGSERIAL PRIMARY KEY, follower_email TEXT, following_email TEXT, created TIMESTAMP DEFAULT NOW(), UNIQUE(follower_email, following_email))")
        conn.commit()
        if shop_email:
            cur.execute("SELECT follower_email FROM sannlas_follows WHERE LOWER(following_email)=%s", (shop_email,))
            for r in cur.fetchall():
                if r[0]: followers_set.add(r[0].lower())
            cur.execute("SELECT following_email FROM sannlas_follows WHERE LOWER(follower_email)=%s", (shop_email,))
            for r in cur.fetchall():
                if r[0]: following_set.add(r[0].lower())
        if shop_slug:
            cur.execute("SELECT follower_email FROM sannlas_follows WHERE LOWER(following_email)=%s", (shop_slug,))
            for r in cur.fetchall():
                if r[0]: followers_set.add(r[0].lower())
        cur.close(); conn.close()
    except Exception as e:
        print("live counts PG fail:", e)
        return {'followers': len(followers_set), 'following': len(following_set)}

# ===== ✅ NEW - LIVE LIKES - Products + Reels, no fake *5! =====
def get_live_like_counts(shop_email, shop_slug, prods):
    shop_email = (shop_email or '').lower().strip()
    shop_slug = (shop_slug or '').lower().strip()
    product_likes = 0
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT data FROM kv_store WHERE key=%s", ('likes.json',))
        row = cur.fetchone(); cur.close(); conn.close()
        likes = row[0] if row else []
        if isinstance(likes, str):
            try: likes = json.loads(likes)
            except: likes = []
        my_pids = set([str(p.get('id')) for p in (prods or []) if isinstance(p, dict)])
        product_likes = len([l for l in (likes or []) if str(l.get('product_id')) in my_pids])
        if product_likes == 0:
            product_likes = sum(int(p.get('likes',0) or 0) for p in (prods or []))
    except:
        product_likes = sum(int(p.get('likes',0) or 0) for p in (prods or []))
    reel_likes = 0
    reel_views = 0
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(likes),0), COALESCE(SUM(views),0) FROM sannlas_reels WHERE LOWER(user_email)=%s OR LOWER(shop_slug)=%s", (shop_email, shop_slug))
        r = cur.fetchone()
        if r and len(r) >= 2:
            reel_likes = int(r[0] or 0); reel_views = int(r[1] or 0)
        cur.close(); conn.close()
    except Exception as e:
        print("reel likes fail:", e)
    product_views = sum(int(p.get('views',0) or 0) for p in (prods or []))
    return {'total_likes': product_likes + reel_likes, 'total_views': product_views + reel_views}

# ===== ✅ FIXED STATS - Live count, no cache trap =====
@shops_bp.route('/api/shop/<path:slug>/stats')
def shop_stats(slug):
    try:
        cleaned = clean_slug_fix(slug)
        cached = _SHOP_CACHE.get(cleaned)
        if cached and time.time() - cached['time'] < _CACHE_TTL:
            prods = cached['data'].get('products', []) or []
            total_products = len(prods)
            shop = cached['data'].get('shop', {}) or {}
            if not isinstance(shop, dict): shop = {}
            # ✅ Each helper in its own try - if one crashes, others still work!
            try:
                _lc = get_live_like_counts(shop.get('owner_email') or shop.get('email') or '', cleaned, prods)
                total_likes = _lc['total_likes']; total_views = _lc['total_views']
            except Exception as e:
                print("stats likes fail:", e)
                total_likes = sum(int((p or {}).get('likes',0) or 0) for p in prods)
                total_views = sum(int((p or {}).get('views',0) or 0) for p in prods)
            try:
                counts = get_live_follow_counts(shop.get('owner_email') or shop.get('email') or '', cleaned)
            except Exception as e:
                print("stats follows fail:", e)
                counts = {'followers':0,'following':0}
            return jsonify({
                'shop_slug': cleaned,
                'business_name': shop.get('business_name',''),
                'logo': shop.get('logo',''),
                'followers': counts['followers'],
                'following': counts['following'],
                'total_likes': total_likes,
                'total_views': total_views,
                'total_products': total_products
            })
        shop = None
        try:
            shop = get_shop_fast(cleaned)
        except Exception as e:
            print("get_shop_fast fail:", e)
        if not isinstance(shop, dict): shop = {}
        # ✅ If shop not found, build from products (Sann 2 case!)
        if not shop:
            try:
                conn = get_conn(); cur = conn.cursor()
                cur.execute("SELECT data FROM products WHERE data->>'business' ILIKE %s LIMIT 1", ('%'+cleaned.replace('-',' %')+'%',))
                row = cur.fetchone(); cur.close(); conn.close()
                if row and row[0]:
                    p = row[0]
                    if isinstance(p, str):
                        try: p = json.loads(p)
                        except: p = {}
                    if isinstance(p, dict):
                        biz = p.get('business','')
                        shop = {"shop_slug": clean_slug_fix(biz), "slug": clean_slug_fix(biz), "business_name": biz, "name": biz, "owner_email": p.get('seller_email',''), "logo": p.get('shop_logo','')}
            except Exception as e:
                print("shop_stats fallback shop fail:", e)
        if not isinstance(shop, dict): shop = {}
        try:
            prods = get_shop_products_fast(cleaned, shop) if shop else []
        except Exception as e:
            print("get_shop_products fail:", e)
            prods = []
        if not isinstance(prods, list): prods = []
        total_products = len(prods)
        try:
            _lc = get_live_like_counts(shop.get('owner_email') or shop.get('email') or '', cleaned, prods)
            total_likes = _lc['total_likes']; total_views = _lc['total_views']
        except Exception as e:
            print("stats likes fail2:", e)
            total_likes = sum(int((p or {}).get('likes',0) or 0) for p in prods if isinstance(p, dict))
            total_views = sum(int((p or {}).get('views',0) or 0) for p in prods if isinstance(p, dict))
        try:
            counts = get_live_follow_counts(shop.get('owner_email') or shop.get('email') or '', cleaned)
        except Exception as e:
            print("stats follows fail2:", e)
            counts = {'followers':0,'following':0}
        return jsonify({
            'shop_slug': cleaned,
            'business_name': shop.get('business_name','') if shop else cleaned,
            'logo': shop.get('logo','') if shop else '',
            'followers': counts['followers'],
            'following': counts['following'],
            'total_likes': total_likes,
            'total_views': total_views,
            'total_products': total_products
        })
    except Exception as e:
        import traceback; traceback.print_exc()
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
.shop-profile-header{background:#fff;padding:16px 16px 0;text-align:center;border-bottom:1px solid #eee}
.avatar-wrap{position:relative;width:110px;height:110px;margin:0 auto}
.avatar-ring{width:110px;height:110px;border-radius:50%;background:linear-gradient(135deg,#FFCC02,#FF6A00);padding:3px}
.avatar-box{width:100%;height:100%;border-radius:50%;background:#fff;overflow:hidden;display:flex;align-items:center;justify-content:center;font-size:48px;font-weight:900}
.avatar-box img{width:100%;height:100%;object-fit:cover}
.verified-badge{position:absolute;bottom:4px;right:4px;width:26px;height:26px;background:#00AFF0;color:#fff;border-radius:50%;border:2px solid #fff;display:flex;align-items:center;justify-content:center;font-size:14px}
.shop-name{font-weight:900;font-size:22px;margin:12px 0 2px}
.shop-handle{font-size:13px;color:#666;font-weight:700}
.shop-bio{font-size:13px;color:#333;margin:8px 20px;line-height:1.4}
.stats-row{display:flex;justify-content:center;gap:28px;margin:14px 0;text-align:center}
.stat b{display:block;font-size:18px;color:#111}
.stat span{font-size:12px;color:#888}
.action-row{display:flex;gap:8px;justify-content:center;margin-bottom:12px}
.tab-row{display:flex;border-top:1px solid #eee;margin-top:4px}
.tab-row button{flex:1;padding:12px;border:none;background:none;font-weight:700;color:#888;font-size:14px;border-bottom:3px solid transparent}
.tab-row button.active{color:#000;border-bottom:3px solid #000;font-weight:900}
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
<div class="shop-profile-header" id="shop-header" style="display:none">
  <div class="avatar-wrap"><div class="avatar-ring"><div class="avatar-box" id="shopAvatarBox">S</div></div><div class="verified-badge">✓</div></div>
  <div class="shop-name" id="shopNameBig">Loading...</div>
  <div class="shop-handle" id="shopHandleText">@shop</div>
  <div class="shop-bio" id="shopBioText"></div>
  <div class="stats-row">
    <div class="stat"><b id="statFollowing">0</b><span>Following</span></div>
    <div class="stat"><b id="statFollowers">0</b><span>Followers</span></div>
    <div class="stat"><b id="statLikes">0</b><span>Likes</span></div>
    <div class="stat"><b id="statViews">0</b><span>Views</span></div>
  </div>
  <div class="action-row" id="shopActions"></div>
  <div class="tab-row">
    <button id="tabProductsBtn" class="active" onclick="showShopTab('products')">🛍️ Products</button>
    <button id="tabReelsBtn" onclick="showShopTab('reels')">🎬 Reels</button>
  </div>
</div>
<div id="shopReelsTab" style="display:none;padding:12px;background:#fff">
  <div id="shopReelsGrid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px"></div>
  <p id="shopReelsEmpty" style="text-align:center;color:#888;font-size:13px;padding:20px">No reels yet</p>
</div>
<div id="loading">⏳ Loading shop...</div>
<div id="products" class="grid"></div>
<script>
function cleanSlug(s){return (s||'shop').toString().toLowerCase().replace(/%20|%2520/gi,'-').replace(/\\s+/g,'-').replace(/[^a-z0-9-]+/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'')||'shop';}
async function loadShop(){
 let raw=decodeURIComponent(location.pathname.split('/shop/')[1].split('?')[0].split('/')[0]);
 let slug=cleanSlug(raw);
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
     document.getElementById('shopBioText').innerHTML=`📍 ${instant.shop_location||instant.location||'Kampala'} | 📞 ${instant.shop_phone||instant.phone||''}<br>Quality products, fast delivery in Uganda 🇺🇬`;
   }
 }catch(e){}
 try{
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
   document.getElementById('shopHandleText').innerText='@'+cleanSlug(shop.shop_slug||shop.business_name)+' • '+(shop.category||'Shop');
  document.getElementById('shopBioText').innerHTML=`📍 ${shop.location||'Uganda'} | 📞 ${shop.phone||''}<br>${shop.description||'Welcome to '+ (shop.business_name||'shop') +' shop! Quality products, fast delivery in Uganda 🇺🇬'}<br><span style="color:#FF6A00;font-weight:800">${prods.length} Products • Kampala</span>`;
    // ✅ OWNER vs VISITOR SPLIT
  let _me = null; try{ _me = JSON.parse(localStorage.getItem('sannlas_user')||'null'); }catch(e){}
  let _myEmail = (_me && _me.email ? _me.email.toLowerCase() : '');
  let _ownerEmail = ((shop.owner_email||shop.email||'').toLowerCase());
  let _isOwner = _myEmail && _ownerEmail && _myEmail === _ownerEmail;

  if(_isOwner){
    // 👑 OWNER ONLY - No Follow, No Message, No WhatsApp, No Call
    document.getElementById('shopActions').innerHTML=`
      <div style="background:#FFCC02;color:#000;padding:10px;border-radius:10px;font-weight:900;font-size:13px;margin-bottom:8px">👑 This is YOUR Shop</div>
      <div style="display:flex;gap:8px;justify-content:center;width:100%">
        <a href="/my-shop" style="flex:1;background:#000;color:#FFCC02;text-decoration:none;padding:11px;border-radius:8px;font-weight:800;font-size:14px;text-align:center">✏️ Edit Shop</a>
        <a href="/my-shop" style="flex:1;background:#FFCC02;color:#000;text-decoration:none;padding:11px;border-radius:8px;font-weight:800;font-size:14px;text-align:center;border:2px solid #000">➕ Add Product</a>
        <button onclick="shareShopLink()" style="width:44px;background:#F1F1F2;border:none;border-radius:8px;font-size:18px">↗️</button>
      </div>
      <div style="display:flex;gap:8px;justify-content:center;width:100%;margin-top:8px">
        <a href="/my-shop" style="flex:1;background:#fff;color:#000;border:2px solid #000;text-decoration:none;padding:10px;border-radius:8px;font-weight:800;font-size:13px;text-align:center">💰 Earnings</a>
        <a href="/my-shop" style="flex:1;background:#fff;color:#000;border:2px solid #000;text-decoration:none;padding:10px;border-radius:8px;font-weight:800;font-size:13px;text-align:center">📦 Orders</a>
      </div>`;
  } else {
    // 👤 VISITOR ONLY - No Edit, No My Shop
    document.getElementById('shopActions').innerHTML=`
      <div style="display:flex;gap:8px;justify-content:center;width:100%">
        <button id="followShopBtn" onclick="toggleFollowShop()" style="flex:1;max-width:160px;background:#FE2C55;color:#fff;border:none;padding:11px;border-radius:8px;font-weight:800;font-size:14px">➕ Follow</button>
        <button onclick="openShopChat()" style="flex:1;max-width:160px;background:#F1F1F2;color:#000;border:none;padding:11px;border-radius:8px;font-weight:800;font-size:14px">💬 Message</button>
        <button onclick="shareShopLink()" style="width:44px;background:#F1F1F2;border:none;border-radius:8px;font-size:18px">↗️</button>
      </div>
      <div style="display:flex;gap:8px;justify-content:center;width:100%;margin-top:8px">
        <a href="https://wa.me/${(shop.phone||'').toString().replace(/[^0-9]/g,'')}" style="flex:1;max-width:160px;background:#25D366;color:#fff;text-decoration:none;padding:10px;border-radius:8px;font-weight:800;font-size:13px;text-align:center">💬 WhatsApp</a>
        <a href="tel:${shop.phone||''}" style="flex:1;max-width:160px;background:#000;color:#FFCC02;text-decoration:none;padding:10px;border-radius:8px;font-weight:800;font-size:13px;text-align:center">📞 Call Shop</a>
      </div>`;
  }
  window._currentShop = shop;
  // ✅ Check real follow status on load
  try{
    let me = JSON.parse(localStorage.getItem('sannlas_user')||'null');
    if(me && me.email){
      let chk = await fetch('/api/follow/check?email='+encodeURIComponent(me.email)+'&target='+encodeURIComponent(shop.owner_email||slug)).then(r=>r.json()).catch(()=>null);
      if(chk && chk.is_following){ let b=document.getElementById('followShopBtn'); if(b){ b.innerText='✓ Following'; b.style.background='#F1F1F2'; b.style.color='#000'; } }
    }
  }catch(e){}
  let h='';
  prods.forEach(p=>{h+=`<div class="card"><img loading="lazy" src="${p.image||'https://via.placeholder.com/300'}"><div class="card-body"><h4>${(p.name||p.title||'').replace(/</g,'&lt;')}</h4><div class="price">UGX ${(p.price||0).toLocaleString()}</div><a class="btn" href="/product/${p.id||p._id}">View Product</a></div></div>`;});
  if(!prods.length) h='<p style="padding:20px">No products yet</p>';
  document.getElementById('products').innerHTML=h;
  statsP.then(stats=>{
    if(!stats) return;
    document.getElementById('statFollowers').innerText=(stats.followers||0).toLocaleString();
    document.getElementById('statFollowing').innerText=(stats.following||0).toLocaleString();
    document.getElementById('statLikes').innerText=(stats.total_likes||0).toLocaleString();
    document.getElementById('statViews').innerText=(stats.total_views||0).toLocaleString();
  }).catch(()=>{});
  }catch(e){ document.getElementById('loading').innerHTML='Error: '+e.message; }
}
function showShopTab(tab){
  let pBtn=document.getElementById('tabProductsBtn'), rBtn=document.getElementById('tabReelsBtn');
  let reelsDiv=document.getElementById('shopReelsTab'), prodGrid=document.getElementById('products');
  if(tab==='reels'){
    rBtn.classList.add('active'); pBtn.classList.remove('active');
    reelsDiv.style.display='block'; prodGrid.style.display='none';
    loadShopReels();
  } else {
    pBtn.classList.add('active'); rBtn.classList.remove('active');
    reelsDiv.style.display='none'; prodGrid.style.display='grid';
  }
}
async function loadShopReels(){
  try{
    let slug=cleanSlug((window._currentShop||{}).shop_slug||(window._currentShop||{}).business_name||'');
    let r=await fetch('/api/sannlas/reels/feed?shop='+encodeURIComponent(slug));
    let reels=await r.json();
    let grid=document.getElementById('shopReelsGrid'), empty=document.getElementById('shopReelsEmpty');
    if(!reels.length){ empty.style.display='block'; return; }
    empty.style.display='none';
    grid.innerHTML=reels.map(re=>`<div onclick="location.href='/reels'" style="aspect-ratio:9/16;background:#000;border-radius:8px;overflow:hidden"><video src="${re.video_url}" muted style="width:100%;height:100%;object-fit:cover"></video></div>`).join('');
  }catch(e){}
}
function openShopChat(){ let s=window._currentShop||{}; location.href='/chat?shop='+encodeURIComponent(cleanSlug(s.shop_slug||s.business_name||'')); }
function shareShopLink(){ let url=location.href; if(navigator.share) navigator.share({title:document.getElementById('shopNameBig').innerText, url:url}); else { navigator.clipboard.writeText(url); alert('Link copied!'); } }
async function toggleFollowShop(){
  let b=document.getElementById('followShopBtn'); if(!b) return;
  let me=null; try{ me=JSON.parse(localStorage.getItem('sannlas_user')||'null'); }catch(e){}
  if(!me || !me.email){ alert('Login first to Follow Boss!'); location.href='/login'; return; }
  let s=window._currentShop||{};
  let isF=b.innerText.includes('Following');
  b.disabled=true; b.innerText='...';
  try{
    let url = isF ? '/api/unfollow' : '/api/follow';
    let body = isF ? {email: me.email, target_email: s.owner_email||s.email||''} : {email: me.email, target_email: s.owner_email||s.email||'', target_shop: s.shop_slug||s.business_name||''};
    let r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    let j=await r.json();
    if(j.success || j.followers!==undefined){
      b.innerText = isF ? '➕ Follow' : '✓ Following';
      b.style.background = isF ? '#FE2C55' : '#F1F1F2';
      b.style.color = isF ? '#fff' : '#000';
      // Refresh real count from server
      let slug=cleanSlug(s.shop_slug||s.business_name||'');
      let stats=await fetch('/api/shop/'+encodeURIComponent(slug)+'/stats').then(r=>r.json()).catch(()=>null);
      if(stats) document.getElementById('statFollowers').innerText=(stats.followers||0).toLocaleString();
    } else { alert(j.message||'Follow failed'); b.innerText = isF ? '✓ Following' : '➕ Follow'; }
  }catch(e){ alert('Follow error: '+e.message); b.innerText = isF ? '✓ Following' : '➕ Follow'; }
  b.disabled=false;
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
        cached = _SHOP_CACHE.get(cleaned)
        if cached and time.time() - cached['time'] < _CACHE_TTL:
            return jsonify(cached['data'])
        shop = get_shop_fast(cleaned, raw)
        if not shop:
            try:
                conn = get_conn(); cur = conn.cursor()
                cur.execute("SELECT data FROM products WHERE data->>'business' ILIKE %s LIMIT 1", ('%'+raw+'%',))
                row = cur.fetchone(); cur.close(); conn.close()
                if row:
                    p = row[0]
                    if isinstance(p, str): p = json.loads(p)
                    biz = p.get('business','')
                    shop = {"shop_slug": clean_slug_fix(biz), "slug": clean_slug_fix(biz), "business_name": biz, "name": biz, "description": f"Welcome to {biz} shop!", "location": p.get('location','Kampala'), "phone": p.get('phone',''), "owner_email": p.get('seller_email',''), "logo": p.get('shop_logo',''), "verified": False}
            except: pass
        if not shop:
            return jsonify({'success':False,'shop':None,'products':[], 'message': f'Shop {raw} not found'}),404
        shop_products = get_shop_products_fast(cleaned, shop)
        result = {'success':True,'shop':shop,'products':shop_products[:100]}
        _SHOP_CACHE[cleaned] = {'time': time.time(), 'data': result}
        return jsonify(result)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success':False,'message':str(e)}),500

@shops_bp.route('/api/shops')
def get_all_shops():
    try:
        if _SHOPS_LIST_CACHE["data"] is not None and time.time() - _SHOPS_LIST_CACHE["time"] < _CACHE_TTL:
            return jsonify(_SHOPS_LIST_CACHE["data"])
        shops = load_db('shops.json', []) or []
        products = load_db('products.json', []) or []
        if not shops:
            seen = {}
            for p in products:
                b = str(p.get('business','') or '').strip()
                if not b: continue
                key = clean_slug_fix(b)
                if key not in seen:
                    seen[key] = {"shop_slug": key, "slug": key, "business_name": b, "name": b, "location": p.get('location','Kampala'), "logo": "", "total_products": 0}
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
        _SHOPS_LIST_CACHE["data"] = shops
        _SHOPS_LIST_CACHE["time"] = time.time()
        return jsonify(shops)
    except Exception as e:
        return jsonify([])
