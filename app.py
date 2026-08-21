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

# ===== YOUR NEW BUSINESS CATEGORIES SYSTEM =====
BUSINESS_CATEGORIES = {
"Agriculture & Farming":["Crop Farming","Livestock Farming","Poultry Farming","Dairy Farming","Fish Farming","Beekeeping","Horticulture","Floriculture","Farm Machinery","Seeds & Fertilizers","Animal Feeds"],
"Food & Beverages":["Restaurants","Fast Food","Cafes","Bakeries","Butcheries","Supermarkets","Grocery Stores","Catering","Food Delivery","Beverages","Food Processing","Fresh Foods"],
"Construction & Building":["Cement","Bricks & Blocks","Sand & Aggregates","Roofing Materials","Steel & Metal","Plumbing Materials","Electrical Materials","Paints","Tiles","Doors & Windows","Building Tools","Construction Machinery","Road Construction","Interior Finishing","Landscaping"],
"Real Estate":["Land","Houses","Apartments","Offices","Shops","Warehouses","Rental Properties","Commercial Buildings","Property Management","Real Estate Agencies"],
"Fashion & Clothing":["Men's Clothing","Women's Clothing","Children's Clothing","Suits","Dresses","Shirts","Trousers","Shoes","Bags","Sportswear","Underwear","Jewelry","Watches","Fashion Accessories"],
"Electronics & Technology":["Mobile Phones","Laptops","Desktop Computers","Tablets","Televisions","Cameras","Speakers","Headphones","Computer Accessories","Phone Accessories","Printers","Gaming Devices","Smart Devices","Home Appliances"],
"Automotive":["Cars","Motorcycles","Trucks","Buses","Car Parts","Motorcycle Parts","Tires","Batteries","Car Accessories","Car Repair","Car Washing","Car Rental","Vehicle Insurance"],
"Health & Medical":["Hospitals","Clinics","Pharmacies","Medical Equipment","Medical Supplies","Laboratories","Dental Services","Optical Services","Nursing Services","Home Healthcare"],
"Beauty & Personal Care":["Cosmetics","Skincare","Hair Products","Hair Salons","Barbershops","Makeup","Perfumes","Nail Care","Spa Services","Beauty Equipment"],
"Education":["Schools","Universities","Vocational Training","Online Courses","Tutoring","Books","Stationery","Educational Software","Training Centers","Educational Consultancy"],
"Financial Services":["Banking","Insurance","Loans","Microfinance","Accounting","Auditing","Investment","Tax Services","Financial Consultancy","Payment Services"],
"Transport & Logistics":["Taxi Services","Bus Services","Trucking","Motorcycle Transport","Courier Services","Delivery Services","Freight Forwarding","Warehousing","Shipping","Moving Services"],
"Travel & Tourism":["Hotels","Lodges","Resorts","Travel Agencies","Tour Operators","Safari Services","Car Hire","Tourist Attractions","Travel Booking","Airlines"],
"Entertainment & Media":["Music","Movies","Photography","Videography","Gaming","DJs","Event Management","Radio","Television","Publishing","Streaming"],
"Sports & Fitness":["Gyms","Fitness Training","Sports Equipment","Sportswear","Football","Basketball","Swimming","Martial Arts","Sports Clubs","Fitness Centers"],
"Home & Furniture":["Sofas","Beds","Tables","Chairs","Cabinets","Mattresses","Curtains","Carpets","Kitchen Equipment","Home Decorations","Household Products"],
"Energy & Utilities":["Solar Energy","Solar Panels","Batteries","Generators","Electrical Equipment","Gas","Water Supply","Renewable Energy","Energy Services"],
"Manufacturing":["Textile Manufacturing","Food Manufacturing","Furniture Manufacturing","Metal Fabrication","Plastic Products","Chemical Products","Paper Products","Machinery","Industrial Equipment","Packaging"],
"Professional Services":["Lawyers","Accountants","Engineers","Architects","Surveyors","Consultants","Marketing Agencies","Advertising Agencies","HR Services","Business Consultancy"],
"Information Technology":["Website Development","Mobile App Development","Software Development","Cybersecurity","Cloud Services","Data Services","Artificial Intelligence","Computer Repair","Networking","Digital Marketing"],
"Telecommunications":["Mobile Networks","Internet Services","Fiber Internet","Broadband","SIM Cards","Communication Equipment","Telecommunication Services"],
"Home & Property Services":["Cleaning","Plumbing","Electrical Services","Painting","Carpentry","Masonry","Roofing","Gardening","Pest Control","Security Services"],
"Security Services":["Security Guards","CCTV Systems","Alarm Systems","Access Control","Security Equipment","Security Consultancy","Private Investigation"],
"Pets & Animals":["Pet Food","Pet Accessories","Veterinary Services","Pet Grooming","Pet Shops","Animal Breeding","Animal Equipment"],
"Events & Weddings":["Wedding Planning","Event Decoration","Catering","Photography","Videography","Wedding Dresses","Event Venues","Entertainment","Event Equipment"],
"Printing & Stationery":["Printing","Graphic Design","Business Cards","Posters","Books","Stationery","Branding","Sign Making","Packaging"],
"Repair & Maintenance Services":["Phone Repair","Computer Repair","Appliance Repair","Vehicle Repair","Electrical Repair","Plumbing Repair","Machinery Repair","Furniture Repair"],
"Business & Consulting Services":["Business Consulting","Management Consulting","Marketing Consulting","Financial Consulting","IT Consulting","Human Resources","Business Registration","Entrepreneurship Services"]
}

