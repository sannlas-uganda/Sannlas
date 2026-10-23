# sannlas_commission.py - AUTO MONEY SPLIT ENGINE - LIKE MTN
# Every transaction = auto profit for you + agent + shop owner
from flask import Blueprint, request, jsonify, render_template
import os, json, time, random, hashlib

sannlas_commission_bp = Blueprint('sannlas_commission', __name__)

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

COMMISSION_FILE = 'sannlas_commissions.json'
AGENT_FILE = 'sannlas_agents.json'
PAYOUT_FILE = 'sannlas_payouts.json' # withdrawal requests
SANNLAS_PROFIT_FILE = 'sannlas_profit.json'

def get_commissions():
    return load_db(COMMISSION_FILE, [])

def save_commissions(c):
    save_db(COMMISSION_FILE, c)

def get_agents():
    return load_db(AGENT_FILE, [])

def save_agents(a):
    save_db(AGENT_FILE, a)

def get_payouts():
    return load_db(PAYOUT_FILE, [])

def save_payouts(p):
    save_db(PAYOUT_FILE, p)

def get_sannlas_profit():
    return load_db(SANNLAS_PROFIT_FILE, {"total_profit":0,"from_coins":0,"from_uploads":0,"from_sales":0,"history":[]})

def save_sannlas_profit(p):
    save_db(SANNLAS_PROFIT_FILE, p)

# ===== CORE FUNCTION - CALLED BY OTHER SYSTEMS =====
def split_and_record(type_, total_amount, agent_phone=None, shop_slug=None, meta=None):
    """
    type_: coin_resale, upload, broker_sale
    Returns: {agent_amount, sannlas_amount, owner_amount}
    """
    agent_amount = 0
    sannlas_amount = 0
    owner_amount = 0

    if type_ == "coin_resale":
        # User buys coins 5990 -> Agent 15% = 898, You 85% = 5092
        agent_amount = int(total_amount * 0.15)
        sannlas_amount = total_amount - agent_amount
        owner_amount = 0 # No shop owner in coin sale

    elif type_ == "upload":
        # Shop owner pays 500 per upload -> Agent 400, You 100
        # total_amount = 500 charged to owner
        agent_amount = int(meta.get('commission_per_upload', 400)) if meta else 400
        sannlas_amount = total_amount - agent_amount
        owner_amount = 0 # Owner is payer, not earner here

    elif type_ == "broker_sale":
        # Product sale 500k -> Owner 94% = 470k, Agent 4% = 20k, You 2% = 10k
        owner_amount = int(total_amount * 0.94)
        agent_amount = int(total_amount * 0.04)
        sannlas_amount = total_amount - owner_amount - agent_amount

    # Record commission
    commissions = get_commissions()
    entry = {
        "id": int(time.time()*1000) + random.randint(1,999),
        "type": type_,
        "total_amount": total_amount,
        "agent_phone": agent_phone,
        "shop_slug": shop_slug,
        "agent_amount": agent_amount,
        "sannlas_amount": sannlas_amount,
        "owner_amount": owner_amount,
        "meta": meta or {},
        "time": time.time(),
        "status": "completed"
    }
    commissions.append(entry)
    save_commissions(commissions)

    # Update agent balance
    if agent_phone:
        agents = get_agents()
        for a in agents:
            if a['phone']==agent_phone:
                a['total_earned'] = a.get('total_earned',0) + agent_amount
                a['balance'] = a.get('balance',0) + agent_amount
                if type_=="coin_resale": a['coins_sold'] = a.get('coins_sold',0)+1
                if type_=="upload": a['products_uploaded'] = a.get('products_uploaded',0)+1
                if type_=="broker_sale": a['sales_brokered'] = a.get('sales_brokered',0)+1
                break
        save_agents(agents)

    # Update Sannlas profit
    profit = get_sannlas_profit()
    profit['total_profit'] = profit.get('total_profit',0) + sannlas_amount
    if type_=="coin_resale": profit['from_coins'] = profit.get('from_coins',0) + sannlas_amount
    if type_=="upload": profit['from_uploads'] = profit.get('from_uploads',0) + sannlas_amount
    if type_=="broker_sale": profit['from_sales'] = profit.get('from_sales',0) + sannlas_amount
    profit['history'].append(entry)
    # Keep only last 500
    profit['history'] = profit['history'][-500:]
    save_sannlas_profit(profit)

    return entry

