from flask import Flask, request, jsonify, render_template, Response, send_from_directory, session, redirect, make_response
import os, json, uuid, time, hashlib, base64, random, smtplib, threading, re
from datetime import datetime, timedelta
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

# === FORGOT PASSWORD SYSTEM CONFIG ===
OWNER_EMAIL = "natelieabigail@gmail.com"
EMAIL_FROM = "natelieabigail@gmail.com"
EMAIL_APP_PASSWORD = "ywhe hdfs otgw zztx" # <-- YOUR 16 LETTER PASSWORD HERE! REMOVE SPACES WHEN PASTING OK? KEEP AS IS CODE WILL REMOVE SPACES
OWNER_MOMO = "0795712326"
COIN_PRICE = 599
UPLOAD_COST = 3
TOTAL_COINS = 1000000000
WITHDRAW_MIN_COINS = 50
FREE_TRIAL = 10
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
        cfg = {"active": False, "type": "image", "media_url": "", "text": "Welcome to Sannlas - Shop Smart, Sell Faster", "link": "", "created": time.time(), "expires_at": None}
        save_db('billboard.json', cfg)
        return cfg
    exp = cfg.get('expires_at')
    if exp and cfg.get('active'):
        try:
            from datetime import datetime
            if isinstance(exp, str):
                exp_dt = datetime.fromisoformat(exp)
            else:
                exp_dt = datetime.fromtimestamp(float(exp))
            if datetime.now() > exp_dt:
                cfg['active'] = False
                save_db('billboard.json', cfg)
        except: pass
    return cfg

def make_shop_slug(business):
    if not business: return 'shop'
    base = re.sub(r'[^a-z0-9]+', '-', business.lower()).strip('-')
    if not base: base = 'shop'
    return base[:50]

def get_biz_key(name):
    if not name: return ''
    return re.sub(r'[^a-z0-9]+', '', name.lower())

def ensure_shop_for_user(user):
    shops = load_db('shops.json', [])
    biz = (user.get('business') or '').strip()
    if not biz: biz = 'Shop'
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
            if email: s['owner_email'] = email
            if user.get('phone'): s['phone'] = user.get('phone')
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
WANTS_FILE = 'wants.json'
def get_wants_data(): return load_db(WANTS_FILE, [])
def save_wants_data(wants): save_db(WANTS_FILE, wants)

# === FORGOT PASSWORD EMAIL FUNCTION ===
def send_reset_email(to_email, otp, user_name="Boss"):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Sannla Shop <{EMAIL_FROM}>"
        msg['To'] = to_email
        msg['Subject'] = f"Your Sannla Reset Code is {otp}"
        body = f"""
        <div style="font-family:Arial;max-width:420px;margin:auto;border:1px solid #eee;border-radius:15px;overflow:hidden">
          <div style="background:#000;color:#FFCC02;padding:18px;text-align:center"><h2 style="margin:0">🏪 Sannla</h2><p style="margin:5px 0 0 0;color:#fff">Shop Smart, Sell Faster</p></div>
          <div style="padding:22px">
            <h3 style="margin:0 0 10px 0">Hi {user_name},</h3>
            <p style="color:#333">Your password reset code is:</p>
            <h1 style="background:#000;color:#FFCC02;padding:16px;text-align:center;letter-spacing:8px;border-radius:12px;font-size:32px;margin:15px 0">{otp}</h1>
            <p style="color:#666;font-size:14px">This code expires in <b>10 minutes</b>. If you didn't request this, just ignore this email.</p>
            <p style="color:#999;font-size:12px;margin-top:20px">Don't share this code with anyone. Sannla team will never ask for it.</p>
          </div>
        </div>
        """
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_APP_PASSWORD.replace(' ',''))
        server.send_message(msg)
        server.quit()
        print(f"Email sent to {to_email} OTP {otp}")
        return True
    except Exception as e:
        print("Email error:", e)
        return False

# ===== API ROUTES - YOUR EXISTING CODE CONTINUES =====

@app.route('/product/<pid>')
def product_link(pid):
    ref = request.args.get('ref','')
    promo = request.args.get('promo','')
    try:
        clicks = load_db('promo_clicks.json',[])
        clicks.append({'product_id':pid,'ref':ref,'promo':promo,'time':time.time(),'ip':request.remote_addr})
        save_db('promo_clicks.json', clicks)
    except: pass
    path = 'templates/index.html' if os.path.exists('templates/index.html') else 'index.html'
    try:
        html = open(path,'r',encoding='utf-8').read()
    except:
        html = "<html><body>Loading...<script>window.location='/?promo={{promo}}&product={{pid}}'</script></body></html>"
    inject = f"""
    <script>
    localStorage.setItem('sannlas_aff_ref','{ref}');
    localStorage.setItem('sannlas_ref_product','{pid}');
    if('{promo}') localStorage.setItem('pending_promo','{promo}');
    window.addEventListener('load',()=>{{
        setTimeout(()=>{{
            if(typeof viewProd==='function') viewProd('{pid}');
        }},1200);
    }});
    </script>
    </body>
    """
    html = html.replace('</body>', inject)
    return html

@app.route('/p/<pid>')
def product_short(pid):
    return product_link(pid)

@app.route('/')
def home():
    ref = request.args.get('ref')
    promo = request.args.get('promo','')
    product = request.args.get('product','')
    resp = make_response(render_template('index.html'))
    if ref:
        resp.set_cookie('ref_code', ref, max_age=30*24*60*60, httponly=False, samesite='Lax')
    if promo and product:
        try:
            clicks = load_db('promo_clicks.json',[])
            clicks.append({'product_id':product,'promo':promo,'ref':ref,'time':time.time(),'ip':request.remote_addr})
            save_db('promo_clicks.json', clicks)
        except:
            pass
    return resp

@app.route('/wallet')
def wallet_page():
    return redirect('/balance')
@app.route('/balance')
def balance_page(): return render_template('balance.html')
@app.route('/invite')
def invite_page(): return render_template('invite.html')
@app.route('/shop/<slug>')
def shop_page_slug(slug): return render_template('shop.html')
@app.route('/shop')
def shop_page(): return render_template('shop.html')

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
def get_billboard(): return jsonify(get_billboard_config())

