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
    response.headers['Accept-CH'] = 'DPR, Viewport-Width, Width'
    return response

OWNER_EMAIL = "natelieabigail@gmail.com"
OWNER_PHONE = "0795712326"
OWNER_MOMO = "0795712326"

COIN_PRICE = 599
UPLOAD_COST = 3
TOTAL_COINS = 1000000000

PLANS = {
    "free14": {"days": 14, "price": 0, "name": "14 Days FREE", "requires_payment": False},
    "30": {"days": 30, "price": 6540, "name": "30 Days", "requires_payment": True},
    "60": {"days": 60, "price": 13090, "name": "2 Months", "requires_payment": True},
    "180": {"days": 180, "price": 39500, "name": "6 Months", "requires_payment": True},
    "365": {"days": 365, "price": 80000, "name": "1 Year", "requires_payment": True}
}

COIN_PACKS = {
    "10": {"coins": 10, "price": 5990, "name": "Starter"},
    "30": {"coins": 30, "price": 17970, "name": "Popular"},
    "60": {"coins": 60, "price": 35940, "name": "Business"},
    "150": {"coins": 150, "price": 89850, "name": "Boss Pro"}
}

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
    for attempt in range(3):
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
                except Exception as e1:
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
                    except Exception as e2:
                        try: conn.close()
                        except: pass
                        if attempt < 2:
                            time.sleep(1)
                            continue
                        return default
            else:
                path=f'data/{file}'
                if os.path.exists(path):
                    try: return json.load(open(path))
                    except: return default
                return default
        except Exception as e:
            print(f"load_db {file} attempt {attempt} failed: {e}")
            if attempt < 2:
                time.sleep(1.5)
                continue
            return default
    return default

def save_db(file, data):
    global PRODUCTS_CACHE
    if file == 'products.json' or file == 'users.json':
        PRODUCTS_CACHE["data"] = None
        PRODUCTS_CACHE["time"] = 0
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

def save_coin_config(cfg):
    save_db('coin_config.json', cfg)

def send_email_helper(to_email, subject, html_body):
    try:
        smtp_email = os.environ.get('SMTP_EMAIL', OWNER_EMAIL); smtp_pass = os.environ.get('SMTP_PASSWORD', '')
        if smtp_pass:
            msg = MIMEMultipart(); msg['From']=smtp_email; msg['To']=to_email; msg['Subject']=subject; msg.attach(MIMEText(html_body,'html'))
            server = smtplib.SMTP('smtp.gmail.com',587); server.starttls(); server.login(smtp_email,smtp_pass); server.send_message(msg); server.quit(); return True
        else: return True
    except: return False

# ===== SHOP HELPER - ONLY NEW CODE =====
def make_shop_slug(business):
    base = re.sub(r'[^a-z0-9]+', '-', (business or 'shop').lower()).strip('-')
    if not base: base='shop'
    return base + '-' + uuid.uuid4().hex[:4]

def ensure_shop_for_user(user):
    shops = load_db('shops.json', [])
    biz = user.get('business','')
    existing = next((s for s in shops if s.get('user_id')==user.get('id') or s.get('business_name')==biz), None)
    if existing: return existing
    slug = make_shop_slug(biz)
    while any(s.get('shop_slug')==slug for s in shops):
        slug = make_shop_slug(biz)
    shop = {
        "id": int(time.time()*1000),
        "user_id": user.get('id'),
        "business_name": biz,
        "shop_slug": slug,
        "phone": user.get('phone',''),
        "location": "Kampala",
        "description": "Welcome to " + biz + " shop on SANNLAS UGANDA!",
        "logo_url": "",
        "banner_url": "",
        "verified": False,
        "total_products": 0,
        "created_at": time.time()
    }
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
def shop_page_slug(slug):
    try: return render_template('shop.html')
    except:
        html = "<script>localStorage.setItem('open_shop_slug','" + slug + "');location.href='/shop?slug=" + slug + "'</script>"
        return Response(html, mimetype='text/html')
@app.route('/shop')
def shop_page():
    try: return render_template('shop.html')
    except: return Response("<h3>Please create templates/shop.html</h3>", mimetype='text/html')
@app.route('/googleac311007501ff6bc.html')
def google_verify_bc(): return send_from_directory('.', 'googleac311007501ff6bc.html')
@app.route('/robots.txt')
def robots_txt(): return Response("User-agent: *\nAllow: /\nSitemap: https://sannlas.onrender.com/sitemap.xml\n", mimetype='text/plain')
@app.route('/sitemap.xml')
def sitemap_xml():
    products = load_db('products.json', [])
    urls=[]
    urls.append('<url><loc>https://sannlas.onrender.com/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>')
    for p in products[:500]:
        urls.append(f'<url><loc>https://sannlas.onrender.com/?product={p.get("id","")}</loc><changefreq>daily</changefreq><priority>0.8</priority></url>')
    xml = f"""<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{''.join(urls)}</urlset>"""
    return Response(xml, mimetype='application/xml')
@app.route('/api/categories')
def get_cats(): return jsonify(BUSINESS_CATEGORIES)
@app.route('/api/plans')
def get_plans(): return jsonify(PLANS)
@app.route('/api/coins/config')
def coins_config():
    cfg = get_coin_config()
    return jsonify(cfg)
@app.route('/api/coins/packs')
def coins_packs():
    return jsonify(COIN_PACKS)
@app.route('/api/coins/balance')
def coins_balance():
    email=request.args.get('email','').lower().strip()
    phone=request.args.get('phone','').strip()
    users=load_db('users.json',[])
    u=next((x for x in users if x['email']==email or x['phone']==phone), None)
    if not u:
        return jsonify({'success':False,'coins':0})
    return jsonify({'success':True,'coins': u.get('coins',0), 'email': u.get('email'), 'phone': u.get('phone')})
