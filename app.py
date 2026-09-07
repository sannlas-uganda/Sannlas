from flask import Flask, request, jsonify, render_template, Response, send_from_directory, session, redirect
import os, json, uuid, time, hashlib, base64, random, smtplib, threading, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sannlas-secret-2026-boss-key')
app.config['UPLOAD_FOLDER']='static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)
os.makedirs('static/billboards', exist_ok=True)

Talisman(app, content_security_policy=None, force_https=False)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per 15 minutes"], storage_uri="memory://",)
CORS(app, origins=["https://sannlas.onrender.com"])
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

PRODUCTS_CACHE = {"data": None, "time": 0}
CACHE_TTL = 10
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'SannlasBoss123')

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('is_admin'):
            return f(*args, **kwargs)
        if request.path.startswith('/api/admin'):
            return jsonify({'success': False, 'message': 'Admin login required'}), 401
        return redirect('/admin/login')
    return decorated
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

def get_billboard_config():
    cfg = load_db('billboard.json', None)
    if not cfg:
        cfg = {"active": False, "type": "image", "media_url": "", "text": "Welcome to Sannlas - Shop Smart, Sell Faster", "link": "", "created": time.time()}
        save_db('billboard.json', cfg)
    return cfg
def make_shop_slug(business):
    if not business:
        return 'shop'
    import re
    base = re.sub(r'[^a-z0-9]+', '-', business.lower()).strip('-')
    if not base:
        base = 'shop'
    return base[:50]

def get_biz_key(name):
    if not name:
        return ''
    import re
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
    shop = {
        "id": int(time.time()*1000),
        "user_id": user.get('id'),
        "business_name": biz,
        "name": biz,
        "shop_slug": slug,
        "slug": slug,
        "phone": user.get('phone',''),
        "owner_email": email,
        "location": "Kampala",
        "description": "Welcome to " + biz + " shop!",
        "logo_url": "",
        "banner_url": "",
        "verified": False,
        "total_products": 0,
        "product_count": 0,
        "created_at": time.time()
    }
    shops.append(shop)
    save_db('shops.json', shops)
    return shop

BUSINESS_CATEGORIES = {"Agriculture & Farming":["Fish Farming","Poultry Farming","Crop Farming","Livestock","Animal Feeds"],"Food & Beverages":["Restaurants","Bakeries","Fast Foods","Drinks","Catering"],"Construction & Building":["Cement","Hardware","Plumbing","Electrical","Tiles"],"Fashion & Clothing":["Men's Clothing","Women's Clothing","Kids","Shoes","Bags"],"Electronics & Technology":["Mobile Phones","Laptops","Accessories","TVs","Solar"]}

@app.route('/')
def home(): return render_template('index.html')
@app.route('/wallet')
def wallet_page(): return render_template('wallet.html')
@app.route('/balance')
def balance_page(): return render_template('balance.html')
@app.route('/shop/<slug>')
def shop_page_slug(slug): return render_template('shop.html')
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'GET':
        if session.get('is_admin'):
            return redirect('/admin')
        return render_template('admin_login.html')
    data = request.get_json() if request.is_json else request.form
    pwd = data.get('password','') if data else ''
    if pwd == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({'success': True}) if request.is_json else redirect('/admin')
    return jsonify({'success': False, 'message': 'Wrong admin password'}), 401 if request.is_json else render_template('admin_login.html', error='Wrong password')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect('/admin/login')

@app.route('/admin')
def admin_page():
    if not session.get('is_admin'):
        return redirect('/admin/login')
    return render_template('admin.html')

@app.route('/api/billboard')
def get_billboard():
    cfg = get_billboard_config()
    return jsonify(cfg)

@app.route('/api/admin/billboard', methods=['GET'])
@admin_required
def admin_get_billboard():
    return jsonify(get_billboard_config())

@app.route('/api/admin/billboard', methods=['POST'])
@admin_required
def admin_save_billboard():
    data = request.json or {}
    cfg = get_billboard_config()
    cfg['active'] = bool(data.get('active', cfg.get('active', False)))
    cfg['text'] = data.get('text', cfg.get('text',''))[:200]
    cfg['link'] = data.get('link', cfg.get('link',''))[:300]
    cfg['media_url'] = data.get('media_url', cfg.get('media_url',''))
    cfg['type'] = data.get('type', cfg.get('type','image'))
    cfg['updated'] = time.time()
    save_db('billboard.json', cfg)
    return jsonify({'success': True, 'config': cfg})

