# ============================================================
# SANNLAS AGENTS - ALL IN ONE
# File: sannlas_agents.py
# Contains: Agents + Agency + Permissions + Commission
# HTML File: templates/sannlas_agents.html
# ============================================================
from flask import Blueprint, Response, request, jsonify
import os
import json
import time
import hashlib
import random
import string

# ------------------------------------------------------------
# 1. SETUP
# ------------------------------------------------------------
sannlas_agents_bp = Blueprint('sannlas_agents_bp', __name__)

# ------------------------------------------------------------
# 2. DATABASE HELPERS - Uses app.py load_db / save_db
# ------------------------------------------------------------
def load_db(file, default):
    try:
        from app import load_db as main_load
        return main_load(file, default)
    except Exception:
        path = f'data/{file}'
        if os.path.exists(path):
            try:
                return json.load(open(path))
            except Exception:
                return default
        return default

def save_db(file, data):
    try:
        from app import save_db as main_save
        return main_save(file, data)
    except Exception:
        os.makedirs('data', exist_ok=True)
        json.dump(data, open(f'data/{file}', 'w'), indent=2)

def hash_pwd(password):
    return hashlib.sha256(password.encode()).hexdigest()

def make_agent_code(phone_or_email):
    base = str(phone_or_email or '1234')
    # If email like stephen@gmail.com -> take first 4 letters "STEP"
    # If phone like 0795712326 -> take last 4 "2326"
    if '@' in base:
        last4 = base.split('@')[0][:4].upper()
    else:
        last4 = base[-4:] if len(base) >= 4 else '1234'
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"SANN-AGENT-{last4}-{rand}"

def hide_password(agent):
    return {k: v for k, v in agent.items() if k != 'password'}

# ------------------------------------------------------------
# 3. PERMISSION HELPER - Can agent do this action?
# ------------------------------------------------------------
# --- NEW SECURE ONE ---
VALID_SCOPES = ["upload_product","view_products","view_orders","edit_own_product","delete_own_product"]

def can_agent_do(agent_phone, shop_slug, action):
    perms = load_db('sannlas_permissions.json', [])
    perm = next(
        (x for x in perms
         if x['agent_phone'] == agent_phone
         and x['shop_slug'].lower() == shop_slug.lower()
         and x['status'] == 'active'),
        None
    )
    if not perm:
        return False, "No permission for this shop"
    if action not in perm.get('scopes', []):
        return False, f"Scope {action} not allowed. Your scopes: {perm.get('scopes')}"
    if perm.get('expires_at') and time.time() > perm['expires_at']:
        return False, "Permission expired"
    return True, "Allowed"

# ------------------------------------------------------------
# 4. PAGES - One HTML has BOTH dashboards (Agent + Owner)
# ------------------------------------------------------------
@sannlas_agents_bp.route('/dashboard')
@sannlas_agents_bp.route('/owner-dashboard')
@sannlas_agents_bp.route('/agent/dashboard')
@sannlas_agents_bp.route('/agency')
@sannlas_agents_bp.route('/agents')
@sannlas_agents_bp.route('/collaborators')
@sannlas_agents_bp.route('/commission')
def all_page():
    # FIXED: Now looks for sannlas_agents.html (not all.html)
    for path in ['templates/sannlas_agents.html', 'sannlas_agents.html']:
        if os.path.exists(path):
            return Response(open(path).read(), mimetype='text/html')
    return Response("Create sannlas_agents.html first", mimetype='text/html')

# ============================================================
# 5. AGENTS - REGISTER / LOGIN
# ============================================================
@sannlas_agents_bp.route('/api/agents/register', methods=['POST'])
def register_agent():
    d = request.json or {}
    name = d.get('name', '').strip()
    phone = d.get('phone', '').strip()
    email = d.get('email', '').lower().strip()
    pwd = d.get('password', '').strip()
    roles = d.get('roles', ["reseller", "uploader", "broker"])

    # EMAIL IS NOW REQUIRED - PHONE IS OPTIONAL
    if not name or not email or not pwd:
        return jsonify({'success': False, 'message': 'Name, Email, Password required'}), 400

    if '@' not in email or '.' not in email:
        return jsonify({'success': False, 'message': 'Enter valid email e.g. stephen@gmail.com'}), 400

    agents = load_db('sannlas_agents.json', [])

    # Check EMAIL duplicate - not phone!
    if any(a.get('email', '').lower() == email for a in agents if a.get('email')):
        return jsonify({'success': False, 'message': 'Email already registered - Login instead'}), 400

    # Phone duplicate only if phone given
    if phone and any(a.get('phone') == phone for a in agents if a.get('phone')):
        return jsonify({'success': False, 'message': 'Phone already used - Use different phone or leave empty'}), 400

    agent = {
        "id": int(time.time() * 1000),
        "name": name,
        "phone": phone,
        "email": email,
        "password": hash_pwd(pwd),
        "agent_code": make_agent_code(phone or email),
        "roles": roles,
        "is_reseller": "reseller" in roles,
        "is_uploader": "uploader" in roles,
        "is_broker": "broker" in roles,
        "status": "active",
        "total_earned": 0,
        "coins_sold": 0,
        "products_uploaded": 0,
        "sales_brokered": 0,
        "balance": 0,
        "created": time.time(),
        "last_active": time.time()
    }
    agents.append(agent)
    save_db('sannlas_agents.json', agents)
    return jsonify({'success': True, 'message': 'Agent registered with Email! Start earning Boss!', 'agent': hide_password(agent)})