@app.route('/api/coins/buy', methods=['POST'])
def coins_buy():
    data=request.json
    email=data.get('email','').lower().strip()
    phone=data.get('phone','').strip()
    pack_id=data.get('pack','10')
    momo_code=data.get('momo_code','').strip().upper()
    momo_phone=data.get('momo_phone','').strip()
    pack = COIN_PACKS.get(pack_id)
    if not pack:
        return jsonify({'success':False,'message':'Invalid pack'}),400
    txs = load_db('coin_transactions.json', [])
    if any(t.get('momo_code','').upper()==momo_code for t in txs):
        return jsonify({'success':False,'message':f'Trans ID {momo_code} already used!'}),400
    cfg = get_coin_config()
    if cfg['remaining'] < pack['coins']:
        return jsonify({'success':False,'message':'Coins finished!'}),400
    new_tx = {'id': int(time.time()*1000), 'email': email, 'phone': phone, 'pack': pack_id, 'coins': pack['coins'], 'price': pack['price'], 'momo_code': momo_code, 'momo_phone': momo_phone, 'time': time.time(), 'status': 'pending_owner_verify', 'to_momo': OWNER_MOMO}
    txs.append(new_tx)
    save_db('coin_transactions.json', txs)
    users=load_db('users.json',[])
    for u in users:
        if u['email']==email or u['phone']==phone:
            u['coins'] = u.get('coins',0) + pack['coins']
    save_db('users.json',users)
    cfg['remaining'] -= pack['coins']
    cfg['sold'] += pack['coins']
    save_coin_config(cfg)
    return jsonify({'success':True,'message':f'Bought {pack["coins"]} coins! Now you can upload {pack["coins"]//3} products','coins': pack['coins'], 'config': cfg})
@app.route('/api/coins/verify', methods=['POST'])
def coins_verify():
    data=request.json
    trans_id=data.get('momo_code','').strip().upper()
    action=data.get('action','verify')
    txs=load_db('coin_transactions.json',[])
    users=load_db('users.json',[])
    cfg=get_coin_config()
    for t in txs:
        if t.get('momo_code','').upper()==trans_id:
            if action=='block_fake':
                t['status']='blocked_fake'
                for u in users:
                    if u['email']==t.get('email') or u['phone']==t.get('phone'):
                        u['coins'] = max(0, u.get('coins',0) - t.get('coins',0))
                cfg['remaining'] += t.get('coins',0)
                cfg['sold'] -= t.get('coins',0)
            else:
                t['status']='verified_by_owner'
    save_db('coin_transactions.json', txs)
    save_db('users.json', users)
    save_coin_config(cfg)
    return jsonify({'success':True})
@app.route('/manifest.json')
def manifest_json():
    return jsonify({"name": "SANNLAS UGANDA-Buy & sell Everything","short_name": "SANNLAS","start_url": "/","scope": "/","display": "standalone","background_color": "#c0392b","theme_color": "#000000","description": "The best online shop in Uganda SN","icons": [{"src": "/icon-192.png","sizes": "192x192","type": "image/png"},{"src": "/icon-512.png","sizes": "512x512","type": "image/png"}]})
@app.route('/service-worker.js')
def sw():
    js = """const CACHE="sannlas-v3"; self.addEventListener('install', e => self.skipWaiting()); self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k))))); }); self.addEventListener('fetch', e => { e.respondWith(fetch(e.request)); });"""
    return Response(js, mimetype='application/javascript')
@app.route('/sw.js')
def sw2():
    return sw()
@app.route('/icon-192.png')
def icon192_json():
    if os.path.exists('icon-192.png'): return send_from_directory('.', 'icon-192.png')
    return ("", 204)
@app.route('/icon-512.png')
def icon512_json():
    if os.path.exists('icon-512.png'): return send_from_directory('.', 'icon-512.png')
    return ("", 204)
@app.route('/api/register', methods=['POST'])
def register():
    data=request.json; email=data.get('email','').lower().strip(); phone=data.get('phone','').strip(); pwd=data.get('password',''); role=data.get('role','seller'); biz=data.get('business','')
    if not email or not phone or not pwd: return jsonify({'success':False,'message':'Email, phone, password required'}),400
    users=load_db('users.json',[])
    if any(u['email']==email for u in users): return jsonify({'success':False,'message':'Email already registered - Login'}),400
    user={'id':int(time.time()*1000),'email':email,'phone':phone,'password':hash_pwd(pwd),'role':role,'business':biz,'created':time.time(),'plan':'free14','plan_name':'14 Days FREE','subscription_expires':time.time()+14*86400,'free_used':True,'paid':True,'verified':False,'nin_status':'not_uploaded','followers':0,'total_likes':0,'total_stars':0,'coins':0}
    users.append(user); save_db('users.json',users)
    try: shop = ensure_shop_for_user(user)
    except: shop = None
    safe={k:v for k,v in user.items() if k!='password'}
    if shop: safe['shop']=shop
    return jsonify({'success':True,'message':'Registered! 14 Days FREE active','user':safe})
@app.route('/api/login', methods=['POST'])
def login():
    data=request.json; email=data.get('email','').lower(); pwd=data.get('password','')
    users=load_db('users.json',[]); u=next((x for x in users if x['email']==email and x['password']==hash_pwd(pwd)),None)
    if not u: return jsonify({'success':False,'message':'Wrong email/password'}),401
    try: ensure_shop_for_user(u)
    except: pass
    safe={k:v for k,v in u.items() if k!='password'}; safe['subscription_active']=safe['subscription_expires']>time.time()
    if 'coins' not in safe: safe['coins']=0
    try:
        shops=load_db('shops.json',[])
        sh=next((s for s in shops if s.get('user_id')==u.get('id') or s.get('business_name')==u.get('business')), None)
        if sh: safe['shop']=sh
    except: pass
    return jsonify({'success':True,'user':safe})
