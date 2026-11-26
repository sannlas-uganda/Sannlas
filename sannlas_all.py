# sannlas_all.py - ALL IN ONE - REPLACES ALL 6 FILES
# Agents + Agency + Permissions + Commission + Owner + Agent Dashboards
from flask import Blueprint, Response, request, jsonify
import os, json, time, hashlib, random, string

sannlas_all_bp = Blueprint('sannlas_all_bp', __name__)

def load_db(file, default):
    try:
        from app import load_db as main_load
        return main_load(file, default)
    except:
        path = f'data/{file}'
        if os.path.exists(path):
            try: return json.load(open(path))
            except: return default
        return default

def save_db(file, data):
    try:
        from app import save_db as main_save
        return main_save(file, data)
    except:
        os.makedirs('data', exist_ok=True)
        json.dump(data, open(f'data/{file}','w'), indent=2)

def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()
def make_agent_code(phone):
    return f"SANN-AGENT-{phone[-4:] if len(phone)>=4 else '1234'}-{''.join(random.choices(string.ascii_uppercase+string.digits,k=4))}"

# ===== PERMISSIONS HELPER =====
def can_agent_do(agent_phone, shop_slug, action):
    perms = load_db('sannlas_permissions.json', [])
    perm = next((x for x in perms if x['agent_phone']==agent_phone and x['shop_slug'].lower()==shop_slug.lower() and x['status']=='active'), None)
    if not perm: return False, "No permission"
    if action not in perm.get('scopes',[]): return False, f"Scope {action} denied"
    return True, "Allowed"

# ===== PAGES - ONE HTML HAS BOTH DASHBOARDS =====
@sannlas_all_bp.route('/dashboard')
@sannlas_all_bp.route('/owner-dashboard')
@sannlas_all_bp.route('/agent/dashboard')
@sannlas_all_bp.route('/agency')
@sannlas_all_bp.route('/agents')
@sannlas_all_bp.route('/collaborators')
@sannlas_all_bp.route('/commission')
def all_page():
    # Load the single HTML file
    for p in ['templates/sannlas_all.html','sannlas_all.html']:
        if os.path.exists(p):
            return Response(open(p).read(), mimetype='text/html')
    return Response("Create sannlas_all.html first", mimetype='text/html')

# ===== AGENTS: REGISTER / LOGIN =====
@sannlas_all_bp.route('/api/agents/register', methods=['POST'])
def register_agent():
    d=request.json or {}; name=d.get('name','').strip(); phone=d.get('phone','').strip(); email=d.get('email','').lower().strip(); pwd=d.get('password','').strip(); roles=d.get('roles',["reseller","uploader","broker"])
    if not name or not phone or not pwd: return jsonify({'success':False,'message':'Name, phone, password required'}),400
    agents=load_db('sannlas_agents.json',[])
    if any(a['phone']==phone for a in agents): return jsonify({'success':False,'message':'Phone already registered - Login'}),400
    agent={"id":int(time.time()*1000),"name":name,"phone":phone,"email":email,"password":hash_pwd(pwd),"agent_code":make_agent_code(phone),"roles":roles,"is_reseller":"reseller" in roles,"is_uploader":"uploader" in roles,"is_broker":"broker" in roles,"status":"active","total_earned":0,"coins_sold":0,"products_uploaded":0,"sales_brokered":0,"balance":0,"created":time.time(),"last_active":time.time()}
    agents.append(agent); save_db('sannlas_agents.json',agents)
    safe={k:v for k,v in agent.items() if k!='password'}
    return jsonify({'success':True,'message':'Agent registered! Start earning Boss!','agent':safe})

@sannlas_all_bp.route('/api/agents/login', methods=['POST'])
def login_agent():
    d=request.json or {}; phone=d.get('phone','').strip(); email=d.get('email','').lower().strip(); pwd=d.get('password','').strip()
    agents=load_db('sannlas_agents.json',[])
    agent=None
    for a in agents:
        if (phone and a['phone']==phone) or (email and a.get('email','').lower()==email.lower()):
            if a['password']==hash_pwd(pwd): agent=a; break
    if not agent: return jsonify({'success':False,'message':'Wrong phone/email or password'}),401
    agent['last_active']=time.time(); save_db('sannlas_agents.json',agents)
    return jsonify({'success':True,'agent':{k:v for k,v in agent.items() if k!='password'}})