@sannlas_agents_bp.route('/api/agents/login', methods=['POST'])
def login_agent():
    d = request.json or {}
    phone = d.get('phone', '').strip()
    email = d.get('email', '').lower().strip()
    pwd = d.get('password', '').strip()

    agents = load_db('sannlas_agents.json', [])
    agent = None
    for a in agents:
        # EMAIL FIRST - main login
        email_match = email and a.get('email', '').lower() == email
        # Phone still works for old users
        phone_match = phone and a.get('phone') == phone
        if (email_match or phone_match) and a['password'] == hash_pwd(pwd):
            agent = a
            break

    if not agent:
        return jsonify({'success': False, 'message': 'Wrong email or password'}), 401

    agent['last_active'] = time.time()
    save_db('sannlas_agents.json', agents)
    return jsonify({'success': True, 'agent': hide_password(agent)})

# ============================================================
# 6. AGENTS - STATS / REFERRAL / COIN SOLD
# ============================================================
@sannlas_agents_bp.route('/api/agents/stats')
def agent_stats():
    phone = request.args.get('phone', '').strip()
    email = request.args.get('email', '').lower().strip()
    code = request.args.get('code', '').strip()
    agents = load_db('sannlas_agents.json', [])
    agent = next((a for a in agents if (phone and a.get('phone') == phone) or (email and a.get('email','').lower() == email) or (code and a.get('agent_code') == code)), None)
    if not agent:
        return jsonify({'success': False, 'message': 'Agent not found'}), 404

    comms = load_db('sannlas_commissions.json', [])
    my = [c for c in comms if c.get('agent_phone') == agent['phone']]

    total = sum(c.get('agent_amount', 0) for c in my)
    coins = sum(1 for c in my if c.get('type') == 'coin_resale')
    uploads = sum(1 for c in my if c.get('type') == 'upload')
    sales = sum(1 for c in my if c.get('type') == 'broker_sale')

    perms = load_db('sannlas_permissions.json', [])
    my_perms = [p for p in perms if p.get('agent_phone') == phone and p.get('status') == 'active']

    # Earnings per shop
    per_shop = {}
    for c in my:
        s = c.get('shop_slug', 'other')
        per_shop[s] = per_shop.get(s, 0) + c.get('agent_amount', 0)

    agent.update({
        "total_earned": total,
        "coins_sold": coins,
        "products_uploaded": uploads,
        "sales_brokered": sales,
        "balance": total
    })
    save_db('sannlas_agents.json', agents)

    return jsonify({
        'success': True,
        'agent': hide_password(agent),
        'commissions': sorted(my, key=lambda x: x.get('time', 0), reverse=True)[:50],
        'stats': {
            'total_earned': total,
            'coins_sold': coins,
            'products_uploaded': uploads,
            'sales_brokered': sales,
            'total_shops': len(my_perms)
        },
        'my_shops': my_perms,
        'earnings_per_shop': per_shop
    })

@sannlas_agents_bp.route('/api/agents/referral-link')
def referral_link():
    phone = request.args.get('phone', '').strip()
    email = request.args.get('email', '').lower().strip()
    agents = load_db('sannlas_agents.json', [])
    agent = next((a for a in agents if (phone and a.get('phone') == phone) or (email and a.get('email','').lower() == email)), None)
    if not agent:
        return jsonify({'success': False, 'message': 'Agent not found'}), 404

    base = "https://sannlas.store"
    links = {
        "coin_link": f"{base}/coins?ref={agent['agent_code']}",
        "shop_link": f"{base}/?ref={agent['agent_code']}",
        "product_link": f"{base}/?ref={agent['agent_code']}",
        "become_agent_link": f"{base}/agents?ref={agent['agent_code']}"
    }
    return jsonify({'success': True, 'links': links, 'agent_code': agent['agent_code']})

@sannlas_agents_bp.route('/api/agents/coin-sold', methods=['POST'])
def coin_sold():
    d = request.json or {}
    code = d.get('agent_code', '').strip()
    buyer = d.get('buyer_phone', '').strip()
    coins = int(d.get('coins', 0))
    price = int(d.get('price_paid', 0))

    if not code or not buyer:
        return jsonify({'success': False, 'message': 'agent_code and buyer_phone required'}), 400

    agents = load_db('sannlas_agents.json', [])
    agent = next((a for a in agents if a['agent_code'] == code), None)
    if not agent or not agent.get('is_reseller'):
        return jsonify({'success': False, 'message': 'Invalid agent'}), 404

    cut = int(price * 0.15)  # Agent gets 15%
    comms = load_db('sannlas_commissions.json', [])
    comms.append({
        "id": int(time.time() * 1000),
        "agent_phone": agent['phone'],
        "type": "coin_resale",
        "total_amount": price,
        "agent_amount": cut,
        "sannlas_amount": price - cut,
        "owner_amount": 0,
        "meta": {"buyer_phone": buyer, "coins": coins},
        "time": time.time(),
        "status": "paid"
    })
    save_db('sannlas_commissions.json', comms)
    return jsonify({'success': True, 'message': f'Commission {cut} UGX given', 'agent_cut': cut})

