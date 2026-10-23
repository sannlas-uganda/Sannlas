# sannlas_agents.py - SANNLAS AGENT SYSTEM - MTN STYLE
# Handles: Coin Resellers, Shop Uploaders, Sales Brokers
from flask import Blueprint, request, jsonify, render_template, session, redirect
import os, json, time, hashlib, random, string, re
from functools import wraps

sannlas_agents_bp = Blueprint('sannlas_agents', __name__)

# Use same DB functions as app.py
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
        json.dump(data, open(f'data/{file}','w'), indent=2)

def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()

AGENT_FILE = 'sannlas_agents.json'
PERM_FILE = 'sannlas_permissions.json'
COMMISSION_FILE = 'sannlas_commissions.json'

def get_agents():
    return load_db(AGENT_FILE, [])

def save_agents(a):
    save_db(AGENT_FILE, a)

def make_agent_code(phone):
    suffix = phone[-4:] if len(phone)>=4 else "1234"
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"SANN-AGENT-{suffix}-{rand}"

def make_api_key():
    return f"sk_live_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:32]}"

# ===== PUBLIC PAGES =====
@sannlas_agents_bp.route('/agents')
def agents_home():
    return render_template('sannlas_agents.html')

@sannlas_agents_bp.route('/become-agent')
def become_agent_page():
    return render_template('sannlas_agents.html')

@sannlas_agents_bp.route('/agent/dashboard')
def agent_dashboard():
    return render_template('agent_dashboard.html')

# ===== API: REGISTER AGENT =====
@sannlas_agents_bp.route('/api/agents/register', methods=['POST'])
def register_agent():
    data = request.json or {}
    name = data.get('name','').strip()
    phone = data.get('phone','').strip()
    email = data.get('email','').lower().strip()
    pwd = data.get('password','').strip()
    roles = data.get('roles', ["reseller","uploader","broker"]) # can be all
    
    if not name or not phone or not pwd:
        return jsonify({'success':False,'message':'Name, phone, password required'}),400
    
    agents = get_agents()
    if any(a['phone']==phone for a in agents):
        return jsonify({'success':False,'message':'Phone already registered as agent - Login'}),400
    if email and any(a.get('email','').lower()==email.lower() for a in agents if a.get('email')):
        return jsonify({'success':False,'message':'Email already registered'}),400
    
    agent = {
        "id": int(time.time()*1000),
        "name": name,
        "phone": phone,
        "email": email,
        "password": hash_pwd(pwd),
        "agent_code": make_agent_code(phone),
        "api_key": make_api_key(),
        "roles": roles, # ["reseller","uploader","broker"]
        "is_reseller": "reseller" in roles,
        "is_uploader": "uploader" in roles,
        "is_broker": "broker" in roles,
        "status": "active",
        "total_earned": 0,
        "total_commission": 0,
        "coins_sold": 0,
        "products_uploaded": 0,
        "sales_brokered": 0,
        "balance": 0, # UGX + coins value
        "created": time.time(),
        "last_active": time.time()
    }
    agents.append(agent)
    save_agents(agents)
    
    safe = {k:v for k,v in agent.items() if k!='password'}
    return jsonify({'success':True,'message':'Agent registered! Start earning Boss!','agent':safe})

# ===== API: LOGIN AGENT =====
@sannlas_agents_bp.route('/api/agents/login', methods=['POST'])
def login_agent():
    data = request.json or {}
    phone = data.get('phone','').strip()
    email = data.get('email','').lower().strip()
    pwd = data.get('password','').strip()
    
    agents = get_agents()
    agent = None
    for a in agents:
        if (phone and a['phone']==phone) or (email and a.get('email','').lower()==email.lower()):
            if a['password']==hash_pwd(pwd):
                agent = a
                break
    if not agent:
        return jsonify({'success':False,'message':'Wrong phone/email or password'}),401
    
    agent['last_active'] = time.time()
    save_agents(agents)
    
    safe = {k:v for k,v in agent.items() if k!='password'}
    return jsonify({'success':True,'agent':safe})

