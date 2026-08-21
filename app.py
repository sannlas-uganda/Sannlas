from flask import Flask, jsonify, request, send_from_directory,render_template,Response
from flask_cors import CORS
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from functools import wraps
app = Flask(__name__)
CORS(app)
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
products = [{"id": 1, "name": "iPhone 15 Pro", "price": 4500000, "image": "https://m.media-amazon.com/images/I/71d7rfSl0wL._AC_SL1500_.jpg", "description": "Latest Apple iPhone", "business": "Apple Store UG", "location": "Kampala", "phone": "0795712326"}]
sellers = []
orders = []
PLANS = {"free": {"days": 14, "price": 0, "label": "14 Days FREE"}, "30days": {"days": 30, "price": 5000, "label": "30 Days - 5,000"}, "6month": {"days": 180, "price": 30000, "label": "6 Months - 30,000"}, "1year": {"days": 365, "price": 60000, "label": "1 Year - 60,000"}}
@app.route('/api/products')
def get_products(): return jsonify(products)
@app.route('/api/sell', methods=['POST'])
def sell_product():
    business_phone = request.form['phone']
    seller = next((s for s in sellers if s['phone'] == business_phone), None)
    if not seller or datetime.strptime(seller['expiry'], '%Y-%m-%d') < datetime.now():
        return jsonify({"success": False, "message": "Subscription expired."}), 403
    file = request.files['image']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    new_product = {"id": len(products) + 1, "name": request.form['name'], "price": int(request.form['price']), "image": '/' + filepath, "description": request.form['desc'], "business": request.form['business'], "location": request.form['location'], "phone": request.form['phone']}
    products.append(new_product)
    return jsonify({"success": True})
@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    data = request.json
    plan = PLANS[data['plan']]
    expiry = datetime.now() + timedelta(days=plan['days'])
    seller_data = {"business": data['business'], "phone": data['phone'], "location": data['location'], "plan": data['plan'], "plan_label": plan['label'], "price_paid": plan['price'], "expiry": expiry.strftime('%Y-%m-%d'), "started": datetime.now().strftime('%Y-%m-%d')}
    global sellers
    sellers = [s for s in sellers if s['phone'] != data['phone']]
    sellers.append(seller_data)
    return jsonify({"success": True, "message": f"Subscribed! Expires {expiry.strftime('%Y-%m-%d')}"})
@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.json
    data['order_id'] = len(orders) + 1
    data['date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    orders.append(data)
    return jsonify({"success": True, "message": f"Order Received! Deliver to {data['buyer']['district']}"})
@app.route('/api/admin/data')
def admin_data():
    total_revenue = sum([s['price_paid'] for s in sellers])
    return jsonify({"sellers": sellers, "orders": orders, "products": products, "total_revenue": total_revenue, "total_sellers": len(sellers), "total_orders": len(orders)})
@app.route('/static/uploads/<filename>')
def uploaded_file(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

from functools import wraps
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Sannlas2026!")

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.password != ADMIN_PASSWORD:
            return Response('Admin Login Required', 401, {'WWW-Authenticate': 'Basic realm="Admin"'})
        return f(*args, **kwargs)
    return decorated


ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ThE,RISE")

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.password != ADMIN_PASSWORD:
            return Response('Admin Login Required', 401, {'WWW-Authenticate': 'Basic realm="Admin"'})
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def serve_frontend(): return send_from_directory('templates', 'index.html')

@app.route('/admin')
@admin_required
def serve_admin(): return send_from_directory('templates', 'admin.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
