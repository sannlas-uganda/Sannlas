from flask import Flask, request, jsonify, render_template
import os, json, uuid, time
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER']='static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)

# YOUR CONTACT — EDIT HERE
OWNER_EMAIL = "natelieabigail@gmail.com"
OWNER_PHONE = "0795712326"
OWNER_MOMO = "0795712326"

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
"Health & Medical":["Clinics","Pharmacies","Lab Services"],
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

@app.route('/api/products')
def get_products():
    products=load_db('products.json', [])
    main=request.args.get('main'); sub=request.args.get('sub')
    q=request.args.get('q','').lower(); min_p=request.args.get('min'); max_p=request.args.get('max')
    filtered=products
    if main: filtered=[p for p in filtered if p.get('main_category')==main]
    if sub: filtered=[p for p in filtered if p.get('sub_category')==sub]
    if q: filtered=[p for p in filtered if q in p.get('name','').lower() or q in p.get('description','').lower() or q in p.get('business','').lower()]
    if min_p: filtered=[p for p in filtered if p.get('price',0)>=int(min_p)]
    if max_p: filtered=[p for p in filtered if p.get('price',0)<=int(max_p)]
    filtered=sorted(filtered, key=lambda x: x.get('boosted',0), reverse=True)
    return jsonify(filtered)

@app.route('/api/sell', methods=['POST'])
def sell():
    name=request.form.get('name'); price=int(request.form.get('price',0))
    business=request.form.get('business'); location=request.form.get('location')
    phone=request.form.get('phone'); desc=request.form.get('desc','')
    main_cat=request.form.get('main_category'); sub_cat=request.form.get('sub_category')
    stock=int(request.form.get('stock',10))
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
    prod={'id':int(time.time()*1000),'name':name,'price':price,'business':business,'location':location,'phone':phone,'description':desc,'image':images[0],'images':images,'main_category':main_cat,'sub_category':sub_cat,'stock':stock,'sold':0,'rating':5.0,'reviews':[],'views':0,'verified':False,'boosted':0,'bargain_allowed':True,'created':time.time()}
    products.append(prod); save_db('products.json', products)
    return jsonify({'success':True})

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
    data['id']=int(time.time()); data['status']='pending'
    bargains.append(data); save_db('bargains.json', bargains)
    return jsonify({'success':True,'message':"Offer sent! Seller will call you."})

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
    data['id']=int(time.time()); data['referral_code']=str(uuid.uuid4())[:6].upper()
    sellers.append(data); save_db('sellers.json', sellers)
    return jsonify({'message':'Subscribed! Welcome to SANNLAS PRO'})

@app.route('/api/checkout', methods=['POST'])
def checkout():
    data=request.json; orders=load_db('orders.json', [])
    data['id']=int(time.time()); data['status']='Packed'
    orders.append(data); save_db('orders.json', orders)
    products=load_db('products.json', [])
    for item in data['cart']:
        for p in products:
            if p['id']==item['id']: p['stock']=max(0,p.get('stock',10)-1)
    save_db('products.json', products)
    return jsonify({'message':'Order placed! ID: '+str(data['id'])})

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
    data['job_id']=jid; data['id']=int(time.time()); apps.append(data); save_db('applications.json', apps)
    return jsonify({'success':True,'message':'Application sent!'})

@app.route('/api/contact', methods=['POST'])
def contact_owner():
    data=request.json; contacts=load_db('contacts.json', [])
    contacts.append({**data, 'time':time.time(), 'id':int(time.time()), 'owner_email':OWNER_EMAIL})
    save_db('contacts.json', contacts)
    return jsonify({'success':True,'message':f'Message sent to {OWNER_EMAIL}!'})

# --- NEW ADMIN API FOR YOUR DASHBOARD ---
@app.route('/api/admin/data')
def admin_data():
    return jsonify({
        'products': load_db('products.json',[]),
        'sellers': load_db('sellers.json',[]),
        'orders': load_db('orders.json',[]),
        'jobs': load_db('jobs.json',[]),
        'contacts': load_db('contacts.json',[]),
        'applications': load_db('applications.json',[]),
        'bargains': load_db('bargains.json',[]),
        'total_revenue': sum([o.get('total',0) for o in load_db('orders.json',[])]),
        'total_sellers': len(load_db('sellers.json',[])),
        'total_orders': len(load_db('orders.json',[]))
    })

@app.route('/api/admin/<string:filetype>')
def admin_generic(filetype):
    allowed=['contacts','applications','orders','bargains','sellers','jobs','products']
    if filetype not in allowed: return jsonify([])
    return jsonify(load_db(f'{filetype}.json', []))

if __name__=='__main__': app.run(debug=True)