@app.route('/api/send-otp', methods=['POST'])
@limiter.limit("10 per minute")
def send_otp():
    data=request.json; email=data.get('email','').lower().strip(); phone=data.get('phone',''); business=data.get('business',''); otp=data.get('otp') or str(random.randint(100000,999999)); otps=load_db('otps.json',[]); otps=[o for o in otps if o['email']!=email]; otps.append({'email':email,'otp':otp,'phone':phone,'business':business,'time':time.time(),'expires':time.time()+600}); save_db('otps.json', otps)
    send_email_helper(email, f"SANNLAS OTP Code: {otp}", f"<h2>OTP: {otp}</h2>"); send_email_helper(OWNER_EMAIL, f"New User: {business} {email} {phone}", f"<p>{business} {email} {phone} OTP {otp}</p>")
    return jsonify({'success':True,'message':f'OTP sent','otp':otp})
@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data=request.json; email=data.get('email','').lower().strip(); otp=data.get('otp','').strip(); otps=load_db('otps.json',[]); found=next((o for o in otps if o['email']==email and o['otp']==otp and o['expires']>time.time()), None)
    if found: otps=[o for o in otps if o['email']!=email]; save_db('otps.json', otps); return jsonify({'success':True,'message':'OTP verified!'})
    return jsonify({'success':False,'message':'Wrong or expired OTP'}),400
@app.route('/api/verify-nin-number', methods=['POST'])
def verify_nin_number():
    data=request.json; phone=data.get('phone','').strip(); email=data.get('email','').lower().strip(); nin_number=data.get('nin_number','').strip()
    users=load_db('users.json',[]); updated=False
    for u in users:
        if u['phone']==phone or u['email']==email: u['nin_number']=nin_number; u['nin_status']='verified_number'; u['verified']=True; u['nin_names']=u.get('business',''); updated=True
    save_db('users.json',users)
    if updated: return jsonify({'success':True,'message':'NIN saved Verified'})
    return jsonify({'success':False,'message':'User not found'}),404
@app.route('/api/user-nin-info')
def user_nin_info():
    email=request.args.get('email','').lower().strip(); phone=request.args.get('phone','').strip(); users=load_db('users.json',[]); u=next((x for x in users if x['email']==email or x['phone']==phone), None)
    if not u: return jsonify({'success':False,'message':'User not found'}),404
    return jsonify({'success': True,'nin_number': u.get('nin_number',''),'nin_names': u.get('nin_names','') or u.get('business',''),'nin_status': u.get('nin_status','not_uploaded'),'verified': u.get('verified',False),'email': u.get('email',''),'phone': u.get('phone',''),'business': u.get('business',''),'followers': u.get('followers',0),'total_likes': u.get('total_likes',0),'total_stars': u.get('total_stars',0)})
@app.route('/api/products')
def get_products():
    global PRODUCTS_CACHE
    now = time.time()
    q = request.args.get('q','').lower()
    main = request.args.get('main')
    sub = request.args.get('sub')
    business = request.args.get('business')
    shop_slug = request.args.get('shop') or request.args.get('shop_slug')
    if not q and not main and not sub and not business and not shop_slug and PRODUCTS_CACHE["data"] and (now - PRODUCTS_CACHE["time"] < CACHE_TTL):
        return jsonify(PRODUCTS_CACHE["data"])
    products=load_db('products.json', []); users=load_db('users.json',[]);
    filtered=products
    if main: filtered=[p for p in filtered if p.get('main_category')==main]
    if sub: filtered=[p for p in filtered if p.get('sub_category')==sub]
    if q: filtered=[p for p in filtered if q in p.get('name','').lower() or q in p.get('description','').lower() or q in p.get('business','').lower()]
    if business: filtered=[p for p in filtered if p.get('business')==business]
    if shop_slug: filtered=[p for p in filtered if p.get('shop_slug')==shop_slug]
    filtered=sorted(filtered,key=lambda x:(x.get('boosted',0),x.get('created',0)),reverse=True)
    seller_stats={}
    for p in products:
        biz=p.get('business')
        if not biz: continue
        if biz not in seller_stats: seller_stats[biz]={'likes':0,'stars':0}
        seller_stats[biz]['likes']+=len(p.get('reviews',[]))
        seller_stats[biz]['stars']+=sum([r.get('rating',0) for r in p.get('reviews',[])])
    public=[]
    for p in filtered:
        pp=p.copy(); pp.pop('phone',None)
        seller=next((u for u in users if u.get('business')==p.get('business')),None)
        stats=seller_stats.get(p.get('business'),{'likes':0,'stars':0})
        pp['seller_verified']=seller.get('verified',False) if seller else False
        pp['seller_followers']=seller.get('followers',0) if seller else 0
        pp['seller_total_likes']=stats['likes']
        pp['seller_total_stars']=stats['stars']
        pp['stars_count']=len(p.get('reviews',[]))
        pp['stars_avg']=p.get('rating',0)
        public.append(pp)
    if not q and not main and not sub and not business and not shop_slug:
        PRODUCTS_CACHE["data"] = public
        PRODUCTS_CACHE["time"] = now
    return jsonify(public)