@app.route('/api/admin/billboard', methods=['GET'])
@admin_required
def admin_get_billboard(): return jsonify(get_billboard_config())

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
    if 'duration' in data:
        dur = str(data.get('duration'))
        if dur == "0": cfg['expires_at'] = None
        else:
            try: cfg['expires_at'] = (datetime.now() + timedelta(hours=int(dur))).isoformat()
            except: pass
    if 'expires_at' in data: cfg['expires_at'] = data['expires_at']
    cfg['updated'] = time.time()
    save_db('billboard.json', cfg)
    return jsonify({'success': True, 'config': cfg})

@app.route('/api/upload/billboard', methods=['POST'])
@admin_required
def upload_billboard():
    from datetime import datetime, timedelta
    file = request.files.get('file')
    text = request.form.get('text','')[:200]
    link = request.form.get('link','')[:300]
    duration = request.form.get('duration','24')
    if not file: return jsonify({"error": "No file selected"}), 400
    data = file.read()
    if len(data) > 12*1024*1024: return jsonify({"error": "File too big! Max 12MB"}), 400
    mime = file.mimetype or 'image/jpeg'
    b64 = base64.b64encode(data).decode('utf-8')
    media_url = f"data:{mime};base64,{b64}"
    filetype = 'video' if 'video' in mime else 'image'
    expires_at = None if str(duration)=="0" else (datetime.now() + timedelta(hours=int(duration))).isoformat()
    cfg = {"active": True,"type": filetype,"media_url": media_url,"text": text or "Welcome","link": link or "","created": time.time(),"updated": time.time(),"expires_at": expires_at}
    save_db('billboard.json', cfg)
    return jsonify({"url": media_url, "type": filetype, "success": True, "config": cfg})

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
    u=next((x for x in users if str(x.get('email','')).lower()==email or str(x.get('phone',''))==phone), None)
    if not u:
        return jsonify({'success':True,'coins':0,'total':0,'bought':0,'earned':0,'spent':0,'bought_value':0,'earned_value':0,'total_value':0,'spent_value':0,'withdrawable':0,'can_upload':0})
    bought = int(u.get('bought', u.get('bought_coins', 0)))
    earned = int(u.get('earned', u.get('earned_coins', 0)))
    spent = int(u.get('spent', 0))
    total = bought + earned - spent
    if total<0: total=0
    withdrawable = total - FREE_TRIAL
    if withdrawable<0: withdrawable=0
    return jsonify({
        'success':True,'coins': total,'total': total,'bought': bought,'earned': earned,'spent': spent,'withdrawable': withdrawable,
        'bought_value': bought * COIN_PRICE,'earned_value': earned * COIN_PRICE,'spent_value': spent * COIN_PRICE,
        'total_value': total * COIN_PRICE,'withdrawable_value': withdrawable * COIN_PRICE,'can_upload': total // UPLOAD_COST
    })

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
    if not target_tx: return jsonify({'success':False,'message':'Transaction not found'}),404
    if action=='block_fake':
        if target_tx.get('status')!= 'blocked_fake':
            cfg['remaining'] += target_tx.get('coins',0)
            cfg['sold'] = max(0, cfg.get('sold',0) - target_tx.get('coins',0))
            for u in users:
                if str(u.get('email','')).lower()==str(target_tx.get('email','')).lower() or str(u.get('phone',''))==str(target_tx.get('phone','')):
                    u['bought'] = max(0, int(u.get('bought',0)) - int(target_tx.get('coins',0)))
                    u['bought_coins'] = u['bought']
                    u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
            target_tx['status']='blocked_fake'
    else:
        if target_tx.get('status')!= 'verified_by_owner':
            target_tx['status']='verified_by_owner'
            for u in users:
                if str(u.get('email','')).lower()==str(target_tx.get('email','')).lower() or str(u.get('phone',''))==str(target_tx.get('phone','')):
                    u['bought'] = int(u.get('bought',0)) + int(target_tx.get('coins',0))
                    u['bought_coins'] = u['bought']
                    u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
    save_db('coin_transactions.json', txs); save_db('users.json', users); save_coin_config(cfg)
    return jsonify({'success':True, 'action': action})

@app.route('/api/admin/coins/add', methods=['POST'])
@admin_required
def admin_add_coins():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    coins = int(data.get('coins',0))
    reason = data.get('reason','Admin refill')
    if coins <=0: return jsonify({'success': False, 'message': 'Coins must be >0'}),400
    users = load_db('users.json', [])
    found = None
    for u in users:
        if (email and str(u.get('email','')).lower()==email) or (phone and str(u.get('phone',''))==phone):
            u['earned'] = int(u.get('earned',0)) + coins
            u['earned_coins'] = u['earned']
            u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
            found = u; break
    if not found: return jsonify({'success': False, 'message': 'User not found'}),404
    save_db('users.json', users)
    txs = load_db('coin_transactions.json', [])
    txs.append({'id': int(time.time()*1000), 'email': found.get('email'), 'phone': found.get('phone'), 'coins': coins, 'price': 0, 'momo_code': f'ADMIN-{uuid.uuid4().hex[:6].upper()}', 'reason': reason, 'time': time.time(), 'status': 'admin_gift'})
    save_db('coin_transactions.json', txs)
    return jsonify({'success': True, 'message': f'Added {coins} coins to {found.get("email")}', 'user': {'email': found.get('email'), 'coins': found.get('coins')}})

@app.route('/api/admin/coins/config', methods=['GET'])
@admin_required
def admin_coin_config_get(): return jsonify(get_coin_config())

