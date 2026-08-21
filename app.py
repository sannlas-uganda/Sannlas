from flask import Flask, request, jsonify, render_template
import os, json, uuid, time
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER']='static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)

# YOUR CONTACT
OWNER_EMAIL = "natelieabigali@gmail.com"
OWNER_PHONE = "0795712328"
OWNER_MOMO = "0795712328"

# SUBSCRIPTION PLANS - UGX
PLANS = {
    "free14": {"days": 14, "price": 0, "name": "14 Days FREE"},
    "30": {"days": 30, "price": 6540, "name": "30 Days"},
    "60": {"days": 60, "price": 13090, "name": "2 Months"},
    "180": {"days": 180, "price": 39500, "name": "6 Months"},
    "365": {"days": 365, "price": 80000, "name": "1 Year"}
}

def load_db(file, default):
    path=f'data/{file}'
    if os.path.exists(path):
        try: return json.load(open(path))
        except: return default
    return default

def save_db(file, data):
    json.dump(data, open(f'data/{file}','w'), indent=2)

BUSINESS_CATEGORIES = {
"Agriculture & Farming":["Fish Farming","Poultry Farming","Crop Farming","Livestock","Animal Feeds"],
"Food & Beverages":["Restaurants","Bakeries","Fast Foods","Drinks","Catering"],
"Construction & Building":["Cement","Hardware","Plumbing","Electrical","Tiles"],
"Fashion & Clothing":["Men's Clothing","Women's Clothing","Kids","Shoes","Bags"],
"Electronics & Technology":["Mobile Phones","Laptops","Accessories","TVs","Solar"],
"Automotive":["Spare Parts","Car Repair","Boda Boda","Tyres"],
"Health & Medical":["Clinics","Pharmacies","Lab Services","Hospitals","Herbal"],
"Beauty & Personal Care":["Hair Salons","Cosmetics","Barbers"],
"Home & Furniture":["Furniture","Sofas","Kitchenware"],
"Professional Services":["Lawyers","Accountants","Printing"],
"Education":["Schools","Coaching"],"Travel & Tourism":["Hotels","Tours"]
}

@app.route('/')
def home(): return render_template('index.html')
@app.route('/admin')
def admin_page(): return render_template('admin.html')

@app.route('/api/categories')
def get_cats(): return jsonify(BUSINESS_CATEGORIES)

@app.route('/api/plans')
def get_plans(): return jsonify(PLANS)

@app.route('/api/products')
def get_products():
    products=load_db('products.json', [])
    main=request.args.get('main'); sub=request.args.get('sub')
    q=request.args.get('q','').lower(); min_p=request.args.get('min'); max_p=request.args.get('max')
    new_only=request.args.get('new') #?new=1 for new products button

    filtered=products
    if main: filtered=[p for p in filtered if p.get('main_category')==main]
    if sub: filtered=[p for p in filtered if p.get('sub_category')==sub]
    if q: filtered=[p for p in filtered if q in p.get('name','').lower() or q in p.get('description','').lower() or q in p.get('business','').lower()]
    if min_p: filtered=[p for p in filtered if p.get('price',0)>=int(min_p)]
    if max_p: filtered=[p for p in filtered if p.get('price',0)<=int(max_p)]

    # NEW PRODUCTS - last 48h or last 100
    if new_only:
        cutoff = time.time() - 48*3600
        filtered = [p for p in filtered if p.get('created',0) > cutoff]
        if not filtered: # if none in 48h, show last 50
            filtered = sorted(products, key=lambda x: x.get('created',0), reverse=True)[:50]

    # Sort boosted + newest first for continuous down
    filtered=sorted(filtered, key=lambda x: (x.get('boosted',0), x.get('created',0)), reverse=True)

    # HIDE TELEPHONE - Admin only sees - REMOVE PHONE TEXT ON FRONT
    public=[]
    for p in filtered:
        pp = p.copy()
        pp.pop('phone', None) # HIDDEN - admin only
        # Keep business name owner visible
        public.append(pp)
    return jsonify(public)

