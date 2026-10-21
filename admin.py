from flask import Blueprint, request, jsonify, render_template, session, redirect, make_response, send_from_directory, Response
import json, time, hashlib, uuid, random, re, base64, math
from functools import wraps
from werkzeug.utils import secure_filename
import os

admin_bp = Blueprint('admin_bp', __name__)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'SannlasBoss123')
KASSAG_ADMIN_PASSWORD = os.environ.get('KASSAG_ADMIN_PASSWORD', 'KASSAG2024')
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

COIN_PRICE = 599
FREE_TRIAL = 10
PRODUCTS_CACHE = {"data": None, "time": 0}

def get_conn():
    if not DATABASE_URL:
        raise Exception("No DATABASE_URL")
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except Exception:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def ensure_tables():
    if not DATABASE_URL: return
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, data JSONB NOT NULL);")
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, data JSONB NOT NULL);")
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print("ensure_tables:", e)

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
        return default
    path=f'data/{file}'
    import os as _os
    if _os.path.exists(path):
        try: return json.load(open(path))
        except: return default
    return default

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
        cfg = {"total": 1000000000, "remaining": 1000000000, "sold": 0, "price": 599, "upload_cost": 0}
        save_db('coin_config.json', cfg)
    cfg['upload_cost'] = 0
    return cfg
def save_coin_config(cfg): save_db('coin_config.json', cfg)
def get_billboard_config():
    cfg = load_db('billboard.json', None)
    if not cfg:
        cfg = {"active": False, "type": "image", "media_url": "", "text": "Welcome to Sannlas", "link": "", "created": time.time(), "expires_at": None}
        save_db('billboard.json', cfg)
        return cfg
    return cfg
def get_hero_stories(): return load_db('hero_stories.json', [])
def save_hero_stories(s): save_db('hero_stories.json', s)
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('is_admin'):
            return f(*args, **kwargs)
        if request.path.startswith('/api/admin'):
            return jsonify({'success': False, 'message': 'Admin login required'}), 401
        return redirect('/admin/login')
    return decorated
def kassag_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('is_admin') or session.get('is_kassag_admin'):
            return f(*args, **kwargs)
        if request.path.startswith('/api/kassag'):
            return jsonify({'success': False, 'message': 'KASSAG admin login required'}), 401
        return redirect('/kassag/admin/login')
    return decorated

KASSAG_INFO_FILE = 'kassag_info.json'
KASSAG_MEMBERS_FILE = 'kassag_members.json'
KASSAG_PAYMENTS_FILE = 'kassag_payments.json'
def get_kassag_info():
    info = load_db(KASSAG_INFO_FILE, None)
    if not info:
        info = {"name": "KASSAG", "logo": "", "goals": "To save together", "vision": "Financial freedom", "mission": "Weekly savings", "terms": "Pay weekly", "privacy": "Private group", "max_members": 50}
        save_db(KASSAG_INFO_FILE, info)
    return info
def get_kassag_members(): return load_db(KASSAG_MEMBERS_FILE, [])
def save_kassag_members(m): save_db(KASSAG_MEMBERS_FILE, m)
def get_kassag_payments(): return load_db(KASSAG_PAYMENTS_FILE, [])
def save_kassag_payments(p): save_db(KASSAG_PAYMENTS_FILE, p)
def get_kassag_expenditures():
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS kassag_expenditures (id BIGSERIAL PRIMARY KEY, title TEXT, amount NUMERIC, reason TEXT, date TEXT, created TIMESTAMP DEFAULT NOW())")
        conn.commit()
        cur.execute("SELECT id, title, amount, reason, date, created FROM kassag_expenditures ORDER BY created DESC")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return [{"id": r[0], "title": r[1], "amount": float(r[2] or 0), "reason": r[3], "date": r[4], "created": str(r[5])} for r in rows]
    except Exception as e:
        print("GET EXPEND ERROR:", e)
        return []