@app.route('/api/admin/coins/config', methods=['POST'])
@admin_required
def admin_update_coin_config():
    data = request.json or {}
    cfg = get_coin_config()
    action = data.get('action')
    if action in ('add', 'reduce'):
        try: amount = int(data.get('amount', 0))
        except: return jsonify({"success": False, "message": "Invalid amount"}), 400
        if amount <= 0: return jsonify({"success": False, "message": "Enter amount >0"}), 400
        if action == "add":
            cfg['total'] = int(cfg.get('total', 0)) + amount
            cfg['remaining'] = int(cfg.get('remaining', 0)) + amount
            save_coin_config(cfg)
            return jsonify({"success": True, "message": f"Added {amount:,} coins", "config": cfg})
        else:
            if int(cfg.get('remaining',0)) < amount:
                return jsonify({"success": False, "message": f"Only {cfg.get('remaining',0):,} remaining!"}), 400
            cfg['total'] = int(cfg.get('total', 0)) - amount
            cfg['remaining'] = int(cfg.get('remaining', 0)) - amount
            save_coin_config(cfg)
            return jsonify({"success": True, "message": f"Reduced {amount:,} coins", "config": cfg})
    if 'price' in data: cfg['price'] = int(data['price'])
    if 'upload_cost' in data: cfg['upload_cost'] = int(data['upload_cost'])
    if 'total' in data:
        diff = int(data['total']) - cfg.get('total', TOTAL_COINS)
        cfg['total'] = int(data['total'])
        cfg['remaining'] = max(0, cfg.get('remaining',0) + diff)
    save_coin_config(cfg)
    return jsonify({'success': True, 'config': cfg, 'message': 'Config updated'})

@app.route('/api/withdraw', methods=['POST'])
def request_withdraw():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    amount = int(data.get('amount',0))
    momo_number = data.get('momo_number','').strip()
    momo_name = data.get('momo_name','').strip()
    if amount < 5000: return jsonify({'success': False, 'message': 'Minimum withdraw 5000 UGX'}),400
    if not momo_number: return jsonify({'success': False, 'message': 'MoMo number required'}),400
    withdraws = load_db('withdraws.json', [])
    new_w = {'id': int(time.time()*1000), 'email': email, 'phone': phone, 'amount': amount, 'momo_number': momo_number, 'momo_name': momo_name, 'status': 'pending', 'time': time.time(), 'paid_time': None}
    withdraws.append(new_w)
    save_db('withdraws.json', withdraws)
    return jsonify({'success': True, 'message': 'Withdraw request sent!', 'withdraw': new_w})

@app.route('/api/withdraws')
def my_withdraws():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    withdraws = load_db('withdraws.json', [])
    result = [w for w in withdraws if (email and w.get('email','').lower()==email) or (phone and w.get('phone','')==phone)]
    return jsonify(result[::-1])

@app.route('/api/admin/withdraws')
@admin_required
def admin_withdraws(): return jsonify(load_db('withdraws.json', [])[::-1])

@app.route('/api/admin/withdraw/action', methods=['POST'])
@admin_required
def admin_withdraw_action():
    data = request.json or {}
    wid = data.get('id')
    action = data.get('action','paid')
    withdraws = load_db('withdraws.json', [])
    for w in withdraws:
        if str(w.get('id')) == str(wid):
            w['status'] = action
            if action == 'paid': w['paid_time'] = time.time()
            break
    save_db('withdraws.json', withdraws)
    return jsonify({'success': True})

@app.route('/api/sales/summary')
def sales_summary():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    orders = load_db('orders.json', [])
    my_orders = []
    for o in orders:
        if (email and o.get('seller_email','').lower()==email) or (phone and o.get('seller_phone','')==phone) or (email and o.get('seller','').lower()==email):
            my_orders.append(o)
    total_sales = sum(o.get('total', o.get('amount',0)) for o in my_orders)
    total_orders = len(my_orders)
    withdraws = load_db('withdraws.json', [])
    my_withdraws = [w for w in withdraws if (email and w.get('email','').lower()==email) or (phone and w.get('phone','')==phone)]
    withdrawn = sum(w.get('amount',0) for w in my_withdraws if w.get('status')=='paid')
    pending_withdraw = sum(w.get('amount',0) for w in my_withdraws if w.get('status')=='pending')
    balance = total_sales - withdrawn - pending_withdraw
    return jsonify({'success': True, 'total_sales': total_sales, 'total_orders': total_orders, 'withdrawn': withdrawn, 'pending_withdraw': pending_withdraw, 'balance': max(0,balance), 'orders': my_orders[-20:], 'withdraws': my_withdraws[-10:]})

@app.route('/api/my-referral')
def my_referral_api():
    phone = request.args.get('phone','').strip() or session.get('phone','')
    email = request.args.get('email','').lower().strip() or session.get('email','')
    if not phone and not email: return jsonify({"success":False, "message":"Login first"}), 401
    users = load_db('users.json', [])
    u = None
    for user in users:
        if (phone and user.get('phone')==phone) or (email and user.get('email','').lower()==email):
            u = user; break
    if not u: return jsonify({"success":False, "message":"User not found"}), 404
    if not u.get('referral_code'):
        code = f"SANN-{u.get('phone','0000')[-4:]}-{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))}"
        u['referral_code'] = code
        save_db('users.json', users)
    host = request.host_url.rstrip('/')
    link = f"{host}/?ref={u['referral_code']}"
    invites = [x for x in users if x.get('invited_by')==u['referral_code']]
    return jsonify({"success": True,"code": u['referral_code'],"link": link,"total_invites": len(invites),"earned_coins": len(invites) * 1,"earned_ugx": len(invites) * COIN_PRICE,"invites": [{"email": i.get('email'), "phone": i.get('phone'), "business": i.get('business')} for i in invites[-20:]]})

@app.route('/api/balance')
def api_balance():
    phone = request.args.get('phone','').strip()
    email = request.args.get('email','').lower().strip()
    users = load_db('users.json', [])
    u = next((x for x in users if (phone and x.get('phone')==phone) or (email and x.get('email','').lower()==email)), None)
    if not u: return jsonify({"success":False, "message":"User not found"}), 404
    txs = load_db('coin_transactions.json', [])
    my_txs = [t for t in txs if (phone and t.get('phone')==phone) or (email and t.get('email','').lower()==email)]
    bought = int(u.get('bought', u.get('bought_coins',0)))
    earned = int(u.get('earned', u.get('earned_coins',0)))
    spent = int(u.get('spent',0))
    total = bought + earned - spent
    if total<0: total=0
    withdrawable = total - FREE_TRIAL
    if withdrawable<0: withdrawable=0
    return jsonify({"success": True,"bought": bought,"earned": earned,"spent": spent,"withdrawable": withdrawable,"bought_coins": bought,"earned_coins": earned,"total_coins": total,"coins": total,"ugx_value": total*COIN_PRICE,"bought_value": bought*COIN_PRICE,"earned_value": earned*COIN_PRICE,"spent_value": spent*COIN_PRICE,"withdrawable_value": withdrawable*COIN_PRICE,"history": my_txs[::-1][:30]})

