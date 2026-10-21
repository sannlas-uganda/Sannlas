from flask import Blueprint, request, jsonify
import json, os, time
from datetime import datetime

my_shop_bp = Blueprint('my_shop', __name__)

def load_db(file, default):
    try:
        from app import DATABASE_URL, get_conn, ensure_tables
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
                try: conn.close()
                except: pass
                return default
        else:
            path=f'data/{file}'
            if os.path.exists(path):
                return json.load(open(path))
            return default
    except: return default

def save_db(file, data):
    try:
        from app import DATABASE_URL, get_conn, ensure_tables
        if DATABASE_URL:
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

def make_shop_slug(business):
    import re
    if not business: return 'shop'
    base = re.sub(r'[^a-z0-9]+', '-', business.lower()).strip('-')
    return base[:50] or 'shop'

@my_shop_bp.route('/my-shop')
def my_shop_page():
    from flask import render_template
    return render_template('my_shop.html')

@my_shop_bp.route('/api/my-shop')
def api_my_shop():
    email = request.args.get('email','').lower().strip()
    page = int(request.args.get('page','1'))
    limit = 10
    offset = (page-1)*limit
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
        shop = {"business_name": user.get('business','My Shop'), "shop_slug": make_shop_slug(user.get('business','shop')), "location":"Kampala", "phone":user.get('phone',''), "description":"Welcome!", "logo":"", "verified":False}
    products = load_db('products.json', [])
    all_mine = [p for p in products if str(p.get('seller_email','')).lower()==email]
    total = len(all_mine)
    my_products = all_mine[offset:offset+limit]
    coins = int(user.get('coins',0))
    if coins==0:
        coins = int(user.get('bought',0)) + int(user.get('earned',0)) - int(user.get('spent',0))
        if coins<0: coins=0
    return jsonify({
        'success':True, 'shop': shop, 'products': my_products,
        'stats': {"views": sum(int(p.get('views',0)) for p in all_mine), "total_products": total, "call_clicks": total*2, "whatsapp_clicks": total+5, "coins": coins},
        'orders': [], 'matching_wants': [], 'total': total, 'has_more': (offset+limit) < total, 'page': page
    })

@my_shop_bp.route('/api/my-shop/update-price', methods=['POST'])
def my_shop_update_price():
    data=request.json or {}
    pid=str(data.get('id','')); price=int(data.get('price',0)); email=data.get('email','').lower()
    products=load_db('products.json',[])
    for p in products:
        if str(p['id'])==pid and str(p.get('seller_email','')).lower()==email:
            p['price']=price; save_db('products.json',products); return jsonify({'success':True})
    return jsonify({'success':False,'message':'Not your product'}),403

@my_shop_bp.route('/api/my-shop/update-stock', methods=['POST'])
def my_shop_update_stock():
    data=request.json or {}
    pid=str(data.get('id','')); stock=int(data.get('stock',0)); email=data.get('email','').lower()
    products=load_db('products.json',[])
    for p in products:
        if str(p['id'])==pid and str(p.get('seller_email','')).lower()==email:
            p['stock']=stock; save_db('products.json',products); return jsonify({'success':True})
    return jsonify({'success':False,'message':'Not your product'}),403

@my_shop_bp.route('/api/my-shop/toggle-hide', methods=['POST'])
def my_shop_toggle_hide():
    data=request.json or {}
    pid=str(data.get('id','')); hidden=bool(data.get('hidden',False)); email=data.get('email','').lower()
    products=load_db('products.json',[])
    for p in products:
        if str(p['id'])==pid and str(p.get('seller_email','')).lower()==email:
            p['is_hidden']=hidden; save_db('products.json',products); return jsonify({'success':True})
    return jsonify({'success':False}),403

@my_shop_bp.route('/api/my-shop/delete', methods=['POST'])
def my_shop_delete():
    data=request.json or {}
    pid=str(data.get('id','')); email=data.get('email','').lower()
    products=load_db('products.json',[])
    new_products=[p for p in products if not (str(p['id'])==pid and str(p.get('seller_email','')).lower()==email)]
    if len(new_products)!=len(products):
        save_db('products.json',new_products); return jsonify({'success':True})
    return jsonify({'success':False,'message':'Not found'}),404

@my_shop_bp.route('/api/my-shop/update-settings', methods=['POST'])
def my_shop_update_settings():
    data=request.json or {}
    email=data.get('email','').lower()
    shops=load_db('shops.json',[])
    for s in shops:
        if str(s.get('owner_email','')).lower()==email:
            s['business_name']=data.get('business_name',s.get('business_name'))
            s['location']=data.get('location',s.get('location'))
            s['phone']=data.get('phone',s.get('phone'))
            s['delivery_info']=data.get('delivery_info',s.get('delivery_info'))
            s['working_hours']=data.get('working_hours',s.get('working_hours'))
            s['payment']=data.get('payment',s.get('payment'))
            s['description']=data.get('description',s.get('description'))
            save_db('shops.json',shops); return jsonify({'success':True})
    return jsonify({'success':False,'message':'Shop not found'}),404
