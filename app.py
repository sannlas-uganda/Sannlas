from flask import Flask, request, jsonify, render_template, Response, send_from_directory
import os, json, uuid, time, hashlib, base64, random, smtplib, threading, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

app = Flask(__name__)
app.config['UPLOAD_FOLDER']='static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)

Talisman(app, content_security_policy=None, force_https=False)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per 15 minutes"], storage_uri="memory://",)
CORS(app, origins=["https://sannlas.onrender.com"])
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

PRODUCTS_CACHE = {"data": None, "time": 0}
CACHE_TTL = 10

@app.after_request
def clarity_headers(response):
    response.headers['X-Clarity'] = 'HD-Enabled'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response

OWNER_EMAIL = "natelieabigail@gmail.com"
OWNER_MOMO = "0795712326"
COIN_PRICE = 599
UPLOAD_COST = 3
TOTAL_COINS = 1000000000

PLANS = {"free14":{"days":14,"price":0,"name":"14 Days FREE"},"30":{"days":30,"price":6540,"name":"30 Days"},"60":{"days":60,"price":13090,"name":"2 Months"},"180":{"days":180,"price":39500,"name":"6 Months"},"365":{"days":365,"price":80000,"name":"1 Year"}}
COIN_PACKS = {"10":{"coins":10,"price":5990,"name":"Starter"},"30":{"coins":30,"price":17970,"name":"Popular"},"60":{"coins":60,"price":35940,"name":"Business"},"150":{"coins":150,"price":89850,"name":"Boss Pro"}}

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL: raise Exception("No DATABASE_URL")
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except ImportError:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def ensure_tables():
    if not DATABASE_URL: return
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, data JSONB NOT NULL);")
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, data JSONB NOT NULL);")
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print("ensure_tables:", e)

def load_db(file, default):
    try:
        if DATABASE_URL:
            ensure_tables(); conn = get_conn()
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
                else:
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                    if not row: return default
                    d=row['data']
                    if isinstance(d,str):
                        try: d=json.loads(d)
                        except: pass
                    return d
            except:
                try:
                    import psycopg2.extras
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
                    else:
                        cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,)); row = cur.fetchone(); cur.close(); conn.close()
                        if not row: return default
                        d=row['data']
                        if isinstance(d,str):
                            try: d=json.loads(d)
                            except: pass
                        return d
                except:
                    try: conn.close()
                    except: pass
                    return default
        else:
            path=f'data/{file}'
            if os.path.exists(path):
                try: return json.load(open(path))
                except: return default
            return default
    except: return default

def save_db(file, data):
    global PRODUCTS_CACHE
    if file in ('products.json','users.json','shops.json'):
        PRODUCTS_CACHE["data"] = None
    if DATABASE_URL:
        try:
            ensure_tables(); conn = get_conn(); cur = conn.cursor()
            try:
                from psycopg.types.json import Jsonb
                if file == 'products.json':
                    cur.execute("DELETE FROM products")
                    for item in data: cur.execute("INSERT INTO products (data) VALUES (%s)", [Jsonb(item)])
                else:
                    cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, Jsonb(data)))
            except ImportError:
                import json as js
                if file == 'products.json':
                    cur.execute("DELETE FROM products")
                    for item in data: cur.execute("INSERT INTO products (data) VALUES (%s)", [js.dumps(item)])
                else:
                    cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, js.dumps(data)))
            conn.commit(); cur.close(); conn.close(); return
        except Exception as e: print(e)
    json.dump(data, open(f'data/{file}','w'), indent=2)

def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()
def get_coin_config():
    cfg = load_db('coin_config.json', None)
    if not cfg:
        cfg = {"total": TOTAL_COINS, "remaining": TOTAL_COINS, "sold": 0, "price": COIN_PRICE, "upload_cost": UPLOAD_COST}
        save_db('coin_config.json', cfg)
    return cfg
def save_coin_config(cfg): save_db('coin_config.json', cfg)

# ===== FIXED SLUG LOGIC - NO RANDOM =====
def make_shop_slug(business):
    if not business:
        return 'shop'
    base = re.sub(r'[^a-z0-9]+', '-', business.lower()).strip('-')
    if not base:
        base = 'shop'
    return base[:50]

def get_biz_key(name):
    if not name:
        return ''
    return re.sub(r'[^a-z0-9]+', '', name.lower())