# ===== BOSS FIXED: AUTO LANDSCAPE 1200x400 CONVERTER =====
@app.route('/api/upload/billboard', methods=['POST'])
def upload_billboard():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Empty"}), 400
        
        # Make folders
        os.makedirs('static/billboards', exist_ok=True)
        
        filename = str(int(time.time())) + '_' + file.filename
        filepath = os.path.join('static/billboards', filename)
        file.save(filepath)
        
        # Try to convert to 1200x400 landscape - if Pillow missing, just skip
        try:
            from PIL import Image
            img = Image.open(filepath)
            # Auto landscape 1200x400 with cover
            img = img.convert('RGB')
            target_w, target_h = 1200, 400
            # Cover crop logic
            img_ratio = img.width / img.height
            target_ratio = target_w / target_h
            if img_ratio > target_ratio:
                # too wide, crop width
                new_h = target_h
                new_w = int(img.width * (target_h / img.height))
                img = img.resize((new_w, new_h))
                left = (new_w - target_w) // 2
                img = img.crop((left, 0, left+target_w, target_h))
            else:
                new_w = target_w
                new_h = int(img.height * (target_w / img.width))
                img = img.resize((new_w, new_h))
                top = (new_h - target_h) // 2
                img = img.crop((0, top, target_w, top+target_h))
            img.save(filepath, quality=85)
        except Exception as e:
            print("Pillow convert failed:", e)
            # keep original if convert fails
        
        ext = filename.lower().split('.')[-1]
        ftype = 'video' if ext in ['mp4','mov','webm'] else 'image'
        url = f"/static/billboards/{filename}"
        return jsonify({"url": url, "type": ftype})
    except Exception as e:
        print("BILLBOARD UPLOAD ERROR:", e)
        return jsonify({"error": str(e)}), 500
    PLANS = {"free14":{"days":14,"price":0,"name":"14 Days FREE"},"30":{"days":30,"price":6540,"name":"30 Days"},"60":{"days":60,"price":13090,"name":"2 Months"},"180":{"days":180,"price":39500,"name":"6 Months"},"365":{"days":365,"price":80000,"name":"1 Year"}}
COIN_PACKS = {"10":{"coins":10,"price":5990,"name":"Starter"},"30":{"coins":30,"price":17970,"name":"Popular"},"60":{"coins":60,"price":35940,"name":"Business"},"150":{"coins":150,"price":89850,"name":"Boss Pro"}}

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
@admin_required
def coins_verify():
    data=request.json; trans_id=data.get('momo_code','').strip().upper(); action=data.get('action','verify')
    txs=load_db('coin_transactions.json',[]); users=load_db('users.json',[]); cfg=get_coin_config()
    target_tx = None
    for t in txs:
        if t.get('momo_code','').upper()==trans_id:
            target_tx = t; break
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
    else:
        if target_tx.get('status')!= 'verified_by_owner':
            target_tx['status']='verified_by_owner'
            for u in users:
                if u.get('email','').lower()==target_tx.get('email','').lower() or u.get('phone','')==target_tx.get('phone',''):
                    u['coins'] = u.get('coins',0) + target_tx.get('coins',0)
    save_db('coin_transactions.json', txs); save_db('users.json', users); save_coin_config(cfg)
    return jsonify({'success':True, 'action': action})

@app.route('/api/admin/coins/add', methods=['POST'])
@admin_required
def admin_add_coins():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    coins = int(data.get('coins',0))
    if coins <=0: return jsonify({'success': False, 'message': 'Coins must be >0'}),400
    users = load_db('users.json', [])
    found = None
    for u in users:
        if (email and u.get('email','').lower()==email) or (phone and u.get('phone','')==phone):
            u['coins'] = u.get('coins',0) + coins
            found = u; break
    if not found: return jsonify({'success': False, 'message': 'User not found'}),404
    save_db('users.json', users)
    return jsonify({'success': True, 'message': f'Added {coins} coins'})

