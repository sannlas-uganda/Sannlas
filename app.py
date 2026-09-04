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

#... rest continues same as your file...

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
    exp_time = seller['subscription_expires'] if seller and seller['subscription_expires'] > time.time() else time.time() + plan_info['days'] * 86400
    prod = {
        'id': int(time.time() * 1000),
        'name': name,
        'price': price,
        'business': business,
        'location': location,
        'phone': phone,
        'seller_email': user_email,
        'description': desc,
        'image': images[0],
        'images': images,
        'main_category': main_cat,
        'sub_category': sub_cat,
        'stock': stock,
        'sold': 0,
        'rating': 5.0,
        'reviews': [],
        'views': 0,
        'verified': False,
        'boosted': 0,
        'bargain_allowed': True,
        'created': time.time(),
        'plan': plan,
        'plan_name': plan_info['name'],
        'plan_price': plan_info['price'],
        'subscription_expires': exp_time,
        'shop_id': shop_id,
        'shop_slug': shop_slug
    }
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

# --- KEEP ALL YOUR OTHER ROUTES SAME (follow, unfollow, orders etc) ---
# For brevity, paste your original routes from /api/follow to /api/notifications here - they are unchanged!

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

#... (keep your verify-nin, update-order-status, seller/sales, my-products, delete-product, rate, bargain, boost, subscribe, check-subscription, activate-subscription, checkout, jobs, contact, admin/send-message, notifications - all same)

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