@sannlas_agents_bp.route('/api/agents/list')
def list_agents():
    if request.args.get('key', '') != 'SANNLAS2026SECURE':
        return jsonify({"success": False, "message": "Admin key required"}), 403
    agents = load_db('sannlas_agents.json', [])
    clean = [hide_password(a) for a in agents]
    return jsonify(sorted(clean, key=lambda x: x.get('total_earned', 0), reverse=True))

# ============================================================
# 7. AGENCY - MY CLIENTS / AVAILABLE / REQUEST / APPROVE
# ============================================================
@sannlas_agents_bp.route('/api/agency/my-clients')
def my_clients():
    phone = request.args.get('phone', '').strip()
    email = request.args.get('email', '').lower().strip()

    perms = load_db('sannlas_permissions.json', [])
    shops_db = load_db('shops.json', [])
    my_perms = [p for p in perms if p.get('agent_phone') == phone and p.get('status') == 'active']

    result = []
    for perm in my_perms:
        shop = next(
            (s for s in shops_db if (s.get('shop_slug', '') or s.get('slug', '')).lower() == perm['shop_slug'].lower()),
            {"shop_slug": perm['shop_slug'], "business_name": perm.get('shop_name', perm['shop_slug'])}
        )
        result.append({"permission": perm, "shop": shop, "is_my_client": True})

    # If agent has 0 shops, show available shops to request
    if not result:
        for s in shops_db[:100]:
            slug = s.get('shop_slug') or s.get('slug') or s.get('business_name', 'shop')
            result.append({
                "permission": {
                    "shop_slug": slug,
                    "shop_name": s.get('business_name') or s.get('name') or 'Shop',
                    "status": "available",
                    "scopes": ["upload_product"],
                    "products_uploaded": 0,
                    "total_earned": 0,
                    "commission_per_upload": 400
                },
                "shop": s,
                "is_my_client": False
            })
    return jsonify({"success": True, "shops": result})

@sannlas_agents_bp.route('/api/agency/available-shops')
def available_shops():
    shops = load_db('shops.json', [])
    sorted_shops = sorted(shops, key=lambda x: x.get('total_products', 0) or 0, reverse=True)[:200]
    return jsonify({"success": True, "shops": sorted_shops})

@sannlas_agents_bp.route('/api/agency/request', methods=['POST'])
def request_helper():
    d = request.json or {}
    slug = d.get('shop_slug', '').lower().strip()
    phone = d.get('agent_phone', '').strip()
    if not slug or not phone:
        return jsonify({"success": False, "message": "shop and phone needed"}), 400

    perms = load_db('sannlas_permissions.json', [])
    exists = next((p for p in perms if p['agent_phone'] == phone and p['shop_slug'].lower() == slug), None)
    if exists:
        return jsonify({"success": True, "message": "Already requested / already helper"})

    perms.append({
        "id": int(time.time() * 1000),
        "shop_slug": slug,
        "shop_name": d.get('shop_name', slug),
        "agent_phone": phone,
        "agent_name": d.get('agent_name', 'Helper'),
        "owner_phone": "",
        "scopes": ["upload_product", "view_products", "edit_own_product"],
        "status": "pending",
        "products_uploaded": 0,
        "total_earned": 0,
        "commission_per_upload": 400,
        "created": time.time()
    })
    save_db('sannlas_permissions.json', perms)
    return jsonify({"success": True, "message": f"Request sent to {slug}! Owner will approve."})

@sannlas_agents_bp.route('/api/agency/pending-requests')
def pending_requests():
    owner_phone = request.args.get('owner_phone', '').strip()
    owner_email = request.args.get('owner_email', '').lower().strip()

    perms = load_db('sannlas_permissions.json', [])
    shops_db = load_db('shops.json', [])

    my_slugs = []
    for s in shops_db:
        sl = (s.get('shop_slug') or s.get('slug') or '').lower()
        if not sl:
            continue
        if owner_phone and (str(s.get('phone', '')) == owner_phone or str(s.get('owner_phone', '')) == owner_phone):
            my_slugs.append(sl)
        if owner_email and str(s.get('owner_email', '')).lower() == owner_email:
            my_slugs.append(sl)
    my_slugs = list(set(my_slugs))

    pending = [p for p in perms if p.get('status') == 'pending' and (not my_slugs or p.get('shop_slug', '').lower() in my_slugs)]
    return jsonify({"success": True, "requests": pending, "my_shops": my_slugs})