# ===== AGENTS: STATS + SHOPS + EARNINGS PER SHOP =====
@sannlas_all_bp.route('/api/agents/stats')
def agent_stats():
    phone=request.args.get('phone','').strip(); code=request.args.get('code','').strip()
    agents=load_db('sannlas_agents.json',[])
    agent=next((a for a in agents if a['phone']==phone or a['agent_code']==code),None)
    if not agent: return jsonify({'success':False,'message':'Agent not found'}),404
    comms=load_db('sannlas_commissions.json',[])
    my=[c for c in comms if c.get('agent_phone')==agent['phone']]
    total=sum(c.get('agent_amount',0) for c in my)
    coins=sum(1 for c in my if c.get('type')=='coin_resale'); uploads=sum(1 for c in my if c.get('type')=='upload'); sales=sum(1 for c in my if c.get('type')=='broker_sale')
    # Shops I manage
    perms=load_db('sannlas_permissions.json',[])
    my_perms=[p for p in perms if p.get('agent_phone')==phone and p.get('status')=='active']
    # Earnings per shop
    per_shop={}
    for c in my:
        s=c.get('shop_slug','other')
        per_shop[s]=per_shop.get(s,0)+c.get('agent_amount',0)
    agent.update({"total_earned":total,"coins_sold":coins,"products_uploaded":uploads,"sales_brokered":sales,"balance":total}); save_db('sannlas_agents.json',agents)
    return jsonify({'success':True,'agent':{k:v for k,v in agent.items() if k!='password'},'commissions':sorted(my,key=lambda x:x.get('time',0),reverse=True)[:50],'stats':{'total_earned':total,'coins_sold':coins,'products_uploaded':uploads,'sales_brokered':sales,'total_shops':len(my_perms)},'my_shops':my_perms,'earnings_per_shop':per_shop})

@sannlas_all_bp.route('/api/agents/referral-link')
def referral_link():
    phone=request.args.get('phone','').strip(); agents=load_db('sannlas_agents.json',[])
    agent=next((a for a in agents if a['phone']==phone),None)
    if not agent: return jsonify({'success':False,'message':'Agent not found'}),404
    base="https://sannlas.onrender.com"
    links={"coin_link":f"{base}/coins?ref={agent['agent_code']}","shop_link":f"{base}/?ref={agent['agent_code']}","product_link":f"{base}/?ref={agent['agent_code']}","become_agent_link":f"{base}/agents?ref={agent['agent_code']}"}
    return jsonify({'success':True,'links':links,'agent_code':agent['agent_code']})

@sannlas_all_bp.route('/api/agents/coin-sold', methods=['POST'])
def coin_sold():
    d=request.json or {}; code=d.get('agent_code','').strip(); buyer=d.get('buyer_phone','').strip(); coins=int(d.get('coins',0)); price=int(d.get('price_paid',0))
    if not code or not buyer: return jsonify({'success':False,'message':'agent_code and buyer_phone required'}),400
    agents=load_db('sannlas_agents.json',[]); agent=next((a for a in agents if a['agent_code']==code),None)
    if not agent or not agent.get('is_reseller'): return jsonify({'success':False,'message':'Invalid agent'}),404
    cut=int(price*0.15)
    comms=load_db('sannlas_commissions.json',[]); comms.append({"id":int(time.time()*1000),"agent_phone":agent['phone'],"type":"coin_resale","total_amount":price,"agent_amount":cut,"sannlas_amount":price-cut,"owner_amount":0,"meta":{"buyer_phone":buyer,"coins":coins},"time":time.time(),"status":"paid"}); save_db('sannlas_commissions.json',comms)
    return jsonify({'success':True,'message':f'Commission {cut} UGX given','agent_cut':cut})

