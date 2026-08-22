from flask import Flask, request, jsonify, render_template
import os, json, uuid, time, hashlib
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER']='static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)

OWNER_EMAIL = "natelieabigali@gmail.com"
OWNER_PHONE = "0795712326"
OWNER_MOMO = "0795712326"

PLANS = {
    "free14": {"days": 14, "price": 0, "name": "14 Days FREE", "requires_payment": False},
    "30": {"days": 30, "price": 6540, "name": "30 Days", "requires_payment": True},
    "60": {"days": 60, "price": 13090, "name": "2 Months", "requires_payment": True},
    "180": {"days": 180, "price": 39500, "name": "6 Months", "requires_payment": True},
    "365": {"days": 365, "price": 80000, "name": "1 Year", "requires_payment": True}
}

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_conn():
    if not DATABASE_URL:
        raise Exception("No DATABASE_URL")
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require')
    except ImportError:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require')

def ensure_tables():
    if not DATABASE_URL: return
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, data JSONB NOT NULL);")
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, data JSONB NOT NULL);")
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print(f"ensure_tables error: {e}")

def load_db(file, default):
    if DATABASE_URL:
        try:
            ensure_tables()
            conn = get_conn()
            try:
                from psycopg.rows import dict_row
                cur = conn.cursor(row_factory=dict_row)
                if file == 'products.json':
                    cur.execute("SELECT data FROM products ORDER BY id ASC")
                    rows = cur.fetchall()
                    cur.close(); conn.close()
                    return [r['data'] for r in rows]
                else:
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
                    row = cur.fetchone()
                    cur.close(); conn.close()
                    return row['data'] if row else default
            except Exception as e1:
                try:
                    import psycopg2.extras
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    if file == 'products.json':
                        cur.execute("SELECT data FROM products ORDER BY id ASC")
                        rows = cur.fetchall()
                        cur.close(); conn.close()
                        return [r['data'] for r in rows]
                    else:
                        cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
                        row = cur.fetchone()
                        cur.close(); conn.close()
                        return row['data'] if row else default
                except Exception as e2:
                    print(f"load_db {file} error v2 {e2} / v3 {e1}")
                    return default
        except Exception as e:
            print(f"load_db {file} error: {e}")
            return default
    path=f'data/{file}'
    if os.path.exists(path):
        try: return json.load(open(path))
        except: return default
    return default

def save_db(file, data):
    if DATABASE_URL:
        try:
            ensure_tables()
            conn = get_conn()
            cur = conn.cursor()
            try:
                from psycopg.types.json import Jsonb
                if file == 'products.json':
                    cur.execute("DELETE FROM products")
                    for item in data:
                        cur.execute("INSERT INTO products (data) VALUES (%s)", [Jsonb(item)])
                else:
                    cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, Jsonb(data)))
            except ImportError:
                import json as js
                if file == 'products.json':
                    cur.execute("DELETE FROM products")
                    for item in data:
                        cur.execute("INSERT INTO products (data) VALUES (%s)", [js.dumps(item)])
                else:
                    cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, js.dumps(data)))
            conn.commit(); cur.close(); conn.close()
            return
        except Exception as e:
            print(f"save_db {file} error: {e}")
    json.dump(data, open(f'data/{file}','w'), indent=2)

def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()

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

@app.route('/api/register', methods=['POST'])
def register():
    data=request.json
    email=data.get('email','').lower().strip(); phone=data.get('phone','').strip()
    pwd=data.get('password',''); role=data.get('role','seller'); biz=data.get('business','')
    if not email or not phone or not pwd:
        return jsonify({'success':False,'message':'Email, phone, password required'}),400
    users=load_db('users.json',[])
    if any(u['email']==email for u in users):
        return jsonify({'success':False,'message':'Email already registered - Login'}),400
    user={'id':int(time.time()*1000),'email':email,'phone':phone,'password':hash_pwd(pwd),'role':role,'business':biz,'created':time.time(),'plan':'free14','plan_name':'14 Days FREE','subscription_expires':time.time()+14*86400,'free_used':True,'paid':True}
    users.append(user); save_db('users.json',users)
    safe={k:v for k,v in user.items() if k!='password'}
    return jsonify({'success':True,'message':'Registered! 14 Days FREE active - Login now','user':safe})

@app.route('/api/login', methods=['POST'])
def login():
    data=request.json; email=data.get('email','').lower(); pwd=data.get('password','')
    users=load_db('users.json',[])
    u=next((x for x in users if x['email']==email and x['password']==hash_pwd(pwd)),None)
    if not u: return jsonify({'success':False,'message':'Wrong email/password'}),401
    safe={k:v for k,v in u.items() if k!='password'}
    safe['subscription_active']=safe['subscription_expires']>time.time()
    return jsonify({'success':True,'user':safe})