@app.route('/api/sell', methods=['POST'])
def sell():
    name=request.form.get('name'); price=int(request.form.get('price',0)); business=request.form.get('business'); location=request.form.get('location'); phone=request.form.get('phone'); desc=request.form.get('desc',''); main_cat=request.form.get('main_category'); sub_cat=request.form.get('sub_category'); stock=int(request.form.get('stock',10)); plan=request.form.get('plan','free14'); user_email=request.form.get('user_email','').lower()
    users=load_db('users.json',[]); products=load_db('products.json',[]); seller=next((u for u in users if u['phone']==phone or u['email']==user_email),None); plan_info=PLANS.get(plan,PLANS['free14'])
    if not seller:
        return jsonify({'success':False,'message':'Register first as seller'}),402
    if seller.get('coins',0) < UPLOAD_COST:
        return jsonify({'success':False,'message':f'You need {UPLOAD_COST} coins to upload! Buy coins in My Wallet. You have {seller.get("coins",0)} coins.','needs_coins':True,'coins_needed':UPLOAD_COST,'my_coins':seller.get('coins',0)}),402
    if seller.get('subscription_expires',0) < time.time():
        return jsonify({'success':False,'message':f'Subscription expired! Renew: Pay to {OWNER_MOMO} and enter Transaction ID','needs_subscription':True,'plans':PLANS}),402
    if not seller.get('paid', False) and plan_info.get('requires_payment'):
        return jsonify({'success':False,'message':f'PAY BEFORE UPLOAD! Pay UGX {plan_info["price"]} to {OWNER_MOMO}','needs_subscription':True}),402
    images=[]
    for key in request.files:
        f=request.files[key]
        if f and f.filename and 'nin' not in key.lower() and 'review' not in key.lower():
            file_bytes=f.read(); mime=f.mimetype or 'image/jpeg'; b64=base64.b64encode(file_bytes).decode('utf-8'); data_uri=f"data:{mime};base64,{b64}"; images.append(data_uri)
    img_url=request.form.get('image_url')
    if img_url and not images: images=[img_url]
    if not images: images=['https://via.placeholder.com/300']
    try:
        shop = ensure_shop_for_user(seller)
        shop_id = shop.get('id')
        shop_slug = shop.get('shop_slug')
    except Exception as e:
        print("shop ensure failed", e)
        shop_id = None
        shop_slug = None
    exp_time = seller['subscription_expires'] if seller and seller['subscription_expires']>time.time() else time.time()+plan_info['days']*86400
    prod={'id':int(time.time()*1000),'name':name,'price':price,'business':business,'location':location,'phone':phone,'seller_email':user_email,'description':desc,'image':images[0],'images':images,'main_category':main_cat,'sub_category':sub_cat,'stock':stock,'sold':0,'rating':5.0,'reviews':[],'views':0,'verified':False,'boosted':0,'bargain_allowed':True,'created':time.time(),'plan':plan,'plan_name':plan_info['name'],'plan_price':plan_info['price'],'subscription_expires':exp_time,'shop_id': shop_id,'shop_slug': shop_slug}
        if DATABASE_URL:
        try:
            ensure_tables(); import json as js; conn=get_conn(); cur=conn.cursor()
            try:
                from psycopg.types.json import Jsonb; cur.execute("INSERT INTO products (data) VALUES (%s)", [Jsonb(prod)])
            except: cur.execute("INSERT INTO products (data) VALUES (%s)", [js.dumps(prod)])
            conn.commit(); cur.close(); conn.close()
        except Exception as e: return jsonify({'success':False,'message':f'Upload failed: {str(e)}'}),500
    else: products.append(prod); save_db('products.json', products)
    try:
        shops = load_db('shops.json', [])
        for s in shops:
            if s.get('shop_slug')==shop_slug:
                s['total_products']=s.get('total_products',0)+1
        save_db('shops.json', shops)
    except: pass
    for u in users:
        if u['phone']==phone or u['email']==user_email:
            u['coins'] = max(0, u.get('coins',0) - UPLOAD_COST)
    save_db('users.json', users)
    return jsonify({'success':True,'message':f'Added with {plan_info["name"]} - {UPLOAD_COST} coins used! {seller.get("coins",0)-UPLOAD_COST} left'})
@app.route('/api/shops')
def list_shops():
    shops = load_db('shops.json', [])
    try:
        products = load_db('products.json', [])
        counts={}
        for p in products:
            slug=p.get('shop_slug')
            if slug: counts[slug]=counts.get(slug,0)+1
        for s in shops:
            s['total_products']=counts.get(s.get('shop_slug'), s.get('total_products',0))
    except: pass
    shops_sorted = sorted(shops, key=lambda x: x.get('total_products',0), reverse=True)
    return jsonify(shops_sorted)
@app.route('/api/shop/<slug>')
def get_shop_by_slug(slug):
    shops = load_db('shops.json', [])
    shop = next((s for s in shops if s.get('shop_slug')==slug), None)
    if not shop:
        return jsonify({'success':False,'message':'Shop not found'}),404
    products = load_db('products.json', [])
    shop_products = [p for p in products if p.get('shop_slug')==slug]
    public_products=[]
    for p in shop_products:
        pp=p.copy(); pp.pop('phone',None)
        public_products.append(pp)
    public_products = sorted(public_products, key=lambda x: x.get('created',0), reverse=True)
    return jsonify({'success':True,'shop':shop,'products':public_products})
@app.route('/api/follow', methods=['POST'])
def follow_seller():
    data=request.json; business=data.get('business'); follower_phone=data.get('follower_phone'); follower_email=data.get('follower_email','').lower()
    if not business: return jsonify({'success':False,'message':'Business required'}),400
    followers=load_db('followers.json',[]); users=load_db('users.json',[])
    if any(f['business']==business and (f.get('follower_phone')==follower_phone or f.get('follower_email')==follower_email) for f in followers): return jsonify({'success':False,'message':'Already following'}),400
    followers.append({'id':int(time.time()*1000),'business':business,'follower_phone':follower_phone,'follower_email':follower_email,'time':time.time()}); save_db('followers.json',followers)
    for u in users:
        if u.get('business')==business: u['followers']=u.get('followers',0)+1
    save_db('users.json',users); return jsonify({'success':True,'message':f'Following {business}'})