@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template('admin_login.html') if os.path.exists('templates/admin_login.html') else """<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{background:#0f0f0f;display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:Arial;color:white}.box{background:#1e1e1e;padding:30px;border-radius:20px;width:350px;text-align:center;border:1px solid #ff0000}input{width:90%;padding:14px;border:none;border-radius:12px;margin:10px 0;background:#2a2a2a;color:white}button{width:95%;padding:14px;background:#ff0000;border:none;border-radius:12px;font-weight:900;cursor:pointer;color:white}</style></head><body><div class="box"><h2>SANNLAS ADMIN</h2><form method="POST"><input type="password" name="password" placeholder="Password" required><button type="submit">Unlock</button></form></div></body></html>"""
    pwd = request.json.get('password','') if request.is_json else request.form.get('password','')
    if pwd == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({'success': True}) if request.is_json else redirect('/admin')
    return (jsonify({'success': False, 'message': 'Wrong password'}), 401) if request.is_json else '<h3 style="text-align:center;margin-top:100px;color:red">Wrong! <a href="/admin/login">Retry</a></h3>'

@admin_bp.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect('/admin/login')

@admin_bp.route('/admin')
@admin_required
def admin_page():
    return render_template('admin.html')

@admin_bp.route('/admin/chats')
@admin_required
def admin_chats():
    try:
        return render_template('admin_chats.html')
    except:
        return redirect('/admin')

@admin_bp.route('/api/admin/billboard', methods=['GET'])
@admin_required
def admin_get_billboard():
    return jsonify(get_billboard_config())

@admin_bp.route('/api/admin/billboard', methods=['POST'])
@admin_required
def admin_set_billboard():
    data = request.json or {}
    cfg = get_billboard_config()
    cfg['active'] = data.get('active', False)
    cfg['text'] = data.get('text', cfg.get('text',''))
    cfg['link'] = data.get('link', cfg.get('link',''))
    if 'media_url' in data: cfg['media_url'] = data['media_url']
    if 'type' in data: cfg['type'] = data['type']
    cfg['expires_at'] = data.get('expires_at')
    save_db('billboard.json', cfg)
    return jsonify({'success': True, 'config': cfg})

@admin_bp.route('/api/upload/billboard', methods=['POST'])
@admin_required
def upload_billboard():
    try:
        import cloudinary.uploader
        file = request.files.get('file')
        if not file: return jsonify({'success': False, 'error': 'No file'}), 400
        res = cloudinary.uploader.upload(file, folder="sannlas/billboard", resource_type="auto")
        url = res['secure_url']
        text = request.form.get('text','')
        link = request.form.get('link','')
        duration = request.form.get('duration','24')
        cfg = get_billboard_config()
        cfg['active'] = True
        cfg['media_url'] = url
        cfg['text'] = text
        cfg['link'] = link
        cfg['type'] = 'video' if res.get('resource_type')=='video' else 'image'
        if duration != '0':
            from datetime import datetime, timedelta
            cfg['expires_at'] = (datetime.now() + timedelta(hours=int(duration))).isoformat()
        else:
            cfg['expires_at'] = None
        save_db('billboard.json', cfg)
        return jsonify({'success': True, 'url': url, 'config': cfg})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/admin/billboard/animated', methods=['POST'])
@admin_required
def admin_animated_billboard():
    data = request.json or {}
    cfg = get_billboard_config()
    cfg['active'] = True
    cfg['type'] = 'animated'
    cfg['text'] = data.get('text','Welcome')
    save_db('billboard.json', cfg)
    return jsonify({'success': True})

@admin_bp.route('/api/admin/hero-stories', methods=['GET'])
@admin_required
def admin_get_hero():
    return jsonify(get_hero_stories())