@app.route('/api/withdraw/coins', methods=['POST'])
def withdraw_coins():
    data = request.json or {}
    phone = data.get('phone','').strip()
    email = data.get('email','').lower().strip()
    coins = int(data.get('coins',0))
    momo = data.get('momo_number','').strip()
    if coins <=0: return jsonify({"success":False,"message":"Enter coins >0"}),400
    if coins < WITHDRAW_MIN_COINS:
        return jsonify({"success":False,"message":f"Minimum withdraw is {WITHDRAW_MIN_COINS} coins = UGX {WITHDRAW_MIN_COINS*COIN_PRICE:,}!"}),400
    if not momo: return jsonify({"success":False,"message":"MoMo number required"}),400
    users = load_db('users.json', [])
    u = next((x for x in users if (phone and x.get('phone')==phone) or (email and x.get('email','').lower()==email)), None)
    if not u: return jsonify({"success":False,"message":"User not found"}),404
    bought = int(u.get('bought',0))
    earned = int(u.get('earned',0))
    spent = int(u.get('spent',0))
    total = bought + earned - spent
    if total<0: total=0
    withdrawable = total - FREE_TRIAL
    if withdrawable<0: withdrawable=0
    if withdrawable < WITHDRAW_MIN_COINS:
        return jsonify({"success":False,"message":f"You have {total} total, but {FREE_TRIAL} free not withdrawable. Withdrawable = {withdrawable}. Need {WITHDRAW_MIN_COINS}!"}),400
    if coins > withdrawable:
        return jsonify({"success":False,"message":f"Max withdrawable is {withdrawable} coins"}),400
    ugx = coins * COIN_PRICE
    u['spent'] = spent + coins
    u['coins'] = bought + earned - u['spent']
    if u['coins']<0: u['coins']=0
    save_db('users.json', users)
    withdraws = load_db('withdraws.json', [])
    withdraws.append({'id': int(time.time()*1000),'email': u.get('email'),'phone': u.get('phone'),'amount': ugx,'coins': coins,'momo_number': momo,'momo_name': data.get('momo_name',''),'status': 'pending','type': 'withdrawable','time': time.time(),'paid_time': None})
    save_db('withdraws.json', withdraws)
    txs = load_db('coin_transactions.json', [])
    txs.append({'id': int(time.time()*1000), 'email': u.get('email'), 'phone': u.get('phone'), 'coins': -coins, 'price': ugx, 'momo_code': f'WD-{uuid.uuid4().hex[:6].upper()}', 'reason': f'Withdraw {coins} coins -> UGX {ugx} to {momo}', 'time': time.time(), 'status': 'withdraw_pending'})
    save_db('coin_transactions.json', txs)
    return jsonify({"success":True, "message":f"Request sent! {coins} coins = UGX {ugx:,} to {momo}."})

@app.route('/api/register', methods=['POST'])
def register():
    data=request.json; email=data.get('email','').lower().strip(); phone=data.get('phone','').strip(); pwd=data.get('password',''); biz=data.get('business','')
    ref_code = data.get('ref') or request.args.get('ref') or request.cookies.get('ref_code') or ''
    if not email or not phone or not pwd: return jsonify({'success':False,'message':'Fill all'}),400
    users=load_db('users.json',[])
    if any(u['email']==email for u in users): return jsonify({'success':False,'message':'Email exists - Login'}),400
    import random, string
    my_ref_code = f"SANN-{phone[-4:]}-{''.join(random.choices(string.ascii_uppercase+string.digits, k=4))}"
    user={'id':int(time.time()*1000),'email':email,'phone':phone,'password':hash_pwd(pwd),'business':biz,'created':time.time(),'plan':'free14','plan_name':'14 Days FREE','subscription_expires':time.time()+14*86400,'paid':True,'verified':False,'followers':0,'total_likes':0,'total_stars':0,'coins':10,'bought':0,'earned':10,'spent':0,'bought_coins':0,'earned_coins':10,'trial_given':True,'referral_code':my_ref_code,'invited_by':ref_code}
    users.append(user)
    if ref_code:
        for ru in users:
            if ru.get('referral_code')==ref_code:
                ru['earned'] = int(ru.get('earned',0)) + 1
                ru['earned_coins'] = ru['earned']
                ru['coins'] = int(ru.get('bought',0)) + int(ru.get('earned',0)) - int(ru.get('spent',0))
                txs = load_db('coin_transactions.json', [])
                txs.append({'id': int(time.time()*1000), 'email': ru.get('email'), 'phone': ru.get('phone'), 'coins': 1, 'price': 0, 'momo_code': f'INVITE-{uuid.uuid4().hex[:6].upper()}', 'reason': f'Invite bonus - {phone} joined', 'time': time.time(), 'status': 'invite_bonus', 'invited_phone': phone})
                save_db('coin_transactions.json', txs)
                break
    save_db('users.json',users)
    try: shop = ensure_shop_for_user(user)
    except: shop = None
    safe={k:v for k,v in user.items() if k!='password'}
    if shop: safe['shop']=shop
    return jsonify({'success':True,'user':safe})

@app.route('/api/account/set-password', methods=['POST'])
def set_password_api():
    try:
        data=request.json or {}
        email=data.get('email','').strip().lower()
        phone=data.get('phone','').strip()
        pwd=data.get('password','')
        if len(pwd)<4:
            return jsonify({"success":False,"message":"Password too short! Min 4 chars Boss!"})
        from werkzeug.security import generate_password_hash
        users = load_db('users.json', [])
        found=False
        for u in users:
            if (u.get('email','').lower()==email) or (phone and u.get('phone')==phone):
                u['password_hash']=generate_password_hash(pwd)
                u['password']=hash_pwd(pwd)
                u['has_password']=True
                found=True
                break
        if not found:
            return jsonify({"success":False,"message":"User not found"})
        save_db('users.json', users)
        return jsonify({"success":True,"message":"🔒 Password saved! Your account is now protected Boss!"})
    except Exception as e:
        return jsonify({"success":False,"message":str(e)})

