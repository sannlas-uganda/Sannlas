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
            if ps_clean==cleaned or pb_clean==real_name_clean or pb_clean==cleaned or (owner_email and p_email==owner_email):
                pp=dict(p); pp.pop('phone',None); out.append(pp)
            if len(out) >= 100:
                break
        return out
    except:
        return []

def get_live_follow_counts(shop_email, shop_slug):
    shop_email = (shop_email or '').lower().strip()
    shop_slug = (shop_slug or '').lower().strip()
    followers_set = set()
    following_set = set()
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
            return jsonify({'shop_slug': cleaned,'business_name': shop.get('business_name',''),'logo': shop.get('logo',''),'followers': counts['followers'],'following': counts['following'],'total_likes': total_likes,'total_views': total_views,'total_products': total_products})
        shop = None
        try:
            shop = get_shop_fast(cleaned)
        except Exception as e:
            print("get_shop_fast fail:", e)
        if not isinstance(shop, dict): shop = {}
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
        return jsonify({'shop_slug': cleaned,'business_name': shop.get('business_name','') if shop else cleaned,'logo': shop.get('logo','') if shop else '','followers': counts['followers'],'following': counts['following'],'total_likes': total_likes,'total_views': total_views,'total_products': total_products})
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
<div class="shop-profile-header" id="shop-header" style="display:none;padding:0 0 0 0">
  <!-- ✅ BANNER - FIXED -->
  <div id="shopBannerWrap" style="margin:0;background:#FF6A00;overflow:hidden;position:relative;display:none">
  <img id="shopBannerImg" src="" style="width:100%;height:auto;max-height:280px;object-fit:contain;display:block;background:#FF6A00">