@app.route('/api/products')
def get_products():
    products=load_db('products.json', [])
    main=request.args.get('main'); sub=request.args.get('sub')
    q=request.args.get('q','').lower(); min_p=request.args.get('min'); max_p=request.args.get('max')
    new_only=request.args.get('new')
    filtered=products
    if main: filtered=[p for p in filtered if p.get('main_category')==main]
    if sub: filtered=[p for p in filtered if p.get('sub_category')==sub]
    if q: filtered=[p for p in filtered if q in p.get('name','').lower() or q in p.get('description','').lower() or q in p.get('business','').lower()]
    if min_p: filtered=[p for p in filtered if p.get('price',0)>=int(min_p)]
    if max_p: filtered=[p for p in filtered if p.get('price',0)<=int(max_p)]
    if new_only:
        cutoff=time.time()-48*3600
        filtered=[p for p in filtered if p.get('created',0)>cutoff]
        if not filtered: filtered=sorted(products,key=lambda x:x.get('created',0),reverse=True)[:50]
    filtered=sorted(filtered,key=lambda x:(x.get('boosted',0),x.get('created',0)),reverse=True)
    public=[]
    for p in filtered:
        if p.get('subscription_expires',0) < time.time(): continue
        pp=p.copy(); pp.pop('phone',None); public.append(pp)
    return jsonify(public)

@app.route('/api/sell', methods=['POST'])
def sell():
    name=request.form.get('name'); price=int(request.form.get('price',0))
    business=request.form.get('business'); location=request.form.get('location')
    phone=request.form.get('phone'); desc=request.form.get('desc','')
    main_cat=request.form.get('main_category'); sub_cat=request.form.get('sub_category')
    stock=int(request.form.get('stock',10)); plan=request.form.get('plan','free14')
    user_email=request.form.get('user_email','').lower()
    users=load_db('users.json',[]); products=load_db('products.json',[])
    seller=next((u for u in users if u['phone']==phone or u['email']==user_email),None)
    plan_info=PLANS.get(plan,PLANS['free14'])
    if plan == "free14" or not plan_info.get('requires_payment'):
        if seller and seller.get('free_used') and seller['subscription_expires'] < time.time():
            return jsonify({'success':False,'message':'14 Days FREE already used & expired. Choose paid plan and PAY BEFORE UPLOAD'}),402
        if not seller and any(p.get('phone')==phone and p.get('plan')=='free14' for p in products):
            return jsonify({'success':False,'message':'Phone already used FREE trial. Register & pay before upload'}),402
    else:
        if not seller:
            return jsonify({'success':False,'message':f'PAY BEFORE UPLOAD: Register & Pay UGX {plan_info["price"]} for {plan_info["name"]} to MoMo {OWNER_MOMO} first. Then admin activates.'}),402
        if seller['subscription_expires'] < time.time() or not seller.get('paid') or seller.get('plan')!= plan:
            return jsonify({'success':False,'message':f'PAY BEFORE UPLOAD: Your subscription expired or not paid for {plan_info["name"]}. Pay UGX {plan_info["price"]} to MoMo {OWNER_MOMO}. Submit code in Subscription popup. Wait admin activation.'}),402
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
    exp_time = seller['subscription_expires'] if seller and seller['subscription_expires']>time.time() else time.time()+plan_info['days']*86400
    prod={'id':int(time.time()*1000),'name':name,'price':price,'business':business,'location':location,'phone':phone,'seller_email':user_email,'description':desc,'image':images[0],'images':images,'main_category':main_cat,'sub_category':sub_cat,'stock':stock,'sold':0,'rating':5.0,'reviews':[],'views':0,'verified':False,'boosted':0,'bargain_allowed':True,'created':time.time(),'plan':plan,'plan_name':plan_info['name'],'plan_price':plan_info['price'],'subscription_expires':exp_time}
    if DATABASE_URL:
        try:
            ensure_tables()
            import json as js
            conn=get_conn(); cur=conn.cursor()
            try:
                from psycopg.types.json import Jsonb
                cur.execute("INSERT INTO products (data) VALUES (%s)", [Jsonb(prod)])
            except:
                cur.execute("INSERT INTO products (data) VALUES (%s)", [js.dumps(prod)])
            conn.commit(); cur.close(); conn.close()
        except Exception as e:
            print(e); return jsonify({'success':False,'message':'Upload failed - try again'}),500
    else:
        products.append(prod); save_db('products.json', products)
    return jsonify({'success':True,'message':f'Added with {plan_info["name"]} - Continuous Down'})