@sannlas_agents_bp.route('/api/agency/approve-request', methods=['POST'])
def approve_req():
    d = request.json or {}
    perms = load_db('sannlas_permissions.json', [])
    for p in perms:
        if p['shop_slug'].lower() == d.get('shop_slug', '').lower() and p['agent_phone'] == d.get('agent_phone', '') and p.get('status') == 'pending':
            p['status'] = 'active'
            p['owner_phone'] = d.get('owner_phone', '')
            p['owner_email'] = d.get('owner_email', '')
            p['approved_at'] = time.time()
            save_db('sannlas_permissions.json', perms)
            return jsonify({"success": True, "message": f"✅ Approved! {d.get('agent_phone')} can now upload"})
    return jsonify({"success": False, "message": "Request not found"}), 404

@sannlas_agents_bp.route('/api/agency/reject-request', methods=['POST'])
def reject_req():
    d = request.json or {}
    perms = load_db('sannlas_permissions.json', [])
    perms = [p for p in perms if not (
        p['shop_slug'].lower() == d.get('shop_slug', '').lower()
        and p['agent_phone'] == d.get('agent_phone', '')
        and p.get('status') == 'pending'
    )]
    save_db('sannlas_permissions.json', perms)
    return jsonify({"success": True, "message": "❌ Rejected"})

@sannlas_agents_bp.route('/api/agency/my-helpers')
def my_helpers():
    owner_phone = request.args.get('owner_phone', '').strip()
    perms = load_db('sannlas_permissions.json', [])
    active = [p for p in perms if p.get('owner_phone') == owner_phone and p.get('status') == 'active']
    return jsonify({"success": True, "permissions": active})

@sannlas_agents_bp.route('/api/agency/switch', methods=['POST'])
def switch_ctx():
    d = request.json or {}
    ok, reason = can_agent_do(d.get('agent_phone', ''), d.get('shop_slug', ''), 'view_products')
    if not ok:
        return jsonify({"success": False, "message": reason}), 403
    return jsonify({"success": True, "message": f"Switched to {d.get('shop_slug')}", "active_shop": d.get('shop_slug')})

# ============================================================
# 8. CREATE SHOP FOR SOMEONE - Client has no shop yet
# ============================================================
@sannlas_agents_bp.route('/api/agency/create-shop-for-client', methods=['POST'])
def create_shop_for_client():
    d = request.json or {}
    name = d.get('business_name', '').strip()
    cphone = d.get('phone', '').strip() or d.get('owner_phone', '').strip()
    cemail = d.get('owner_email', '').lower().strip() or d.get('email', '').lower().strip()
    cpwd = d.get('owner_password', '').strip()
    aphone = d.get('agent_phone', '').strip()

    # EMAIL + PASSWORD NOW REQUIRED - Owner must login later!
    if not name or not cemail or not cpwd or not aphone:
        return jsonify({"success": False, "message": "Business name, Owner Email, Owner Password, Agent required! Owner needs email to login later!"}), 400
    if '@' not in cemail:
        return jsonify({"success": False, "message": "Enter valid Owner Email e.g. aminah@gmail.com"}), 400

    shops = load_db('shops.json', [])
    slug = name.lower().replace(' ', '-').replace('/', '-')
    if any((s.get('shop_slug') or s.get('slug', '')).lower() == slug for s in shops):
        slug = f"{slug}-{cphone[-4:]}"

       new_shop = {
        "shop_slug": slug,
        "slug": slug,
        "business_name": name,
        "name": name,
        "phone": cphone,
        "owner_phone": cphone,
        "owner_email": cemail,
        "owner_password": hash_pwd(cpwd),
        "email": cemail,
        "business_type": d.get('business_type', ''),
        "location": d.get('location', 'Uganda'),
        "created_by_agent": aphone,
        "created": time.time(),
        "total_products": 0
    }
    shops.append(new_shop)
    save_db('shops.json', shops)

    # Auto make agent = collaborator
    perms = load_db('sannlas_permissions.json', [])
    perms.append({
        "id": int(time.time() * 1000),
        "shop_slug": slug,
        "shop_name": name,
        "agent_phone": aphone,
        "agent_name": d.get('agent_name', 'Agent'),
        "owner_phone": cphone,
        "scopes": ["upload_product", "view_products", "edit_own_product", "view_orders"],
        "status": "active",
        "products_uploaded": 0,
        "total_earned": 0,
        "commission_per_upload": 400,
        "created": time.time()
    })
    save_db('sannlas_permissions.json', perms)
    return jsonify({"success": True, "message": f"✅ Shop {name} created! Owner can login with {cemail} / password you set!", "shop": {k:v for k,v in new_shop.items() if k != 'owner_password'}, "slug": slug, "owner_email": cemail, "owner_login": f"Email: {cemail} | Password: (you set it)"})