@app.route('/api/withdraw', methods=['POST'])
def request_withdraw():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    amount = int(data.get('amount',0))
    momo_number = data.get('momo_number','').strip()
    momo_name = data.get('momo_name','').strip()
    if amount < 5000: return jsonify({'success': False, 'message': 'Minimum withdraw 5000 UGX'}),400
    withdraws = load_db('withdraws.json', [])
    new_w = {'id': int(time.time()*1000), 'email': email, 'phone': phone, 'amount': amount, 'momo_number': momo_number, 'momo_name': momo_name, 'status': 'pending', 'time': time.time()}
    withdraws.append(new_w); save_db('withdraws.json', withdraws)
    return jsonify({'success': True, 'message': 'Withdraw request sent!'})

@app.route('/api/register', methods=['POST'])
def register():
    data=request.json; email=data.get('email','').lower().strip(); phone=data.get('phone','').strip(); pwd=data.get('password',''); biz=data.get('business','')
    if not email or not phone or not pwd: return jsonify({'success':False,'message':'Fill all'}),400
    users=load_db('users.json',[])
    if any(u['email']==email for u in users): return jsonify({'success':False,'message':'Email exists - Login'}),400
    user={'id':int(time.time()*1000),'email':email,'phone':phone,'password':hash_pwd(pwd),'business':biz,'created':time.time(),'coins':0}
    users.append(user); save_db('users.json',users)
    try: shop = ensure_shop_for_user(user)
    except: shop = None
    safe={k:v for k,v in user.items() if k!='password'}
    return jsonify({'success':True,'user':safe})

@app.route('/api/login', methods=['POST'])
def login():
    data=request.json; email=data.get('email','').lower(); pwd=data.get('password','')
    users=load_db('users.json',[]); u=next((x for x in users if x['email']==email and x['password']==hash_pwd(pwd)),None)
    if not u: return jsonify({'success':False,'message':'Wrong email/password'}),401
    safe={k:v for k,v in u.items() if k!='password'}
    return jsonify({'success':True,'user':safe})

@app.route('/api/products')
def get_products():
    q = request.args.get('q','').lower()
    shop_slug = request.args.get('shop')
    products=load_db('products.json', [])
    filtered=products
    if q: filtered=[p for p in filtered if q in p.get('name','').lower() or q in p.get('business','').lower()]
    if shop_slug:
        filtered=[p for p in filtered if p.get('shop_slug')==shop_slug]
    filtered=sorted(filtered,key=lambda x:x.get('created',0),reverse=True)
    return jsonify(filtered)

@app.route('/api/sell', methods=['POST'])
def sell():
    name=request.form.get('name'); price=int(request.form.get('price',0)); business=request.form.get('business'); location=request.form.get('location'); phone=request.form.get('phone'); desc=request.form.get('desc',''); main_cat=request.form.get('main_category'); stock=int(request.form.get('stock',10)); user_email=request.form.get('user_email','').lower()
    users=load_db('users.json',[]); seller=next((u for u in users if u['phone']==phone or u['email']==user_email),None)
    if not seller: return jsonify({'success':False,'message':'Register first'}),402
    images=[]
    for key in request.files:
        f=request.files[key]
        if f and f.filename:
            import base64; file_bytes=f.read(); mime=f.mimetype or 'image/jpeg'; b64=base64.b64encode(file_bytes).decode('utf-8'); images.append(f"data:{mime};base64,{b64}")
    if not images: images=['https://via.placeholder.com/300']
    prod = {'id': int(time.time()*1000),'name': name,'price': price,'business': business,'location': location,'phone': phone,'seller_email': user_email,'description': desc,'image': images[0],'images': images,'main_category': main_cat,'stock': stock,'created': time.time(),'shop_slug': make_shop_slug(business)}
    products=load_db('products.json',[]); products.append(prod); save_db('products.json', products)
    for u in users:
        if u['phone']==phone or u['email']==user_email: u['coins'] = max(0, u.get('coins',0) - 3)
    save_db('users.json', users)
    return jsonify({'success':True})

@app.route('/api/shops')
def list_shops():
    shops = load_db('shops.json', [])
    return jsonify(shops)

@app.route('/api/admin/data')
@admin_required
def admin_data():
    products=load_db('products.json',[]) or []
    users=load_db('users.json',[]) or []
    coin_transactions=load_db('coin_transactions.json',[]) or []
    billboard=get_billboard_config()
    coin_config=get_coin_config()
    return jsonify({'products':products,'users':users,'coin_transactions':coin_transactions,'billboard':billboard,'coin_config':coin_config})

if __name__=='__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