@admin_bp.route('/api/admin/hero-stories', methods=['POST'])
@admin_required
def admin_add_hero():
    try:
        import cloudinary.uploader
        file = request.files.get('image')
        if not file: return jsonify({'success': False, 'message': 'No image'}), 400
        res = cloudinary.uploader.upload(file, folder="sannlas/hero")
        url = res['secure_url']
        stories = get_hero_stories()
        new_story = {"id": int(time.time()*1000), "image": url, "title_en": request.form.get('title_en',''), "subtitle_en": request.form.get('subtitle_en',''), "order": len(stories), "created": time.time()}
        stories.append(new_story)
        save_hero_stories(stories)
        return jsonify({'success': True, 'story': new_story})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/api/admin/hero-stories/<int:sid>', methods=['DELETE'])
@admin_required
def admin_del_hero(sid):
    stories = get_hero_stories()
    stories = [s for s in stories if s.get('id') != sid]
    save_hero_stories(stories)
    return jsonify({'success': True})

@admin_bp.route('/api/admin/shop/verify', methods=['POST'])
@admin_required
def admin_verify_shop():
    data = request.json or {}
    slug = data.get('shop_slug','').lower().strip()
    action = data.get('action','verify')
    shops = load_db('shops.json', [])
    for s in shops:
        if str(s.get('shop_slug','')).lower() == slug or str(s.get('business_name','')).lower() == slug:
            s['verified'] = True if action=='verify' else False
            s['is_verified'] = s['verified']
            save_db('shops.json', shops)
            return jsonify({'success': True, 'shop': s})
    return jsonify({'success': False, 'message': 'Shop not found'}), 404

@admin_bp.route('/api/admin/delete_shop/<slug>', methods=['DELETE', 'POST'])
@admin_required
def admin_delete_shop(slug):
    try:
        slug = slug.lower().strip()
        shops = load_db('shops.json', [])
        products = load_db('products.json', [])
        if not shops:
            return jsonify({"success": False, "message": "No shops found"}), 404
        target = None
        for s in shops:
            if str(s.get('shop_slug','')).lower() == slug or str(s.get('slug','')).lower() == slug:
                target = s; break
            if str(s.get('business_name','')).lower() == slug or str(s.get('name','')).lower() == slug:
                target = s; break
        if not target:
            for s in shops:
                if slug in str(s.get('shop_slug','')).lower() or slug in str(s.get('business_name','')).lower():
                    target = s; break
        if not target:
            return jsonify({"success": False, "message": f"Shop '{slug}' not found"}), 404
        real_slug = str(target.get('shop_slug') or target.get('slug') or slug).lower()
        owner_email = str(target.get('owner_email','')).lower()
        biz_name = str(target.get('business_name') or target.get('name','')).lower()
        before = len(products)
        new_products = []
        for p in products:
            ps = str(p.get('shop_slug','')).lower()
            pb = str(p.get('business','')).lower()
            pe = str(p.get('seller_email','')).lower()
            if ps == real_slug or pb == biz_name or (owner_email and pe == owner_email):
                continue
            if real_slug in ps and ps != "":
                continue
            new_products.append(p)
        deleted_count = before - len(new_products)
        save_db('products.json', new_products)
        new_shops = [s for s in shops if s != target]
        save_db('shops.json', new_shops)
        global PRODUCTS_CACHE
        PRODUCTS_CACHE["data"] = None
        return jsonify({"success": True, "message": f"Deleted shop '{real_slug}' + {deleted_count} products!"})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@admin_bp.route('/api/admin/coins/add', methods=['POST'])
@admin_required
def admin_add_coins():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    coins = int(data.get('coins',0))
    reason = data.get('reason','Admin refill')
    if coins <=0: return jsonify({'success':False,'message':'Enter coins'}),400
    users = load_db('users.json', [])
    found=False
    for u in users:
        if (email and u.get('email','').lower()==email) or (phone and u.get('phone','')==phone):
            u['earned'] = int(u.get('earned',0)) + coins
            u['earned_coins'] = u['earned']
            u['coins'] = int(u.get('bought',0)) + int(u.get('earned',0)) - int(u.get('spent',0))
            found=True
            break
    if not found: return jsonify({'success':False,'message':'User not found'}),404
    save_db('users.json', users)
    txs = load_db('coin_transactions.json', [])
    txs.append({'id': int(time.time()*1000), 'email': email, 'phone': phone, 'coins': coins, 'price': 0, 'momo_code': f'ADMIN-{uuid.uuid4().hex[:4].upper()}', 'reason': reason, 'time': time.time(), 'status': 'admin_add'})
    save_db('coin_transactions.json', txs)
    return jsonify({'success':True,'message':f'Added {coins} coins to {email or phone}'})