# ============================================================
# 9. PERMISSIONS - INVITE / LIST / REVOKE
# ============================================================
@sannlas_agents_bp.route('/api/permissions/invite', methods=['POST'])
def invite_perm():
    d = request.json or {}
    slug = d.get('shop_slug', '').lower().strip()
    owner_phone = d.get('owner_phone', '').strip()
    owner_email = d.get('owner_email', '').lower().strip()
    aphone = d.get('agent_phone', '').strip()
    scopes = d.get('scopes', ["upload_product", "view_products", "edit_own_product"])
    commission_per_upload = int(d.get('commission_per_upload', 400))
    commission_percent = d.get('commission_percent', 0)

    if not slug or not aphone:
        return jsonify({"success": False, "message": "shop_slug and agent_phone required"}), 400

    # 1. Shop must exist
    shops = load_db('shops.json', [])
    shop = next((s for s in shops if s.get('shop_slug', '').lower() == slug or s.get('slug', '').lower() == slug), None)
    if not shop:
        return jsonify({"success": False, "message": "Shop not found"}), 404

    # 2. Only REAL owner can invite
    shop_owner_phone = shop.get('phone', '')
    shop_owner_email = shop.get('owner_email', '').lower()
    if owner_phone and shop_owner_phone and owner_phone != shop_owner_phone:
        if not (owner_email and shop_owner_email and owner_email == shop_owner_email):
            return jsonify({"success": False, "message": "You are not shop owner"}), 403

    # 3. Agent must exist + must be uploader
    agents = load_db('sannlas_agents.json', [])
    agent = next((a for a in agents if a['phone'] == aphone), None)
    if not agent:
        return jsonify({"success": False, "message": "Agent not found. Ask him to register at /agents"}), 404
    if not agent.get('is_uploader'):
        return jsonify({"success": False, "message": "This user is not registered as uploader. Tell him to enable uploader role at /agents"}), 400

    # 4. Only SAFE scopes
    safe_scopes = [s for s in scopes if s in VALID_SCOPES]
    if not safe_scopes:
        safe_scopes = ["upload_product", "view_products"]

    perms = load_db('sannlas_permissions.json', [])
    ex = next((p for p in perms if p['agent_phone'] == aphone and p['shop_slug'].lower() == slug and p.get('status') == 'active'), None)
    if ex:
        return jsonify({"success": False, "message": "Agent already has access to this shop", "permission": ex}), 400

    new_perm = {
        "id": int(time.time() * 1000),
        "shop_slug": slug,
        "shop_name": shop.get('business_name') or shop.get('name') or slug,
        "owner_phone": owner_phone or shop_owner_phone,
        "owner_email": owner_email or shop_owner_email,
        "agent_phone": aphone,
        "agent_name": agent.get('name', ''),
        "agent_code": agent.get('agent_code', ''),
        "scopes": safe_scopes,
        "commission_per_upload": commission_per_upload,
        "commission_percent": commission_percent,
        "status": "active",
        "products_uploaded": 0,
        "total_earned": 0,
        "created": time.time(),
        "expires_at": None,
        "created_by": owner_phone or owner_email
    }
    perms.append(new_perm)
    save_db('sannlas_permissions.json', perms)
    return jsonify({"success": True, "message": f"Agent {agent['name']} can now upload to {slug} - CANNOT edit shop details! Scopes: {safe_scopes}", "permission": new_perm})
    
@sannlas_agents_bp.route('/api/permissions/list')
def list_perm():
    slug = request.args.get('shop_slug', '').lower().strip()
    perms = load_db('sannlas_permissions.json', [])
    return jsonify([p for p in perms if p['shop_slug'].lower() == slug and p.get('status') == 'active'])

@sannlas_agents_bp.route('/api/permissions/revoke', methods=['POST'])
def revoke_perm():
    d = request.json or {}
    perms = load_db('sannlas_permissions.json', [])
    for p in perms:
        by_id = d.get('permission_id') and p.get('id') == d.get('permission_id')
        by_phone = p['shop_slug'].lower() == d.get('shop_slug', '').lower() and p['agent_phone'] == d.get('agent_phone', '')
        if by_id or by_phone:
            p['status'] = 'revoked'
            save_db('sannlas_permissions.json', perms)
            return jsonify({"success": True, "message": "Revoked!"})
    return jsonify({"success": False, "message": "Not found"}), 404

# ============================================================
# 10. AGENCY UPLOAD AS SHOP - Agent uploads, gets 400 UGX
# ============================================================
@sannlas_agents_bp.route('/api/agency/upload', methods=['POST'])
def agency_upload():
    d = request.json or {}
    slug = d.get('shop_slug', '').lower().strip()
    aphone = d.get('agent_phone', '').strip()
    prod = d.get('product', {})

    ok, reason = can_agent_do(aphone, slug, "upload_product")
    if not ok:
        return jsonify({"success": False, "message": reason}), 403

    products = load_db('products.json', [])
    shops = load_db('shops.json', [])
    shop = next((s for s in shops if (s.get('shop_slug') or s.get('slug', '')).lower() == slug), None)
    if not shop:
        return jsonify({"success": False, "message": "Shop not found"}), 404

    new_product = {
        "id": int(time.time() * 1000),
        "name": prod.get('name', ''),
        "price": prod.get('price', 0),
        "description": prod.get('description', ''),
        "image": prod.get('image', ''),
        "category": prod.get('category', 'Other'),
        "shop_slug": slug,
        "business": shop.get('business_name') or shop.get('name') or slug,
        "seller_email": shop.get('owner_email', ''),
        "phone": shop.get('phone', ''),
        "uploaded_by_agent": aphone,
        "is_agent_upload": True,
        "created": time.time()
    }
    products.append(new_product)
    save_db('products.json', products)

    # Commission: Agent 400 / Sannlas 100
    comms = load_db('sannlas_commissions.json', [])
    comms.append({
        "id": int(time.time() * 1000),
        "type": "upload",
        "total_amount": 500,
        "agent_phone": aphone,
        "shop_slug": slug,
        "agent_amount": 400,
        "sannlas_amount": 100,
        "owner_amount": 0,
        "time": time.time(),
        "status": "completed"
    })
    save_db('sannlas_commissions.json', comms)

    perms = load_db('sannlas_permissions.json', [])
    for p in perms:
        if p['agent_phone'] == aphone and p['shop_slug'].lower() == slug:
            p['products_uploaded'] = p.get('products_uploaded', 0) + 1
            p['total_earned'] = p.get('total_earned', 0) + 400
    save_db('sannlas_permissions.json', perms)
    return jsonify({"success": True, "message": "Product uploaded AS shop! +400 UGX", "product": new_product})

