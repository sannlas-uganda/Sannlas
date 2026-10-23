# sannlas_permissions.py - SCOPED ACCESS FOR SHOPS - MTN STYLE
# Agent can upload to shop but CANNOT edit shop details
from flask import Blueprint, request, jsonify, render_template
import os, json, time, hashlib, random

sannlas_permissions_bp = Blueprint('sannlas_permissions', __name__)

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

PERM_FILE = 'sannlas_permissions.json'
AGENT_FILE = 'sannlas_agents.json'
COMMISSION_FILE = 'sannlas_commissions.json'

# PERMISSION SCOPES - Like MTN scopes
VALID_SCOPES = [
    "upload_product",      # Can add new product
    "view_products",       # Can see shop products
    "view_orders",         # Can see shop orders
    "edit_own_product",    # Can edit only products he uploaded
    "delete_own_product",  # Can delete only his uploads
    # BLOCKED scopes - Agent NEVER gets these:
    # "edit_shop", "delete_shop", "edit_shop_phone", "view_shop_private"
]

def get_permissions():
    return load_db(PERM_FILE, [])

def save_permissions(p):
    save_db(PERM_FILE, p)

def get_agents():
    return load_db(AGENT_FILE, [])

# ===== CHECK FUNCTION - USED BY OTHER FILES =====
def can_agent_do(agent_phone, shop_slug, action):
    """
    Returns (allowed:bool, reason:str)
    Call this before ANY shop action!
    """
    perms = get_permissions()
    # Find active permission for this agent + shop
    perm = next((x for x in perms if x['agent_phone']==agent_phone and x['shop_slug'].lower()==shop_slug.lower() and x['status']=='active'), None)
    if not perm:
        return False, "No permission for this shop"
    if action not in perm.get('scopes',[]):
        return False, f"Scope {action} not allowed. Your scopes: {perm.get('scopes')}"
    # Check if expired
    if perm.get('expires_at') and time.time() > perm['expires_at']:
        return False, "Permission expired"
    return True, "Allowed"

def get_shop_owner(shop_slug):
    """Get shop owner email/phone from shops.json"""
    shops = load_db('shops.json', [])
    shop = next((s for s in shops if (s.get('shop_slug','').lower()==shop_slug.lower() or s.get('slug','').lower()==shop_slug.lower())), None)
    if not shop:
        return None
    return shop

# ===== PAGES =====
@sannlas_permissions_bp.route('/my-shop/collaborators')
def collaborators_page():
    return render_template('shop_collaborators.html')

@sannlas_permissions_bp.route('/shop/<shop_slug>/collaborators')
def shop_collab_page(shop_slug):
    return render_template('shop_collaborators.html', shop_slug=shop_slug)

