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
        cfg = {"active": False, "type": "image", "media_url": "", "text": "Welcome to Sannlas", "link": "", "created": time.time(), "expires_at": None}
        save_db('billboard.json', cfg)
        return cfg
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
    shop = {"id": int(time.time()*1000),"user_id": user.get('id'),"business_name": biz,"name": biz,"shop_slug": slug,"slug": slug,"phone": user.get('phone',''),"owner_email": email,"location": "Kampala","description": "Welcome to " + biz + " shop!","verified": False,"total_products": 0,"created_at": time.time()}
    shops.append(shop)
    save_db('shops.json', shops)
    return shop
    @app.route('/product/<pid>')
def product_link(pid):
    ref = request.args.get('ref','')
    resp = make_response(render_template('index.html'))
    if ref:
        resp.set_cookie('ref_code', ref, max_age=30*24*60*60, httponly=False, samesite='Lax')
    return resp

@app.route('/')
def home():
    ref = request.args.get('ref')
    resp = make_response(render_template('index.html'))
    if ref:
        resp.set_cookie('ref_code', ref, max_age=30*24*60*60, httponly=False, samesite='Lax')
    return resp

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
    return jsonify({'success': False, 'message': 'Wrong admin password'}), 401

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

@app.route('/api/coins/config')
def coins_config(): return jsonify(get_coin_config())

@app.route('/api/coins/balance')
def coins_balance():
    email=request.args.get('email','').lower().strip()
    phone=request.args.get('phone','').strip()
    users=load_db('users.json',[])
    u=next((x for x in users if str(x.get('email','')).lower()==email or str(x.get('phone',''))==phone), None)
    if not u:
        return jsonify({'success':True,'coins':0,'total':0,'bought':0,'earned':0,'spent':0,'withdrawable':0})
    bought = int(u.get('bought', 0))
    earned = int(u.get('earned', 0))
    spent = int(u.get('spent', 0))
    total = bought + earned - spent
    if total<0: total=0
    withdrawable = total - FREE_TRIAL
    if withdrawable<0: withdrawable=0
    return jsonify({'success':True,'coins': total,'total': total,'bought': bought,'earned': earned,'spent': spent,'withdrawable': withdrawable,'withdrawable_value': withdrawable * COIN_PRICE})

# ===== FIXED LOGIN - THIS WAS BROKEN =====
@app.route('/api/login', methods=['POST'])
def login():
    data=request.json or {}
    email=data.get('email','').lower().strip()
    pwd=data.get('password','') or ''
    users=load_db('users.json',[])

    def check_pwd(u, pwd_try):
        if u.get('password') == hash_pwd(pwd_try):
            return True
        try:
            from werkzeug.security import check_password_hash
            if u.get('password_hash') and check_password_hash(u.get('password_hash'), pwd_try):
                return True
        except:
            pass
        return False

    u=next((x for x in users if x['email'].lower()==email and check_pwd(x,pwd)), None)
    if not u:
        return jsonify({'success':False,'message':'Wrong email/password'}),401
    if 'bought' not in u: u['bought'] = int(u.get('bought_coins',0))
    if 'earned' not in u: u['earned'] = int(u.get('earned_coins',0))
    if 'spent' not in u: u['spent'] = 0
    u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
    if u['coins']<0: u['coins']=0
    save_db('users.json', users)
    try: ensure_shop_for_user(u)
    except: pass
    safe={k:v for k,v in u.items() if k!='password'}
    safe['subscription_active']=safe.get('subscription_expires',0)>time.time()
    session['phone']=u.get('phone')
    session['email']=u.get('email')
    return jsonify({'success':True,'user':safe})

@app.route('/api/register', methods=['POST'])
def register():
    data=request.json; email=data.get('email','').lower().strip(); phone=data.get('phone','').strip(); pwd=data.get('password',''); biz=data.get('business','')
    ref_code = data.get('ref') or request.args.get('ref') or request.cookies.get('ref_code') or ''
    if not email or not phone or not pwd: return jsonify({'success':False,'message':'Fill all'}),400
    users=load_db('users.json',[])
    if any(u['email']==email for u in users): return jsonify({'success':False,'message':'Email exists'}),400
    my_ref_code = f"SANN-{phone[-4:]}-{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))}"
    user={'id':int(time.time()*1000),'email':email,'phone':phone,'password':hash_pwd(pwd),'business':biz,'created':time.time(),'coins':10,'bought':0,'earned':10,'spent':0,'referral_code':my_ref_code,'invited_by':ref_code}
    users.append(user)
    if ref_code:
        for ru in users:
            if ru.get('referral_code')==ref_code:
                ru['earned'] = int(ru.get('earned',0)) + 1
                ru['coins'] = int(ru.get('bought',0)) + int(ru.get('earned',0)) - int(ru.get('spent',0))
                break
    save_db('users.json',users)
    safe={k:v for k,v in user.items() if k!='password'}
    return jsonify({'success':True,'user':safe})