def ensure_shop_for_user(user):
    shops = load_db('shops.json', [])
    biz = (user.get('business') or '').strip()
    if not biz:
        biz = 'Shop'
    biz_key = get_biz_key(biz)
    slug = make_shop_slug(biz)
    email = (user.get('email') or '').lower()
    for s in shops:
        s_biz = s.get('business_name') or s.get('name') or ''
        if get_biz_key(s_biz) == biz_key and biz_key:
            s['shop_slug'] = slug
            s['slug'] = slug
            s['business_name'] = biz
            s['name'] = biz
            if email:
                s['owner_email'] = email
            if user.get('phone'):
                s['phone'] = user.get('phone')
            save_db('shops.json', shops)
            return s
    existing = next((s for s in shops if (s.get('shop_slug')==slug or s.get('slug')==slug)), None)
    if existing:
        existing['business_name'] = biz
        existing['name'] = biz
        existing['shop_slug'] = slug
        existing['slug'] = slug
        save_db('shops.json', shops)
        return existing
    existing2 = next((s for s in shops if s.get('user_id')==user.get('id')), None)
    if existing2:
        existing2['business_name'] = biz
        existing2['name'] = biz
        existing2['shop_slug'] = slug
        existing2['slug'] = slug
        save_db('shops.json', shops)
        return existing2
    shop = {"id": int(time.time()*1000),"user_id": user.get('id'),"business_name": biz,"name": biz,"shop_slug": slug,"slug": slug,"phone": user.get('phone',''),"owner_email": email,"location": "Kampala","description": "Welcome to " + biz + " shop!","logo_url": "","banner_url": "","verified": False,"total_products": 0,"product_count": 0,"created_at": time.time()}
    shops.append(shop)
    save_db('shops.json', shops)
    return shop

BUSINESS_CATEGORIES = {"Agriculture & Farming":["Fish Farming","Poultry Farming","Crop Farming","Livestock","Animal Feeds"],"Food & Beverages":["Restaurants","Bakeries","Fast Foods","Drinks","Catering"],"Construction & Building":["Cement","Hardware","Plumbing","Electrical","Tiles"],"Fashion & Clothing":["Men's Clothing","Women's Clothing","Kids","Shoes","Bags"],"Electronics & Technology":["Mobile Phones","Laptops","Accessories","TVs","Solar"],"Automotive":["Spare Parts","Car Repair","Boda Boda","Tyres"],"Health & Medical":["Clinics","Pharmacies","Lab Services","Hospitals","Herbal"],"Beauty & Personal Care":["Hair Salons","Cosmetics","Barbers"],"Home & Furniture":["Furniture","Sofas","Kitchenware"],"Professional Services":["Lawyers","Accountants","Printing"],"Education":["Schools","Coaching"],"Travel & Tourism":["Hotels","Tours"]}

@app.route('/')
def home(): return render_template('index.html')
@app.route('/admin')
def admin_page(): return render_template('admin.html')
@app.route('/wallet')
def wallet_page(): return render_template('wallet.html')
@app.route('/balance')
def balance_page(): return render_template('balance.html')
@app.route('/shop/<slug>')
def shop_page_slug(slug): return render_template('shop.html')
@app.route('/shop')
def shop_page(): return render_template('shop.html')
@app.route('/api/categories')
def get_cats(): return jsonify(BUSINESS_CATEGORIES)
@app.route('/api/coins/config')
def coins_config(): return jsonify(get_coin_config())
@app.route('/api/coins/packs')
def coins_packs(): return jsonify(COIN_PACKS)

@app.route('/api/coins/balance')
def coins_balance():
    email=request.args.get('email','').lower().strip()
    phone=request.args.get('phone','').strip()
    users=load_db('users.json',[])
    u=next((x for x in users if x['email']==email or x['phone']==phone), None)
    if not u: return jsonify({'success':False,'coins':0})
    return jsonify({'success':True,'coins': u.get('coins',0)})