@app.route('/api/unfollow', methods=['POST'])
def unfollow_seller():
    data=request.json; business=data.get('business'); phone=data.get('follower_phone'); email=data.get('follower_email','').lower(); followers=load_db('followers.json',[]); users=load_db('users.json',[]); before=len(followers); followers=[f for f in followers if not (f['business']==business and (f.get('follower_phone')==phone or f.get('follower_email')==email))]
    if len(followers)<before:
        for u in users:
            if u.get('business')==business: u['followers']=max(0,u.get('followers',1)-1)
        save_db('users.json',users)
    save_db('followers.json',followers); return jsonify({'success':True})
@app.route('/api/followers/<business>')
def get_followers(business): followers=load_db('followers.json',[]); filtered=[f for f in followers if f['business']==business]; return jsonify({'business':business,'count':len(filtered),'followers':filtered})
@app.route('/api/verify-nin', methods=['POST'])
def upload_nin():
    phone=request.form.get('phone'); email=request.form.get('email','').lower(); nin_number=request.form.get('nin_number'); users=load_db('users.json',[]); front=request.files.get('nin_front'); back=request.files.get('nin_back'); front_url=''; back_url=''
    if front and front.filename: fn='nin_front_'+str(uuid.uuid4())[:8]+'_'+secure_filename(front.filename); front.save(os.path.join(app.config['UPLOAD_FOLDER'], fn)); front_url='/static/uploads/'+fn
    if back and back.filename: fn='nin_back_'+str(uuid.uuid4())[:8]+'_'+secure_filename(back.filename); back.save(os.path.join(app.config['UPLOAD_FOLDER'], fn)); back_url='/static/uploads/'+fn
    for u in users:
        if u['phone']==phone or u['email']==email: u['nin_number']=nin_number; u['nin_front']=front_url; u['nin_back']=back_url; u['nin_status']='pending'; u['verified']=False
    save_db('users.json',users); return jsonify({'success':True,'message':'NIN uploaded!'})
@app.route('/api/update-order-status', methods=['POST'])
def update_order():
    data=request.json; order_id=data.get('order_id'); new_status=data.get('status'); boda_phone=data.get('boda_phone',''); boda_name=data.get('boda_name',''); orders=load_db('orders.json',[])
    for o in orders:
        if o['id']==order_id:
            if 'tracking' not in o: o['tracking']=[]
            o['tracking'].append({'status':new_status,'time':time.time(),'boda_name':boda_name,'boda_phone':boda_phone}); o['status']=new_status
    save_db('orders.json',orders); return jsonify({'success':True,'message':f'Order {new_status}'})
@app.route('/api/seller/sales')
def seller_sales():
    phone=request.args.get('phone'); email=request.args.get('email','').lower(); period=request.args.get('period','all')
    if not phone and not email: return jsonify({'success':False,'message':'Phone/email required'}),400
    orders=load_db('orders.json',[]); products=load_db('products.json',[]); my_prods=[p for p in products if p.get('phone')==phone or p.get('seller_email')==email]; my_ids=set(p['id'] for p in my_prods); my_orders=[]; now=time.time()
    for o in orders:
        if period=='today' and now-o.get('time',0)>86400: continue
        if period=='week' and now-o.get('time',0)>7*86400: continue
        if o.get('type')=='bargain': continue
        cart=o.get('cart',[]); mine=[i for i in cart if i.get('id') in my_ids]
        if mine: oc=o.copy(); oc['my_items']=mine; oc['my_total']=sum(i.get('price',0) for i in mine); my_orders.append(oc)
    total=sum(o['my_total'] for o in my_orders); return jsonify({'success':True,'period':period,'total_sales':total,'total_orders':len(my_orders),'products_count':len(my_prods),'orders':my_orders[::-1],'products':my_prods})
@app.route('/api/my-products')
def my_products():
    phone=request.args.get('phone'); email=request.args.get('email','').lower(); products=load_db('products.json', [])
    if phone: products=[p for p in products if p.get('phone')==phone]
    if email: products=[p for p in products if p.get('seller_email')==email or p.get('phone')==phone]
    return jsonify(products)
@app.route('/api/delete-product/<int:pid>', methods=['DELETE'])
def delete_prod(pid):
    if DATABASE_URL:
        try:
            ensure_tables(); conn=get_conn(); cur=conn.cursor(); cur.execute("SELECT id, data FROM products"); rows=cur.fetchall()
            for row in rows:
                if isinstance(row, dict): r_id, r_data = row['id'], row['data']
                else: r_id, r_data = row[0], row[1]
                if isinstance(r_data, str): r_data=json.loads(r_data)
                if r_data.get('id')==pid: cur.execute("DELETE FROM products WHERE id=%s", (r_id,)); break
            conn.commit(); cur.close(); conn.close()
        except Exception as e: print(e)
    else: products=load_db('products.json', []); products=[p for p in products if p['id']!=pid]; save_db('products.json', products)
    global PRODUCTS_CACHE
    PRODUCTS_CACHE["data"] = None
    return jsonify({'success':True})