@admin_bp.route('/api/admin/coins/config', methods=['GET'])
@admin_required
def admin_coins_config_get():
    return jsonify(get_coin_config())

@admin_bp.route('/api/admin/coins/config', methods=['POST'])
@admin_required
def admin_coins_config_post():
    data = request.json or {}
    cfg = get_coin_config()
    for k in ['total','remaining','sold','price','upload_cost','share_profit_coins','share_profit_ugx']:
        if k in data: cfg[k]=data[k]
    save_coin_config(cfg)
    return jsonify({'success':True,'config':cfg})

@admin_bp.route('/api/admin/coins/major/add', methods=['POST'])
@admin_required
def add_major_coins():
    data=request.json
    amount=int(data.get('amount',0))
    action=data.get('type','add')
    if amount <=0:
        return jsonify({'success':False,'message':'Enter amount'})
    cfg=get_coin_config()
    if action == 'remove':
        cfg['total'] = max(0, cfg.get('total',1000000000) - amount)
        cfg['remaining'] = max(0, cfg.get('remaining',1000000000) - amount)
    else:
        cfg['total'] = cfg.get('total',1000000000) + amount
        cfg['remaining'] = cfg.get('remaining',1000000000) + amount
    save_coin_config(cfg)
    return jsonify({'success':True,'message':f'{action} {amount} done','config':cfg})

@admin_bp.route('/api/coins/verify', methods=['POST'])
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
            coins_bought = int(target_tx.get('coins',0))
            cfg['remaining'] = max(0, cfg.get('remaining',1000000000) - coins_bought)
            cfg['sold'] = cfg.get('sold',0) + coins_bought
    save_db('coin_transactions.json', txs); save_db('users.json', users); save_coin_config(cfg)
    return jsonify({'success':True, 'action': action})

@admin_bp.route('/api/admin/withdraws', methods=['GET'])
@admin_required
def admin_withdraws():
    return jsonify(load_db('withdraws.json', []))

@admin_bp.route('/api/admin/withdraw/action', methods=['POST'])
@admin_required
def admin_withdraw_action():
    data=request.json or {}; wid=int(data.get('id',0)); action=data.get('action','paid')
    withdraws=load_db('withdraws.json', [])
    for w in withdraws:
        if int(w.get('id',0))==wid:
            w['status']=action
            if action=='paid': w['paid_time']=time.time()
            break
    save_db('withdraws.json', withdraws)
    return jsonify({'success':True})