@app.route('/api/coins/buy', methods=['POST'])
def coins_buy():
    data=request.json
    email=data.get('email','').lower().strip()
    phone=data.get('phone','').strip()
    pack_id=data.get('pack','10')
    momo_code=data.get('momo_code','').strip().upper()
    momo_phone=data.get('momo_phone','').strip()
    pack = COIN_PACKS.get(pack_id)
    if not pack: return jsonify({'success':False,'message':'Invalid pack'}),400
    txs = load_db('coin_transactions.json', [])
    if any(t.get('momo_code','').upper()==momo_code for t in txs):
        return jsonify({'success':False,'message':f'{momo_code} already used!'}),400
    cfg = get_coin_config()
    if cfg['remaining'] < pack['coins']: return jsonify({'success':False,'message':'Coins finished!'}),400
    new_tx = {'id': int(time.time()*1000), 'email': email, 'phone': phone, 'pack': pack_id, 'coins': pack['coins'], 'price': pack['price'], 'momo_code': momo_code, 'momo_phone': momo_phone, 'time': time.time(), 'status': 'pending'}
    txs.append(new_tx); save_db('coin_transactions.json', txs)
    cfg['remaining'] -= pack['coins']; cfg['sold'] += pack['coins']; save_coin_config(cfg)
    return jsonify({'success':True,'message':'Pending verification by owner!','coins': 0, 'config': cfg, 'pending': True})

@app.route('/api/coins/verify', methods=['POST'])
def coins_verify():
    data=request.json; trans_id=data.get('momo_code','').strip().upper(); action=data.get('action','verify')
    txs=load_db('coin_transactions.json',[]); users=load_db('users.json',[]); cfg=get_coin_config()
    target_tx = None
    for t in txs:
        if t.get('momo_code','').upper()==trans_id:
            target_tx = t
            break
    if not target_tx:
        return jsonify({'success':False,'message':'Transaction not found'}),404
    if action=='block_fake':
        if target_tx.get('status')!= 'blocked_fake':
            cfg['remaining'] += target_tx.get('coins',0)
            cfg['sold'] = max(0, cfg.get('sold',0) - target_tx.get('coins',0))
            for u in users:
                if u.get('email','').lower()==target_tx.get('email','').lower() or u.get('phone','')==target_tx.get('phone',''):
                    u['coins'] = max(0, u.get('coins',0) - target_tx.get('coins',0))
            target_tx['status']='blocked_fake'
            try:
                products = load_db('products.json', [])
                fake_email = target_tx.get('email','').lower()
                fake_phone = target_tx.get('phone','')
                products = [p for p in products if not (p.get('seller_email','').lower()==fake_email or p.get('phone','')==fake_phone)]
                if DATABASE_URL:
                    ensure_tables(); conn=get_conn(); cur=conn.cursor()
                    cur.execute("SELECT id, data FROM products"); rows=cur.fetchall()
                    for row in rows:
                        r_id, r_data = row[0], row[1]
                        if isinstance(r_data, str): r_data=json.loads(r_data)
                        if r_data.get('seller_email','').lower()==fake_email or r_data.get('phone','')==fake_phone:
                            cur.execute("DELETE FROM products WHERE id=%s", (r_id,))
                    conn.commit(); cur.close(); conn.close()
                else:
                    save_db('products.json', products)
                shops = load_db('shops.json', [])
                for s in shops:
                    if s.get('phone','')==fake_phone:
                        s['total_products']=0
                save_db('shops.json', shops)
            except Exception as e:
                print("Delete fake products error:", e)
    else:
        if target_tx.get('status')!= 'verified_by_owner':
            target_tx['status']='verified_by_owner'
            for u in users:
                if u.get('email','').lower()==target_tx.get('email','').lower() or u.get('phone','')==target_tx.get('phone',''):
                    u['coins'] = u.get('coins',0) + target_tx.get('coins',0)
    save_db('coin_transactions.json', txs); save_db('users.json', users); save_coin_config(cfg)
    return jsonify({'success':True, 'action': action})

@app.route('/api/register', methods=['POST'])
def register():
    data=request.json; email=data.get('email','').lower().strip(); phone=data.get('phone','').strip(); pwd=data.get('password',''); biz=data.get('business','')
    if not email or not phone or not pwd: return jsonify({'success':False,'message':'Fill all'}),400
    users=load_db('users.json',[])
    if any(u['email']==email for u in users): return jsonify({'success':False,'message':'Email exists - Login'}),400
    user={'id':int(time.time()*1000),'email':email,'phone':phone,'password':hash_pwd(pwd),'business':biz,'created':time.time(),'plan':'free14','plan_name':'14 Days FREE','subscription_expires':time.time()+14*86400,'paid':True,'verified':False,'followers':0,'total_likes':0,'total_stars':0,'coins':0}
    users.append(user); save_db('users.json',users)
    try: shop = ensure_shop_for_user(user)
    except: shop = None
    safe={k:v for k,v in user.items() if k!='password'}
    if shop: safe['shop']=shop
    return jsonify({'success':True,'user':safe})