# === FORGOT PASSWORD API - NEW ===
@app.route('/api/forgot-password', methods=['POST'])
@limiter.limit("5 per minute")
def forgot_password_api():
    data = request.get_json() or {}
    email = data.get('email','').lower().strip()
    if not email: return jsonify({"success": False, "message": "Enter email"}), 400
    users = load_db('users.json', [])
    user = next((u for u in users if u.get('email','').lower()==email), None)
    if not user:
        return jsonify({"success": False, "message": "Email not found - Check your email Boss!"}), 404

    # Load existing resets
    resets = load_db('password_resets.json', {})
    # Delete old for this email
    if email in resets:
        del resets[email]

    otp = str(random.randint(100000, 999999))
    expires_at = time.time() + 10*60 # 10 mins

    resets[email] = {"otp": otp, "expires": expires_at, "tries": 0, "created": time.time()}
    save_db('password_resets.json', resets)

    # Send email in background thread so API fast
    threading.Thread(target=send_reset_email, args=(email, otp, user.get('business','Boss'))).start()

    return jsonify({"success": True, "message": f"Code sent to {email}"})

@app.route('/api/reset-password', methods=['POST'])
@limiter.limit("10 per minute")
def reset_password_api():
    data = request.get_json() or {}
    email = data.get('email','').lower().strip()
    otp = data.get('otp','').strip()
    new_password = data.get('new_password','').strip()

    if not email or not otp or not new_password:
        return jsonify({"success": False, "message": "Fill all fields"}), 400
    if len(new_password) < 4:
        return jsonify({"success": False, "message": "Password min 4 chars"}), 400

    resets = load_db('password_resets.json', {})
    rec = resets.get(email)
    if not rec:
        return jsonify({"success": False, "message": "No reset request. Send code again."}), 400

    # Check expiry
    if time.time() > rec.get('expires',0):
        del resets[email]
        save_db('password_resets.json', resets)
        return jsonify({"success": False, "message": "Code expired after 10 mins. Request new code!"}), 400

    if rec.get('tries',0) >= 3:
        del resets[email]
        save_db('password_resets.json', resets)
        return jsonify({"success": False, "message": "Too many wrong tries. Request new code!"}), 400

    if rec.get('otp')!= otp:
        rec['tries'] = rec.get('tries',0)+1
        save_db('password_resets.json', resets)
        return jsonify({"success": False, "message": f"Wrong code! {3-rec['tries']} tries left"}), 400

    # OTP CORRECT - Update password
    users = load_db('users.json', [])
    found = False
    for u in users:
        if u.get('email','').lower()==email:
            try:
                from werkzeug.security import generate_password_hash
                u['password_hash'] = generate_password_hash(new_password)
            except: pass
            u['password'] = hash_pwd(new_password)
            u['has_password'] = True
            found = True
            break
    if not found:
        return jsonify({"success": False, "message": "User not found"}), 404

    save_db('users.json', users)

    # DELETE OTP AFTER USE - Important!
    del resets[email]
    save_db('password_resets.json', resets)

    return jsonify({"success": True, "message": "Password changed! Login now Boss!"})

# === END FORGOT PASSWORD ===

@app.route('/api/my-sales/stats')
def my_sales_stats():
    email=request.args.get('email','').lower().strip()
    phone=request.args.get('phone','').strip()
    orders = load_db('orders.json', [])
    products = load_db('products.json', [])
    promo_spent=0
    for p in products:
        if (email and (p.get('seller_email','').lower()==email)) or (phone and p.get('phone')==phone):
            promo_spent += int(p.get('promo_commission',0)) * int(p.get('sold',0))
    import datetime
    now = datetime.datetime.now()
    today=0; week=0; year=0
    my_orders=[]
    for o in orders:
        if (email and str(o.get('seller_email','')).lower()==email) or (phone and str(o.get('seller_phone',''))==phone) or (email and str(o.get('seller','')).lower()==email):
            my_orders.append(o)
    for o in my_orders:
        amt = o.get('total', o.get('amount',0))
        try:
            t = o.get('time',0)
            d = datetime.datetime.fromtimestamp(float(t)) if isinstance(t,(int,float)) else now
        except:
            d=now
        if d.date()==now.date(): today+=amt
        if (now - d).days <7: week+=amt
        if d.year==now.year: year+=amt
    return jsonify({"today":today,"week":week,"year":year,"orders":len(my_orders),"promo_coins_spent":promo_spent})

@app.route('/api/login', methods=['POST'])
def login():
    data=request.json; email=data.get('email','').lower(); pwd=data.get('password','')
    users=load_db('users.json',[])
    def check_pwd(u, pwd):
        if u.get('password') == hash_pwd(pwd):
            return True
        try:
            from werkzeug.security import check_password_hash
            if u.get('password_hash') and check_password_hash(u.get('password_hash'), pwd):
                return True
        except: pass
        return False
    u=next((x for x in users if x['email']==email and check_pwd(x,pwd)), None)
    if not u: return jsonify({'success':False,'message':'Wrong email/password'}),401
    if 'bought' not in u: u['bought'] = int(u.get('bought_coins',0))
    if 'earned' not in u: u['earned'] = int(u.get('earned_coins',0))
    if 'spent' not in u: u['spent'] = 0
    if 'bought_coins' not in u: u['bought_coins']=u['bought']
    if 'earned_coins' not in u: u['earned_coins']=u['earned']
    if int(u.get('coins',0))==0 and int(u.get('bought',0))==0 and int(u.get('earned',0))==0 and not u.get('trial_given'):
        u['earned']=10; u['earned_coins']=10; u['coins']=10; u['trial_given']=True
    u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
    if u['coins']<0: u['coins']=0
    save_db('users.json', users)
    try: ensure_shop_for_user(u)
    except: pass
    safe={k:v for k,v in u.items() if k!='password'}
    safe['subscription_active']=safe.get('subscription_expires',0)>time.time()
    session['phone']=u.get('phone'); session['email']=u.get('email')
    return jsonify({'success':True,'user':safe})

@app.route('/api/wants')
def get_wants_api():
    q = request.args.get('q','').lower()
    district = request.args.get('district','').lower()
    wants = get_wants_data()
    filtered = [w for w in wants if w.get('status','open') == 'open']
    if q:
        filtered = [w for w in filtered if q in w.get('item','').lower() or q in w.get('note','').lower()]
    if district:
        filtered = [w for w in filtered if district in w.get('district','').lower()]
    filtered = sorted(filtered, key=lambda x: x.get('created',0), reverse=True)
    return jsonify(filtered[:100])