@admin_bp.route('/api/admin/data')
@admin_required
def admin_data():
    try:
        products_full = load_db('products.json', []) or []
        users_full = load_db('users.json', []) or []
        shops_full = load_db('shops.json', []) or []
        orders_full = load_db('orders.json', []) or []
        coins_full = load_db('coin_transactions.json', []) or []
        billboard = load_db('billboard.json', {}) or {}
        contacts_full = load_db('contacts.json', []) or []
        withdraws_full = load_db('withdraws.json', []) or []
        wants_full = load_db('wants.json', []) or []
        shares_full = load_db('share_transactions.json', []) or []
        coin_cfg = load_db('coin_config.json', {}) or {}
        for s in shops_full: s['total_products'] = sum(1 for p in products_full if p.get('shop_slug','')==s.get('shop_slug',''))
        safe_products = []
        for p in products_full[-50:][::-1]:
            np = dict(p)
            if 'images' in np: del np['images']
            if 'image' in np and len(str(np.get('image',''))) > 700:
                if not str(np['image']).startswith('http'):
                    np['image'] = ""
            safe_products.append(np)
        if billboard.get('media_url','') and len(str(billboard.get('media_url','')))>1500:
            billboard['media_url']=""
            billboard['active']=False
        return jsonify({
            'products': safe_products,
            'products_count': len(products_full),
            'users': users_full[-100:],
            'users_count': len(users_full),
            'shops': shops_full,
            'shops_count': len(shops_full),
            'orders': orders_full[-50:],
            'orders_count': len(orders_full),
            'billboard': billboard,
            'contacts': contacts_full[-50:],
            'contacts_count': len(contacts_full),
            'coin_transactions': coins_full[-100:],
            'coin_transactions_count': len(coins_full),
            'coin_config': coin_cfg,
            'withdraws': withdraws_full[-50:],
            'withdraws_count': len(withdraws_full),
            'wants': wants_full[-50:],
            'wants_count': len(wants_full),
            'shares': shares_full[-100:][::-1],
            'shares_count': len(shares_full),
            'share_profit_coins': coin_cfg.get('share_profit_coins',0),
            'share_profit_ugx': coin_cfg.get('share_profit_ugx',0),
            'chat_unlocks': []
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'products':[],'users':[],'shops':[],'error':str(e)})

@admin_bp.route('/api/admin/transactions')
@admin_required
def admin_transactions(): return jsonify(load_db('transactions.json', []) or [])

@admin_bp.route('/api/admin/data-fixed')
@admin_required
def admin_data_fixed():
    try:
        products=load_db('products.json',[]) or []
        users=load_db('users.json',[]) or []
        shops=load_db('shops.json',[]) or []
        products_trim = []
        for p in products[-20:][::-1]:
            pp = {k: str(v)[:200] if isinstance(v,str) and len(str(v))>200 else v for k,v in p.items()}
            pp.pop('images',None)
            products_trim.append(pp)
        return jsonify({'products': products_trim, 'users': users[-20:], 'shops': shops, 'total': len(products)})
    except Exception as e:
        return jsonify({'products':[],'users':[],'shops':[],'error': str(e)})

@admin_bp.route('/kassag/admin/login', methods=['GET','POST'])
def kassag_admin_login():
    if request.method == 'GET':
        return """<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{background:#f8fafc;display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:Arial}.box{background:white;padding:30px;border-radius:20px;box-shadow:0 4px 20px rgba(0,0,0,0.1);width:350px;text-align:center;border:2px solid #FFCC02}input{width:90%;padding:14px;border:1px solid #ddd;border-radius:12px;margin:10px 0}button{width:95%;padding:14px;background:#FFCC02;border:2px solid #000;border-radius:12px;font-weight:900;cursor:pointer}</style></head><body><div class="box"><h2>🏦 KASSAG ADMIN</h2><p style="color:#666;font-size:13px">Private - Treasurer Only</p><form method="POST"><input type="password" name="password" placeholder="KASSAG Password" required><button type="submit">Unlock KASSAG 👑</button></form><p style="margin-top:15px;font-size:12px"><a href="/kassag" style="color:#666">← Back to Group</a></p></div></body></html>"""
    pwd = request.form.get('password','')
    if pwd == KASSAG_ADMIN_PASSWORD or pwd == ADMIN_PASSWORD:
        session['is_kassag_admin'] = True
        return redirect('/kassag/admin')
    return '<h3 style="text-align:center;margin-top:100px">❌ Wrong Password! <a href="/kassag/admin/login">Retry</a></h3>'

@admin_bp.route('/kassag/admin/logout')
def kassag_admin_logout():
    session.pop('is_kassag_admin', None)
    return redirect('/kassag/admin/login')

@admin_bp.route('/kassag/admin')
@kassag_admin_required
def kassag_admin_page():
    return render_template('kassag_admin.html')

@admin_bp.route('/api/kassag/admin/members')
@kassag_admin_required
def kassag_admin_members():
    return jsonify(get_kassag_members())