@app.route('/api/login', methods=['POST'])
def login():
    data=request.json; email=data.get('email','').lower(); pwd=data.get('password','')
    users=load_db('users.json',[]); u=next((x for x in users if x['email']==email and x['password']==hash_pwd(pwd)),None)
    if not u: return jsonify({'success':False,'message':'Wrong email/password'}),401
    try: ensure_shop_for_user(u)
    except: pass
    safe={k:v for k,v in u.items() if k!='password'}
    safe['subscription_active']=safe.get('subscription_expires',0)>time.time()
    return jsonify({'success':True,'user':safe})

@app.route('/api/products')
def get_products():
    q = request.args.get('q','').lower()
    shop_slug = request.args.get('shop') or request.args.get('shop_slug')
    products=load_db('products.json', [])
    filtered=products
    if q: filtered=[p for p in filtered if q in p.get('name','').lower() or q in p.get('business','').lower()]
    if shop_slug:
        sf = shop_slug.strip()
        exact = [p for p in filtered if p.get('shop_slug')==sf]
        if exact:
            filtered = exact
        else:
            sf_key = get_biz_key(sf.replace('-',' '))
            fallback = []
            for p in filtered:
                pb = p.get('business') or ''
                if get_biz_key(pb) == sf_key or make_shop_slug(pb) == sf:
                    fallback.append(p)
            filtered = fallback
    filtered=sorted(filtered,key=lambda x:x.get('created',0),reverse=True)
    public=[]
    for p in filtered:
        pp=p.copy(); pp.pop('phone',None); public.append(pp)
    return jsonify(public)

@app.route('/api/sell', methods=['POST'])
def sell():
    name=request.form.get('name'); price=int(request.form.get('price',0)); business=request.form.get('business'); location=request.form.get('location'); phone=request.form.get('phone'); desc=request.form.get('desc',''); main_cat=request.form.get('main_category'); stock=int(request.form.get('stock',10)); user_email=request.form.get('user_email','').lower()
    users=load_db('users.json',[]); seller=next((u for u in users if u['phone']==phone or u['email']==user_email),None)
    if not seller: return jsonify({'success':False,'message':'Register first'}),402
    if seller.get('coins',0) < UPLOAD_COST: return jsonify({'success':False,'message':f'Need {UPLOAD_COST} coins! You have {seller.get("coins",0)}','needs_coins':True,'my_coins':seller.get('coins',0)}),402
    images=[]
    for key in request.files:
        f=request.files[key]
        if f and f.filename:
            import base64; file_bytes=f.read(); mime=f.mimetype or 'image/jpeg'; b64=base64.b64encode(file_bytes).decode('utf-8'); images.append(f"data:{mime};base64,{b64}")
    if not images: images=['https://via.placeholder.com/300']
    shop_id=None; shop_slug=None
    try:
        shop = ensure_shop_for_user(seller); shop_id=shop.get('id'); shop_slug=shop.get('shop_slug')
    except Exception as e: print("shop fail", e)
    prod = {'id': int(time.time()*1000),'name': name,'price': price,'business': business,'location': location,'phone': phone,'seller_email': user_email,'description': desc,'image': images[0],'images': images,'main_category': main_cat,'stock': stock,'sold': 0,'rating': 5.0,'reviews': [],'created': time.time(),'shop_id': shop_id,'shop_slug': shop_slug}
    if DATABASE_URL:
        try:
            ensure_tables(); import json as js; conn=get_conn(); cur=conn.cursor()
            try:
                from psycopg.types.json import Jsonb; cur.execute("INSERT INTO products (data) VALUES (%s)", [Jsonb(prod)])
            except: cur.execute("INSERT INTO products (data) VALUES (%s)", [js.dumps(prod)])
            conn.commit(); cur.close(); conn.close()
        except Exception as e: return jsonify({'success':False,'message':f'Upload failed: {str(e)}'}),500
    else:
        products=load_db('products.json',[]); products.append(prod); save_db('products.json', products)
    try:
        shops = load_db('shops.json', [])
        for s in shops:
            if s.get('shop_slug')==shop_slug: s['total_products']=s.get('total_products',0)+1
        save_db('shops.json', shops)
    except: pass
    for u in users:
        if u['phone']==phone or u['email']==user_email: u['coins'] = max(0, u.get('coins',0) - UPLOAD_COST)
    save_db('users.json', users)
    return jsonify({'success':True,'message':f'Added! {UPLOAD_COST} coins used'})