@app.route('/api/want', methods=['POST'])
def create_want_api():
    data = request.get_json() or {}
    item = data.get('item','').strip()
    quantity = data.get('quantity','').strip()
    district = data.get('district','').strip()
    phone = data.get('phone','').strip()
    email = data.get('email','').lower().strip()
    note = data.get('note','').strip()
    if not item:
        return jsonify({'success': False, 'message': 'What do you want to buy?'}), 400
    if not phone and not email:
        return jsonify({'success': False, 'message': 'Add phone number Boss!'}), 400
    wants = get_wants_data()
    new_want = {
        'id': int(time.time()*1000),
        'item': item,
        'quantity': quantity,
        'district': district,
        'phone': phone,
        'email': email,
        'note': note,
        'status': 'open',
        'created': time.time(),
        'created_at': time.time()
    }
    wants.append(new_want)
    save_wants_data(wants)
    return jsonify({'success': True, 'message': 'WANT posted! Sellers will see it!', 'want': new_want})

@app.route('/api/want/<int:wid>/close', methods=['POST'])
def close_want_api(wid):
    wants = get_wants_data()
    for w in wants:
        if w['id'] == wid:
            w['status'] = 'closed'
            break
    save_wants_data(wants)
    return jsonify({'success': True})

@app.route('/api/my-wants')
def my_wants_api():
    phone = request.args.get('phone','').strip()
    email = request.args.get('email','').lower().strip()
    wants = get_wants_data()
    result = [w for w in wants if (phone and w.get('phone')==phone) or (email and w.get('email','').lower()==email)]
    return jsonify(sorted(result, key=lambda x: x.get('created',0), reverse=True))

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
        if exact: filtered = exact
    filtered=sorted(filtered,key=lambda x:x.get('created',0),reverse=True)
    public=[]
    for p in filtered:
        pp=p.copy(); pp.pop('phone',None); public.append(pp)
    return jsonify(public)

@app.route('/api/sell', methods=['POST'])
def sell():
    name=request.form.get('name')
    price=int(request.form.get('price',0))
    original_price = int(request.form.get('original_price') or request.form.get('price',0))
    if original_price < price: original_price = price
    business=request.form.get('business')
    location=request.form.get('location')
    phone=request.form.get('phone')
    desc=request.form.get('desc','') or request.form.get('description','')
    main_cat=request.form.get('main_category')
    stock=int(request.form.get('stock',10))
    promo_commission = int(request.form.get('promo_commission','3'))
    user_email=request.form.get('user_email','').lower()
    users=load_db('users.json',[]); seller=next((u for u in users if u['phone']==phone or u['email']==user_email),None)
    if not seller: return jsonify({'success':False,'message':'Register first'}),402
    if int(seller.get('coins',0)) < UPLOAD_COST: return jsonify({'success':False,'message':f'Need {UPLOAD_COST} coins! You have {seller.get("coins",0)}','needs_coins':True,'my_coins':seller.get('coins',0)}),402
    images=[]
    for key in request.files:
        f=request.files[key]
        if f and f.filename:
            import base64; file_bytes=f.read(); mime=f.mimetype or 'image/jpeg'; b64=base64.b64encode(file_bytes).decode('utf-8'); images.append(f"data:{mime};base64,{b64}")
    if not images: images=['https://via.placeholder.com/300']
    shop_id=None; shop_slug=None
    try:
        shop = ensure_shop_for_user(seller); shop_id=shop.get('id'); shop_slug=shop.get('shop_slug')
    except: pass
    prod = {'id': int(time.time()*1000),'name': name,'price': price,'original_price': original_price,'business': business,'location': location,'phone': phone,'seller_email': user_email,'description': desc,'image': images[0],'images': images,'main_category': main_cat,'stock': stock,'sold': 0,'rating': 5.0,'reviews': [],'created': time.time(),'shop_id': shop_id,'shop_slug': shop_slug,'promo_commission': promo_commission}
    products=load_db('products.json',[]); products.append(prod); save_db('products.json', products)
    for u in users:
        if u['phone']==phone or u['email']==user_email:
            u['spent'] = int(u.get('spent',0)) + UPLOAD_COST
            u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
            if u['coins']<0: u['coins']=0
            u['bought_coins']=int(u.get('bought',0)); u['earned_coins']=int(u.get('earned',0))
    save_db('users.json', users)
    return jsonify({'success':True,'message':f'Added! {UPLOAD_COST} coins used'})

@app.route('/api/shops')
def list_shops():
    shops = load_db('shops.json', [])
    products = load_db('products.json', [])
    counts = {}
    for p in products:
        slug = p.get('shop_slug')
        if slug: counts[slug] = counts.get(slug, 0) + 1
    for s in shops:
        slug = s.get('shop_slug')
        s['total_products'] = counts.get(slug, 0)
    filtered = [s for s in shops if s.get('total_products',0)>0]
    return jsonify(sorted(filtered, key=lambda x: x.get('total_products',0), reverse=True))

@app.route('/api/shop/<slug>')
def get_shop_by_slug(slug):
    shops = load_db('shops.json', [])
    products = load_db('products.json', [])
    shop = next((s for s in shops if s.get('shop_slug')==slug), None)
    shop_products = [p for p in products if p.get('shop_slug')==slug]
    if shop:
        return jsonify({'success':True,'shop':shop,'products':shop_products})
    return jsonify({'success':False,'message':'Shop not found'}),404

@app.route('/api/my-products')
def my_products():
    phone=request.args.get('phone','').strip()
    email=request.args.get('email','').lower().strip()
    products=load_db('products.json', [])
    result=[p for p in products if (email and (p.get('seller_email') or '').lower()==email) or (phone and p.get('phone')==phone)]
    return jsonify(result)

@app.route('/api/delete-product/<int:pid>', methods=['DELETE'])
def delete_prod(pid):
    products=load_db('products.json', []); products=[p for p in products if p['id']!=pid]; save_db('products.json', products)
    return jsonify({'success':True})