# ============================================================
# 11. COMMISSION - LIST / WITHDRAW / PROFIT / PAYOUTS
# ============================================================
@sannlas_agents_bp.route('/api/commission/list')
def comm_list():
    phone = request.args.get('agent_phone', '').strip()
    comms = load_db('sannlas_commissions.json', [])
    if phone:
        comms = [c for c in comms if c.get('agent_phone') == phone]
    return jsonify(sorted(comms, key=lambda x: x.get('time', 0), reverse=True)[:100])

@sannlas_agents_bp.route('/api/commission/withdraw', methods=['POST'])
def withdraw():
    d = request.json or {}
    amt = int(d.get('amount', 0) or 0)
    phone = d.get('agent_phone', '').strip()
    momo = d.get('momo_number', '').strip()

    if amt < 5000:
        return jsonify({"success": False, "message": "Min 5000 UGX"}), 400
    if not momo:
        return jsonify({"success": False, "message": "MoMo number required"}), 400

    comms = load_db('sannlas_commissions.json', [])
    total = sum(c.get('agent_amount', 0) for c in comms if c.get('agent_phone') == phone)
    payouts = load_db('sannlas_payouts.json', [])
    already = sum(p.get('amount', 0) for p in payouts if p.get('agent_phone') == phone and p.get('status') in ['pending', 'paid'])
    if amt > total - already:
        return jsonify({"success": False, "message": f"Not enough balance. Available: {total - already} UGX"}), 400

    payouts.append({
        "id": int(time.time() * 1000),
        "agent_phone": phone,
        "agent_name": phone,
        "amount": amt,
        "momo_number": momo,
        "status": "pending",
        "time": time.time()
    })
    save_db('sannlas_payouts.json', payouts)
    return jsonify({"success": True, "message": f"Withdraw request {amt} UGX sent! We will pay via MoMo."})

@sannlas_agents_bp.route('/api/commission/sannlas-profit')
def profit():
    if request.args.get('key', '') != 'SANNLAS2026SECURE':
        return jsonify({"success": False, "message": "Admin key required"}), 403
    comms = load_db('sannlas_commissions.json', [])
    total_profit = sum(c.get('sannlas_amount', 0) for c in comms)
    stats = {
        "total_profit": total_profit,
        "from_coins": sum(c.get('sannlas_amount', 0) for c in comms if c.get('type') == 'coin_resale'),
        "from_uploads": sum(c.get('sannlas_amount', 0) for c in comms if c.get('type') == 'upload'),
        "from_sales": sum(c.get('sannlas_amount', 0) for c in comms if c.get('type') == 'broker_sale'),
        "total_sales_volume": sum(c.get('total_amount', 0) for c in comms if c.get('type') == 'broker_sale'),
        "total_coin_volume": sum(c.get('total_amount', 0) for c in comms if c.get('type') == 'coin_resale'),
        "total_uploads": sum(1 for c in comms if c.get('type') == 'upload'),
        "total_commissions": len(comms)
    }
    recent = sorted(comms, key=lambda x: x.get('time', 0), reverse=True)[:50]
    return jsonify({"success": True, "stats": stats, "recent": recent})

@sannlas_agents_bp.route('/api/commission/payouts')
def payouts():
    if request.args.get('key', '') != 'SANNLAS2026SECURE':
        return jsonify({"success": False, "message": "Admin key required"}), 403
    payouts = load_db('sannlas_payouts.json', [])
    status = request.args.get('status', '')
    if status:
        payouts = [p for p in payouts if p.get('status') == status]
    return jsonify(sorted(payouts, key=lambda x: x.get('time', 0), reverse=True))

@sannlas_agents_bp.route('/api/commission/payout/approve', methods=['POST'])
def approve_payout():
    d = request.json or {}
    if d.get('key', '') != 'SANNLAS2026SECURE':
        return jsonify({"success": False, "message": "Admin key required"}), 403
    payouts = load_db('sannlas_payouts.json', [])
    for p in payouts:
        if p.get('id') == d.get('payout_id'):
            p['status'] = 'paid'
            save_db('sannlas_payouts.json', payouts)
            return jsonify({"success": True, "message": "Marked paid!"})
    return jsonify({"success": False, "message": "Not found"}), 404

