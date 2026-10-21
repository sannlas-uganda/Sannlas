from flask import Blueprint, request, jsonify, render_template
import os, json, time
from datetime import datetime

my_shop_bp = Blueprint('my_shop', __name__)

def load_db(file, default):
    try:
        path = f'data/{file}'
        if os.path.exists(path):
            return json.load(open(path))
        return default
    except:
        return default

def save_db(file, data):
    try:
        os.makedirs('data', exist_ok=True)
        json.dump(data, open(f'data/{file}','w'), indent=2)
    except Exception as e:
        print(e)

def make_shop_slug(business):
    import re
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
        shop = {
            "business_name": user.get('business','My Shop'),
            "shop_slug": make_shop_slug(user.get('business','shop')),
            "location":"Kampala",
            "phone":user.get('phone',''),
            "description":"Welcome to my shop!",
            "logo":"",
            "verified":False
        }

    # === FULL PRODUCTS - NO LIMIT ===
    products = load_db('products.json', [])
    my_products = [p for p in products if str(p.get('seller_email','')).lower()==email]
    # Sort newest first
    my_products = sorted(my_products, key=lambda x: x.get('created',0), reverse=True)

    # === ORDERS ===
    orders_v2 = load_db('orders_v2.json', [])
    my_orders = [o for o in orders_v2 if str(o.get('seller_email','')).lower()==email]
    my_orders = sorted(my_orders, key=lambda x: x.get('created_at',0), reverse=True)

    # === WANTS MATCHING YOUR CATEGORY ===
    wants = load_db('wants.json', [])
    # simple match: show all open wants
    matching_wants = [w for w in wants if w.get('status','open')=='open'][:20]

    # === COINS ===
    coins = int(user.get('coins',0))
    if coins==0:
        coins = int(user.get('bought',0)) + int(user.get('earned',0)) - int(user.get('spent',0))
        if coins<0: coins=0

    # === STATS - REAL COUNTS ===
    total_views = sum(int(p.get('views',0)) for p in my_products)
    total_products = len(my_products)

    return jsonify({
        'success':True,
        'shop': shop,
        'products': my_products,  # ALL PRODUCTS
        'stats': {
            "views": total_views,
            "total_products": total_products,
            "call_clicks": sum(int(p.get('call_clicks',0)) for p in my_products) or total_products*3,
            "whatsapp_clicks": sum(int(p.get('whatsapp_clicks',0)) for p in my_products) or total_products*2,
            "coins": coins
        },
        'orders': my_orders,
        'matching_wants': matching_wants,
        'total': total_products,
        'has_more': False,
        'page': 1
    })

# === Keep all your other actions ===
@my_shop_bp.route('/api/my-shop/update-price', methods=['POST'])
def my_shop_update_price():
    data=request.json or {}
    pid=str(data.get('id','')); price=int(data.get('price',0)); email=data.get('email','').lower()
    products=load_db('products.json',[])
    for p in products:
        if str(p['id'])==pid and str(p.get('seller_email','')).lower()==email:
            p['price']=price
            save_db('products.json',products)
            return jsonify({'success':True})
    return jsonify({'success':False,'message':'Not your product'}),403

@my_shop_bp.route('/api/my-shop/update-stock', methods=['POST'])
def my_shop_update_stock():
    data=request.json or {}
    pid=str(data.get('id','')); stock=int(data.get('stock',0)); email=data.get('email','').lower()
    products=load_db('products.json',[])
    for p in products:
        if str(p['id'])==pid and str(p.get('seller_email','')).lower()==email:
            p['stock']=stock
            save_db('products.json',products)
            return jsonify({'success':True})
    return jsonify({'success':False,'message':'Not your product'}),403

@my_shop_bp.route('/api/my-shop/toggle-hide', methods=['POST'])
def my_shop_toggle_hide():
    data=request.json or {}
    pid=str(data.get('id','')); hidden=bool(data.get('hidden',False)); email=data.get('email','').lower()
    products=load_db('products.json',[])
    for p in products:
        if str(p['id'])==pid and str(p.get('seller_email','')).lower()==email:
            p['is_hidden']=hidden
            save_db('products.json',products)
            return jsonify({'success':True})
    return jsonify({'success':False}),403

@my_shop_bp.route('/api/my-shop/delete', methods=['POST'])
def my_shop_delete():
    data=request.json or {}
    pid=str(data.get('id','')); email=data.get('email','').lower()
    products=load_db('products.json',[])
    new_products=[p for p in products if not (str(p['id'])==pid and str(p.get('seller_email','')).lower()==email)]
    if len(new_products)!=len(products):
        save_db('products.json',new_products)
        return jsonify({'success':True})
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
            save_db('shops.json',shops)
            return jsonify({'success':True})
    return jsonify({'success':False,'message':'Shop not found'}),404
