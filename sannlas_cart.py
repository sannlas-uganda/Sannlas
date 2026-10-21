from flask import Blueprint, request, jsonify, render_template
import os, json, time

cart_bp = Blueprint('cart_bp', __name__)

def load_db(file, default):
    try:
        path = f'data/{file}'
        if os.path.exists(path):
            with open(path,'r') as f:
                return json.load(f)
        return default
    except:
        return default

def save_db(file, data):
    os.makedirs('data', exist_ok=True)
    with open(f'data/{file}','w') as f:
        json.dump(data,f,indent=2)

# ===== CART DB =====
def get_carts(): return load_db('carts.json', [])
def save_carts(c): save_db('carts.json', c)

@cart_bp.route('/cart')
def cart_page():
    return render_template('cart.html')

@cart_bp.route('/api/cart', methods=['GET'])
def api_get_cart():
    email = request.args.get('email','').lower()
    phone = request.args.get('phone','')
    carts = get_carts()
    user_cart = next((c for c in carts if (email and c.get('email')==email) or (phone and c.get('phone')==phone)), None)
    if not user_cart:
        return jsonify({"items": [], "total": 0, "count": 0})
    items = sorted(user_cart.get('items', []), key=lambda x: x.get('added_at',0), reverse=True)
    total = sum(float(i.get('price',0)) * int(i.get('qty',1)) for i in items)
    return jsonify({"items": items, "total": total, "count": len(items)})

@cart_bp.route('/api/cart/add', methods=['POST'])
def api_add_to_cart():
    data = request.get_json() or {}
    email = (data.get('email') or '').lower()
    phone = data.get('phone','')
    product_id = str(data.get('product_id'))
    name = data.get('name','Product')
    price = float(data.get('price',0))
    image = data.get('image','')
    shop_name = data.get('shop_name','')
    shop_slug = data.get('shop_slug','')
    qty = int(data.get('qty',1))

    if not product_id or price==0:
        return jsonify({"success": False, "message": "Invalid product - price is 0 Boss! Select real product"}), 400

    carts = get_carts()
    user_cart = next((c for c in carts if (email and c.get('email')==email) or (phone and c.get('phone')==phone)), None)
    if not user_cart:
        user_cart = {"email": email, "phone": phone, "items": [], "created": time.time()}
        carts.append(user_cart)

    existing = next((i for i in user_cart['items'] if str(i.get('product_id'))==product_id), None)
    if existing:
        existing['qty'] = int(existing.get('qty',1)) + qty
    else:
        user_cart['items'].append({
            "product_id": product_id,
            "name": name,
            "price": price,
            "image": image,
            "shop_name": shop_name,
            "shop_slug": shop_slug,
            "qty": qty,
            "added_at": time.time()
        })
    
    # SORT CART: Newest first + group by shop
    user_cart['items'] = sorted(user_cart['items'], key=lambda x: (x.get('shop_slug',''), -x.get('added_at',0)))
    
    save_carts(carts)
    return jsonify({"success": True, "message": f"{name} added!"})

@cart_bp.route('/api/cart/remove', methods=['POST'])
def api_remove():
    data = request.get_json() or {}
    email = (data.get('email') or '').lower()
    phone = data.get('phone','')
    product_id = str(data.get('product_id'))
    carts = get_carts()
    uc = next((c for c in carts if (email and c.get('email')==email) or (phone and c.get('phone')==phone)), None)
    if uc:
        uc['items'] = [i for i in uc['items'] if str(i.get('product_id')) != product_id]
        save_carts(carts)
    return jsonify({"success": True})
