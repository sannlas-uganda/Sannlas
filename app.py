import os, json, time, hashlib, re, random, string
from flask import Flask, request, jsonify, session, render_template, redirect
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'sannlas_secret_2024')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'SannlasBoss123')
DATABASE_URL = os.environ.get('DATABASE_URL')

def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()
def gen_slug(name): return re.sub(r'[^a-z0-9]+','-',(name or 'shop').lower()).strip('-')[:50] or 'shop'
def make_shop_slug(biz): return gen_slug(biz)
def get_biz_key(biz): return re.sub(r'[^a-z0-9]','',(biz or '').lower())
UPLOAD_COST = 3

def get_conn():
    import psycopg
    return psycopg.connect(DATABASE_URL)

def ensure_tables():
    if not DATABASE_URL: return
    conn = get_conn(); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS kv_store (k TEXT PRIMARY KEY, v TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, data JSONB)")
    cur.execute("CREATE TABLE IF NOT EXISTS shops (id SERIAL PRIMARY KEY, data JSONB)")
    conn.commit(); cur.close(); conn.close()

def load_db(name, default):
    if DATABASE_URL:
        try:
            ensure_tables(); conn=get_conn(); cur=conn.cursor()
            if name=='shops.json': cur.execute("SELECT data FROM shops")
            elif name=='products.json': cur.execute("SELECT data FROM products")
            else:
                cur.execute("SELECT v FROM kv_store WHERE k=%s", (name,))
                row=cur.fetchone()
                if not row: cur.close(); conn.close(); return default
                val=row[0]
                try: data=json.loads(val)
                except: data=default
                cur.close(); conn.close(); return data
            rows=cur.fetchall(); out=[]
            for r in rows:
                d=r[0]
                if isinstance(d,str):
                    try: d=json.loads(d)
                    except: continue
                out.append(d)
            cur.close(); conn.close(); return out
        except Exception as e:
            print("DB load fail", e); return default
    else:
        try:
            if os.path.exists(name):
                with open(name,'r') as f: return json.load(f)
        except: pass
        return default

def save_db(name, data):
    if DATABASE_URL:
        try:
            ensure_tables(); conn=get_conn(); cur=conn.cursor()
            if name in ('shops.json','products.json'):
                cur.execute(f"DELETE FROM {name.split('.')[0]}")
                for item in data:
                    import json as js
                    try:
                        from psycopg.types.json import Jsonb
                        cur.execute(f"INSERT INTO {name.split('.')[0]} (data) VALUES (%s)", [Jsonb(item)])
                    except:
                        cur.execute(f"INSERT INTO {name.split('.')[0]} (data) VALUES (%s)", [js.dumps(item)])
            else:
                cur.execute("INSERT INTO kv_store (k,v) VALUES (%s,%s) ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v", (name, json.dumps(data)))
            conn.commit(); cur.close(); conn.close()
        except Exception as e: print("DB save fail", e)
    else:
        try:
            with open(name,'w') as f: json.dump(data,f)
        except Exception as e: print("File save fail", e)

def get_coin_config():
    cfg=load_db('coin_config.json', None)
    if not cfg:
        cfg={"total":1000000000,"remaining":1000000000,"sold":0,"price":599}
        save_db('coin_config.json', cfg)
    return cfg

def get_billboard_config():
    bb=load_db('billboard.json', None)
    if not bb:
        bb={"active":False,"type":"image","media_url":"","text":"Welcome to Sannlas!","link":""}
        save_db('billboard.json', bb)
    return bb

def ensure_shop_for_user(user):
    shops=load_db('shops.json', [])
    biz=user.get('business') or user.get('email','').split('@')[0]
    slug=make_shop_slug(biz)
    exist=next((s for s in shops if s.get('user_id')==user['id'] or s.get('owner_email','').lower()==user['email'].lower()), None)
    if exist: return exist
    shop={"id":int(time.time()*1000),"user_id":user['id'],"business_name":biz,"name":biz,"business":biz,"shop_slug":slug,"slug":slug,"owner_email":user['email'],"phone":user.get('phone',''),"location":user.get('location','Uganda'),"total_products":0,"product_count":0,"description":f"Welcome to {biz} shop!"}
    shops.append(shop); save_db('shops.json', shops); return shop

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args,**kwargs):
        if not session.get('is_admin'): return jsonify({'error':'Admin login required'}),401
        return f(*args,**kwargs)
    return wrapper