@app.route('/api/shops')
def list_shops():
    shops = load_db('shops.json', [])
    products = load_db('products.json', [])
    counts = {}
    for p in products:
        slug = p.get('shop_slug')
        if slug:
            counts[slug] = counts.get(slug, 0) + 1
    shop_map = {s.get('shop_slug'): s for s in shops if s.get('shop_slug')}
    for s in shops:
        slug = s.get('shop_slug')
        cnt = counts.get(slug, 0)
        s['total_products'] = cnt
        s['product_count'] = cnt
        s['name'] = s.get('business_name') or s.get('business') or s.get('name') or 'Shop'
        s['slug'] = slug
        s['shop_slug'] = slug
        if not s.get('location'):
            s['location'] = 'Uganda'
    for slug, cnt in counts.items():
        if slug not in shop_map:
            sample = next((p for p in products if p.get('shop_slug') == slug), None)
            if sample:
                shops.append({
                    "business_name": sample.get('business') or "Shop",
                    "name": sample.get('business') or "Shop",
                    "business": sample.get('business') or "Shop",
                    "shop_slug": slug,
                    "slug": slug,
                    "location": sample.get('location') or "Uganda",
                    "owner_email": sample.get('seller_email') or "",
                    "phone": sample.get('phone') or "",
                    "total_products": cnt,
                    "product_count": cnt
                })
    no_slug = [p for p in products if not p.get('shop_slug')]
    if no_slug:
        from collections import defaultdict
        biz_groups = defaultdict(list)
        for p in no_slug:
            key = (p.get('business') or p.get('seller_email') or 'Shop').strip()
            biz_groups[key].append(p)
        for biz, plist in biz_groups.items():
            exists = any((s.get('business_name') == biz or s.get('name') == biz) for s in shops)
            if not exists and biz:
                slug = make_shop_slug(biz)
                shops.append({
                    "business_name": biz,
                    "name": biz,
                    "business": biz,
                    "shop_slug": slug,
                    "slug": slug,
                    "location": plist[0].get('location') or "Uganda",
                    "owner_email": plist[0].get('seller_email') or "",
                    "phone": plist[0].get('phone') or "",
                    "total_products": len(plist),
                    "product_count": len(plist)
                })
    filtered = [s for s in shops if (s.get('total_products', 0) > 0 or s.get('product_count', 0) > 0)]
    filtered = sorted(filtered, key=lambda x: x.get('total_products', 0), reverse=True)
    return jsonify(filtered)

@app.route('/api/shop/<slug>')
def get_shop_by_slug(slug):
    shops = load_db('shops.json', [])
    products = load_db('products.json', [])
    shop = next((s for s in shops if s.get('shop_slug')==slug or s.get('slug')==slug), None)
    if shop:
        shop_products = [p for p in products if p.get('shop_slug')==slug or p.get('shop_slug')==shop.get('shop_slug')]
        if not shop_products:
            bk = get_biz_key(shop.get('business_name') or '')
            shop_products = [p for p in products if get_biz_key(p.get('business') or '')==bk]
        shop['total_products'] = len(shop_products)
        shop['product_count'] = len(shop_products)
        shop['name'] = shop.get('business_name') or shop.get('name') or 'Shop'
        shop['slug'] = shop.get('shop_slug') or slug
        return jsonify({'success':True,'shop':shop,'products':shop_products})
    shop_products = [p for p in products if p.get('shop_slug')==slug]
    if not shop_products:
        bk = get_biz_key(slug.replace('-',' '))
        shop_products = [p for p in products if get_biz_key(p.get('business') or '')==bk or make_shop_slug(p.get('business') or '')==slug]
    if shop_products:
        sample = shop_products[0]
        virtual_shop = {
            "business_name": sample.get('business') or "Shop",
            "name": sample.get('business') or "Shop",
            "business": sample.get('business') or "Shop",
            "shop_slug": slug,
            "slug": slug,
            "location": sample.get('location') or "Uganda",
            "owner_email": sample.get('seller_email') or "",
            "phone": sample.get('phone') or "",
            "total_products": len(shop_products),
            "product_count": len(shop_products),
            "description": "Welcome to " + (sample.get('business') or "Shop") + " shop!"
        }
        return jsonify({'success':True,'shop':virtual_shop,'products':shop_products})
    return jsonify({'success':False,'message':'Shop not found'}),404