@app.route('/api/rate', methods=['POST'])
def rate():
    if request.content_type and 'multipart/form-data' in request.content_type:
        pid=int(request.form.get('id')); rating=int(request.form.get('rating',5)); comment=request.form.get('comment',''); photo=request.files.get('review_photo'); photo_url=''
        if photo and photo.filename: fn='review_'+str(uuid.uuid4())[:8]+'_'+secure_filename(photo.filename); photo.save(os.path.join(app.config['UPLOAD_FOLDER'], fn)); photo_url='/static/uploads/'+fn
        products=load_db('products.json', []); business_name=""
        for p in products:
            if p['id']==pid: p['reviews'].append({'rating':rating,'comment':comment,'photo':photo_url,'time':time.time(),'verified_purchase':True}); p['rating']=sum(r['rating'] for r in p['reviews'])/len(p['reviews']); business_name=p.get('business','')
        save_db('products.json', products)
        if business_name:
            users=load_db('users.json',[])
            for u in users:
                if u.get('business')==business_name: u['total_likes']=u.get('total_likes',0)+1; u['total_stars']=u.get('total_stars',0)+rating
            save_db('users.json',users)
        return jsonify({'success':True,'message':'Review added!'})
    else:
        data=request.json; pid=data['id']; products=load_db('products.json', []); business_name=""
        for p in products:
            if p['id']==pid: p['reviews'].append({'rating':data['rating'],'comment':data.get('comment',''),'time':time.time(),'verified_purchase':True}); p['rating']=sum(r['rating'] for r in p['reviews'])/len(p['reviews']); business_name=p.get('business','')
        save_db('products.json', products)
        if business_name:
            users=load_db('users.json',[])
            for u in users:
                if u.get('business')==business_name: u['total_likes']=u.get('total_likes',0)+1; u['total_stars']=u.get('total_stars',0)+data.get('rating',0)
            save_db('users.json',users)
        return jsonify({'success':True})
@app.route('/api/bargain', methods=['POST'])
def bargain(): data=request.json; bargains=load_db('bargains.json', []); data['id']=int(time.time()); data['status']='pending'; data['time']=time.time(); bargains.append(data); save_db('bargains.json', bargains); orders=load_db('orders.json', []); orders.append({'id':data['id'],'type':'bargain','bargain':data,'total':data.get('offer'),'buyer':{'names':data.get('buyer_name','Bargain'),'phone1':data.get('buyer_phone','')},'cart':[{'name':data.get('product_name')}],'time':time.time(),'seller_phone':data.get('seller_phone')}); save_db('orders.json', orders); return jsonify({'success':True,'message':"Bargain sent!"})
@app.route('/api/boost', methods=['POST'])
def boost():
    data = request.json
    pid = data['id']
    products = load_db('products.json', [])
    for p in products:
        if p['id'] == pid:
            p['boosted'] = time.time() + 86400 * int(data.get('days', 1))
    save_db('products.json', products)
    return jsonify({'success': True, 'message': 'Boosted!'})
@app.route('/api/subscribe', methods=['POST'])
def sub():
    data=request.json
    sellers=load_db('sellers.json', [])
    users=load_db('users.json', [])
    transactions=load_db('transactions.json', [])
    plan=data.get('plan','30')
    email=data.get('email','').lower().strip()
    phone=data.get('phone','').strip()
    business_phone=data.get('business_phone','').strip() or phone
    momo_code=data.get('momo_code','').strip().upper()
    momo_phone=data.get('momo_phone','').strip() or phone
    plan_info=PLANS.get(plan,PLANS['30'])
    if plan == 'free14':
        found=False
        for u in users:
            if u['email']==email or u['phone']==phone or u['phone']==business_phone:
                u['plan']=plan; u['plan_name']=plan_info['name']; u['paid']=True
                u['momo_code']=momo_code; u['momo_transaction']=momo_code
                u['business_phone']=business_phone; u['momo_phone']=business_phone; u['payer_phone']=business_phone
                u['paid_amount']=0; u['subscription_expires']=time.time()+plan_info['days']*86400
                u['subscription_active']=True; u['payment_status']='verified_free'; u['owner_verified']=True; u['free_used']=True
                found=True
        if not found:
            new_user={'id':int(time.time()*1000),'email':email,'phone':business_phone or phone,'password':hash_pwd('free14user'),'business': data.get('business', business_phone) or 'SANNLAS Seller','role':'seller','created':time.time(),'plan':plan,'plan_name':plan_info['name'],'paid':True,'paid_amount':0,'subscription_expires':time.time()+plan_info['days']*86400,'subscription_active':True,'payment_status':'verified_free','owner_verified':True,'verified':False,'free_used':True,'followers':0,'total_likes':0,'total_stars':0,'momo_code':momo_code,'coins':0}
            users.append(new_user)
        save_db('users.json',users)
        sellers.append({'id':int(time.time()),'email':email,'phone':phone,'business_phone':business_phone,'momo_phone':business_phone,'plan':plan,'plan_name':plan_info['name'],'plan_price':0,'paid_amount':0,'transaction_id':momo_code,'time':time.time(),'status':'verified_free'})
        save_db('sellers.json',sellers)
        return jsonify({'success':True,'message':f'FREE 14 Days Activated! Upload now!','expires': time.time()+plan_info['days']*86400})
    if business_phone.replace(" ","")!= momo_phone.replace(" ",""):
        return jsonify({'success':False,'message':f'BLOCKED: Business {business_phone} must SAME as MoMo payer {momo_phone} that sent to 0795712326!'}),400
    if plan_info.get('requires_payment'):
        if not momo_code:
            return jsonify({'success':False,'message':'Enter Transaction ID from MoMo SMS after sending to 0795712326'}),400
        if any(t.get('transaction_id','').upper()==momo_code for t in transactions):
            return jsonify({'success':False,'message':f'BLOCKED FAKE! Trans ID {momo_code} already used! One-time only.'}),400
        transactions.append({'transaction_id': momo_code,'phone': phone,'business_phone': business_phone,'momo_phone': momo_phone,'payer_phone': momo_phone,'plan': plan,'plan_name': plan_info['name'],'amount': plan_info['price'],'paid_amount': plan_info['price'],'time': time.time(),'timestamp': time.time(),'to_number': OWNER_MOMO,'to_momo': OWNER_MOMO,'status': 'pending_owner_verify','email': email,'business': data.get('business','')})
        save_db('transactions.json', transactions)
    found=False
    for u in users:
        if u['email']==email or u['phone']==phone or u['phone']==business_phone:
            u['plan']=plan; u['plan_name']=plan_info['name']; u['paid']=True; u['momo_code']=momo_code; u['momo_transaction']=momo_code; u['business_phone']=business_phone; u['momo_phone']=momo_phone; u['payer_phone']=momo_phone; u['paid_amount']=plan_info['price']; u['subscription_expires']=time.time()+plan_info['days']*86400; u['subscription_active']=True; u['payment_status']='pending_owner_verify'; u['owner_verified']=False; found=True
    if not found:
        return jsonify({'success':False,'message':'Seller not found - Register first'}),404
    save_db('users.json',users)
    data['id']=int(time.time()); data['plan_name']=plan_info['name']; data['plan_price']=plan_info['price']; data['paid_amount']=plan_info['price']; data['transaction_id']=momo_code; data['payer_phone']=momo_phone; data['business_phone']=business_phone; data['time']=time.time(); data['status']='pending_owner_verify'
    sellers.append(data); save_db('sellers.json',sellers)
    return jsonify({'success':True,'message':f'Payment OK! {plan_info["name"]} active {plan_info["days"]} days.','expires': time.time()+plan_info['days']*86400})