# ===== PAGES =====
@sannlas_commission_bp.route('/commissions')
def commissions_page():
    return render_template('sannlas_commissions.html')

@sannlas_commission_bp.route('/admin/profit')
def profit_page():
    return render_template('sannlas_commissions.html')

# ===== API: RECORD SALE (Called when order is created) =====
@sannlas_commission_bp.route('/api/commission/sale', methods=['POST'])
def record_sale_commission():
    """
    Called when a product is sold
    Body: {product_id, total_amount, shop_slug, agent_phone (broker), buyer_phone}
    """
    data = request.json or {}
    total = int(data.get('total_amount',0))
    shop_slug = data.get('shop_slug','').lower()
    agent_phone = data.get('agent_phone','').strip() # Broker who found buyer
    product_id = data.get('product_id')
    buyer_phone = data.get('buyer_phone','')

    if total <=0:
        return jsonify({'success':False,'message':'total_amount required'}),400

    if not agent_phone:
        # No agent = 100% to shop owner, 0 to you? Actually you still take 2%? For now 100% to owner
        # But recommend you take 2% platform fee even without agent
        entry = split_and_record("broker_sale", total, None, shop_slug, meta={"product_id":product_id,"buyer_phone":buyer_phone,"note":"no broker - 100% owner"})
        # Override to give 98% owner, 2% you if no broker
        commissions = get_commissions()
        # Adjust last entry
        if commissions:
            last = commissions[-1]
            last['owner_amount'] = int(total*0.98)
            last['sannlas_amount'] = total - last['owner_amount']
            last['agent_amount'] = 0
            save_commissions(commissions)
            # Update profit
            profit = get_sannlas_profit()
            profit['total_profit'] += last['sannlas_amount'] - entry['sannlas_amount']
            save_sannlas_profit(profit)
        return jsonify({'success':True,'entry':last})

    # With broker
    entry = split_and_record("broker_sale", total, agent_phone, shop_slug, meta={"product_id":product_id,"buyer_phone":buyer_phone})

    return jsonify({'success':True,'message':f"Sale split: Owner {entry['owner_amount']} | Agent {entry['agent_amount']} | Sannlas {entry['sannlas_amount']}",'entry':entry})

# ===== API: RECORD UPLOAD COMMISSION =====
@sannlas_commission_bp.route('/api/commission/upload', methods=['POST'])
def record_upload_commission():
    data = request.json or {}
    agent_phone = data.get('agent_phone','')
    shop_slug = data.get('shop_slug','')
    product_id = data.get('product_id')
    commission = int(data.get('commission',400))

    entry = split_and_record("upload", 500, agent_phone, shop_slug, meta={"product_id":product_id,"commission_per_upload":commission})
    return jsonify({'success':True,'entry':entry})

# ===== API: AGENT REQUEST PAYOUT / WITHDRAW =====
@sannlas_commission_bp.route('/api/commission/withdraw', methods=['POST'])
def request_withdraw():
    data = request.json or {}
    agent_phone = data.get('agent_phone','').strip()
    amount = int(data.get('amount',0))
    method = data.get('method','momo') # momo, bank
    momo_number = data.get('momo_number','').strip()

    if not agent_phone or amount<=0:
        return jsonify({'success':False,'message':'agent_phone and amount required'}),400

    agents = get_agents()
    agent = next((a for a in agents if a['phone']==agent_phone), None)
    if not agent:
        return jsonify({'success':False,'message':'Agent not found'}),404

    balance = agent.get('balance',0)
    if amount > balance:
        return jsonify({'success':False,'message':f'Insufficient balance. You have {balance} UGX'}),400

    if amount < 5000:
        return jsonify({'success':False,'message':'Min withdraw 5000 UGX'}),400

    # Deduct balance
    agent['balance'] -= amount
    agent['total_withdrawn'] = agent.get('total_withdrawn',0) + amount
    save_agents(agents)

    payouts = get_payouts()
    payout = {
        "id": int(time.time()*1000),
        "agent_phone": agent_phone,
        "agent_name": agent.get('name',''),
        "amount": amount,
        "method": method,
        "momo_number": momo_number or agent_phone,
        "status": "pending", # pending, approved, paid
        "requested_at": time.time(),
        "paid_at": None
    }
    payouts.append(payout)
    save_payouts(payouts)

    return jsonify({'success':True,'message':f'Withdraw request {amount} UGX submitted! Admin will pay to {momo_number} within 24h','payout':payout})