products = [{"id": 1, "name": "iPhone 15 Pro", "price": 4500000, "image": "https://m.media-amazon.com/images/I/71d7rfSl0wL._AC_SL1500_.jpg", "description": "Latest Apple iPhone", "business": "Apple Store UG", "location": "Kampala", "phone": "0795712326", "main_category":"Electronics & Technology", "sub_category":"Mobile Phones"}]
sellers = []
orders = []
PLANS = {"free": {"days": 14, "price": 0, "label": "14 Days FREE"}, "30days": {"days": 30, "price": 5000, "label": "30 Days - 5,000"}, "6month": {"days": 180, "price": 30000, "label": "6 Months - 30,000"}, "1year": {"days": 365, "price": 60000, "label": "1 Year - 60,000"}}

@app.route('/api/categories')
def get_categories():
    return jsonify(BUSINESS_CATEGORIES)

@app.route('/api/products')
def get_products():
    main = request.args.get('main')
    sub = request.args.get('sub')
    q = request.args.get('q','').lower()
    filtered = products
    if main:
        filtered = [p for p in filtered if p.get('main_category')==main]
    if sub:
        filtered = [p for p in filtered if p.get('sub_category')==sub]
    if q:
        filtered = [p for p in filtered if q in p['name'].lower() or q in p.get('main_category','').lower() or q in p.get('sub_category','').lower() or q in p.get('description','').lower()]
    return jsonify(filtered)

@app.route('/api/sell', methods=['POST'])
def sell_product():
    business_phone = request.form['phone']
    seller = next((s for s in sellers if s['phone'] == business_phone), None)
    if not seller or datetime.strptime(seller['expiry'], '%Y-%m-%d') < datetime.now():
        return jsonify({"success": False, "message": "Subscription expired."}), 403
    file = request.files.get('image')
    if file and file.filename:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        img_path = '/' + filepath
    else:
        img_path = request.form.get('image_url','')
    new_product = {"id": len(products) + 1, "name": request.form['name'], "price": int(request.form['price']), "image": img_path, "description": request.form.get('desc',''), "business": request.form['business'], "location": request.form['location'], "phone": request.form['phone'], "main_category": request.form.get('main_category',''), "sub_category": request.form.get('sub_category','')}
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
def serve_admin(): return send_from_directory('templates', 'admin.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