# ============================================================
# 12. PROMOTION - PROMOTE & EARN COINS
# Merged from sannlas_promotion.py - Now deleted
# ============================================================
PROMOTION_HTML = """
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Promote & Earn - Sannlas</title>
<style>
body{font-family:Arial;background:#f5f5f5;margin:0;padding:15px;padding-bottom:80px}
.card{background:#fff;border-radius:12px;padding:15px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1)}
.btn{width:100%;padding:12px;border:none;border-radius:10px;font-weight:bold;cursor:pointer;margin:6px 0}
.btn-black{background:#000;color:#FFCC02;border:2px solid #FFCC02}
.btn-green{background:#00c853;color:#fff}
input{width:100%;padding:12px;border:1px solid #ccc;border-radius:8px;margin:8px 0;box-sizing:border-box}
.item{padding:12px;border-bottom:1px solid #eee}
.small{font-size:12px;color:#666}
h2{margin:0 0 10px}
.nav{position:fixed;bottom:0;left:0;right:0;background:#fff;display:flex;justify-content:space-around;padding:10px;border-top:1px solid #ddd}
.nav a{text-decoration:none;color:#666;font-size:12px;text-align:center}
.nav a.active{color:#ff6f00;font-weight:bold}
.link-box{background:#000;color:#FFCC02;padding:10px;border-radius:8px;word-break:break-all;margin:8px 0}
</style></head><body>
<h2>🚀 Promote & Earn Coins</h2>
<div class="card">
<b>How it works:</b><br>
<small>1. Pick product to promote<br>2. Get your unique link<br>3. Share link - when someone buys, you earn coins!<br>4. Commission = product owner sets (3-10 coins per sale)</small>
</div>
<div class="card">
<h3>📦 My Promotion Links</h3>
<div id="myPromos">Loading...</div>
</div>
<div class="card">
<h3>📥 Requests For My Products</h3>
<small>People who want to promote your products</small>
<div id="requests">Loading...</div>
</div>
<div class="nav">
<a href="/">🏠 Home</a><a href="/promote" class="active">🚀 Promote</a><a href="/balance">💰 Balance</a><a href="/">🏪 Shops</a>
</div>
<script>
let myUser=JSON.parse(localStorage.getItem('sannlas_user')||'{}'); if(myUser.user) myUser=myUser.user;
async function loadMy(){
 let res=await fetch(`/api/promote/my?email=${myUser.email||''}&phone=${myUser.phone||''}`);
 let data=await res.json(); let html='';
 if(!data.length) html='No promotions yet. Go to a product > Click Promote & Earn button!';
 else data.forEach(p=>{
   let link=`https://sannlas.store/?promo=${p.promo_code}&product=${p.product_id}`;
   html+=`<div class=item><b>${p.product_name||p.product_id}</b><br><span class=small>Code: ${p.promo_code} | Commission: ${p.commission_coins} coins | Sales: ${p.sales||0} | Status: ${p.status}</span><div class=link-box>${link}</div><button class=btn-black onclick="navigator.clipboard.writeText('${link}');alert('Copied!')">📋 Copy Link</button><button class=btn-black onclick="share('${link}')">📤 Share WhatsApp</button></div>`;
 });
 document.getElementById('myPromos').innerHTML=html;
}
async function loadRequests(){
 let res=await fetch(`/api/promote/requests?email=${myUser.email||''}&phone=${myUser.phone||''}`);
 let data=await res.json(); let html='';
 if(!data.length) html='No requests yet';
 else data.forEach(p=>{
   html+=`<div class=item><b>${p.freelancer_phone} / ${p.freelancer_email}</b> wants to promote <b>${p.product_name}</b> for ${p.commission_coins} coins<br><span class=small>${new Date(p.created*1000).toLocaleString()} | ${p.promo_code} | Sales: ${p.sales}</span><br><button class=btn-green onclick="actionPromo(${p.id},'approved')">✅ Approve</button> <button class=btn-black onclick="actionPromo(${p.id},'rejected')">❌ Reject</button></div>`;
 });
 document.getElementById('requests').innerHTML=html;
}
async function actionPromo(id,act){
 let res=await fetch('/api/promote/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,action:act})});
 let d=await res.json(); alert(d.message); loadRequests();
}
function share(link){ window.open(`https://wa.me/?text=${encodeURIComponent('Check this product Boss! '+link)}`,'_blank');}
loadMy(); loadRequests();
</script></body></html>
"""

@sannlas_agents_bp.route('/promote')
@sannlas_agents_bp.route('/promotion')
@sannlas_agents_bp.route('/promote-and-earn')
def promote_page():
    return Response(PROMOTION_HTML, mimetype='text/html')