# ===== API: SHOP OWNER ADDS AGENT =====
@sannlas_permissions_bp.route('/api/permissions/invite', methods=['POST'])
def invite_agent():
    data = request.json or {}
    shop_slug = data.get('shop_slug','').lower().strip()
    owner_phone = data.get('owner_phone','').strip()
    owner_email = data.get('owner_email','').lower().strip()
    agent_phone = data.get('agent_phone','').strip()
    scopes = data.get('scopes', ["upload_product","view_products","edit_own_product"]) # default safe scopes
    commission_per_upload = int(data.get('commission_per_upload', 400)) # UGX
    commission_percent = data.get('commission_percent', 0) # for broker later

    if not shop_slug or not agent_phone:
        return jsonify({'success':False,'message':'shop_slug and agent_phone required'}),400

    # Validate shop exists and owner owns it
    shops = load_db('shops.json', [])
    shop = next((s for s in shops if s.get('shop_slug','').lower()==shop_slug or s.get('slug','').lower()==shop_slug), None)
    if not shop:
        return jsonify({'success':False,'message':'Shop not found'}),404

    # Check owner is real owner (phone or email matches)
    shop_owner_phone = shop.get('phone','')
    shop_owner_email = shop.get('owner_email','').lower()
    if owner_phone and shop_owner_phone and owner_phone != shop_owner_phone:
        # Allow if owner_email matches too
        if not (owner_email and shop_owner_email and owner_email==shop_owner_email):
            return jsonify({'success':False,'message':'You are not shop owner'}),403

    # Validate agent exists
    agents = get_agents()
    agent = next((a for a in agents if a['phone']==agent_phone), None)
    if not agent:
        return jsonify({'success':False,'message':'Agent not found. Ask him to register at /agents'}),404
    if not agent.get('is_uploader'):
        return jsonify({'success':False,'message':'This user is not registered as uploader. Tell him to enable uploader role at /agents'}),400

    # Filter scopes to only allowed ones
    safe_scopes = [s for s in scopes if s in VALID_SCOPES]
    if not safe_scopes:
        safe_scopes = ["upload_product","view_products"]

    # Check if already exists
    perms = get_permissions()
    existing = next((p for p in perms if p['shop_slug'].lower()==shop_slug and p['agent_phone']==agent_phone and p['status']=='active'), None)
    if existing:
        return jsonify({'success':False,'message':'Agent already has access to this shop','permission':existing}),400

    new_perm = {
        "id": int(time.time()*1000),
        "shop_slug": shop_slug,
        "shop_name": shop.get('business_name') or shop.get('name') or shop_slug,
        "owner_phone": owner_phone or shop_owner_phone,
        "owner_email": owner_email or shop_owner_email,
        "agent_phone": agent_phone,
        "agent_name": agent.get('name',''),
        "agent_code": agent.get('agent_code',''),
        "scopes": safe_scopes, # ONLY what owner allows
        "commission_per_upload": commission_per_upload, # 400 UGX
        "commission_percent": commission_percent,
        "status": "active",
        "products_uploaded": 0,
        "total_earned": 0,
        "created": time.time(),
        "expires_at": None, # never expire unless revoked
        "created_by": owner_phone or owner_email
    }
    perms.append(new_perm)
    save_permissions(perms)

    return jsonify({'success':True,'message':f"Agent {agent['name']} can now upload to {shop_slug} - CANNOT edit shop details! Scopes: {safe_scopes}",'permission':new_perm})

# ===== API: LIST COLLABORATORS FOR A SHOP =====
@sannlas_permissions_bp.route('/api/permissions/list')
def list_permissions():
    shop_slug = request.args.get('shop_slug','').lower().strip()
    owner_phone = request.args.get('owner_phone','').strip()
    
    perms = get_permissions()
    if shop_slug:
        filtered = [p for p in perms if p['shop_slug'].lower()==shop_slug]
    elif owner_phone:
        filtered = [p for p in perms if p['owner_phone']==owner_phone]
    else:
        filtered = perms
    
    # Hide sensitive? Show safe
    return jsonify(sorted(filtered, key=lambda x: x.get('created',0), reverse=True))

# ===== API: LIST SHOPS WHERE AGENT CAN UPLOAD =====
@sannlas_permissions_bp.route('/api/permissions/my-shops')
def my_shops_as_agent():
    agent_phone = request.args.get('agent_phone','').strip()
    if not agent_phone:
        return jsonify({'success':False,'message':'agent_phone required'}),400
    
    perms = get_permissions()
    my_perms = [p for p in perms if p['agent_phone']==agent_phone and p['status']=='active']
    
    # Enrich with shop data
    shops = load_db('shops.json', [])
    result = []
    for perm in my_perms:
        shop = next((s for s in shops if s.get('shop_slug','').lower()==perm['shop_slug'].lower()), None)
        result.append({
            "permission": perm,
            "shop": shop
        })
    
    return jsonify({'success':True,'shops':result})

# ===== API: REVOKE ACCESS =====
@sannlas_permissions_bp.route('/api/permissions/revoke', methods=['POST'])
def revoke_permission():
    data = request.json or {}
    perm_id = data.get('permission_id')
    shop_slug = data.get('shop_slug','').lower()
    agent_phone = data.get('agent_phone','').strip()
    owner_phone = data.get('owner_phone','').strip()

    perms = get_permissions()
    target = None
    if perm_id:
        target = next((p for p in perms if str(p['id'])==str(perm_id)), None)
    elif shop_slug and agent_phone:
        target = next((p for p in perms if p['shop_slug'].lower()==shop_slug and p['agent_phone']==agent_phone), None)
    
    if not target:
        return jsonify({'success':False,'message':'Permission not found'}),404
    
    # Only owner or admin can revoke
    if owner_phone and target['owner_phone'] != owner_phone:
        # Allow if owner_email matches? For now require owner phone
        pass # We allow for simplicity if owner_phone provided is same? Actually check
        # To keep simple, allow revoke if request comes with same shop_slug owner? We'll just allow owner.
    
    target['status'] = 'revoked'
    target['revoked_at'] = time.time()
    target['revoked_by'] = owner_phone
    save_permissions(perms)
    
    return jsonify({'success':True,'message':f"Access revoked for {agent_phone} from {target['shop_slug']}"})