# ===== AGENCY: MY CLIENTS / AVAILABLE / REQUEST / APPROVE =====
@sannlas_all_bp.route('/api/agency/my-clients')
def my_clients():
    phone=request.args.get('phone','').strip(); email=request.args.get('email','').lower().strip()
    perms=load_db('sannlas_permissions.json',[]); shops_db=load_db('shops.json',[])
    my_perms=[p for p in perms if p.get('agent_phone')==phone and p.get('status')=='active']
    result=[]
    for perm in my_perms:
        shop=next((s for s in shops_db if (s.get('shop_slug','') or s.get('slug','')).lower()==perm['shop_slug'].lower()),{"shop_slug":perm['shop_slug'],"business_name":perm.get('shop_name',perm['shop_slug'])})
        result.append({"permission":perm,"shop":shop,"is_my_client":True})
    if not result:
        for s in shops_db[:100]:
            slug=s.get('shop_slug') or s.get('slug') or s.get('business_name','shop')
            result.append({"permission":{"shop_slug":slug,"shop_name":s.get('business_name') or s.get('name') or 'Shop',"status":"available","scopes":["upload_product"],"products_uploaded":0,"total_earned":0,"commission_per_upload":400},"shop":s,"is_my_client":False})
    return jsonify({"success":True,"shops":result})

@sannlas_all_bp.route('/api/agency/available-shops')
def available_shops():
    shops=load_db('shops.json',[]); return jsonify({"success":True,"shops":sorted(shops,key=lambda x:x.get('total_products',0) or 0,reverse=True)[:200]})

@sannlas_all_bp.route('/api/agency/request', methods=['POST'])
def request_helper():
    d=request.json or {}; slug=d.get('shop_slug','').lower().strip(); phone=d.get('agent_phone','').strip()
    if not slug or not phone: return jsonify({"success":False,"message":"shop and phone needed"}),400
    perms=load_db('sannlas_permissions.json',[])
    if next((p for p in perms if p['agent_phone']==phone and p['shop_slug'].lower()==slug),None): return jsonify({"success":True,"message":"Already requested / already helper"})
    perms.append({"id":int(time.time()*1000),"shop_slug":slug,"shop_name":d.get('shop_name',slug),"agent_phone":phone,"agent_name":d.get('agent_name','Helper'),"owner_phone":"","scopes":["upload_product","view_products","edit_own_product"],"status":"pending","products_uploaded":0,"total_earned":0,"commission_per_upload":400,"created":time.time()}); save_db('sannlas_permissions.json',perms)
    return jsonify({"success":True,"message":f"Request sent to {slug}! Owner will approve."})

@sannlas_all_bp.route('/api/agency/pending-requests')
def pending_requests():
    owner_phone=request.args.get('owner_phone','').strip(); owner_email=request.args.get('owner_email','').lower().strip()
    perms=load_db('sannlas_permissions.json',[]); shops_db=load_db('shops.json',[])
    my_slugs=[]
    for s in shops_db:
        sl=(s.get('shop_slug') or s.get('slug') or '').lower()
        if owner_phone and (str(s.get('phone',''))==owner_phone or str(s.get('owner_phone',''))==owner_phone): my_slugs.append(sl)
        if owner_email and str(s.get('owner_email','')).lower()==owner_email: my_slugs.append(sl)
    my_slugs=list(set([s for s in my_slugs if s]))
    pending=[p for p in perms if p.get('status')=='pending' and (not my_slugs or p.get('shop_slug','').lower() in my_slugs)]
    return jsonify({"success":True,"requests":pending,"my_shops":my_slugs})