# --- Apply to promote a product ---
@sannlas_agents_bp.route('/api/promote/apply', methods=['POST'])
def promote_apply():
    data = request.json or {}
    product_id = str(data.get('product_id', '')).strip()
    phone = (data.get('phone') or '').strip()
    email = (data.get('email') or '').lower().strip()

    if not phone and not email:
        return jsonify({"success": False, "message": "Login first"}), 401

    products = load_db('products.json', [])
    prod = next((p for p in products if str(p.get('id')) == product_id), None)
    if not prod:
        return jsonify({"success": False, "message": "Product not found"}), 404

    promos = load_db('promotions.json', [])
    existing = next(
        (p for p in promos
         if str(p.get('product_id')) == product_id
         and (p.get('freelancer_phone') == phone or p.get('freelancer_email', '').lower() == email)),
        None
    )
    if existing:
        code = existing.get('promo_code')
        link = f"https://sannlas.store/?promo={code}&product={product_id}"
        return jsonify({"success": True, "message": "Already applied!", "promo": existing, "link": link, "promo_link": link, "code": code})

    code = f"PROMO{product_id[:3]}{phone[-3:]}{''.join(random.choices(string.ascii_uppercase + string.digits, k=3))}"
    new_promo = {
        "id": int(time.time() * 1000),
        "product_id": product_id,
        "product_name": prod.get('name'),
        "product_owner_phone": prod.get('phone'),
        "product_owner_email": (prod.get('seller_email') or '').lower(),
        "freelancer_phone": phone,
        "freelancer_email": email,
        "commission_coins": int(prod.get('promo_commission', 3)),
        "promo_code": code,
        "status": "approved",
        "sales": 0,
        "created": time.time()
    }
    promos.append(new_promo)
    save_db('promotions.json', promos)
    link = f"https://sannlas.store/?promo={code}&product={product_id}"
    return jsonify({"success": True, "message": f"Applied! Earn {new_promo['commission_coins']} coins per sale! Link: {link}", "promo": new_promo, "link": link, "promo_link": link, "code": code})

# --- My promotions (I am freelancer) ---
@sannlas_agents_bp.route('/api/promote/my', methods=['GET'])
def my_promotions():
    phone = request.args.get('phone', '').strip()
    email = request.args.get('email', '').lower().strip()
    promos = load_db('promotions.json', [])
    result = [p for p in promos if (phone and p.get('freelancer_phone') == phone) or (email and p.get('freelancer_email', '').lower() == email)]
    return jsonify(result[::-1])

# --- Requests for my products (I am owner) ---
@sannlas_agents_bp.route('/api/promote/requests', methods=['GET'])
def promote_requests():
    phone = request.args.get('phone', '').strip()
    email = request.args.get('email', '').lower().strip()
    promos = load_db('promotions.json', [])
    result = [p for p in promos if (phone and p.get('product_owner_phone') == phone) or (email and p.get('product_owner_email', '').lower() == email)]
    return jsonify(result[::-1])

# --- Approve / Reject promoter ---
@sannlas_agents_bp.route('/api/promote/action', methods=['POST'])
def promote_action():
    data = request.json or {}
    pid = int(data.get('id', 0))
    action = data.get('action', 'approved')
    promos = load_db('promotions.json', [])
    for p in promos:
        if int(p.get('id')) == pid:
            p['status'] = action
            break
    save_db('promotions.json', promos)
    return jsonify({"success": True, "message": f"Promoter {action}!"})

# --- Promo click tracking ---
@sannlas_agents_bp.route('/api/promote/click', methods=['POST'])
def promo_click():
    data = request.json or {}
    clicks = load_db('promo_clicks.json', [])
    clicks.append({
        'product_id': data.get('product_id'),
        'promo': data.get('promo'),
        'ref': data.get('ref'),
        'time': time.time(),
        'ip': request.remote_addr
    })
    save_db('promo_clicks.json', clicks)
    return jsonify({'success': True})

# --- Product promoters list ---
@sannlas_agents_bp.route('/api/promote/product/<product_id>')
def product_promoters(product_id):
    promos = load_db('promotions.json', [])
    result = [p for p in promos if str(p.get('product_id')) == str(product_id) and p.get('status') == 'approved']
    return jsonify(result)

# --- ADD THESE 2 ROUTES AT BOTTOM ---
@sannlas_agents_bp.route('/api/permissions/my-shops')
def my_shops_as_agent():
    agent_phone = request.args.get('agent_phone', '').strip()
    if not agent_phone:
        return jsonify({'success': False, 'message': 'agent_phone required'}), 400
    perms = load_db('sannlas_permissions.json', [])
    my_perms = [p for p in perms if p['agent_phone'] == agent_phone and p['status'] == 'active']
    shops = load_db('shops.json', [])
    result = []
    for perm in my_perms:
        shop = next((s for s in shops if s.get('shop_slug', '').lower() == perm['shop_slug'].lower()), None)
        result.append({"permission": perm, "shop": shop})
    return jsonify({'success': True, 'shops': result})

@sannlas_agents_bp.route('/api/permissions/admin/list')
def admin_list_perms():
    if request.args.get('key', '') != 'SANNLAS2026SECURE':
        return jsonify({"success": False, "message": "Admin key required"}), 403
    return jsonify(load_db('sannlas_permissions.json', []))