@app.route('/api/my-products')
def my_products():
    phone=request.args.get('phone','').strip()
    email=request.args.get('email','').lower().strip()
    products=load_db('products.json', [])
    result=[]
    for p in products:
        p_email = (p.get('seller_email') or '').lower()
        p_phone = p.get('phone') or ''
        if email and p_email == email:
            result.append(p)
        elif phone and p_phone == phone:
            result.append(p)
        elif not email and not phone:
            result.append(p)
    return jsonify(result)

@app.route('/api/delete-product/<int:pid>', methods=['DELETE'])
def delete_prod(pid):
    if DATABASE_URL:
        try:
            ensure_tables(); conn=get_conn(); cur=conn.cursor(); cur.execute("SELECT id, data FROM products"); rows=cur.fetchall()
            for row in rows:
                r_id, r_data = row[0], row[1]
                if isinstance(r_data, str): r_data=json.loads(r_data)
                if r_data.get('id')==pid: cur.execute("DELETE FROM products WHERE id=%s", (r_id,)); break
            conn.commit(); cur.close(); conn.close()
        except Exception as e: print(e)
    else:
        products=load_db('products.json', []); products=[p for p in products if p['id']!=pid]; save_db('products.json', products)
    return jsonify({'success':True})

@app.route('/api/fix-slugs')
def fix_slugs():
    products = load_db('products.json', [])
    fixed = 0
    for p in products:
        b = p.get('business') or ''
        if b:
            new_slug = make_shop_slug(b)
            if p.get('shop_slug')!= new_slug:
                p['shop_slug'] = new_slug
                fixed += 1
    save_db('products.json', products)
    shops_map = {}
    for p in products:
        b = p.get('business') or 'Shop'
        slug = p.get('shop_slug')
        if slug not in shops_map:
            shops_map[slug] = {
                "business_name": b,
                "name": b,
                "business": b,
                "shop_slug": slug,
                "slug": slug,
                "location": p.get('location') or "Uganda",
                "owner_email": p.get('seller_email') or "",
                "phone": p.get('phone') or "",
                "total_products": 0,
                "product_count": 0,
                "description": f"Welcome to {b} shop!"
            }
    for s in shops_map.values():
        cnt = sum(1 for p in products if p.get('shop_slug')==s['shop_slug'])
        s['total_products']=cnt
        s['product_count']=cnt
    save_db('shops.json', list(shops_map.values()))
    return jsonify({'success':True,'fixed_products':fixed,'total_shops':len(shops_map),'message':'Slugs fixed! Now use /shop/business-name. Delete this route after.'})

@app.route('/api/admin/data')
def admin_data():
    try:
        products=load_db('products.json',[]) or []
        users=load_db('users.json',[]) or []
        orders=load_db('orders.json',[]) or []
        contacts=load_db('contacts.json',[]) or []
        coin_transactions=load_db('coin_transactions.json',[]) or []
        shops=load_db('shops.json',[]) or []
        coin_config=get_coin_config()
        coin_rev = sum(t.get('price',0) for t in coin_transactions if t.get('status')!='blocked_fake')
        return jsonify({'products':products,'users':users,'orders':orders,'contacts':contacts,'coin_transactions':coin_transactions,'shops':shops,'coin_config':coin_config,'coin_revenue':coin_rev,'total_revenue':0,'total_sellers':len(users),'total_orders':len(orders)})
    except Exception as e:
        print("ADMIN DATA ERROR:", e)
        return jsonify({'products':[],'users':[],'orders':[],'contacts':[],'coin_transactions':[],'shops':[],'coin_config':{"total":1000000000,"remaining":1000000000,"sold":0,"price":599},"coin_revenue":0,'total_revenue':0,'total_sellers':0,'total_orders':0,'error': str(e)}), 200

@app.route('/api/admin/transactions')
def admin_transactions(): return jsonify(load_db('transactions.json', []) or [])
@app.route('/api/orders')
def get_orders(): return jsonify(load_db('orders.json', [])[::-1])
@app.route('/api/contact', methods=['POST'])
def contact_owner(): data=request.json; contacts=load_db('contacts.json', []); contacts.append({**data,'time':time.time(),'id':int(time.time())}); save_db('contacts.json', contacts); return jsonify({'success':True})

if __name__=='__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