@app.route('/api/sell', methods=['POST'])
def sell():
    name=request.form.get('name'); price=int(request.form.get('price',0))
    business=request.form.get('business'); location=request.form.get('location')
    phone=request.form.get('phone'); desc=request.form.get('desc','')
    main_cat=request.form.get('main_category'); sub_cat=request.form.get('sub_category')
    stock=int(request.form.get('stock',10))
    plan=request.form.get('plan','free14') # Subscription plan

    images=[]
    for key in request.files:
        f=request.files[key]
        if f and f.filename:
            fn=str(uuid.uuid4())[:8]+'_'+secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            images.append('/static/uploads/'+fn)
    img_url=request.form.get('image_url')
    if img_url and not images: images=[img_url]
    if not images: images=['https://via.placeholder.com/300']

    products=load_db('products.json', [])
    plan_info = PLANS.get(plan, PLANS['free14'])

    prod={
        'id':int(time.time()*1000),
        'name':name,
        'price':price, # Each product own price - no default
        'business':business, # Business name owner visible
        'location':location,
        'phone':phone, # HIDDEN - only admin sees in admin/data
        'description':desc,
        'image':images[0],
        'images':images,
        'main_category':main_cat,
        'sub_category':sub_cat,
        'stock':stock,
        'sold':0,
        'rating':5.0,
        'reviews':[],
        'views':0,
        'verified':False,
        'boosted':0,
        'bargain_allowed':True,
        'created':time.time(),
        'plan': plan,
        'plan_name': plan_info['name'],
        'plan_price': plan_info['price'],
        'subscription_expires': time.time() + plan_info['days']*86400
    }
    products.append(prod); save_db('products.json', products)
    return jsonify({'success':True, 'message': f'Added with {plan_info["name"]}'})

@app.route('/api/my-products')
def my_products():
    phone=request.args.get('phone'); products=load_db('products.json', [])
    if phone: products=[p for p in products if p.get('phone')==phone]
    return jsonify(products)

@app.route('/api/delete-product/<int:pid>', methods=['DELETE'])
def delete_prod(pid):
    products=load_db('products.json', [])
    products=[p for p in products if p['id']!=pid]
    save_db('products.json', products)
    return jsonify({'success':True})

@app.route('/api/rate', methods=['POST'])
def rate():
    data=request.json; pid=data['id']
    products=load_db('products.json', [])
    for p in products:
        if p['id']==pid:
            p['reviews'].append({'rating':data['rating'],'comment':data.get('comment',''),'time':time.time()})
            p['rating']=sum(r['rating'] for r in p['reviews'])/len(p['reviews'])
    save_db('products.json', products)
    return jsonify({'success':True})

@app.route('/api/bargain', methods=['POST'])
def bargain():
    data=request.json; bargains=load_db('bargains.json', [])
    data['id']=int(time.time()); data['status']='pending'; data['time']=time.time()
    bargains.append(data); save_db('bargains.json', bargains)
    # Also add to orders so admin sees in orders list with WhatsApp reply button
    orders=load_db('orders.json', [])
    orders.append({'id':data['id'], 'type':'bargain', 'bargain': data, 'total': data.get('offer'), 'buyer': {'names': data.get('buyer_name','Bargain Buyer'), 'phone1': data.get('buyer_phone','')}, 'cart':[{'name': data.get('product_name')}], 'time':time.time()})
    save_db('orders.json', orders)
    return jsonify({'success':True,'message':"Bargain sent! Seller will reply via WhatsApp."})

@app.route('/api/boost', methods=['POST'])
def boost():
    data=request.json; pid=data['id']
    products=load_db('products.json', [])
    for p in products:
        if p['id']==pid: p['boosted']=time.time()+86400*int(data.get('days',1))
    save_db('products.json', products)
    return jsonify({'success':True,'message':'Boosted to top!'})

@app.route('/api/subscribe', methods=['POST'])
def sub():
    data=request.json; sellers=load_db('sellers.json', [])
    plan = data.get('plan','free14')
    plan_info = PLANS.get(plan, PLANS['free14'])
    data['id']=int(time.time()); data['referral_code']=str(uuid.uuid4())[:6].upper()
    data['plan_name']=plan_info['name']; data['plan_price']=plan_info['price']
    data['expires']=time.time()+plan_info['days']*86400
    sellers.append(data); save_db('sellers.json', sellers)
    return jsonify({'message':f'Subscribed {plan_info["name"]} UGX {plan_info["price"]} - Welcome to SANNLAS PRO'})