@app.route('/api/seller/sales')
def seller_sales():
    phone=request.args.get('phone'); email=request.args.get('email','').lower(); period=request.args.get('period','all')
    if not phone and not email: return jsonify({'success':False,'message':'Phone/email required'}),400
    orders=load_db('orders.json',[]); products=load_db('products.json',[])
    my_prods=[p for p in products if p.get('phone')==phone or p.get('seller_email')==email]
    my_ids=set(p['id'] for p in my_prods)
    my_orders=[]; now=time.time()
    for o in orders:
        if period=='today' and now-o.get('time',0)>86400: continue
        if period=='week' and now-o.get('time',0)>7*86400: continue
        if period=='month' and now-o.get('time',0)>30*86400: continue
        if period=='year' and now-o.get('time',0)>365*86400: continue
        cart=o.get('cart',[]); mine=[i for i in cart if i.get('id') in my_ids]
        if mine:
            oc=o.copy(); oc['my_items']=mine; oc['my_total']=sum(i.get('price',0) for i in mine); my_orders.append(oc)
    total=sum(o['my_total'] for o in my_orders)
    return jsonify({'success':True,'period':period,'total_sales':total,'total_orders':len(my_orders),'products_count':len(my_prods),'orders':my_orders[::-1],'products':my_prods})

@app.route('/api/my-products')
def my_products():
    phone=request.args.get('phone'); email=request.args.get('email','').lower()
    products=load_db('products.json', [])
    if phone: products=[p for p in products if p.get('phone')==phone]
    if email: products=[p for p in products if p.get('seller_email')==email or p.get('phone')==phone]
    return jsonify(products)

@app.route('/api/delete-product/<int:pid>', methods=['DELETE'])
def delete_prod(pid):
    if DATABASE_URL:
        try:
            ensure_tables()
            conn=get_conn(); cur=conn.cursor()
            cur.execute("SELECT id, data FROM products")
            rows=cur.fetchall()
            for row in rows:
                # row can be tuple or dict_row
                if isinstance(row, dict):
                    r_id, r_data = row['id'], row['data']
                else:
                    r_id, r_data = row[0], row[1]
                if isinstance(r_data, str): r_data=json.loads(r_data)
                if r_data.get('id')==pid:
                    cur.execute("DELETE FROM products WHERE id=%s", (r_id,))
                    break
            conn.commit(); cur.close(); conn.close()
        except Exception as e: print(e)
    else:
        products=load_db('products.json', []); products=[p for p in products if p['id']!=pid]; save_db('products.json', products)
    return jsonify({'success':True})

@app.route('/api/rate', methods=['POST'])
def rate():
    data=request.json; pid=data['id']; products=load_db('products.json', [])
    for p in products:
        if p['id']==pid:
            p['reviews'].append({'rating':data['rating'],'comment':data.get('comment',''),'time':time.time()})
            p['rating']=sum(r['rating'] for r in p['reviews'])/len(p['reviews'])
    save_db('products.json', products); return jsonify({'success':True})

@app.route('/api/bargain', methods=['POST'])
def bargain():
    data=request.json; bargains=load_db('bargains.json', []); data['id']=int(time.time()); data['status']='pending'; data['time']=time.time(); bargains.append(data); save_db('bargains.json', bargains)
    orders=load_db('orders.json', []); orders.append({'id':data['id'],'type':'bargain','bargain':data,'total':data.get('offer'),'buyer':{'names':data.get('buyer_name','Bargain'),'phone1':data.get('buyer_phone','')},'cart':[{'name':data.get('product_name')}],'time':time.time(),'seller_phone':data.get('seller_phone')}); save_db('orders.json', orders)
    return jsonify({'success':True,'message':"Bargain sent! Seller will reply via WhatsApp."})

@app.route('/api/boost', methods=['POST'])
def boost():
    data=request.json; pid=data['id']; products=load_db('products.json', [])
    for p in products:
        if p['id']==pid: p['boosted']=time.time()+86400*int(data.get('days',1))
    save_db('products.json', products); return jsonify({'success':True,'message':'Boosted!'})

@app.route('/api/subscribe', methods=['POST'])
def sub():
    data=request.json; sellers=load_db('sellers.json', []); users=load_db('users.json', [])
    plan=data.get('plan','30'); email=data.get('email','').lower(); phone=data.get('phone',''); momo=data.get('momo_code','')
    plan_info=PLANS.get(plan,PLANS['30'])
    for u in users:
        if u['email']==email or u['phone']==phone:
            u['plan']=plan; u['plan_name']=plan_info['name']; u['paid']=False if plan_info['requires_payment'] else True; u['momo_transaction']=momo
            if not plan_info['requires_payment']: u['subscription_expires']=time.time()+plan_info['days']*86400
    save_db('users.json',users)
    data['id']=int(time.time()); data['plan_name']=plan_info['name']; data['plan_price']=plan_info['price']; data['time']=time.time(); sellers.append(data); save_db('sellers.json',sellers)
    return jsonify({'success':True,'message':f'Request {plan_info["name"]} UGX {plan_info["price"]} received. MoMo {OWNER_MOMO} WhatsApp {OWNER_PHONE}'})

