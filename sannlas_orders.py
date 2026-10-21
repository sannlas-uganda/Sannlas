from flask import Blueprint, request, jsonify
from sannlas_cart import load_db, save_db, get_carts, save_carts
import random, time
from datetime import datetime

orders_bp = Blueprint('orders_bp', __name__)

def get_orders():
    return load_db('orders.json', [])

def save_orders(data):
    save_db('orders.json', data)

def gen_tracking_id():
    return f"SN-{random.randint(100000, 999999)}"

@orders_bp.route('/api/orders/create', methods=['POST'])
def create_orders():
    data = request.get_json()
    email = data.get('email','').lower().strip()
    buyer_name = data.get('buyer_name','').strip()
    buyer_phone = data.get('buyer_phone','').strip()
    district = data.get('district','').strip()
    address = data.get('address','').strip()
    
    if not email or not buyer_name or not buyer_phone:
        return jsonify({"success": False, "message": "Name & Phone required"}), 400
    
    carts = get_carts()
    user_carts = [c for c in carts if (c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone)]
    
    if not user_carts:
        return jsonify({"success": False, "message": "Cart empty"}), 400
    
    # Group by shop - SPLIT PER SHOP
    from collections import defaultdict
    shops = defaultdict(list)
    for item in user_carts:
        shop_key = item.get('shop_email') or item.get('shop_name') or 'Sannlas'
        shops[shop_key].append(item)
    
    orders = get_orders()
    created_orders = []
    
    for shop_key, items in shops.items():
        tracking_id = gen_tracking_id()
        total = sum([float(i.get('price',0)) * int(i.get('qty',1)) for i in items])
        shop_name = items[0].get('shop_name','Sannlas')
        shop_email = items[0].get('shop_email','')
        
        order = {
            "order_id": tracking_id,
            "tracking_id": tracking_id,
            "buyer_email": email,
            "buyer_name": buyer_name,
            "buyer_phone": buyer_phone,
            "district": district,
            "address": address,
            "full_address": f"{district}, {address}",
            "shop_key": shop_key,
            "shop_name": shop_name,
            "shop_email": shop_email,
            "items": items,
            "total": total,
            "status": "PENDING",
            "delivery_man_name": "",
            "delivery_man_phone": "",
            "created_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        orders.append(order)
        created_orders.append(order)
    
    save_orders(orders)
    
    # Clear cart after order
    remaining = [c for c in carts if not ((c.get('email','').lower()==email) or (c.get('phone','')==buyer_phone))]
    save_carts(remaining)
    
    return jsonify({"success": True, "orders": created_orders, "message": f"{len(created_orders)} order(s) created!"})

@orders_bp.route('/api/orders/my', methods=['GET'])
def my_orders():
    email = request.args.get('email','').lower()
    if not email:
        return jsonify({"orders": []})
    orders = get_orders()
    my = [o for o in orders if o.get('buyer_email','').lower()==email]
    my.sort(key=lambda x: x.get('timestamp',0), reverse=True)
    return jsonify({"orders": my})

@orders_bp.route('/api/orders/track/<tracking_id>', methods=['GET'])
def track_order(tracking_id):
    orders = get_orders()
    order = next((o for o in orders if o.get('tracking_id')==tracking_id), None)
    if not order:
        return jsonify({"success": False, "message": "Order not found"}), 404
    return jsonify({"success": True, "order": order})