# ===== API: LIST COMMISSIONS =====
@sannlas_commission_bp.route('/api/commission/list')
def list_commissions():
    agent_phone = request.args.get('agent_phone','')
    shop_slug = request.args.get('shop_slug','')
    type_ = request.args.get('type','')

    commissions = get_commissions()
    filtered = commissions
    if agent_phone:
        filtered = [c for c in filtered if c.get('agent_phone')==agent_phone]
    if shop_slug:
        filtered = [c for c in filtered if c.get('shop_slug','').lower()==shop_slug.lower()]
    if type_:
        filtered = [c for c in filtered if c.get('type')==type_]

    return jsonify(sorted(filtered, key=lambda x: x.get('time',0), reverse=True)[:200])

# ===== API: SANNLAS PROFIT (ADMIN) =====
@sannlas_commission_bp.route('/api/commission/sannlas-profit')
def sannlas_profit_api():
    key = request.args.get('key','')
    if key != 'SANNLAS2026SECURE':
        # Allow if session is admin
        from flask import session
        if not session.get('is_admin'):
            return jsonify({'success':False,'message':'Admin key required'}),403

    profit = get_sannlas_profit()
    commissions = get_commissions()

    # Stats
    total_sales = sum(c['total_amount'] for c in commissions if c['type']=='broker_sale')
    total_coin_sales = sum(c['total_amount'] for c in commissions if c['type']=='coin_resale')
    total_uploads = len([c for c in commissions if c['type']=='upload'])

    return jsonify({
        'success':True,
        'profit': profit,
        'stats': {
            'total_profit': profit.get('total_profit',0),
            'from_coins': profit.get('from_coins',0),
            'from_uploads': profit.get('from_uploads',0),
            'from_sales': profit.get('from_sales',0),
            'total_sales_volume': total_sales,
            'total_coin_volume': total_coin_sales,
            'total_uploads': total_uploads,
            'total_commissions': len(commissions)
        },
        'recent': sorted(commissions, key=lambda x: x.get('time',0), reverse=True)[:100]
    })

# ===== API: PAYOUTS LIST (ADMIN) =====
@sannlas_commission_bp.route('/api/commission/payouts')
def list_payouts():
    key = request.args.get('key','')
    status = request.args.get('status','') # pending, paid
    if key != 'SANNLAS2026SECURE':
        from flask import session
        if not session.get('is_admin'):
            return jsonify({'success':False,'message':'Admin key required'}),403

    payouts = get_payouts()
    if status:
        payouts = [p for p in payouts if p.get('status')==status]
    return jsonify(sorted(payouts, key=lambda x: x.get('requested_at',0), reverse=True))

@sannlas_commission_bp.route('/api/commission/payout/approve', methods=['POST'])
def approve_payout():
    data = request.json or {}
    key = data.get('key','')
    payout_id = data.get('payout_id')
    if key != 'SANNLAS2026SECURE':
        return jsonify({'success':False,'message':'Admin key required'}),403

    payouts = get_payouts()
    target = next((p for p in payouts if str(p['id'])==str(payout_id)), None)
    if not target:
        return jsonify({'success':False,'message':'Payout not found'}),404

    target['status'] = 'paid'
    target['paid_at'] = time.time()
    save_payouts(payouts)

    return jsonify({'success':True,'message':'Payout marked as paid','payout':target})