@app.route('/api/admin/activate-subscription', methods=['POST'])
def activate_sub():
    data=request.json; phone=data.get('phone'); email=data.get('email','').lower(); plan=data.get('plan')
    users=load_db('users.json',[]); products=load_db('products.json',[]); plan_info=PLANS.get(plan,PLANS['30'])
    for u in users:
        if u['phone']==phone or u['email']==email:
            u['plan']=plan; u['plan_name']=plan_info['name']; u['paid']=True; u['subscription_expires']=time.time()+plan_info['days']*86400
    save_db('users.json',users)
    for p in products:
        if p.get('phone')==phone or p.get('seller_email')==email:
            p['subscription_expires']=time.time()+plan_info['days']*86400; p['plan']=plan
    save_db('products.json',products)
    return jsonify({'success':True,'message':f'Activated {plan_info["name"]} for {phone}'})

@app.route('/api/checkout', methods=['POST'])
def checkout():
    data=request.json; orders=load_db('orders.json', []); data['id']=int(time.time()); data['status']='Packed'; data['time']=time.time(); orders.append(data); save_db('orders.json', orders)
    products=load_db('products.json', [])
    for item in data['cart']:
        for p in products:
            if p['id']==item['id']: p['stock']=max(0,p.get('stock',10)-1); p['sold']=p.get('sold',0)+1
    save_db('products.json', products); return jsonify({'message':'Order placed! ID: '+str(data['id'])})

@app.route('/api/jobs', methods=['GET','POST'])
def jobs_api():
    if request.method=='POST':
        data=request.json; data['id']=int(time.time()*1000); data['time']=time.time(); all_jobs=load_db('jobs.json', []); all_jobs.append(data); save_db('jobs.json', all_jobs); return jsonify({'success':True,'message':'Job posted!'})
    else:
        all_jobs=load_db('jobs.json', []); q=request.args.get('q','').lower(); cat=request.args.get('category','')
        if q: all_jobs=[j for j in all_jobs if q in j.get('title','').lower() or q in j.get('description','').lower()]
        if cat: all_jobs=[j for j in all_jobs if j.get('category')==cat]
        return jsonify(all_jobs[::-1])

@app.route('/api/jobs/<int:jid>/apply', methods=['POST'])
def apply_job(jid):
    data=request.json; apps=load_db('applications.json', []); data['job_id']=jid; data['id']=int(time.time()); data['time']=time.time(); apps.append(data); save_db('applications.json', apps); return jsonify({'success':True,'message':'Application sent!'})

@app.route('/api/job-applications')
def get_applications(): return jsonify(load_db('applications.json', [])[::-1])
@app.route('/api/orders')
def get_orders(): return jsonify(load_db('orders.json', [])[::-1])
@app.route('/api/contact', methods=['POST'])
def contact_owner():
    data=request.json; contacts=load_db('contacts.json', []); contacts.append({**data,'time':time.time(),'id':int(time.time()),'owner_email':OWNER_EMAIL}); save_db('contacts.json', contacts); return jsonify({'success':True,'message':f'Message sent to {OWNER_EMAIL}!'})

@app.route('/api/admin/data')
def admin_data():
    products=load_db('products.json',[]); now=time.time()
    for p in products:
        if p.get('subscription_expires',0)<now: p['expired']=True
    return jsonify({'products':products,'users':load_db('users.json',[]),'sellers':load_db('sellers.json',[]),'orders':load_db('orders.json',[]),'jobs':load_db('jobs.json',[]),'contacts':load_db('contacts.json',[]),'applications':load_db('applications.json',[]),'bargains':load_db('bargains.json',[]),'total_revenue':sum([o.get('total',0) for o in load_db('orders.json',[]) if isinstance(o.get('total'),(int,float))]),'total_sellers':len(load_db('users.json',[])),'total_orders':len(load_db('orders.json',[])),'plans':PLANS})

@app.route('/api/admin/<string:filetype>')
def admin_generic(filetype):
    allowed=['contacts','applications','orders','bargains','sellers','jobs','products','users']
    if filetype not in allowed: return jsonify([])
    return jsonify(load_db(f'{filetype}.json', []))

if __name__=='__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
