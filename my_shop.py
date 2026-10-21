from flask import Blueprint, request, jsonify, render_template
import os, json, time, re

my_shop_bp = Blueprint('my_shop', __name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL:
        raise Exception("No DATABASE_URL")
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except:
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
        else:
            path=f'data/{file}'
            if os.path.exists(path):
                try: return json.load(open(path))
                except: return default
            return default
    except: return default

def save_db(file, data):
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
        except Exception as e: print("SAVE ERROR:", e)
    json.dump(data, open(f'data/{file}','w'), indent=2)

def make_shop_slug(business):
    if not business: return 'shop'
    base = re.sub(r'[^a-z0-9]+', '-', business.lower()).strip('-')
    return base[:50] or 'shop'

@my_shop_bp.route('/my-shop')
def my_shop_page():
    return render_template('my_shop.html')

@my_shop_bp.route('/api/my-shop')
def api_my_shop():
    email = request.args.get('email','').lower().strip()
    if not email:
        return jsonify({'success':False,'message':'Email required'}),400
    users = load_db('users.json', [])
    user = next((u for u in users if str(u.get('email','')).lower()==email), None)
    if not user:
        return jsonify({'success':False,'message':'User not found'}),404
    shops = load_db('shops.json', [])
    shop = next((s for s in shops if str(s.get('owner_email','')).lower()==email), None)
    if not shop:
        biz = user.get('business','')
        if biz:
            shop = next((s for s in shops if s.get('business_name','').lower()==biz.lower()), None)
    if not shop:
        shop = {"business_name": user.get('business','My Shop'), "shop_slug": make_shop_slug(user.get('business','shop')), "owner_email": email, "location":"Kampala", "phone":user.get('phone',''), "description":"Welcome to my shop!", "logo":"", "verified":False, "created": time.time()}
    products = load_db('products.json', [])
    my_products = [p for p in products if str(p.get('seller_email','')).lower()==email]
    my_products = sorted(my_products, key=lambda x: x.get('created',0), reverse=True)
    orders_v2 = load_db('orders_v2.json', [])
    my_orders = [o for o in orders_v2 if str(o.get('seller_email','')).lower()==email]
    wants = load_db('wants.json', [])
    matching_wants = [w for w in wants if w.get('status','open')=='open'][:20]
    coins = int(user.get('coins',0))
    if coins==0:
        coins = int(user.get('bought',0)) + int(user.get('earned',0)) - int(user.get('spent',0))
        if coins<0: coins=0
    return jsonify({
        'success':True, 'shop': shop, 'products': my_products,
        'stats': {"views": sum(int(p.get('views',0)) for p in my_products), "total_products": len(my_products), "call_clicks": len(my_products)*3, "whatsapp_clicks": len(my_products)*2, "coins": coins},
        'orders': sorted(my_orders, key=lambda x: x.get('created_at',0), reverse=True),
        'matching_wants': matching_wants, 'total': len(my_products), 'has_more': False, 'page': 1
    })

@my_shop_bp.route('/api/my-shop/update-price', methods=['POST'])
def my_shop_update_price():
    data=request.json or {}; pid=str(data.get('id','')); price=int(data.get('price',0)); email=data.get('email','').lower()
    products=load_db('products.json',[])
    for p in products:
        if str(p['id'])==pid and str(p.get('seller_email','')).lower()==email:
            p['price']=price; save_db('products.json',products); return jsonify({'success':True})
    return jsonify({'success':False}),403

@my_shop_bp.route('/api/my-shop/update-stock', methods=['POST'])
def my_shop_update_stock():
    data=request.json or {}; pid=str(data.get('id','')); stock=int(data.get('stock',0)); email=data.get('email','').lower()
    products=load_db('products.json',[])
    for p in products:
        if str(p['id'])==pid and str(p.get('seller_email','')).lower()==email:
            p['stock']=stock; save_db('products.json',products); return jsonify({'success':True})
    return jsonify({'success':False}),403

@my_shop_bp.route('/api/my-shop/toggle-hide', methods=['POST'])
def my_shop_toggle_hide():
    data=request.json or {}; pid=str(data.get('id','')); hidden=bool(data.get('hidden',False)); email=data.get('email','').lower()
    products=load_db('products.json',[])
    for p in products:
        if str(p['id'])==pid and str(p.get('seller_email','')).lower()==email:
            p['is_hidden']=hidden; save_db('products.json',products); return jsonify({'success':True})
    return jsonify({'success':False}),403

@my_shop_bp.route('/api/my-shop/delete', methods=['POST'])
def my_shop_delete():
    data=request.json or {}; pid=str(data.get('id','')); email=data.get('email','').lower()
    products=load_db('products.json',[])
    new_products=[p for p in products if not (str(p['id'])==pid and str(p.get('seller_email','')).lower()==email)]
    if len(new_products)!=len(products):
        save_db('products.json',new_products); return jsonify({'success':True})
    return jsonify({'success':False}),404

@my_shop_bp.route('/api/my-shop/update-settings', methods=['POST'])
def my_shop_update_settings():
    data=request.json or {}
    email=data.get('email','').lower().strip()
    if not email:
        return jsonify({'success':False,'message':'Email required'}),400
    
    print(f"MY-SHOP UPDATE: {email} -> {data}")
    
    shops=load_db('shops.json',[]) or []
    users=load_db('users.json',[]) or []
    products=load_db('products.json',[]) or []
    
    # FIND OR CREATE SHOP - FIXED!
    shop = next((s for s in shops if str(s.get('owner_email','')).lower()==email), None)
    
    if not shop:
        # CREATE NEW SHOP if not exists - THIS WAS MISSING!
        biz_name = data.get('business_name','My Shop').strip() or 'My Shop'
        new_slug = make_shop_slug(biz_name)
        # Ensure slug unique
        existing_slugs = [str(s.get('shop_slug','')).lower() for s in shops]
        base_slug = new_slug
        counter=1
        while new_slug in existing_slugs:
            new_slug = f"{base_slug}-{counter}"
            counter+=1
        
        shop = {
            "business_name": biz_name,
            "shop_slug": new_slug,
            "owner_email": email,
            "location": data.get('location','Kampala'),
            "phone": data.get('phone',''),
            "description": data.get('description','Welcome!'),
            "logo": data.get('logo',''),
            "verified": False,
            "created": time.time(),
            "updated": time.time()
        }
        shops.append(shop)
        print(f"CREATED NEW SHOP: {new_slug}")
    else:
        # UPDATE EXISTING - KEEP SAME SLUG (don't break links)
        old_name = shop.get('business_name','')
        new_name = data.get('business_name','').strip()
        if new_name and new_name != old_name:
            shop['business_name'] = new_name
            # OPTIONAL: Keep old slug for SEO, or uncomment to update slug:
            # shop['shop_slug'] = make_shop_slug(new_name)
        
        shop['location'] = data.get('location', shop.get('location','Kampala'))
        shop['phone'] = data.get('phone', shop.get('phone',''))
        shop['description'] = data.get('description', shop.get('description',''))
        if data.get('logo'):
            shop['logo'] = data.get('logo')
        shop['updated'] = time.time()
        print(f"UPDATED SHOP: {shop['shop_slug']}")

    # ALSO UPDATE USER BUSINESS NAME
    for u in users:
        if str(u.get('email','')).lower()==email:
            if data.get('business_name'):
                u['business'] = data.get('business_name')
            if data.get('phone'):
                u['phone'] = data.get('phone')
            break

    # ALSO UPDATE ALL PRODUCTS BUSINESS FIELD (so shop page shows new name)
    updated_products = 0
    for p in products:
        if str(p.get('seller_email','')).lower()==email:
            if data.get('business_name'):
                p['business'] = data.get('business_name')
            # Keep product shop_slug synced to shop
            p['shop_slug'] = shop['shop_slug']
            updated_products+=1

    save_db('shops.json', shops)
    save_db('users.json', users)
    if updated_products>0:
        save_db('products.json', products)

    print(f"SHOP SAVE OK: {shop['shop_slug']} + {updated_products} products updated")
    
    return jsonify({'success':True, 'shop': shop, 'updated_products': updated_products, 'message': f"Shop saved! {updated_products} products updated"})