@app.route('/api/products')
def get_products():
    q = request.args.get('q','').lower()
    products=load_db('products.json', [])
    filtered=products
    if q: filtered=[p for p in filtered if q in p.get('name','').lower()]
    filtered=sorted(filtered,key=lambda x:x.get('created',0),reverse=True)
    return jsonify(filtered)

@app.route('/api/sell', methods=['POST'])
def sell():
    name=request.form.get('name')
    price=int(request.form.get('price',0))
    original_price = int(request.form.get('original_price') or price)
    business=request.form.get('business')
    location=request.form.get('location')
    phone=request.form.get('phone')
    desc=request.form.get('desc','')
    promo_commission = int(request.form.get('promo_commission','3'))
    user_email=request.form.get('user_email','').lower()
    users=load_db('users.json',[]); seller=next((u for u in users if u['phone']==phone or u['email']==user_email),None)
    if not seller: return jsonify({'success':False,'message':'Register first'}),402
    if int(seller.get('coins',0)) < UPLOAD_COST: return jsonify({'success':False,'message':f'Need {UPLOAD_COST} coins!'}),402
    images=[]
    for key in request.files:
        f=request.files[key]
        if f and f.filename:
            import base64; file_bytes=f.read(); mime=f.mimetype or 'image/jpeg'; b64=base64.b64encode(file_bytes).decode('utf-8'); images.append(f"data:{mime};base64,{b64}")
    if not images: images=['https://via.placeholder.com/300']
    shop = ensure_shop_for_user(seller)
    prod = {'id': int(time.time()*1000),'name': name,'price': price,'original_price': original_price,'business': business,'location': location,'phone': phone,'seller_email': user_email,'description': desc,'image': images[0],'images': images,'stock': 10,'created': time.time(),'shop_slug': shop.get('shop_slug'),'promo_commission': promo_commission}
    products=load_db('products.json',[]); products.append(prod); save_db('products.json', products)
    for u in users:
        if u['phone']==phone or u['email']==user_email:
            u['spent'] = int(u.get('spent',0)) + UPLOAD_COST
            u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
    save_db('users.json', users)
    return jsonify({'success':True,'message':'Added!'})

@app.route('/api/shops')
def list_shops():
    shops = load_db('shops.json', [])
    products = load_db('products.json', [])
    counts = {}
    for p in products:
        slug = p.get('shop_slug')
        if slug: counts[slug] = counts.get(slug, 0) + 1
    for s in shops:
        s['total_products'] = counts.get(s.get('shop_slug'), 0)
    filtered = [s for s in shops if s.get('total_products',0)>0]
    return jsonify(sorted(filtered, key=lambda x: x.get('total_products',0), reverse=True))

# ===== CHECKOUT WITH REF COMMISSION - NEW =====
@app.route('/api/checkout', methods=['POST'])
def api_checkout():
    data = request.get_json() or {}
    ref = data.get('ref') or request.args.get('ref') or request.cookies.get('ref_code') or ''
    phone = data.get('phone','').strip()
    email = (data.get('email') or '').lower().strip()
    cart = data.get('cart', [])
    promo_commission = int(data.get('promo_commission', 3))
    product_id = data.get('product_id') or (cart[0].get('id') if cart else None)
    total = sum(int(i.get('price',0)) * int(i.get('qty',1)) for i in cart)
    orders = load_db('orders.json', [])
    new_order = {'id': int(time.time()*1000),'product_id': product_id,'cart': cart,'total': total,'buyer_phone': phone,'buyer_email': email,'ref': ref,'time': time.time(),'status': 'pending'}
    orders.append(new_order)
    save_db('orders.json', orders)
    if ref:
        try:
            users = load_db('users.json', [])
            for usr in users:
                if str(usr.get('phone'))==str(ref) or str(usr.get('email','')).lower()==str(ref).lower() or str(usr.get('referral_code'))==str(ref):
                    usr['earned'] = int(usr.get('earned',0)) + promo_commission
                    usr['coins'] = int(usr.get('bought',0)) + int(usr.get('earned',0)) - int(usr.get('spent',0))
                    break
            save_db('users.json', users)
        except Exception as e:
            print(e)
    return jsonify({'success':True,'message':f'✅ Order placed! Total UGX {total:,}','order':new_order})

@app.route('/api/admin/data')
@admin_required
def admin_data():
    return jsonify({'products':load_db('products.json',[]),'users':load_db('users.json',[]),'orders':load_db('orders.json',[])})

if __name__=='__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