</div>
    <!-- ✅ GLASSY CARD - Lifted halfway on banner -->
  <div style="background:rgba(255,255,255,0.75);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,0.7);border-radius:22px;margin:-110px 14px 0 14px;padding:14px 10px 10px;position:relative;z-index:5;box-shadow:0 12px 30px rgba(0,0,0,0.15)">
  <div class="avatar-wrap" style="margin-top:0">
  <div class="avatar-ring"><div class="avatar-box" id="shopAvatarBox">S</div></div><div class="verified-badge">✓</div></div>
  <div class="shop-name" id="shopNameBig">Loading...</div>
  <div class="shop-handle" id="shopHandleText">@shop</div>
  <div class="shop-bio" id="shopBioText"></div>
  <div class="stats-row">
    <div class="stat"><b id="statFollowing">0</b><span>Following</span></div>
    <div class="stat"><b id="statFollowers">0</b><span>Followers</span></div>
    <div class="stat"><b id="statLikes">0</b><span>Likes</span></div>
    <div class="stat"><b id="statViews">0</b><span>Views</span></div>
  </div>
  </div>
  <div class="action-row" id="shopActions"></div>

  <!-- ✅ NEW OWNER TOOLS - All HERE, NEVER go to /my-shop -->
  <div id="ownerTools" style="display:none;background:#FFCC02;border-radius:12px;padding:12px;margin:0 16px 12px;text-align:center">
    <div style="font-weight:900;margin-bottom:8px">👑 YOUR SHOP - Owner Only</div>
    <div style="display:flex;gap:8px;justify-content:center">
      <button onclick="showOwnerPanel('edit')" style="flex:1;background:#000;color:#FFCC02;border:none;padding:11px;border-radius:8px;font-weight:800">✏️ Edit Shop</button>
      <button onclick="showOwnerPanel('add')" style="flex:1;background:#fff;color:#000;border:none;padding:11px;border-radius:8px;font-weight:800;border:2px solid #000">➕ Add Product</button>
    </div>
    <div style="display:flex;gap:8px;justify-content:center;margin-top:8px">
      <button onclick="showOwnerPanel('products')" style="flex:1;background:#fff;color:#000;border:none;padding:10px;border-radius:8px;font-weight:800">🛠️ Manage</button>
      <button onclick="showOwnerPanel('orders')" style="flex:1;background:#fff;color:#000;border:none;padding:10px;border-radius:8px;font-weight:800">📦 Orders</button>
      <button onclick="showOwnerPanel('earnings')" style="flex:1;background:#fff;color:#000;border:none;padding:10px;border-radius:8px;font-weight:800">💰 Earnings</button>
    </div>
  </div>
  <!-- ✅ OWNER MANAGE - Only owner sees, visitors never -->
  <div id="ownerManage" style="display:none;background:#fff;border:2px solid #FFCC02;border-radius:12px;padding:12px;margin:0 16px 12px;text-align:left">
    <div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin-bottom:10px">
      <button onclick="showOwnerPanel('products')" style="background:#000;color:#FFCC02;border:none;padding:9px 12px;border-radius:8px;font-weight:800">🛠️ Manage Products</button>
      <button onclick="showOwnerPanel('edit')" style="background:#F1F1F2;border:none;padding:9px 12px;border-radius:8px;font-weight:800">✏️ Edit Shop</button>
      <button onclick="showOwnerPanel('orders')" style="background:#F1F1F2;border:none;padding:9px 12px;border-radius:8px;font-weight:800">📦 Orders</button>
      <button onclick="showOwnerPanel('add')" style="background:#F1F1F2;border:none;padding:9px 12px;border-radius:8px;font-weight:800">➕ Add</button>
      <button onclick="showOwnerPanel('earnings')" style="background:#F1F1F2;border:none;padding:9px 12px;border-radius:8px;font-weight:800">💰 Earnings</button>
    </div>
    <div id="panel-products">
      <!-- STATS -->
      <div id="manageStats" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px"></div>
      <!-- SEARCH + FILTER -->
      <input id="manageSearch" placeholder="🔍 Search product..." oninput="renderOwnerManage()" style="width:100%;padding:11px;border-radius:10px;border:1px solid #ddd;margin-bottom:8px;box-sizing:border-box">
      <div style="display:flex;gap:6px;margin-bottom:10px">
        <button onclick="setManageFilter('all')" id="mf-all" style="flex:1;padding:8px;border-radius:20px;border:none;background:#000;color:#FFCC02;font-weight:900">All</button>
        <button onclick="setManageFilter('active')" id="mf-active" style="flex:1;padding:8px;border-radius:20px;border:1px solid #ddd;background:#fff">Active</button>
        <button onclick="setManageFilter('hidden')" id="mf-hidden" style="flex:1;padding:8px;border-radius:20px;border:1px solid #ddd;background:#fff">Hidden</button>
        <button onclick="setManageFilter('low')" id="mf-low" style="flex:1;padding:8px;border-radius:20px;border:1px solid #ddd;background:#fff">⚠️ Low</button>
      </div>
      <div id="ownerProductsList" style="font-size:13px">Loading your products...</div>
    </div>
        <div id="panel-edit" style="display:none">
      <!-- ✅ LOGO - NEW -->
      <div style="text-align:center;margin-bottom:8px">
        <img id="editLogoPreview" src="" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:3px solid #FFCC02;display:none">
        <p style="font-size:12px;font-weight:800;margin:6px 0">🏪 Shop Logo</p>
        <label style="display:block;background:#F1F1F2;padding:10px;border-radius:8px;font-weight:800;font-size:13px;cursor:pointer">
          📷 Choose Logo Photo
          <input type="file" id="editLogoFile" accept="image/*" onchange="previewShopLogo(this)" style="display:none">
        </label>
        <input id="editLogo" placeholder="Or paste Logo Image URL here" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:8px">
              <!-- ✅ BANNER EDIT - NEW -->
      <div style="text-align:center;margin:10px 0">
        <img id="editBannerPreview" src="" style="width:100%;height:90px;object-fit:cover;border-radius:10px;border:2px solid #FFCC02;display:none">
        <p style="font-size:12px;font-weight:800;margin:6px 0">🖼️ Shop Banner / Cover Photo</p>
        <label style="display:block;background:#F1F1F2;padding:10px;border-radius:8px;font-weight:800;font-size:13px;cursor:pointer">
          🖼️ Choose Banner Photo
          <input type="file" id="editBannerFile" accept="image/*" onchange="previewShopBanner(this)" style="display:none">
        </label>
        <input id="editBanner" placeholder="Or paste Banner Image URL here" style="width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:8px">
      </div>
      </div>
      <input id="editBiz" placeholder="Shop Name" style="width:100%;padding:10px;margin:4px 0;border:1px solid #ddd;border-radius:8px">
      <input id="editPhone" placeholder="Phone" style="width:100%;padding:10px;margin:4px 0;border:1px solid #ddd;border-radius:8px">
      <input id="editLoc" placeholder="Location" style="width:100%;padding:10px;margin:4px 0;border:1px solid #ddd;border-radius:8px">
      <textarea id="editDesc" placeholder="Description" style="width:100%;padding:10px;margin:4px 0;border:1px solid #ddd;border-radius:8px"></textarea>
      <button onclick="saveShopSettings()" style="width:100%;background:#000;color:#FFCC02;border:none;padding:12px;border-radius:8px;font-weight:900">💾 Save Shop</button>
    </div>
    <div id="panel-orders" style="display:none">
      <div id="orderStats" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:10px"></div>
      <div style="display:flex;gap:6px;margin-bottom:10px;overflow-x:auto">
        <button onclick="setOrderFilter('all')" id="of-all" style="padding:8px 12px;border-radius:20px;border:none;background:#000;color:#FFCC02;font-weight:900;white-space:nowrap">All</button>
        <button onclick="setOrderFilter('new')" id="of-new" style="padding:8px 12px;border-radius:20px;border:1px solid #ddd;background:#fff;white-space:nowrap">🆕 New</button>
        <button onclick="setOrderFilter('confirmed')" id="of-confirmed" style="padding:8px 12px;border-radius:20px;border:1px solid #ddd;background:#fff;white-space:nowrap">✅ Confirmed</button>
        <button onclick="setOrderFilter('shipped')" id="of-shipped" style="padding:8px 12px;border-radius:20px;border:1px solid #ddd;background:#fff;white-space:nowrap">🚚 Shipped</button>
        <button onclick="setOrderFilter('delivered')" id="of-delivered" style="padding:8px 12px;border-radius:20px;border:1px solid #ddd;background:#fff;white-space:nowrap">✔️ Delivered</button>
      </div>
      <div id="ownerOrdersList" style="font-size:13px">Loading orders...</div>
    </div>
    <div id="panel-earnings" style="display:none">
      <div id="ownerEarningsBox" style="font-size:14px;text-align:center;padding:10px">Loading earnings...</div>
    </div>
  </div>
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
  let bannerWrap = document.getElementById('shopBannerWrap');
  let bannerImg = document.getElementById('shopBannerImg');
  if(bannerWrap && bannerImg && (shop.banner || shop.cover)){ bannerImg.src = shop.banner || shop.cover; bannerWrap.style.display = 'block'; }
  document.getElementById('shopNameBig').innerText='🏪 '+(shop.business_name||shop.name||slug);
  document.getElementById('shopHandleText').innerText='@'+cleanSlug(shop.shop_slug||shop.business_name)+' • '+(shop.category||'Shop');
  document.getElementById('shopBioText').innerHTML=`📍 ${shop.location||'Uganda'} | 📞 ${shop.phone||''}<br>${shop.description||'Welcome to '+ (shop.business_name||'shop') +' shop! Quality products, fast delivery in Uganda 🇺🇬'}<br><span style="color:#FF6A00;font-weight:800">${prods.length} Products • Kampala</span>`;
  let _me = null; try{ _me = JSON.parse(localStorage.getItem('sannlas_user')||'null'); }catch(e){}
  let _myEmail = (_me && _me.email ? _me.email.toLowerCase().trim() : '');
  let _fallbackEmail = (prods[0] && (prods[0].seller_email||prods[0].shop_email||prods[0].user_email) || '');
  let _ownerEmail = ((shop.owner_email||shop.email||_fallbackEmail||'').toLowerCase().trim());
  let _isOwner = _myEmail && _ownerEmail && _myEmail === _ownerEmail;
  let _ownerBox = document.getElementById('ownerTools');
  if(_ownerBox) _ownerBox.style.display = _isOwner ? 'block' : 'none';
  let _manageBox = document.getElementById('ownerManage');
  if(_manageBox) _manageBox.style.display = _isOwner ? 'block' : 'none';
  if(_isOwner){
    document.getElementById('editBiz').value = shop.business_name||'';
    document.getElementById('editPhone').value = shop.phone||'';
    document.getElementById('editLoc').value = shop.location||'Kampala';
    document.getElementById('editDesc').value = shop.description||'';
        // Fill logo - HIDE base64, only show URL
    _newShopLogo = '';
    let logoInput = document.getElementById('editLogo');
    let _logoVal = shop.logo || shop.logo_url || '';
    if(logoInput) logoInput.value = _logoVal.startsWith('http') ? _logoVal : (_logoVal ? '✅ Photo uploaded - choose new to replace' : '');
    let logoPrev = document.getElementById('editLogoPreview');
    if(logoPrev && shop.logo){ logoPrev.src = shop.logo; logoPrev.style.display = 'block'; }
        // Show banner on load - HIDE base64
    _newShopBanner = '';
    let bannerInput = document.getElementById('editBanner');
    let _bannerVal = shop.banner || shop.cover || '';
    if(bannerInput) bannerInput.value = _bannerVal.startsWith('http') ? _bannerVal : (_bannerVal ? '✅ Photo uploaded - choose new to replace' : '');
    let bannerPrev = document.getElementById('editBannerPreview');
    if(bannerPrev && shop.banner){ bannerPrev.src = shop.banner; bannerPrev.style.display = 'block'; }
    let bw2 = document.getElementById('shopBannerWrap');
    let bi2 = document.getElementById('shopBannerImg');
    if(bw2 && bi2 && shop.banner){ bi2.src = shop.banner; bw2.style.display = 'block'; }
    loadOwnerProducts(prods);
    loadOwnerOrders();
  }
  if(_isOwner){
    document.getElementById('shopActions').innerHTML=`
      <div style="display:flex;gap:8px;justify-content:center;width:100%">
        <div style="flex:1;background:#FFCC02;color:#000;padding:11px;border-radius:8px;font-weight:900;text-align:center">👑 This is YOUR Shop</div>
        <button onclick="shareShopLink()" style="width:44px;background:#F1F1F2;border:none;border-radius:8px;font-size:18px">↗️</button>
      </div>`;
  } else {
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
  try{
    let me = JSON.parse(localStorage.getItem('sannlas_user')||'null');
    if(me && me.email){
      let chk = await fetch('/api/follow/check?email='+encodeURIComponent(me.email)+'&target='+encodeURIComponent(shop.owner_email||slug)).then(r=>r.json()).catch(()=>null);
      if(chk && chk.is_following){ let b=document.getElementById('followShopBtn'); if(b){ b.innerText='✓ Following'; b.style.background='#F1F1F2'; b.style.color='#000'; } }
    }
  }catch(e){}
     let h='';
  prods.filter(p=> !(p.is_hidden || p.hidden)).forEach(p=>{
    let disc = Number(p.discount_price||0);
    let stock = Number(p.stock ?? p.quantity ?? 0);
    let saleHtml = disc>0 ? `<div style="font-size:12px;color:#888;text-decoration:line-through">UGX ${Number(p.price||0).toLocaleString()}</div><div class="price" style="color:#c0392b">UGX ${disc.toLocaleString()} 🔥 SALE -${Math.round((1-disc/Number(p.price||1))*100)}%</div>` : `<div class="price">UGX ${Number(p.price||0).toLocaleString()}</div>`;
    let featHtml = p.featured ? `<span style="background:#FFCC02;padding:2px 6px;border-radius:10px;font-size:11px;font-weight:900">⭐ Featured</span>` : '';
    let stockHtml = stock<=0 ? `<div style="color:#ff4444;font-size:11px;font-weight:900">❌ Out of Stock</div>` : stock<5 ? `<div style="color:#ff8800;font-size:11px;font-weight:900">⚠️ Only ${stock} left!</div>` : `<div style="color:#00aa00;font-size:11px">✅ In Stock</div>`;
    let promoHtml = p.promo_coins ? `<div style="color:#00aa00;font-size:11px;font-weight:900">💰 ${p.promo_coins} coins promo</div>` : '';
    h+=`<div class="card"><div style="position:relative"><img loading="lazy" src="${p.image||'https://via.placeholder.com/300'}"><div style="position:absolute;top:6px;left:6px;display:flex;gap:4px">${featHtml} ${disc>0?'<span style="background:#c0392b;color:#fff;padding:2px 6px;border-radius:10px;font-size:11px">SALE</span>':''}</div></div><div class="card-body"><h4>${(p.name||p.title||'').replace(/</g,'&lt;')}</h4>${saleHtml}${stockHtml}${promoHtml}<div style="font-size:11px;color:#888">👁️ ${p.views||0} • 🛒 ${p.sold||0} sold</div><a class="btn" href="/product/${p.id||p._id}">View Product</a></div></div>`;
  });
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
function showOwnerPanel(name){
  // ✅ Add Product -> Go to Sell Page (real upload with 4 photos + promo)
  if(name==='add'){
    location.href = '/sell?mode=form';
    return;
  }
  ['products','edit','orders','add','earnings'].forEach(n=>{
    let el=document.getElementById('panel-'+n);
    if(el) el.style.display = (n===name)?'block':'none';
  });
  if(name==='earnings') loadOwnerEarnings();
}
function _ownerBody(extra){
  let me=JSON.parse(localStorage.getItem('sannlas_user')||'null');
  let s=window._currentShop||{};
  return Object.assign({email:me?.email||'', shop_slug: cleanSlug(s.shop_slug||s.business_name||'')}, extra||{});
}
let _manageProducts = [];
let _manageFilter = 'all';
function setManageFilter(f){
  _manageFilter = f;
  ['all','active','hidden','low'].forEach(x=>{
    let b = document.getElementById('mf-'+x);
    if(b){ b.style.background = (x===f)?'#000':'#fff'; b.style.color = (x===f)?'#FFCC02':'#000'; }
  });
  renderOwnerManage();
}
function loadOwnerProducts(prods){
  _manageProducts = prods || [];
  renderOwnerManage();
}
function renderOwnerManage(){
  let el = document.getElementById('ownerProductsList'); if(!el) return;
  let q = (document.getElementById('manageSearch')?.value || '').toLowerCase();
  let list = _manageProducts.filter(p=>{
    if(q && !(p.name||'').toLowerCase().includes(q)) return false;
    let hidden = p.is_hidden || p.hidden;
    let stock = Number(p.stock ?? p.quantity ?? 0);
    if(_manageFilter==='active' && hidden) return false;
    if(_manageFilter==='hidden' && !hidden) return false;
    if(_manageFilter==='low' && stock >= 5) return false;
    return true;
  });
  // STATS
  let totalVal = _manageProducts.reduce((s,p)=> s + (Number(p.price||0) * Number(p.stock ?? p.quantity ?? 0)), 0);
  let lowCount = _manageProducts.filter(p=> Number(p.stock ?? p.quantity ?? 0) < 5).length;
  let st = document.getElementById('manageStats');
  if(st) st.innerHTML = `
    <div style="background:#000;color:#fff;padding:10px;border-radius:10px;text-align:center"><b style="color:#FFCC02;font-size:18px">${_manageProducts.length}</b><br><small>Products</small></div>
    <div style="background:#fff;padding:10px;border-radius:10px;text-align:center;border:1px solid #eee"><b style="font-size:13px">UGX ${totalVal.toLocaleString()}</b><br><small>Stock Value</small></div>
    <div style="background:${lowCount?'#ff4444':'#00aa00'};color:#fff;padding:10px;border-radius:10px;text-align:center"><b>${lowCount}</b><br><small>Low Stock ⚠️</small></div>`;
  if(!list.length){ el.innerHTML='<p style="text-align:center;color:#888;padding:20px">No products found</p>'; return; }
  el.innerHTML = list.map(p=>{
    let stock = Number(p.stock ?? p.quantity ?? 0);
    let pid = p.id || p._id;
    let disc = Number(p.discount_price || 0);
    let hidden = p.is_hidden || p.hidden;
    let badge = hidden ? '<span style="background:#ff4444;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">🔴 Hidden</span>' : '<span style="background:#00aa00;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">🟢 Active</span>';
    let lowBadge = stock < 5 ? '<span style="background:#FFCC02;color:#000;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:900">⚠️ Low Stock</span>' : '';
    let saleBadge = disc > 0 ? `<span style="background:#c0392b;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">🔥 SALE -${Math.round((1-disc/Number(p.price||1))*100)}%</span>` : '';
    let featBadge = p.featured ? '<span style="background:#FFCC02;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:900">⭐ Featured</span>' : '';
    return `<div style="background:#fff;border-radius:12px;padding:10px;margin-bottom:10px;border:1px solid #eee;display:flex;gap:10px">
      <img src="${p.image||''}" style="width:80px;height:80px;object-fit:cover;border-radius:10px">
      <div style="flex:1;min-width:0">
        <div style="display:flex;gap:4px;flex-wrap:wrap">${badge} ${lowBadge} ${saleBadge} ${featBadge}</div>
        <input value="${(p.name||'').replace(/"/g,'&quot;')}" onchange="ownerUpdateProduct('${pid}','name',this.value)" style="width:100%;font-weight:900;border:none;border-bottom:1px solid #eee;padding:4px 0;margin-top:4px">
        <textarea onchange="ownerUpdateProduct('${pid}','description',this.value)" style="width:100%;border:none;border-bottom:1px solid #eee;font-size:12px;color:#666;resize:none" rows="1">${p.description||''}</textarea>
        <div style="display:flex;gap:6px;align-items:center;margin-top:4px;flex-wrap:wrap">
          <label style="font-size:11px">Price <input type="number" value="${p.price||0}" onchange="ownerUpdateProduct('${pid}','price',this.value)" style="width:75px;padding:5px;border-radius:6px;border:1px solid #ddd"></label>
          <label style="font-size:11px">SALE <input type="number" value="${disc||''}" placeholder="Discount" onchange="ownerUpdateProduct('${pid}','discount_price',this.value)" style="width:75px;padding:5px;border-radius:6px;border:1px solid #FFCC02"></label>
          <label style="font-size:11px">Stock <input type="number" value="${stock}" onchange="ownerUpdateProduct('${pid}','stock',this.value)" style="width:55px;padding:5px;border-radius:6px;border:1px solid #ddd"></label>
          <label style="font-size:11px">💰 Promo <input type="number" value="${p.promo_coins||0}" onchange="ownerUpdateProduct('${pid}','promo_coins',this.value)" style="width:50px;padding:5px;border-radius:6px;border:1px solid #ddd"></label>
        </div>
        <div style="font-size:11px;color:#888;margin-top:4px">👁️ ${p.views||0} views • 🛒 ${p.sold||0} sold</div>
        <div style="display:flex;gap:5px;margin-top:6px">
          <button onclick="ownerUpdateProduct('${pid}','featured',${p.featured?'0':'1'})" style="padding:6px 10px;border-radius:8px;border:1px solid #FFCC02;background:${p.featured?'#FFCC02':'#fff'};font-weight:900;font-size:12px">⭐ Feature</button>
          <button onclick="ownerToggleHide('${pid}',${!hidden})" style="padding:6px 10px;border-radius:8px;border:1px solid #ddd;background:#fff;font-size:12px">${hidden?'👁️ Show':'🙈 Hide'}</button>
          <button onclick="ownerDeleteProduct('${pid}')" style="padding:6px 10px;border-radius:8px;border:none;background:#ff4444;color:#fff;font-size:12px">🗑️ Delete</button>
        </div>
      </div>
    </div>`;
  }).join('');
}
async function ownerUpdateProduct(id, field, value){
  let body = _ownerBody({id:id, field:field, value:value});
  // also send old format for price/stock compat
  body[field] = value;
  let r = await fetch('/api/shop-owner/update-field',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  let j = await r.json().catch(()=>({}));
  if(j.success){
    let p = _manageProducts.find(x=> String(x.id)===String(id));
    if(p){ p[field]=value; if(field==='stock') p.quantity=value; if(field==='featured') p.featured = (value==1||value=='1'); }
    // Don't reload - just re-render to keep search/filter
    renderOwnerManage();
  } else alert(j.message||'Update failed');
}
// Keep old names working
async function ownerUpdatePrice(id,price){ return ownerUpdateProduct(id,'price',price); }
async function ownerUpdateStock(id,stock){ return ownerUpdateProduct(id,'stock',stock); }
async function ownerToggleHide(id,hidden){
  let r = await fetch('/api/shop-owner/toggle-hide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(_ownerBody({id:id,hidden:hidden}))});
  let j = await r.json().catch(()=>({}));
  if(j.success){ let p=_manageProducts.find(x=>String(x.id)===String(id)); if(p){ p.is_hidden=hidden; p.hidden=hidden; } renderOwnerManage(); }
}
async function ownerDeleteProduct(id){
  if(!confirm('Delete this product?')) return;
  await fetch('/api/shop-owner/delete-product',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(_ownerBody({id:id}))});
  _manageProducts = _manageProducts.filter(x=> String(x.id)!==String(id));
  renderOwnerManage();
}
var _newShopBanner = '';

function previewShopBanner(input){
  var file = input.files[0];
  if(!file) return;
  var reader = new FileReader();
  reader.onload = function(e){
    _newShopBanner = e.target.result;
    var prev = document.getElementById('editBannerPreview');
    if(prev){ prev.src = _newShopBanner; prev.style.display = 'block'; }
    var bw = document.getElementById('shopBannerWrap');
    var bi = document.getElementById('shopBannerImg');
    if(bw && bi){ bi.src = _newShopBanner; bw.style.display = 'block'; }
  };
  reader.readAsDataURL(file);
}
let _newShopLogo = ''; // holds new logo if owner picks photo

function previewShopLogo(input){
  let file = input.files[0];
  if(!file) return;
  let reader = new FileReader();
  reader.onload = function(e){
    _newShopLogo = e.target.result; // base64 photo
    let prev = document.getElementById('editLogoPreview');
    prev.src = _newShopLogo;
    prev.style.display = 'block';
    // Also show in top avatar instantly for preview
    let topAvatar = document.getElementById('shopAvatarBox');
    if(topAvatar) topAvatar.innerHTML = `<img src="${_newShopLogo}">`;
  };
  reader.readAsDataURL(file);
}

// When owner types URL, preview it too
document.addEventListener('input', function(e){
  if(e.target && e.target.id === 'editLogo'){
    let url = e.target.value.trim();
    if(url){
      _newShopLogo = url;
      let prev = document.getElementById('editLogoPreview');
      prev.src = url; prev.style.display = 'block';
    }
  }
  if(e.target && e.target.id === 'editBanner'){
    var burl = e.target.value.trim();
    if(burl){
      _newShopBanner = burl;
      var bprev = document.getElementById('editBannerPreview');
      if(bprev){ bprev.src = burl; bprev.style.display = 'block'; }
    }
  }});
async function saveShopSettings(){
  let _logoIn = document.getElementById('editLogo').value.trim();
  let _bannerIn = document.getElementById('editBanner').value.trim();
  let logoVal = _newShopLogo || (_logoIn.startsWith('http') ? _logoIn : '');
  let bannerVal = _newShopBanner || (_bannerIn.startsWith('http') ? _bannerIn : '');
  // If no new photo, keep old one - don't overwrite with empty
  if(!logoVal) logoVal = (window._currentShop||{}).logo || '';
  if(!bannerVal) bannerVal = (window._currentShop||{}).banner || '';
let body = _ownerBody({    business_name: document.getElementById('editBiz').value, logo: logoVal, banner: bannerVal, phone: document.getElementById('editPhone').value, location: document.getElementById('editLoc').value, description: document.getElementById('editDesc').value});  let r=await fetch('/api/shop-owner/update-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  let j=await r.json();
  if(j.success){ alert('Shop saved - visible to all!'); location.reload(); } else alert(j.message||'Failed');
}
async function ownerAddProduct(){
  let body=_ownerBody({name:document.getElementById('addName').value,price:parseInt(document.getElementById('addPrice').value||0),stock:parseInt(document.getElementById('addStock').value||0),image:document.getElementById('addImage').value,description:document.getElementById('addDesc').value});
  if(!body.name||!body.price){ alert('Name + Price required'); return; }
  let r=await fetch('/api/shop-owner/add-product',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  let j=await r.json();
  if(j.success){ alert('✅ Product added - visible to all!'); location.reload(); } else alert(j.message||'Failed');
}
let _allOrders = [];
let _orderFilter = 'all';
function setOrderFilter(f){
  _orderFilter = f;
  ['all','new','confirmed','shipped','delivered'].forEach(x=>{
    let b = document.getElementById('of-'+x);
    if(b){ b.style.background = (x===f)?'#000':'#fff'; b.style.color = (x===f)?'#FFCC02':'#000'; }
  });
  renderOwnerOrders();
}
function renderOwnerOrders(){
  let el = document.getElementById('ownerOrdersList'); if(!el) return;
  let st = document.getElementById('orderStats');
  let newCount = _allOrders.filter(o=> ['new','pending',''].includes(String(o.status||'new').toLowerCase())).length;
  let totalEarn = _allOrders.filter(o=> ['delivered','completed','paid'].includes(String(o.status||'').toLowerCase())).reduce((s,o)=> s+Number(o.total||o.price||0), 0);
  if(st) st.innerHTML = `
    <div style="background:#ff4444;color:#fff;padding:10px;border-radius:10px;text-align:center"><b style="font-size:18px">${newCount}</b><br><small>🆕 New Orders</small></div>
    <div style="background:#000;color:#fff;padding:10px;border-radius:10px;text-align:center"><b style="font-size:18px">${_allOrders.length}</b><br><small>Total Orders</small></div>
    <div style="background:#00aa00;color:#fff;padding:10px;border-radius:10px;text-align:center"><b style="font-size:13px">UGX ${totalEarn.toLocaleString()}</b><br><small>Delivered 💰</small></div>`;
  let list = _allOrders.filter(o=>{
    if(_orderFilter==='all') return true;
    let s = String(o.status||'new').toLowerCase();
    if(_orderFilter==='new') return ['new','pending',''].includes(s);
    return s===_orderFilter;
  });
  if(!list.length){ el.innerHTML='<p style="text-align:center;color:#888;padding:20px">No orders in this filter</p>'; return; }
  el.innerHTML = list.map(o=>{
    let s = String(o.status||'new').toLowerCase();
    let color = s==='new'||s==='pending' ? '#ff8800' : s==='confirmed' ? '#0066ff' : s==='shipped' ? '#8800ff' : s==='delivered'||s==='completed' ? '#00aa00' : s==='cancelled' ? '#ff4444' : '#888';
    let buyer = o.buyer_name || o.customer_name || o.buyer_email || o.email || 'Customer';
    let phone = (o.buyer_phone || o.phone || o.customer_phone || '').toString().replace(/[^0-9]/g,'');
    let date = o.created_at ? new Date(o.created_at).toLocaleDateString() + ' ' + new Date(o.created_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '';
    return `<div style="background:#fff;border:1px solid #eee;border-radius:12px;padding:10px;margin-bottom:10px;display:flex;gap:10px">
      <img src="${o.image||o.product_image||''}" onerror="this.style.display='none'" style="width:70px;height:70px;object-fit:cover;border-radius:10px">
      <div style="flex:1;min-width:0">
        <div style="display:flex;justify-content:space-between;gap:6px"><b>${o.product_name||o.name||o.id}</b><span style="background:${color};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:900;text-transform:uppercase">${s}</span></div>
        <div style="font-size:12px;color:#666;margin-top:3px">👤 ${buyer} • Qty: ${o.qty||o.quantity||1} • ${date}</div>
        <div style="font-weight:900;margin-top:3px">UGX ${Number(o.total||o.price||0).toLocaleString()} ${o.size?`• Size: ${o.size}`:''}</div>
        <div style="display:flex;gap:5px;margin-top:7px;flex-wrap:wrap">
          ${s==='new'||s==='pending'?`<button onclick="updateOrderStatus('${o.id}','confirmed')" style="padding:6px 10px;border:none;border-radius:8px;background:#0066ff;color:#fff;font-weight:900;font-size:12px">✅ Confirm</button>`:''}
          ${s==='confirmed'?`<button onclick="updateOrderStatus('${o.id}','shipped')" style="padding:6px 10px;border:none;border-radius:8px;background:#8800ff;color:#fff;font-weight:900;font-size:12px">🚚 Ship</button>`:''}
          ${s==='shipped'?`<button onclick="updateOrderStatus('${o.id}','delivered')" style="padding:6px 10px;border:none;border-radius:8px;background:#00aa00;color:#fff;font-weight:900;font-size:12px">✔️ Delivered</button>`:''}
          ${!['delivered','cancelled','completed'].includes(s)?`<button onclick="updateOrderStatus('${o.id}','cancelled')" style="padding:6px 10px;border:1px solid #ddd;border-radius:8px;background:#fff;font-size:12px">❌ Cancel</button>`:''}
          ${phone?`<button onclick="window.open('https://wa.me/${phone}')" style="padding:6px 10px;border:none;border-radius:8px;background:#25D366;color:#fff;font-weight:900;font-size:12px">💬 WhatsApp</button>`:''}
        </div>
      </div>
    </div>`;
  }).join('');
}
async function loadOwnerOrders(){
  let el=document.getElementById('ownerOrdersList'); if(!el) return;
  let me=JSON.parse(localStorage.getItem('sannlas_user')||'null');
  let s=window._currentShop||{};
  let slug=cleanSlug(s.shop_slug||s.business_name||'');
  let r=await fetch('/api/shop-owner/dashboard?email='+encodeURIComponent(me?.email||'')+'&slug='+encodeURIComponent(slug)).then(r=>r.json()).catch(()=>null);
  _allOrders = r?.orders || [];
  renderOwnerOrders();
}
async function updateOrderStatus(id, status){
  let me=JSON.parse(localStorage.getItem('sannlas_user')||'null');
  let r = await fetch('/api/shop-owner/update-order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:me?.email||'', id:id, status:status})});
  let j = await r.json().catch(()=>({}));
  if(j.success){
    let o = _allOrders.find(x=> String(x.id)===String(id));
    if(o) o.status = status;
    renderOwnerOrders();
    alert('✅ Order -> ' + status.toUpperCase());
  } else alert(j.message||'Failed - need backend PASTE 3');
}
async function loadOwnerEarnings(){
  let el=document.getElementById('ownerEarningsBox'); if(!el) return;
  let me=JSON.parse(localStorage.getItem('sannlas_user')||'null');
  let s=window._currentShop||{};
  let slug=cleanSlug(s.shop_slug||s.business_name||'');
  let r=await fetch('/api/shop-owner/dashboard?email='+encodeURIComponent(me?.email||'')+'&slug='+encodeURIComponent(slug)).then(r=>r.json()).catch(()=>null);
  if(!r||!r.success){ el.innerHTML='No data'; return; }
  el.innerHTML=`<b style="font-size:22px">UGX ${(r.stats?.total_earnings||0).toLocaleString()}</b><br>${r.stats?.total_orders||0} Orders • ${r.stats?.total_products||0} Products<br>👁️ Views: ${r.stats?.total_views||0} | ❤️ Likes: ${r.stats?.total_likes||0}<br><small style="color:#888">REAL - no fake *3</small>`;
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

# ===== ✅ NEW - INDEPENDENT OWNER SYSTEM - No my_shop.py, No Fake Codes =====
def _owner_email_from_req():
    try:
        d = request.get_json(silent=True) or {}
        e = (d.get('email') or '').lower().strip()
        if e: return e
    except: pass
    e = (request.args.get('email') or request.headers.get('X-User-Email') or '').lower().strip()
    return e

def _is_shop_owner(shop_slug, email):
    if not email: return False
    try:
        shop = get_shop_fast(clean_slug_fix(shop_slug), shop_slug)
        if shop and str(shop.get('owner_email','')).lower().strip() == email:
            return True
    except: pass
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT data FROM products WHERE data->>'shop_slug'=%s LIMIT 1", (clean_slug_fix(shop_slug),))
        row = cur.fetchone(); cur.close(); conn.close()
        if row:
            p = row[0]
            if isinstance(p, str): p = json.loads(p)
            if str(p.get('seller_email','')).lower().strip() == email:
                return True
    except: pass
    return False

@shops_bp.route('/api/shop-owner/dashboard')
def shop_owner_dashboard():
    email = _owner_email_from_req()
    slug = clean_slug_fix(request.args.get('slug',''))
    if not email or not _is_shop_owner(slug, email):
        return jsonify({'success':False,'message':'Not owner'}), 403
    shop = get_shop_fast(slug, slug) or {}
    prods = get_shop_products_fast(slug, shop)
    orders = load_db('orders_v2.json', []) or []
    my_orders = [o for o in orders if str(o.get('seller_email','')).lower()==email]
    total_earnings = sum(int(o.get('total') or o.get('price') or 0) for o in my_orders if str(o.get('status','')).lower() in ['paid','completed','delivered','success'])
    return jsonify({'success':True,'shop':shop,'products':prods,'orders':sorted(my_orders,key=lambda x:x.get('created_at',0),reverse=True),
        'stats':{'total_products':len(prods),'total_orders':len(my_orders),'total_earnings':total_earnings,
        'total_views':sum(int(p.get('views',0) or 0) for p in prods),
        'total_likes':sum(int(p.get('likes',0) or 0) for p in prods)}})

@shops_bp.route('/api/shop-owner/update-settings', methods=['POST'])
def shop_owner_update_settings():
    d = request.get_json() or {}
    email = (d.get('email') or '').lower().strip()
    slug = clean_slug_fix(d.get('shop_slug',''))
    if not _is_shop_owner(slug, email):
        return jsonify({'success':False,'message':'Not owner'}), 403
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT data FROM kv_store WHERE key=%s", ('shops.json',))
    row = cur.fetchone()
    shops = row[0] if row else []
    if isinstance(shops, str): shops = json.loads(shops)
    if not isinstance(shops, list): shops = []
    found=False
    for s in shops:
        if clean_slug_fix(s.get('shop_slug') or s.get('business_name'))==slug:
            if d.get('business_name'): s['business_name']=d['business_name']
            if 'phone' in d: s['phone']=d['phone']
            if 'location' in d: s['location']=d['location']
            if 'description' in d: s['description']=d['description']
            if d.get('logo'): s['logo']=d['logo']
            if d.get('banner'): s['banner']=d['banner']
            if d.get('cover'): s['banner']=d['cover']
            found=True
            break
    if not found:
        shops.append({'shop_slug':slug,'business_name':d.get('business_name',slug),'owner_email':email,'phone':d.get('phone',''),'location':d.get('location','Kampala'),'description':d.get('description',''),'logo':d.get('logo',''),'banner':d.get('banner','')})
    # ✅ ALWAYS SAVE - whether found or new - THIS WAS THE BUG
    cur.execute("INSERT INTO kv_store (key,data) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET data=EXCLUDED.data", ('shops.json', json.dumps(shops)))
    conn.commit(); cur.close(); conn.close()
    _SHOP_CACHE.pop(slug, None)
    _SHOPS_LIST_CACHE["data"]=None
    return jsonify({'success':True})
    
@shops_bp.route('/api/shop-owner/add-product', methods=['POST'])
def shop_owner_add_product():
    d = request.get_json() or {}
    email = (d.get('email') or '').lower().strip()
    slug = clean_slug_fix(d.get('shop_slug',''))
    if not _is_shop_owner(slug, email):
        return jsonify({'success':False,'message':'Not owner'}), 403
    if not d.get('name') or not d.get('price'):
        return jsonify({'success':False,'message':'Name + Price required'}), 400
    conn = get_conn(); cur = conn.cursor()
    shop = get_shop_fast(slug, slug) or {}
    new_p = {'name':d['name'],'title':d['name'],'price':int(d['price']),'stock':int(d.get('stock',0) or 0),
             'image':d.get('image',''),'description':d.get('description',''),
             'business':shop.get('business_name',slug),'shop_slug':slug,
             'seller_email':email,'created':time.time(),'views':0,'likes':0,'is_hidden':False}
    cur.execute("INSERT INTO products (data) VALUES (%s)", (json.dumps(new_p),))
    conn.commit(); cur.close(); conn.close()
    _SHOP_CACHE.pop(slug, None)
    return jsonify({'success':True})

@shops_bp.route('/api/shop-owner/update-field', methods=['POST'])
def shop_owner_update_field():
    d = request.get_json() or {}
    field = d.get('field') or ''
    # map frontend field -> DB field
    if field == 'stock':
        return _shop_owner_update_product_field('stock', d)
    if field == 'is_hidden' or field == 'hidden':
        return _shop_owner_update_product_field('is_hidden', d)
    return _shop_owner_update_product_field(field, d)

@shops_bp.route('/api/shop-owner/update-price', methods=['POST'])
def shop_owner_update_price():
    return _shop_owner_update_product_field('price')
@shops_bp.route('/api/shop-owner/update-stock', methods=['POST'])
def shop_owner_update_stock():
    return _shop_owner_update_product_field('stock')
@shops_bp.route('/api/shop-owner/toggle-hide', methods=['POST'])
def shop_owner_toggle_hide():
    return _shop_owner_update_product_field('is_hidden')

def _shop_owner_update_product_field(field, _d=None):
    d = _d or request.get_json() or {}
    email = (d.get('email') or '').lower().strip()
    pid = str(d.get('id',''))
    # value can be in d['value'] (new) or d[field] (old)
    val = d.get('value', d.get(field, d.get('hidden', '')))
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id, data FROM products")
    rows = cur.fetchall()
    for rid, pdata in rows:
        p = pdata if isinstance(pdata, dict) else json.loads(pdata)
        if str(p.get('id'))==pid and str(p.get('seller_email','')).lower()==email:
            if field in ['is_hidden','hidden']:
                v = val
                if isinstance(v, str): v = v.lower() in ['1','true','yes']
                p['is_hidden'] = bool(v); p['hidden'] = bool(v)
            elif field in ['price','stock','quantity','discount_price','promo_coins','featured','views','sold']:
                try: p[field] = int(float(val or 0))
                except: p[field] = 0
                if field=='stock': p['quantity'] = p['stock']
                if field=='quantity': p['stock'] = p['quantity']
            elif field in ['name','description','title']:
                p[field] = str(val or '')
                if field=='name': p['title'] = str(val or '')
            else:
                p[field] = val
            cur.execute("UPDATE products SET data=%s WHERE id=%s", (json.dumps(p), rid))
            conn.commit(); cur.close(); conn.close()
            _SHOP_CACHE.clear()
            return jsonify({'success':True})
    cur.close(); conn.close()
    return jsonify({'success':False,'message':'Not your product'}), 403

@shops_bp.route('/api/shop-owner/update-order', methods=['POST'])
def shop_owner_update_order():
    d = request.get_json() or {}
    email = (d.get('email') or '').lower().strip()
    oid = str(d.get('id',''))
    status = str(d.get('status','')).lower().strip()
    if status not in ['confirmed','shipped','delivered','cancelled','new']:
        return jsonify({'success':False,'message':'Invalid status'}), 400
    # Try orders_v2.json in kv_store + orders table
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT data FROM kv_store WHERE key=%s", ('orders_v2.json',))
        row = cur.fetchone()
        orders = row[0] if row else []
        if isinstance(orders, str): orders = json.loads(orders)
        changed = False
        for o in (orders or []):
            if str(o.get('id'))==oid and str(o.get('seller_email','')).lower()==email:
                o['status'] = status; changed = True; break
        if changed:
            cur.execute("INSERT INTO kv_store (key,data) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET data=EXCLUDED.data", ('orders_v2.json', json.dumps(orders)))
            conn.commit()
        cur.close(); conn.close()
        if changed: return jsonify({'success':True})
    except Exception as e:
        print("update-order kv fail", e)
    # Fallback: try orders table if exists
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE orders SET data = jsonb_set(data, '{status}', %s::jsonb) WHERE data->>'id'=%s", (json.dumps(status), oid))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'message':str(e)}), 500

@shops_bp.route('/api/shop-owner/delete-product', methods=['POST'])
def shop_owner_delete_product():
    d = request.get_json() or {}
    email = (d.get('email') or '').lower().strip()
    pid = str(d.get('id',''))
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id, data FROM products")
    for rid, pdata in cur.fetchall():
        p = pdata if isinstance(pdata, dict) else json.loads(pdata)
        if str(p.get('id'))==pid and str(p.get('seller_email','')).lower()==email:
            cur.execute("DELETE FROM products WHERE id=%s", (rid,))
            conn.commit(); cur.close(); conn.close()
            _SHOP_CACHE.clear()
            return jsonify({'success':True})
    cur.close(); conn.close()
    return jsonify({'success':False}), 404