@app.route('/')
def home(): return render_template('index.html')
@app.route('/shop/<slug>')
def shop_page(slug): return render_template('shop.html', shop_slug=slug)
@app.route('/wallet')
def wallet(): return render_template('wallet.html')
@app.route('/balance')
def balance(): return render_template('balance.html')

@app.route('/admin')
def admin():
    if not session.get('is_admin'): return render_template('admin_login.html')
    return render_template('admin.html')

@app.route('/admin/login', methods=['GET'])
def admin_login_page():
    return render_template('admin_login.html')

@app.route('/admin/login', methods=['POST'])
def admin_login():
    data=request.json or {}
    pwd=data.get('password','')
    if pwd==ADMIN_PASSWORD:
        session['is_admin']=True
        return jsonify({'success':True})
    return jsonify({'success':False,'message':'Wrong password'}),401

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin',None)
    return jsonify({'success':True})

@app.route('/api/billboard')
def get_billboard():
    return jsonify(get_billboard_config())

@app.route('/api/admin/billboard', methods=['POST'])
@admin_required
def set_billboard():
    data=request.json
    cfg={"active":bool(data.get('active',False)),"type":data.get('type','image'),"media_url":data.get('media_url',''),"text":data.get('text',''),"link":data.get('link',''),"updated":time.time()}
    save_db('billboard.json', cfg)
    return jsonify({'success':True,'config':cfg})

@app.route('/api/coins/config')
def coins_config():
    return jsonify(get_coin_config())

@app.route('/api/coins/balance')
def coins_balance():
    email=request.args.get('email','').lower()
    phone=request.args.get('phone','')
    users=load_db('users.json', [])
    u=next((x for x in users if x['email']==email or x['phone']==phone), None)
    if not u: return jsonify({'coins':0})
    return jsonify({'coins':u.get('coins',0)})

@app.route('/api/admin/coins/add', methods=['POST'])
@admin_required
def admin_add_coins():
    data=request.json; email=data.get('email','').lower(); phone=data.get('phone',''); coins=int(data.get('coins',0)); reason=data.get('reason','Admin add')
    if coins<=0: return jsonify({'success':False,'message':'Invalid coins'}),400
    users=load_db('users.json', [])
    found=False
    for u in users:
        if (email and u['email']==email) or (phone and u['phone']==phone):
            u['coins']=u.get('coins',0)+coins; found=True
    if not found: return jsonify({'success':False,'message':'User not found'}),404
    save_db('users.json', users)
    txs=load_db('coin_transactions.json', [])
    txs.append({'email':email,'phone':phone,'coins':coins,'price':0,'type':'admin_add','reason':reason,'time':time.time()})
    save_db('coin_transactions.json', txs)
    return jsonify({'success':True,'message':f'Added {coins} coins to {email or phone}'})

@app.route('/api/withdraw/request', methods=['POST'])
def withdraw_request():
    data=request.json; email=data.get('email','').lower(); phone=data.get('phone',''); amount=int(data.get('amount',0)); momo=data.get('momo_number',''); mname=data.get('momo_name','')
    if amount<10000: return jsonify({'success':False,'message':'Min 10,000 UGX'}),400
    withdraws=load_db('withdraws.json', [])
    wd={'id':int(time.time()*1000),'email':email,'phone':phone,'amount':amount,'momo_number':momo,'momo_name':mname,'status':'pending','time':time.time()}
    withdraws.append(wd); save_db('withdraws.json', withdraws)
    return jsonify({'success':True,'message':'Withdraw request sent to Admin - 0795712326','withdraw':wd})

@app.route('/api/withdraw/my')
def my_withdraws():
    email=request.args.get('email','').lower()
    withdraws=load_db('withdraws.json', [])
    mine=[w for w in withdraws if w['email']==email]
    return jsonify({'withdraws':mine})

@app.route('/api/admin/withdraw/action', methods=['POST'])
@admin_required
def withdraw_action():
    data=request.json; wid=data.get('id'); action=data.get('action')
    withdraws=load_db('withdraws.json', [])
    for w in withdraws:
        if w['id']==wid:
            w['status']=action; w['action_time']=time.time()
    save_db('withdraws.json', withdraws)
    return jsonify({'success':True})