@app.route('/api/checkout', methods=['POST'])
def checkout():
    data=request.json; orders=load_db('orders.json', [])
    data['id']=int(time.time()); data['status']='Packed'; data['time']=time.time()
    orders.append(data); save_db('orders.json', orders)
    products=load_db('products.json', [])
    for item in data['cart']:
        for p in products:
            if p['id']==item['id']: p['stock']=max(0,p.get('stock',10)-1)
    save_db('products.json', products)
    return jsonify({'message':'Order placed! ID: '+str(data['id'])+' Owner will reply via WhatsApp/Email'})

# --- JOBS DASHBOARD ---
@app.route('/api/jobs', methods=['GET','POST'])
def jobs_api():
    if request.method=='POST':
        data=request.json; data['id']=int(time.time()*1000); data['time']=time.time()
        all_jobs=load_db('jobs.json', []); all_jobs.append(data); save_db('jobs.json', all_jobs)
        return jsonify({'success':True,'message':'Job posted! People will apply now.'})
    else:
        all_jobs=load_db('jobs.json', [])
        q=request.args.get('q','').lower(); cat=request.args.get('category','')
        if q: all_jobs=[j for j in all_jobs if q in j.get('title','').lower() or q in j.get('description','').lower()]
        if cat: all_jobs=[j for j in all_jobs if j.get('category')==cat]
        return jsonify(all_jobs[::-1])

@app.route('/api/jobs/<int:jid>/apply', methods=['POST'])
def apply_job(jid):
    data=request.json; apps=load_db('applications.json', [])
    data['job_id']=jid; data['id']=int(time.time()); data['time']=time.time()
    apps.append(data); save_db('applications.json', apps)
    return jsonify({'success':True,'message':'Application sent! Check Job Applications button'})

@app.route('/api/job-applications')
def get_applications():
    return jsonify(load_db('applications.json', [])[::-1])

@app.route('/api/orders')
def get_orders():
    # For front orders button + WhatsApp reply
    orders=load_db('orders.json', [])[::-1]
    # Hide sensitive? Keep buyer phone for WhatsApp reply button
    return jsonify(orders)

@app.route('/api/contact', methods=['POST'])
def contact_owner():
    data=request.json; contacts=load_db('contacts.json', [])
    contacts.append({**data, 'time':time.time(), 'id':int(time.time()), 'owner_email':OWNER_EMAIL})
    save_db('contacts.json', contacts)
    return jsonify({'success':True,'message':f'Message sent to {OWNER_EMAIL}! Owner will reply via Email/WhatsApp'})

# --- ADMIN DATA - PHONES VISIBLE HERE ONLY ---
@app.route('/api/admin/data')
def admin_data():
    products = load_db('products.json',[])
    # Mark expired subscriptions
    now = time.time()
    for p in products:
        if p.get('subscription_expires',0) < now:
            p['expired']=True
    return jsonify({
        'products': products, # WITH PHONE - admin only
        'sellers': load_db('sellers.json',[]),
        'orders': load_db('orders.json',[]),
        'jobs': load_db('jobs.json',[]),
        'contacts': load_db('contacts.json',[]),
        'applications': load_db('applications.json',[]),
        'bargains': load_db('bargains.json',[]),
        'total_revenue': sum([o.get('total',0) for o in load_db('orders.json',[]) if isinstance(o.get('total'), (int,float))]),
        'total_sellers': len(load_db('sellers.json',[])),
        'total_orders': len(load_db('orders.json',[])),
        'plans': PLANS,
        'owner_email': OWNER_EMAIL,
        'owner_momo': OWNER_MOMO
    })

@app.route('/api/admin/<string:filetype>')
def admin_generic(filetype):
    allowed=['contacts','applications','orders','bargains','sellers','jobs','products']
    if filetype not in allowed: return jsonify([])
    return jsonify(load_db(f'{filetype}.json', []))

if __name__=='__main__': app.run(debug=True, host='0.0.0.0', port=5000)