@admin_bp.route('/api/kassag/admin/payments')
@kassag_admin_required
def kassag_admin_payments():
    return jsonify(get_kassag_payments())

@admin_bp.route('/api/kassag/admin/action/member', methods=['POST'])
@kassag_admin_required
def kassag_member_action():
    data = request.get_json() or {}
    mid = int(data.get('id',0))
    action = data.get('action','approve')
    members = get_kassag_members()
    for m in members:
        if m['id']==mid:
            if action=='approve': m['status']='Active'
            elif action=='reject': m['status']='Rejected'
            elif action=='remove': members = [x for x in members if x['id']!=mid]
            elif action=='make_admin':
                m['is_admin']= not m.get('is_admin',False)
                m['role']='Treasurer' if m.get('is_admin') else 'Member'
            elif action=='edit_role': m['role']=data.get('role','Member')
            break
    save_kassag_members(members)
    return jsonify({'success':True})

@admin_bp.route('/api/kassag/admin/action/payment', methods=['POST'])
@kassag_admin_required
def kassag_payment_action():
    data = request.get_json() or {}
    pid = int(data.get('id',0))
    action = data.get('action','approve')
    payments = get_kassag_payments()
    for p in payments:
        if p['id']==pid:
            p['status']='Approved' if action=='approve' else 'Rejected'
            break
    save_kassag_payments(payments)
    return jsonify({'success':True})

@admin_bp.route('/api/kassag/admin/info', methods=['GET','POST'])
@kassag_admin_required
def kassag_admin_info():
    if request.method=='GET':
        return jsonify(get_kassag_info())
    data = request.get_json() or {}
    info = get_kassag_info()
    for k in ['name','goals','vision','mission','terms','privacy','max_members','logo']:
        if k in data: info[k]=data[k]
    save_db(KASSAG_INFO_FILE, info)
    return jsonify({'success':True,'info':info})

@admin_bp.route('/api/kassag/admin/export/members')
@kassag_admin_required
def kassag_export_members():
    import csv, io
    members = get_kassag_members()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Name','Phone','Role','Status','Is Admin','Join Date'])
    for m in members:
        writer.writerow([m.get('id'), m.get('name'), m.get('phone'), m.get('role'), m.get('status'), m.get('is_admin'), m.get('join_date')])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition":"attachment;filename=kassag_members.csv"})

@admin_bp.route('/api/kassag/admin/export/payments')
@kassag_admin_required
def kassag_export_payments():
    import csv, io
    pays = get_kassag_payments()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Member Name','Phone','Week','Amount','Status','Date','Screenshot'])
    for p in pays:
        writer.writerow([p.get('id'), p.get('member_name'), p.get('member_phone'), p.get('week'), p.get('amount'), p.get('status'), p.get('date'), p.get('screenshot')])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv', headers={"Content-Disposition":"attachment;filename=kassag_payments.csv"})

@admin_bp.route('/api/kassag/expenditure/add', methods=['POST'])
@kassag_admin_required
def add_expenditure():
    try:
        data = request.get_json() or {}
        import psycopg2, datetime
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("INSERT INTO kassag_expenditures (title, amount, reason, date, created) VALUES (%s,%s,%s,%s,%s)",
                    (data.get('title',''), float(data.get('amount',0)), data.get('reason',''), data.get('date',''), datetime.datetime.utcnow()))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True, 'message':'Saved to Neon permanently'})
    except Exception as e:
        print("ADD EXPEND ERROR:", e)
        return jsonify({'success':False, 'message': str(e)}), 500

@admin_bp.route('/api/kassag/expenditure/list')
@kassag_admin_required
def list_expenditure():
    return jsonify(get_kassag_expenditures())

@admin_bp.route('/api/kassag/expenditure/delete/<int:exp_id>', methods=['DELETE'])
@kassag_admin_required
def delete_expenditure(exp_id):
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("DELETE FROM kassag_expenditures WHERE id=%s", (exp_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False, 'message': str(e)}), 500