@app.route('/api/check-subscription')
def check_sub():
    phone=request.args.get('phone','').strip()
    email=request.args.get('email','').lower().strip()
    users=load_db('users.json',[])
    u=next((x for x in users if x['email']==email or x['phone']==phone), None)
    if not u:
        return jsonify({'success':False,'can_upload':False,'message':'Not registered'})
    active = u.get('subscription_expires',0) > time.time() and u.get('paid',False)
    return jsonify({'success':True,'can_upload': active,'subscription_active': active,'expires': u.get('subscription_expires',0),'plan_name': u.get('plan_name',''),'needs_subscription': not active,'plans': PLANS,'pay_to': OWNER_MOMO,'coins': u.get('coins',0),'coins_needed': UPLOAD_COST})
@app.route('/api/admin/activate-subscription', methods=['POST'])
def activate_sub():
    data=request.json; phone=data.get('phone'); email=data.get('email','').lower(); plan=data.get('plan'); users=load_db('users.json',[]); products=load_db('products.json',[]); plan_info=PLANS.get(plan,PLANS['30'])
    for u in users:
        if u['phone']==phone or u['email']==email: u['plan']=plan; u['plan_name']=plan_info['name']; u['paid']=True; u['subscription_expires']=time.time()+plan_info['days']*86400; u['payment_status']='verified_by_owner'; u['owner_verified']=True
    save_db('users.json',users)
    for p in products:
        if p.get('phone')==phone or p.get('seller_email')==email: p['subscription_expires']=time.time()+plan_info['days']*86400; p['plan']=plan
    save_db('products.json',products); return jsonify({'success':True,'message':f'Activated {plan_info["name"]} for {phone}'})
@app.route('/api/checkout', methods=['POST'])
def checkout():
    data=request.json; orders=load_db('orders.json', []); data['id']=int(time.time()); data['status']='Packed'; data['tracking']=[{'status':'Packed','time':time.time()}]; data['time']=time.time(); orders.append(data); save_db('orders.json', orders); products=load_db('products.json', [])
    for item in data['cart']:
        for p in products:
            if p['id']==item['id']: p['stock']=max(0,p.get('stock',10)-1); p['sold']=p.get('sold',0)+1
    save_db('products.json', products); return jsonify({'message':'Order placed! ID: '+str(data['id'])})
@app.route('/api/jobs', methods=['GET','POST'])
def jobs_api():
    if request.method=='POST': data=request.json; data['id']=int(time.time()*1000); data['time']=time.time(); all_jobs=load_db('jobs.json', []); all_jobs.append(data); save_db('jobs.json', all_jobs); return jsonify({'success':True,'message':'Job posted!'})
    else: all_jobs=load_db('jobs.json', []); return jsonify(all_jobs[::-1])
@app.route('/api/jobs/<int:jid>/apply', methods=['POST'])
def apply_job(jid): data=request.json; apps=load_db('applications.json', []); data['job_id']=jid; data['id']=int(time.time()); data['time']=time.time(); apps.append(data); save_db('applications.json', apps); return jsonify({'success':True,'message':'Application sent!'})
@app.route('/api/job-applications')
def get_applications(): return jsonify(load_db('applications.json', [])[::-1])
@app.route('/api/orders')
def get_orders(): orders=load_db('orders.json', [])[::-1]; return jsonify(orders)
@app.route('/api/contact', methods=['POST'])
def contact_owner(): data=request.json; contacts=load_db('contacts.json', []); contacts.append({**data,'time':time.time(),'id':int(time.time())}); save_db('contacts.json', contacts); return jsonify({'success':True,'message':'Message sent!'})
@app.route('/api/admin/send-message', methods=['POST'])
def admin_send_message():
    data=request.json; to_email=data.get('to_email','').lower().strip(); to_phone=data.get('to_phone','').strip(); title=data.get('title','Message from SANNLAS Admin'); message=data.get('message','')
    if not to_email and not to_phone: return jsonify({'success':False,'message':'Email or Phone required'}),400
    notifs=load_db('notifications.json', []); notifs.append({'id': int(time.time()*1000),'to_email': to_email,'to_phone': to_phone,'title': title,'message': message,'time': time.time(),'read': False}); save_db('notifications.json', notifs)
    return jsonify({'success':True,'message':f'Message sent to {to_email or to_phone}'})