@app.route('/api/fix-slugs')
def fix_slugs():
    products = load_db('products.json', [])
    for p in products:
        b = p.get('business') or ''
        if b: p['shop_slug'] = make_shop_slug(b)
    save_db('products.json', products)
    return jsonify({'success':True,'message':'Fixed'})

@app.route('/api/admin/data')
@admin_required
def admin_data():
    try:
        products=load_db('products.json',[]) or []
        users=load_db('users.json',[]) or []
        orders=load_db('orders.json',[]) or []
        contacts=load_db('contacts.json',[]) or []
        coin_transactions=load_db('coin_transactions.json',[]) or []
        shops=load_db('shops.json',[]) or []
        withdraws=load_db('withdraws.json',[]) or []
        billboard=get_billboard_config()
        wants=load_db('wants.json',[]) or []
        coin_config=get_coin_config()
        coin_rev = sum(t.get('price',0) for t in coin_transactions if t.get('status')!='blocked_fake')
        return jsonify({'products':products,'users':users,'orders':orders,'contacts':contacts,'coin_transactions':coin_transactions,'shops':shops,'withdraws':withdraws,'wants':wants,'billboard':billboard,'coin_config':coin_config,'coin_revenue':coin_rev,'total_revenue':0,'total_sellers':len(users),'total_orders':len(orders),'total_wants':len(wants)})
    except Exception as e:
        return jsonify({'products':[],'users':[],'orders':[],'contacts':[],'coin_transactions':[],'shops':[],'withdraws':[],'wants':[],'billboard':{},'coin_config':{"total":1000000000,"remaining":1000000000,"sold":0,"price":599},"coin_revenue":0,'total_revenue':0,'total_sellers':0,'total_orders':0,'total_wants':0,'error': str(e)}), 200

@app.route('/api/admin/transactions')
@admin_required
def admin_transactions(): return jsonify(load_db('transactions.json', []) or [])
@app.route('/api/orders')
def get_orders(): return jsonify(load_db('orders.json', [])[::-1])
@app.route('/api/contact', methods=['POST'])
def contact_owner(): data=request.json; contacts=load_db('contacts.json', []); contacts.append({**data,'time':time.time(),'id':int(time.time())}); save_db('contacts.json', contacts); return jsonify({'success':True})

@app.route('/api/promote/apply', methods=['POST'])
def promote_apply():
    data=request.json or {}
    product_id=str(data.get('product_id','')).strip()
    phone=(data.get('phone') or '').strip()
    email=(data.get('email') or '').lower().strip()
    if not phone and not email:
        return jsonify({"success":False,"message":"Login first"}),401
    products=load_db('products.json',[])
    prod=next((p for p in products if str(p.get('id'))==product_id),None)
    if not prod:
        return jsonify({"success":False,"message":"Product not found"}),404
    promos=load_db('promotions.json',[])
    existing = next((p for p in promos if str(p.get('product_id'))==product_id and (p.get('freelancer_phone')==phone or p.get('freelancer_email','').lower()==email)), None)
    if existing:
        code = existing.get('promo_code')
        link = f"https://sannlas.onrender.com/?promo={code}&product={product_id}"
        return jsonify({"success":True,"message":f"Already applied!","promo":existing,"link":link,"promo_link":link,"code":code})
    import random,string
    code=f"PROMO{product_id[:3]}{phone[-3:]}{''.join(random.choices(string.ascii_uppercase+string.digits,k=3))}"
    new_promo={
        "id":int(time.time()*1000),
        "product_id":product_id,
        "product_name":prod.get('name'),
        "product_owner_phone":prod.get('phone'),
        "product_owner_email":(prod.get('seller_email') or '').lower(),
        "freelancer_phone":phone,
        "freelancer_email":email,
        "commission_coins":int(prod.get('promo_commission',3)),
        "promo_code":code,
        "status":"approved",
        "sales":0,
        "created":time.time()
    }
    promos.append(new_promo)
    save_db('promotions.json',promos)
    link = f"https://sannlas.onrender.com/?promo={code}&product={product_id}"
    return jsonify({"success":True,"message":f"Applied! Earn {new_promo['commission_coins']} coins per sale! Link: {link}","promo":new_promo,"link":link,"promo_link":link,"code":code})

@app.route('/api/promote/my', methods=['GET'])
def my_promotions():
    phone=request.args.get('phone','').strip(); email=request.args.get('email','').lower().strip()
    promos=load_db('promotions.json',[]); result=[p for p in promos if (phone and p.get('freelancer_phone')==phone) or (email and p.get('freelancer_email','').lower()==email)]
    return jsonify(result[::-1])

@app.route('/api/promote/requests', methods=['GET'])
def promote_requests():
    phone=request.args.get('phone','').strip(); email=request.args.get('email','').lower().strip()
    promos=load_db('promotions.json',[]); result=[p for p in promos if (phone and p.get('product_owner_phone')==phone) or (email and p.get('product_owner_email','').lower()==email)]
    return jsonify(result[::-1])

@app.route('/api/promote/action', methods=['POST'])
def promote_action():
    data=request.json or {}; pid=int(data.get('id',0)); action=data.get('action','approve')
    promos=load_db('promotions.json',[])
    for p in promos:
        if int(p.get('id'))==pid: p['status']=action; break
    save_db('promotions.json',promos)
    return jsonify({"success":True,"message":f"Promoter {action}d!"})

@app.route('/api/orders/create', methods=['POST'])
def create_order():
    data=request.json or {}; promo_code=data.get('promo_code','').strip(); product_id=data.get('product_id'); buyer_phone=data.get('buyer_phone','').strip(); buyer_email=data.get('buyer_email','').lower().strip(); amount=data.get('amount',0)
    orders=load_db('orders.json',[]); new_order={"id":int(time.time()*1000),"product_id":product_id,"amount":amount,"buyer_phone":buyer_phone,"buyer_email":buyer_email,"promo_code":promo_code,"time":time.time(),"status":"pending"}
    orders.append(new_order); save_db('orders.json',orders)
    if promo_code:
        promos=load_db('promotions.json',[]); users=load_db('users.json',[])
        for p in promos:
            if p.get('promo_code')==promo_code and p.get('status')=='approved':
                p['sales']=p.get('sales',0)+1
                for u in users:
                    if str(u.get('phone'))==str(p.get('freelancer_phone')) or str(u.get('email','').lower())==str(p.get('freelancer_email','')).lower():
                        u['earned'] = int(u.get('earned',0)) + int(p.get('commission_coins',3))
                        u['earned_coins'] = u['earned']
                        u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
                        break
                break
        save_db('promotions.json',promos); save_db('users.json',users)
    return jsonify({"success":True,"order":new_order})