@sannlas_all_bp.route('/api/agency/approve-request', methods=['POST'])
def approve_req():
    d=request.json or {}; perms=load_db('sannlas_permissions.json',[])
    for p in perms:
        if p['shop_slug'].lower()==d.get('shop_slug','').lower() and p['agent_phone']==d.get('agent_phone','') and p.get('status')=='pending':
            p['status']='active'; p['owner_phone']=d.get('owner_phone',''); p['owner_email']=d.get('owner_email',''); p['approved_at']=time.time(); save_db('sannlas_permissions.json',perms); return jsonify({"success":True,"message":f"✅ Approved! {d.get('agent_phone')} can now upload"})
    return jsonify({"success":False,"message":"Request not found"}),404

@sannlas_all_bp.route('/api/agency/reject-request', methods=['POST'])
def reject_req():
    d=request.json or {}; perms=load_db('sannlas_permissions.json',[])
    perms=[p for p in perms if not (p['shop_slug'].lower()==d.get('shop_slug','').lower() and p['agent_phone']==d.get('agent_phone','') and p.get('status')=='pending')]; save_db('sannlas_permissions.json',perms)
    return jsonify({"success":True,"message":"❌ Rejected"})

@sannlas_all_bp.route('/api/agency/my-helpers')
def my_helpers():
    owner_phone=request.args.get('owner_phone','').strip(); perms=load_db('sannlas_permissions.json',[])
    return jsonify({"success":True,"permissions":[p for p in perms if p.get('owner_phone')==owner_phone and p.get('status')=='active']})

@sannlas_all_bp.route('/api/agency/switch', methods=['POST'])
def switch_ctx():
    d=request.json or {}; ok,reason=can_agent_do(d.get('agent_phone',''),d.get('shop_slug',''),'view_products')
    if not ok: return jsonify({"success":False,"message":reason}),403
    return jsonify({"success":True,"message":f"Switched to {d.get('shop_slug')}","active_shop":d.get('shop_slug')})

# ===== CREATE SHOP FOR SOMEONE - NEW =====
@sannlas_all_bp.route('/api/agency/create-shop-for-client', methods=['POST'])
def create_shop_for_client():
    d=request.json or {}; name=d.get('business_name','').strip(); cphone=d.get('phone','').strip(); aphone=d.get('agent_phone','').strip()
    if not name or not cphone or not aphone: return jsonify({"success":False,"message":"Business name, client phone, agent phone required"}),400
    shops=load_db('shops.json',[]); slug=name.lower().replace(' ','-').replace('/','-')
    if any((s.get('shop_slug') or s.get('slug','')).lower()==slug for s in shops): slug=f"{slug}-{cphone[-4:]}"
    new_shop={"shop_slug":slug,"slug":slug,"business_name":name,"name":name,"phone":cphone,"owner_phone":cphone,"owner_email":d.get('owner_email',''),"business_type":d.get('business_type',''),"location":d.get('location','Uganda'),"created_by_agent":aphone,"created":time.time(),"total_products":0}
    shops.append(new_shop); save_db('shops.json',shops)
    perms=load_db('sannlas_permissions.json',[])
    perms.append({"id":int(time.time()*1000),"shop_slug":slug,"shop_name":name,"agent_phone":aphone,"agent_name":d.get('agent_name','Agent'),"owner_phone":cphone,"scopes":["upload_product","view_products","edit_own_product","view_orders"],"status":"active","products_uploaded":0,"total_earned":0,"commission_per_upload":400,"created":time.time()}); save_db('sannlas_permissions.json',perms)
    return jsonify({"success":True,"message":f"✅ Shop {name} created! You are now Agent to it!","shop":new_shop,"slug":slug})