@app.route('/api/notifications')
def get_notifications(): email=request.args.get('email','').lower().strip(); phone=request.args.get('phone','').strip(); notifs=load_db('notifications.json', []); mine=[n for n in notifs if (email and n.get('to_email')==email) or (phone and n.get('to_phone')==phone)]; return jsonify(mine[::-1])
@app.route('/api/admin/data')
def admin_data():
    def safe_load(file, default):
        try:
            d = load_db(file, default)
            return d if d is not None else default
        except Exception as e:
            print(f"safe_load {file} error: {e}")
            return default
    try:
        products=safe_load('products.json',[]) or []
        users=safe_load('users.json',[]) or []
        sellers=safe_load('sellers.json',[]) or []
        orders=safe_load('orders.json',[]) or []
        jobs=safe_load('jobs.json',[]) or []
        contacts=safe_load('contacts.json',[]) or []
        applications=safe_load('applications.json',[]) or []
        bargains=safe_load('bargains.json',[]) or []
        followers=safe_load('followers.json',[]) or []
        notifications=safe_load('notifications.json',[]) or []
        transactions=safe_load('transactions.json',[]) or []
        coin_transactions=safe_load('coin_transactions.json',[]) or []
        shops=safe_load('shops.json',[]) or []
        coin_config=get_coin_config()
        now=time.time()
        for p in products:
            try:
                if isinstance(p, dict) and p.get('subscription_expires',0)<now: p['expired']=True
            except: pass
        total_rev=0
        try:
            for o in orders:
                if isinstance(o, dict):
                    t=o.get('total',0)
                    if isinstance(t,(int,float)): total_rev+=t
        except: total_rev=0
        coin_rev = sum(t.get('price',0) for t in coin_transactions if isinstance(t,dict) and t.get('status')!='blocked_fake')
        return jsonify({'products':products,'users':users,'sellers':sellers,'orders':orders,'jobs':jobs,'contacts':contacts,'applications':applications,'bargains':bargains,'followers':followers,'notifications':notifications,'transactions':transactions,'coin_transactions':coin_transactions,'shops':shops,'coin_config':coin_config,'total_revenue':total_rev,'coin_revenue':coin_rev,'total_sellers':len(users),'total_orders':len(orders),'plans':PLANS})
    except Exception as e:
        print("ADMIN DATA CRITICAL ERROR:", e)
        import traceback; traceback.print_exc()
        return jsonify({'products':[],'users':[],'sellers':[],'orders':[],'jobs':[],'contacts':[],'applications':[],'bargains':[],'followers':[],'notifications':[],'transactions':[],'coin_transactions':[],'shops':[],'coin_config':{"total":TOTAL_COINS,"remaining":TOTAL_COINS,"sold":0,"price":COIN_PRICE,"upload_cost":UPLOAD_COST},"total_revenue":0,'coin_revenue':0,'total_sellers':0,'total_orders':0,'plans':PLANS,'error': str(e)}), 200

@app.route('/api/admin/<string:filetype>')
def admin_generic(filetype):
    try:
        allowed=['contacts','applications','orders','bargains','sellers','jobs','products','users','followers','notifications','transactions','coin_transactions','coin_config','shops']
        if filetype not in allowed: return jsonify([])
        if filetype=='coin_config':
            return jsonify(get_coin_config())
        data = load_db(f'{filetype}.json', [])
        if data is None: return jsonify([])
        return jsonify(data)
    except Exception as e:
        print(f"admin {filetype} error:", e)
        return jsonify([])
@app.route('/api/admin/transactions')
def admin_transactions():
    try:
        transactions=load_db('transactions.json', []) or []
        return jsonify(transactions[::-1])
    except:
        return jsonify([])
@app.route('/api/admin/verify-transaction', methods=['POST'])
def verify_transaction():
    try:
        data=request.json
        trans_id=data.get('transaction_id','').strip().upper()
        action=data.get('action','verify')
        transactions=load_db('transactions.json', []) or []
        users=load_db('users.json', []) or []
        for t in transactions:
            if isinstance(t, dict) and t.get('transaction_id','').upper()==trans_id:
                if action=='verify':
                    t['status']='verified_by_owner'; t['owner_verified']=True; t['verified_time']=time.time()
                    for u in users:
                        if isinstance(u, dict) and (u.get('momo_code','').upper()==trans_id or u.get('momo_transaction','').upper()==trans_id):
                            u['payment_status']='verified_by_owner'; u['owner_verified']=True
                elif action=='block_fake':
                    t['status']='blocked_fake'; t['owner_verified']=False
                    for u in users:
                        if isinstance(u, dict) and (u.get('momo_code','').upper()==trans_id or u.get('momo_transaction','').upper()==trans_id):
                            u['paid']=False; u['subscription_expires']=0; u['payment_status']='blocked_fake'
        save_db('transactions.json', transactions)
        save_db('users.json', users)
        return jsonify({'success':True,'message':f'Transaction {trans_id} {action} done'})
    except Exception as e:
        return jsonify({'success':False,'message': str(e)}),500
@app.route('/api/admin/block-fake', methods=['POST'])
def block_fake():
    return verify_transaction()
@app.route('/icon.png')
def icon_file():
    return send_from_directory('.', 'icon-512.png')
@app.route('/googleac311007501ff6b1a.html')
def google_verify_b1a():
    return send_from_directory('.', 'googleac311007501ff6b1a.html')

def keep_alive_worker():
    import urllib.request
    while True:
        time.sleep(300)
        try:
            url = os.environ.get('RENDER_EXTERNAL_URL', 'https://sannlas.onrender.com')
            urllib.request.urlopen(f"{url}/api/coins/config", timeout=8).read()
            print("Keep-alive ping OK")
        except Exception as e:
            print("Keep-alive failed:", e)

threading.Thread(target=keep_alive_worker, daemon=True).start()

if __name__=='__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