SPIN_CONFIG_FILE='spin_config.json'
def load_spin_config():
    default={
        "enabled": True,"cost": 1,"house_edge": 15,
        "prizes": [
            {"name":"0x LOST 😢","multiplier":0,"coins":0,"weight":35,"color":"#ff0000"},
            {"name":"1x BACK 🪙","multiplier":1,"coins":1,"weight":25,"color":"#ffffff"},
            {"name":"1.5x SMALL 🔵","multiplier":1.5,"coins":1,"weight":15,"color":"#00aaff"},
            {"name":"2x DOUBLE 🎉","multiplier":2,"coins":2,"weight":12,"color":"#00ff00"},
            {"name":"3x TRIPLE 🔥","multiplier":3,"coins":3,"weight":8,"color":"#FFCC02"},
            {"name":"5x SUPER 👑","multiplier":5,"coins":5,"weight":4,"color":"#aa00ff"},
            {"name":"10x JACKPOT 💎","multiplier":10,"coins":10,"weight":1,"color":"#FFD700"}
        ]
    }
    try:
        if os.path.exists(SPIN_CONFIG_FILE):
            with open(SPIN_CONFIG_FILE,'r') as f:
                cfg=json.load(f)
                if "house_edge" not in cfg: cfg["house_edge"]=15
                for p in cfg.get("prizes",[]):
                    if "multiplier" not in p: p["multiplier"]=p.get("coins",0)
                return cfg
    except: pass
    return default

def save_spin_config(cfg):
    with open(SPIN_CONFIG_FILE,'w') as f: json.dump(cfg,f)

@app.route('/api/spin', methods=['POST'])
def spin_game():
    data=request.json or {}
    phone=(data.get('phone') or '').strip()
    email=(data.get('email') or '').lower().strip()
    stake=int(data.get('stake',0))
    if stake<0: stake=0
    if stake>1000: stake=1000
    users=load_db('users.json',[])
    u=None
    for user in users:
        if (phone and user.get('phone')==phone) or (email and user.get('email','').lower()==email):
            u=user; break
    if not u: return jsonify({"success":False,"message":"Login first"}),401
    cfg=load_spin_config()
    if not cfg.get('enabled',True): return jsonify({"success":False,"message":"Spin disabled"}),400
    actual_cost = cfg.get('cost',1) if stake==0 else stake
    if int(u.get('coins',0)) < actual_cost: return jsonify({"success":False,"message":f"Need {actual_cost} coins, you have {u.get('coins',0)}","my_coins":u.get('coins',0)}),400
    u['spent'] = int(u.get('spent',0)) + actual_cost
    house_edge=cfg.get('house_edge',15)
    admin_cut = int(actual_cost * house_edge / 100) if stake>0 else actual_cost
    game_amount = actual_cost - admin_cut
    if stake==0: game_amount=0
    prizes=cfg.get('prizes',[]); weights=[p.get('weight',10) for p in prizes]
    prize=random.choices(prizes, weights=weights, k=1)[0]
    multiplier=prize.get('multiplier', prize.get('coins',0))
    if stake==0:
        win_amount = int(multiplier) if multiplier>=1 else 0
        if multiplier==1.5: win_amount=1
    else:
        win_amount = int(game_amount * multiplier)
    u['earned'] = int(u.get('earned',0)) + win_amount
    u['earned_coins'] = u['earned']
    u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
    if u['coins']<0: u['coins']=0
    spins=load_db('spins.json',[])
    spins.append({"phone":phone,"email":email,"stake":actual_cost,"fee":admin_cut,"admin_cut":admin_cut,"game_amount":game_amount,"cost":actual_cost,"won":win_amount,"prize":prize['name'],"multiplier":multiplier,"color":prize.get('color'),"time":time.time()})
    save_db('spins.json',spins); save_db('users.json',users)
    return jsonify({"success":True,"prize":prize,"my_coins":u['coins'],"bought":u.get('bought',0),"earned":u.get('earned',0),"spent":u.get('spent',0),"stake":actual_cost,"admin_cut":admin_cut,"game_amount":game_amount,"won":win_amount,"multiplier":multiplier,"message": f"{prize['name']}! Won {win_amount} coins!"})

@app.route('/api/spin/history', methods=['GET'])
def spin_history():
    phone=request.args.get('phone','').strip(); email=request.args.get('email','').lower().strip()
    spins=load_db('spins.json',[]); result=[s for s in spins if s.get('phone')==phone or s.get('email','').lower()==email]
    return jsonify(result[::-1][:20])

@app.route('/api/spin-history')
def spin_history_alias(): return spin_history()

@app.route('/api/admin/spin-config', methods=['GET','POST'])
def admin_spin_config():
    if request.method=='GET': return jsonify(load_spin_config())
    cfg=request.json; save_spin_config(cfg)
    return jsonify({"success":True,"message":"Saved!"})

@app.route('/api/admin/spin-stats')
def spin_stats():
    spins=load_db('spins.json',[]); total=len(spins)
    collected=sum(s.get('stake', s.get('cost',0)) for s in spins)
    paid=sum(s.get('won',0) for s in spins)
    admin_cut=sum(s.get('admin_cut', s.get('fee',0)) for s in spins)
    profit=collected - paid
    return jsonify({"total":total,"collected":collected,"paid":paid,"profit":profit,"admin_cut":admin_cut})

@app.route('/manifest.json')
def manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/sw.js')
def sw():
    return send_from_directory('.', 'sw.js')

@app.route('/icon-192.png')
def icon192():
    return send_from_directory('.', 'icon-192.png')

@app.route('/icon-512.png')
def icon512():
    return send_from_directory('.', 'icon-512.png')
    @app.route('/api/test-email')
def test_email():
    ok = send_reset_email("natelieabigail@gmail.com", "123456", "Test")
    return jsonify({"sent": ok, "email_from": EMAIL_FROM, "has_password": bool(EMAIL_APP_PASSWORD)})

if __name__=='__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