# ===== API: GET AGENT STATS =====
@sannlas_agents_bp.route('/api/agents/stats')
def agent_stats():
    phone = request.args.get('phone','').strip()
    code = request.args.get('code','').strip()
    
    agents = get_agents()
    agent = next((a for a in agents if a['phone']==phone or a['agent_code']==code), None)
    if not agent:
        return jsonify({'success':False,'message':'Agent not found'}),404
    
    commissions = load_db(COMMISSION_FILE, [])
    my_comms = [c for c in commissions if c.get('agent_phone')==agent['phone']]
    
    total_earned = sum(c.get('agent_amount',0) for c in my_comms)
    coins_sold = sum(1 for c in my_comms if c.get('type')=='coin_resale')
    uploads = sum(1 for c in my_comms if c.get('type')=='upload')
    sales = sum(1 for c in my_comms if c.get('type')=='broker_sale')
    
    # Update agent
    agent['total_earned'] = total_earned
    agent['coins_sold'] = coins_sold
    agent['products_uploaded'] = uploads
    agent['sales_brokered'] = sales
    agent['balance'] = total_earned
    save_agents(agents)
    
    return jsonify({
        'success':True,
        'agent': {k:v for k,v in agent.items() if k!='password'},
        'commissions': sorted(my_comms, key=lambda x: x.get('time',0), reverse=True)[:50],
        'stats': {
            'total_earned': total_earned,
            'coins_sold': coins_sold,
            'products_uploaded': uploads,
            'sales_brokered': sales
        }
    })

# ===== API: GENERATE REFERRAL LINK =====
@sannlas_agents_bp.route('/api/agents/referral-link')
def referral_link():
    phone = request.args.get('phone','').strip()
    agents = get_agents()
    agent = next((a for a in agents if a['phone']==phone), None)
    if not agent:
        return jsonify({'success':False,'message':'Agent not found'}),404
    
    base_url = "https://sannlas.onrender.com"
    links = {
        "coin_link": f"{base_url}/coins?ref={agent['agent_code']}",
        "shop_link": f"{base_url}/?ref={agent['agent_code']}",
        "product_link": f"{base_url}/?ref={agent['agent_code']}&promo={agent['agent_code']}",
        "become_agent_link": f"{base_url}/agents?ref={agent['agent_code']}"
    }
    return jsonify({'success':True,'links':links,'agent_code':agent['agent_code']})

# ===== API: RECORD COMMISSION (Called by other systems) =====
def record_commission(agent_phone, type_, amount, agent_amount, sannlas_amount, meta=None):
    """Type: coin_resale, upload, broker_sale"""
    commissions = load_db(COMMISSION_FILE, [])
    entry = {
        "id": int(time.time()*1000) + random.randint(1,999),
        "agent_phone": agent_phone,
        "type": type_,
        "total_amount": amount,
        "agent_amount": agent_amount,
        "sannlas_amount": sannlas_amount,
        "meta": meta or {},
        "time": time.time(),
        "status": "paid"
    }
    commissions.append(entry)
    save_db(COMMISSION_FILE, commissions)
    # Update agent balance
    agents = get_agents()
    for a in agents:
        if a['phone']==agent_phone:
            a['total_earned'] = a.get('total_earned',0) + agent_amount
            a['balance'] = a.get('balance',0) + agent_amount
            break
    save_agents(agents)
    return entry

# ===== API: COIN RESALE - WHEN USER BUYS VIA AGENT LINK =====
@sannlas_agents_bp.route('/api/agents/coin-sold', methods=['POST'])
def coin_sold_via_agent():
    data = request.json or {}
    agent_code = data.get('agent_code','').strip()
    buyer_phone = data.get('buyer_phone','').strip()
    coins = int(data.get('coins',0))
    price_paid = int(data.get('price_paid',0)) # e.g. 5990 for 10 coins
    
    if not agent_code or not buyer_phone:
        return jsonify({'success':False,'message':'agent_code and buyer_phone required'}),400
    
    agents = get_agents()
    agent = next((a for a in agents if a['agent_code']==agent_code), None)
    if not agent or not agent.get('is_reseller'):
        return jsonify({'success':False,'message':'Invalid agent code'}),404
    
    # COMMISSION: 15% to agent, 85% to Sannlas
    agent_cut = int(price_paid * 0.15)
    sannlas_cut = price_paid - agent_cut
    
    record_commission(agent['phone'], 'coin_resale', price_paid, agent_cut, sannlas_cut, 
                      meta={"buyer_phone":buyer_phone,"coins":coins,"agent_code":agent_code})
    
    return jsonify({'success':True,'message':f'Commission {agent_cut} UGX given to agent','agent_cut':agent_cut})

# ===== API: LIST ALL AGENTS (ADMIN) =====
@sannlas_agents_bp.route('/api/agents/list')
def list_agents():
    # Simple admin check via query
    key = request.args.get('key','')
    if key != 'SANNLAS2026SECURE':
        return jsonify({'success':False,'message':'Admin key required'}),403
    agents = get_agents()
    safe = [{k:v for k,v in a.items() if k!='password'} for a in agents]
    return jsonify(sorted(safe, key=lambda x: x.get('total_earned',0), reverse=True))