@app.route('/api/register', methods=['POST'])
def register():
    data=request.json; email=data.get('email','').lower().strip(); phone=data.get('phone','').strip(); pwd=data.get('password',''); biz=data.get('business','')
    if not email or not phone or not pwd: return jsonify({'success':False,'message':'Fill all'}),400
    users=load_db('users.json',[])
    if any(u['email']==email for u in users): return jsonify({'success':False,'message':'Email exists - Login'}),400
    user={'id':int(time.time()*1000),'email':email,'phone':phone,'password':hash_pwd(pwd),'business':biz,'created':time.time(),'plan':'free14','plan_name':'14 Days FREE','subscription_expires':time.time()+14*86400,'paid':True,'verified':False,'followers':0,'total_likes':0,'total_stars':0,'coins':5}
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
    return jsonify({'success':True,'fixed_products':fixed,'total_shops':len(shops_map),'message':'Slugs fixed!'})

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
        coin_config=get_coin_config()
        coin_rev = sum(t.get('price',0) for t in coin_transactions if t.get('status')!='blocked_fake')
        return jsonify({'products':products,'users':users,'orders':orders,'contacts':contacts,'coin_transactions':coin_transactions,'shops':shops,'withdraws':withdraws,'billboard':billboard,'coin_config':coin_config,'coin_revenue':coin_rev,'total_revenue':0,'total_sellers':len(users),'total_orders':len(orders)})
    except Exception as e:
        print("ADMIN DATA ERROR:", e)
        return jsonify({'products':[],'users':[],'orders':[],'contacts':[],'coin_transactions':[],'shops':[],'withdraws':[],'billboard':{},'coin_config':{"total":1000000000,"remaining":1000000000,"sold":0,"price":599},"coin_revenue":0,'total_revenue':0,'total_sellers':0,'total_orders':0,'error': str(e)}), 200

@app.route('/api/admin/transactions')
@admin_required
def admin_transactions(): return jsonify(load_db('transactions.json', []) or [])

@app.route('/api/orders')
def get_orders(): return jsonify(load_db('orders.json', [])[::-1])

@app.route('/api/contact', methods=['POST'])
def contact_owner():
    data=request.json; contacts=load_db('contacts.json', []); contacts.append({**data,'time':time.time(),'id':int(time.time())}); save_db('contacts.json', contacts); return jsonify({'success':True})

@app.route('/api/coins/verify', methods=['POST'])
@admin_required
def verify_coin():
    data=request.json; code=data.get('momo_code'); action=data.get('action')
    txs=load_db('coin_transactions.json', [])
    for t in txs:
        if t.get('momo_code')==code:
            t['status']='verified' if action=='verify' else 'blocked_fake'
    save_db('coin_transactions.json', txs)
    return jsonify({'success':True})

@app.route('/api/admin/activate-subscription', methods=['POST'])
@admin_required
def activate_sub():
    data=request.json; phone=data.get('phone'); email=data.get('email','').lower(); plan=data.get('plan','30')
    days={'30':30,'60':60,'180':180,'365':365}.get(plan,30)
    users=load_db('users.json', [])
    for u in users:
        if u['phone']==phone or u['email']==email:
            u['paid']=True
            u['plan']=plan
            u['subscription_expires']=time.time()+days*86400
    save_db('users.json', users)
    return jsonify({'success':True})

@app.route('/api/admin/send-message', methods=['POST'])
@admin_required
def send_msg():
    data=request.json; notifs=load_db('notifications.json', [])
    notifs.append({**data,'time':time.time(),'id':int(time.time())})
    save_db('notifications.json', notifs)
    return jsonify({'success':True,'message':'Sent'})

@app.route('/api/admin/notifications')
@admin_required
def get_notifs():
    return jsonify(load_db('notifications.json', []) or [])

@app.route('/api/seller/sales')
def seller_sales():
    phone=request.args.get('phone',''); email=request.args.get('email','').lower(); period=request.args.get('period','all')
    orders=load_db('orders.json', []) or []
    my=[]
    for o in orders:
        items=o.get('items',[]) or []
        for it in items:
            if (phone and it.get('phone')==phone) or (email and (it.get('seller_email','').lower()==email)):
                my.append(o); break
    total=sum(o.get('total',0) for o in my)
    return jsonify({'total_sales':total,'total_orders':len(my),'orders':my,'period':period})

if __name__=='__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)