# ===== PERMISSIONS: INVITE / LIST / REVOKE =====
@sannlas_all_bp.route('/api/permissions/invite', methods=['POST'])
def invite_perm():
    d=request.json or {}; slug=d.get('shop_slug','').lower().strip(); aphone=d.get('agent_phone','').strip()
    if not slug or not aphone: return jsonify({"success":False,"message":"shop_slug and agent_phone required"}),400
    perms=load_db('sannlas_permissions.json',[])
    ex=next((p for p in perms if p['agent_phone']==aphone and p['shop_slug'].lower()==slug),None)
    if ex: ex.update({"status":"active","scopes":d.get('scopes',ex.get('scopes',[])),"commission_per_upload":d.get('commission_per_upload',400),"owner_phone":d.get('owner_phone','')}); save_db('sannlas_permissions.json',perms); return jsonify({"success":True,"message":"Collaborator updated!"})
    perms.append({"id":int(time.time()*1000),"shop_slug":slug,"shop_name":slug,"agent_phone":aphone,"agent_name":aphone,"owner_phone":d.get('owner_phone',''),"owner_email":d.get('owner_email',''),"scopes":d.get('scopes',["upload_product","view_products"]),"status":"active","products_uploaded":0,"total_earned":0,"commission_per_upload":d.get('commission_per_upload',400),"created":time.time()}); save_db('sannlas_permissions.json',perms)
    return jsonify({"success":True,"message":"✅ Collaborator added!"})

@sannlas_all_bp.route('/api/permissions/list')
def list_perm():
    slug=request.args.get('shop_slug','').lower().strip(); perms=load_db('sannlas_permissions.json',[])
    return jsonify([p for p in perms if p['shop_slug'].lower()==slug and p.get('status')=='active'])

@sannlas_all_bp.route('/api/permissions/revoke', methods=['POST'])
def revoke_perm():
    d=request.json or {}; perms=load_db('sannlas_permissions.json',[])
    for p in perms:
        if (d.get('permission_id') and p.get('id')==d.get('permission_id')) or (p['shop_slug'].lower()==d.get('shop_slug','').lower() and p['agent_phone']==d.get('agent_phone','')):
            p['status']='revoked'; save_db('sannlas_permissions.json',perms); return jsonify({"success":True,"message":"Revoked!"})
    return jsonify({"success":False,"message":"Not found"}),404

# ===== AGENCY UPLOAD AS SHOP =====
@sannlas_all_bp.route('/api/agency/upload', methods=['POST'])
def agency_upload():
    d=request.json or {}; slug=d.get('shop_slug','').lower().strip(); aphone=d.get('agent_phone','').strip(); prod=d.get('product',{})
    ok,reason=can_agent_do(aphone,slug,"upload_product")
    if not ok: return jsonify({"success":False,"message":reason}),403
    products=load_db('products.json',[]); shops=load_db('shops.json',[]); shop=next((s for s in shops if (s.get('shop_slug') or s.get('slug','')).lower()==slug),None)
    if not shop: return jsonify({"success":False,"message":"Shop not found"}),404
    np={"id":int(time.time()*1000),"name":prod.get('name',''),"price":prod.get('price',0),"description":prod.get('description',''),"image":prod.get('image',''),"category":prod.get('category','Other'),"shop_slug":slug,"business":shop.get('business_name') or shop.get('name') or slug,"seller_email":shop.get('owner_email',''),"phone":shop.get('phone',''),"uploaded_by_agent":aphone,"is_agent_upload":True,"created":time.time()}
    products.append(np); save_db('products.json',products)
    comms=load_db('sannlas_commissions.json',[]); comms.append({"id":int(time.time()*1000),"type":"upload","total_amount":500,"agent_phone":aphone,"shop_slug":slug,"agent_amount":400,"sannlas_amount":100,"owner_amount":0,"time":time.time(),"status":"completed"}); save_db('sannlas_commissions.json',comms)
    perms=load_db('sannlas_permissions.json',[])
    for p in perms:
        if p['agent_phone']==aphone and p['shop_slug'].lower()==slug: p['products_uploaded']=p.get('products_uploaded',0)+1; p['total_earned']=p.get('total_earned',0)+400
    save_db('sannlas_permissions.json',perms)
    return jsonify({"success":True,"message":"Product uploaded AS shop! +400 UGX","product":np})

# ===== COMMISSION: LIST / WITHDRAW / PROFIT / PAYOUTS =====
@sannlas_all_bp.route('/api/commission/list')
def comm_list():
    phone=request.args.get('agent_phone','').strip(); comms=load_db('sannlas_commissions.json',[])
    if phone: comms=[c for c in comms if c.get('agent_phone')==phone]
    return jsonify(sorted(comms,key=lambda x:x.get('time',0),reverse=True)[:100])