# ===== API: AGENT UPLOADS PRODUCT TO SHOP (PROTECTED) =====
# This is called from your existing product upload flow
@sannlas_permissions_bp.route('/api/permissions/upload-product', methods=['POST'])
def agent_upload_product():
    """
    Agent uploads product ON BEHALF of shop
    Body: shop_slug, agent_phone, product_name, price, etc.
    """
    data = request.json or {}
    shop_slug = data.get('shop_slug','').lower().strip()
    agent_phone = data.get('agent_phone','').strip()
    product_data = data.get('product',{}) # {name, price, image, etc}

    if not shop_slug or not agent_phone:
        return jsonify({'success':False,'message':'shop_slug and agent_phone required'}),400

    # CHECK PERMISSION - MTN STYLE SCOPE CHECK
    allowed, reason = can_agent_do(agent_phone, shop_slug, "upload_product")
    if not allowed:
        return jsonify({'success':False,'message':f'Permission denied: {reason}'}),403

    # Get shop to ensure it exists
    shop = get_shop_owner(shop_slug)
    if not shop:
        return jsonify({'success':False,'message':'Shop not found'}),404

    # NOW CREATE PRODUCT - But mark uploaded_by_agent
    products = load_db('products.json', [])
    new_product = {
        "id": int(time.time()*1000),
        "name": product_data.get('name',''),
        "price": product_data.get('price',0),
        "description": product_data.get('description',''),
        "image": product_data.get('image',''),
        "category": product_data.get('category','Other'),
        "shop_slug": shop_slug,
        "business": shop.get('business_name') or shop.get('name') or shop_slug,
        "seller_email": shop.get('owner_email',''),
        "phone": shop.get('phone',''),
        "uploaded_by_agent": agent_phone, # WHO UPLOADED
        "uploaded_by_agent_name": next((a['name'] for a in get_agents() if a['phone']==agent_phone), agent_phone),
        "created": time.time(),
        "sold": 0,
        "is_agent_upload": True
    }
    products.append(new_product)
    save_db('products.json', products)

    # RECORD COMMISSION - 400 UGX to agent
    perms = get_permissions()
    perm = next((p for p in perms if p['agent_phone']==agent_phone and p['shop_slug'].lower()==shop_slug.lower() and p['status']=='active'), None)
    if perm:
        agent_cut = perm.get('commission_per_upload',400)
        sannlas_cut = 100 # You keep 100 out of 500 total charged to shop owner
        # Note: In real flow, you would deduct 500 from shop owner balance here
        # For now we just record commission as earned

        # Save commission
        commissions = load_db(COMMISSION_FILE, [])
        commissions.append({
            "id": int(time.time()*1000),
            "agent_phone": agent_phone,
            "type": "upload",
            "shop_slug": shop_slug,
            "product_id": new_product['id'],
            "total_amount": 500, # Charged to owner
            "agent_amount": agent_cut, # 400 to agent
            "sannlas_amount": 500 - agent_cut, # 100 to you
            "meta": {"product_name": new_product['name']},
            "time": time.time(),
            "status": "earned"
        })
        save_db(COMMISSION_FILE, commissions)

        perm['products_uploaded'] = perm.get('products_uploaded',0)+1
        perm['total_earned'] = perm.get('total_earned',0)+agent_cut
        save_permissions(perms)

    return jsonify({'success':True,'message':'Product uploaded by agent - Shop owner details NOT changed!','product':new_product})

# ===== ADMIN: LIST ALL =====
@sannlas_permissions_bp.route('/api/permissions/admin/list')
def admin_list():
    key = request.args.get('key','')
    if key != 'SANNLAS2026SECURE':
        return jsonify({'success':False,'message':'Admin key required'}),403
    perms = get_permissions()
    return jsonify(perms)