@sannlas_all_bp.route('/api/commission/withdraw', methods=['POST'])
def withdraw():
    d=request.json or {}; amt=int(d.get('amount',0) or 0); phone=d.get('agent_phone','').strip(); momo=d.get('momo_number','').strip()
    if amt<5000: return jsonify({"success":False,"message":"Min 5000 UGX"}),400
    if not momo: return jsonify({"success":False,"message":"MoMo number required"}),400
    comms=load_db('sannlas_commissions.json',[]); total=sum(c.get('agent_amount',0) for c in comms if c.get('agent_phone')==phone)
    payouts=load_db('sannlas_payouts.json',[]); already=sum(p.get('amount',0) for p in payouts if p.get('agent_phone')==phone and p.get('status') in ['pending','paid'])
    if amt>total-already: return jsonify({"success":False,"message":f"Not enough balance. Available: {total-already} UGX"}),400
    payouts.append({"id":int(time.time()*1000),"agent_phone":phone,"agent_name":phone,"amount":amt,"momo_number":momo,"status":"pending","time":time.time()}); save_db('sannlas_payouts.json',payouts)
    return jsonify({"success":True,"message":f"Withdraw request {amt} UGX sent! We will pay via MoMo."})

@sannlas_all_bp.route('/api/commission/sannlas-profit')
def profit():
    if request.args.get('key','')!='SANNLAS2026SECURE': return jsonify({"success":False,"message":"Admin key required"}),403
    comms=load_db('sannlas_commissions.json',[])
    total_profit=sum(c.get('sannlas_amount',0) for c in comms)
    return jsonify({"success":True,"stats":{"total_profit":total_profit,"from_coins":sum(c.get('sannlas_amount',0) for c in comms if c.get('type')=='coin_resale'),"from_uploads":sum(c.get('sannlas_amount',0) for c in comms if c.get('type')=='upload'),"from_sales":sum(c.get('sannlas_amount',0) for c in comms if c.get('type')=='broker_sale'),"total_sales_volume":sum(c.get('total_amount',0) for c in comms if c.get('type')=='broker_sale'),"total_coin_volume":sum(c.get('total_amount',0) for c in comms if c.get('type')=='coin_resale'),"total_uploads":sum(1 for c in comms if c.get('type')=='upload'),"total_commissions":len(comms)},"recent":sorted(comms,key=lambda x:x.get('time',0),reverse=True)[:50]})

@sannlas_all_bp.route('/api/commission/payouts')
def payouts():
    if request.args.get('key','')!='SANNLAS2026SECURE': return jsonify({"success":False,"message":"Admin key required"}),403
    payouts=load_db('sannlas_payouts.json',[]); st=request.args.get('status','')
    if st: payouts=[p for p in payouts if p.get('status')==st]
    return jsonify(sorted(payouts,key=lambda x:x.get('time',0),reverse=True))

@sannlas_all_bp.route('/api/commission/payout/approve', methods=['POST'])
def approve_payout():
    d=request.json or {}
    if d.get('key','')!='SANNLAS2026SECURE': return jsonify({"success":False,"message":"Admin key required"}),403
    payouts=load_db('sannlas_payouts.json',[])
    for p in payouts:
        if p.get('id')==d.get('payout_id'): p['status']='paid'; save_db('sannlas_payouts.json',payouts); return jsonify({"success":True,"message":"Marked paid!"})
    return jsonify({"success":False,"message":"Not found"}),404

@sannlas_all_bp.route('/api/agents/list')
def list_agents():
    if request.args.get('key','')!='SANNLAS2026SECURE': return jsonify({"success":False,"message":"Admin key required"}),403
    agents=load_db('sannlas_agents.json',[])
    return jsonify(sorted([{k:v for k,v in a.items() if k!='password'} for a in agents],key=lambda x:x.get('total_earned',0),reverse=True))
