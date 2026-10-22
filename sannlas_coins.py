# sannlas_coins.py - ONE FILE = COINS SYSTEM - 1B BUG FIXED - FINAL + SHARE
from flask import Blueprint, Response, request, jsonify
import os, json, time, uuid, random, string, hashlib, math

sannlas_coins_bp = Blueprint('sannlas_coins_bp', __name__)

def load_db(file, default):
    try:
        if os.path.exists(f'data/{file}'):
            return json.load(open(f'data/{file}'))
        if os.path.exists(file):
            return json.load(open(file))
        return default
    except:
        return default

def save_db(file, data):
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

COMBINED_COINS_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>COINS - SANNLAS</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial;background:#f1f5f9;padding-bottom:80px}.navbar{background:#000;color:#FFCC02;padding:12px;display:flex;justify-content:space-between;position:sticky;top:0;z-index:10}.balance-card{background:linear-gradient(135deg,#000 0%,#333 100%);color:#FFCC02;padding:20px;margin:10px;border-radius:16px;text-align:center}.balance-card h1{font-size:40px;margin:10px 0}.coin-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:10px}.coin-pack{background:#fff;border-radius:14px;padding:14px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.08);border:2px solid #fff}.coin-pack.best{border-color:#FFCC02;background:#fffde7}.coin-pack b{display:block;font-size:18px}.coin-pack button{background:#000;color:#FFCC02;border:none;padding:10px 16px;border-radius:20px;font-weight:900;margin-top:8px;cursor:pointer;width:100%}.referral-box{background:#fff;margin:10px;padding:14px;border-radius:14px;border:2px dashed #FFCC02;text-align:center}.tx-card{background:#fff;margin:6px 10px;padding:10px;border-radius:10px;display:flex;justify-content:space-between;align-items:center;font-size:13px}.tab-bar{background:#fff;display:flex;border-bottom:2px solid #eee;position:sticky;top:50px;z-index:9}.tab-bar button{flex:1;padding:12px;border:none;background:#fff;font-weight:900;cursor:pointer;border-bottom:3px solid transparent}.tab-bar button.active{border-bottom-color:#FFCC02;background:#fffde7}</style>
</head><body>
<div class="navbar"><a href="/" style="color:#FFCC02;text-decoration:none;font-weight:bold">← SANNLAS</a><b>💰 COINS</b><span></span></div>
<div class="balance-card"><small style="opacity:.7">YOUR BALANCE</small><h1 id="coinBalance">0</h1><div style="display:flex;justify-content:space-around;margin-top:10px;font-size:12px"><div><b id="boughtCoins">0</b><br>Bought</div><div><b id="earnedCoins">0</b><br>Earned</div><div><b id="spentCoins">0</b><br>Spent</div></div><small id="coinInfo" style="display:block;margin-top:10px;opacity:.6"></small></div>
<div class="tab-bar"><button id="tab-buy" class="active" onclick="switchTab('buy')">Buy Coins</button><button id="tab-earn" onclick="switchTab('earn')">Earn Free</button><button id="tab-history" onclick="switchTab('history')">History</button></div>
<div id="tab-buy-content"><div class="coin-grid" id="coinPacks">Loading...</div><div style="padding:10px"><div style="background:#fff;padding:12px;border-radius:12px"><b>How to Buy:</b><p style="font-size:12px;color:#666;margin-top:6px">1. Choose pack<br>2. Send MoMo<br>3. Enter code<br>4. Instant coins!</p><p style="font-size:11px;color:#999;margin-top:8px">Rate: 1 Coin = UGX 599 • 1B Total</p><p style="font-size:11px;color:#e65100;margin-top:4px">Remaining: <b id="remainingCoins">-</b> / 1,000,000,000</p></div></div></div>
<div id="tab-earn-content" style="display:none"><div class="referral-box"><h3>Invite & Earn 1 Coin!</h3><p style="font-size:12px;color:#666;margin:8px 0">Share code - friend joins = 1 coin!</p><p style="background:#000;color:#FFCC02;padding:10px;border-radius:10px;font-weight:900;letter-spacing:2px;margin:10px 0" id="myRefCode">SANN-XXXX-XXXX</p><button onclick="copyRef()" style="background:#FFCC02;color:#000;border:none;padding:8px 16px;border-radius:20px;font-weight:900;cursor:pointer">Copy Link</button><button onclick="shareRef()" style="background:#25D366;color:#fff;border:none;padding:8px 16px;border-radius:20px;font-weight:900;cursor:pointer;margin-left:6px">Share WhatsApp</button><p style="font-size:11px;color:#666;margin-top:10px" id="inviteCount">Invited: 0</p></div></div>
<div id="tab-history-content" style="display:none"><div id="txList"><p style="text-align:center;padding:20px">Loading...</p></div></div>
<div id="buyModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.6);z-index:100;align-items:center;justify-content:center"><div style="background:#fff;margin:20px;padding:20px;border-radius:16px;width:90%;max-width:400px"><h3 id="modalTitle">Buy Coins</h3><p id="modalDesc" style="color:#666;font-size:13px;margin:8px 0"></p><div style="background:#f5f5f5;padding:12px;border-radius:10px;margin:10px 0;text-align:center"><b>Send to MTN MoMo:</b><br><b style="font-size:20px;color:#FFCC02;background:#000;padding:4px 10px;border-radius:8px">078XXXXXXX</b><br><small>Amount: <b id="modalAmount">UGX 0</b></small></div><input id="momoCode" placeholder="Enter MoMo Code" style="width:100%;padding:12px;border-radius:10px;border:1px solid #ddd"><div style="display:flex;gap:10px;margin-top:12px"><button onclick="closeModal()" style="flex:1;padding:12px;border-radius:10px;border:1px solid #ddd;background:#fff;font-weight:900">Cancel</button><button onclick="confirmBuy()" style="flex:1;padding:12px;border-radius:10px;border:none;background:#000;color:#FFCC02;font-weight:900">Confirm Paid</button></div></div></div>
<script>
let currentUser=JSON.parse(localStorage.getItem('sannlas_user')||'{}');let selectedPack=null;
function switchTab(tab){document.querySelectorAll('.tab-bar button').forEach(b=>b.classList.remove('active'));document.getElementById('tab-'+tab).classList.add('active');document.getElementById('tab-buy-content').style.display=tab=='buy'?'block':'none';document.getElementById('tab-earn-content').style.display=tab=='earn'?'block':'none';document.getElementById('tab-history-content').style.display=tab=='history'?'block':'none';if(tab=='history')loadHistory();if(tab=='buy')loadCoinConfig();}
async function loadBalance(){try{let r=await fetch(`/api/coins/balance?email=${encodeURIComponent(currentUser.email||'')}&phone=${encodeURIComponent(currentUser.phone||'')}`);let d=await r.json();document.getElementById('coinBalance').innerText=d.coins||0;document.getElementById('boughtCoins').innerText=d.bought||0;document.getElementById('earnedCoins').innerText=d.earned||0;document.getElementById('spentCoins').innerText=d.spent||0;document.getElementById('coinInfo').innerText=`Total: ${d.bought||0} bought + ${d.earned||0} earned - ${d.spent||0} spent = ${d.coins||0}`;document.getElementById('myRefCode').innerText=d.referral_code||'SANN-XXXX';document.getElementById('inviteCount').innerText=`Invited: ${d.invited_count||0} friends • Earned ${d.earned||0} coins`;}catch(e){}}
async function loadCoinConfig(){try{let r=await fetch('/api/coins/config');let d=await r.json();document.getElementById('remainingCoins').innerText=Number(d.remaining||0).toLocaleString();let packs=[{coins:5,price:5*599,label:'Starter',best:false},{coins:10,price:10*599,label:'Popular',best:true},{coins:20,price:20*599,label:'Value',best:false},{coins:50,price:50*599,label:'Business',best:false},{coins:100,price:100*599,label:'Pro Seller',best:false},{coins:500,price:500*599,label:'Wholesale',best:false}];document.getElementById('coinPacks').innerHTML=packs.map(p=>`<div class="coin-pack ${p.best?'best':''}">${p.best?'<span style="background:#FFCC02;color:#000;font-size:10px;padding:2px 6px;border-radius:10px">BEST</span>':''}<b>${p.coins} Coins</b><small>${p.label}</small><br><small>UGX ${p.price.toLocaleString()}</small><button onclick="openBuyModal(${p.coins},${p.price})">Buy ${p.coins}</button></div>`).join('');}catch(e){document.getElementById('coinPacks').innerHTML='<p>Error</p>';}}
function openBuyModal(coins,price){selectedPack={coins,price};document.getElementById('modalTitle').innerText=`Buy ${coins} Coins`;document.getElementById('modalDesc').innerText=`You will get ${coins} coins after confirmation`;document.getElementById('modalAmount').innerText=`UGX ${price.toLocaleString()}`;document.getElementById('buyModal').style.display='flex';}
function closeModal(){document.getElementById('buyModal').style.display='none';selectedPack=null;document.getElementById('momoCode').value='';}
async function confirmBuy(){let code=document.getElementById('momoCode').value.trim();if(!code){alert('Enter MoMo code!');return;}if(!selectedPack){alert('Select pack!');return;}try{let r=await fetch('/api/coins/buy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:currentUser.email,phone:currentUser.phone,coins:selectedPack.coins,price:selectedPack.price,momo_code:code})});let d=await r.json();alert(d.message||d.error);if(d.success){closeModal();loadBalance();loadCoinConfig();}}catch(e){alert('Error: '+e.message);}}
async function loadHistory(){try{let r=await fetch(`/api/coins/transactions?email=${encodeURIComponent(currentUser.email||'')}&phone=${encodeURIComponent(currentUser.phone||'')}`);let d=await r.json();let txs=d.transactions||[];if(txs.length==0){document.getElementById('txList').innerHTML='<p style="text-align:center;padding:20px;color:#666">No transactions yet</p>';return;}document.getElementById('txList').innerHTML=txs.map(t=>{let badge=t.status=='invite_bonus'?'BONUS':t.status=='buy'?'BUY':'SPENT';let color=t.coins>0?'green':'red';let sign=t.coins>0?'+':'';return `<div class="tx-card"><div><b>${badge}</b><br><small>${t.reason||t.momo_code||''}</small><br><small style="color:#999">${new Date((t.time||0)*1000).toLocaleString()}</small></div><div style="text-align:right"><b style="color:${color}">${sign}${t.coins} coins</b><br><small>UGX ${(t.price||0).toLocaleString()}</small></div></div>`;}).join('');}catch(e){document.getElementById('txList').innerHTML='<p style="color:red;text-align:center">Error</p>';}}
function copyRef(){let code=document.getElementById('myRefCode').innerText;let link=location.origin+'/register?ref='+code;navigator.clipboard.writeText(link);alert('Copied: '+link);}
function shareRef(){let code=document.getElementById('myRefCode').innerText;let link=location.origin+'/register?ref='+code;let text=`Join SANNLAS! Use my code ${code} to get 10 free coins! ${link}`;window.open('https://wa.me/?text='+encodeURIComponent(text),'_blank');}
loadBalance();loadCoinConfig();
</script>
</body></html>
"""

@sannlas_coins_bp.route('/coins')
def coins_page():
    return Response(COMBINED_COINS_HTML, mimetype='text/html')

@sannlas_coins_bp.route('/api/coins/config')
def coins_config():
    cfg = load_db('coin_config.json', {"total":1000000000, "remaining":1000000000, "sold":0, "rate":599})
    if cfg.get('remaining', 1000000000) < 0:
        cfg['remaining'] = 0
        save_db('coin_config.json', cfg)
    if cfg.get('sold',0) > 1000000000:
        cfg['sold'] = 1000000000
        cfg['remaining'] = 0
        save_db('coin_config.json', cfg)
    return jsonify(cfg)

@sannlas_coins_bp.route('/api/coins/balance')
def coins_balance():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    users = load_db('users.json', [])
    user = next((u for u in users if (email and str(u.get('email','')).lower()==email) or (phone and str(u.get('phone',''))==phone)), None)
    if not user:
        return jsonify({'coins':0,'bought':0,'earned':10,'spent':0,'referral_code':'','invited_count':0})
    bought = int(user.get('bought', user.get('bought_coins',0)) or 0)
    earned = int(user.get('earned', user.get('earned_coins',0)) or 0)
    spent = int(user.get('spent',0) or 0)
    real_coins = bought + earned - spent
    if real_coins < 0:
        real_coins = 0
        user['spent'] = bought + earned
        save_db('users.json', users)
    user['coins'] = real_coins
    user['bought'] = bought
    user['earned'] = earned
    user['bought_coins'] = bought
    user['earned_coins'] = earned
    txs = load_db('coin_transactions.json', [])
    invited_count = len([t for t in txs if str(t.get('email','')).lower()==email and t.get('status')=='invite_bonus'])
    return jsonify({
        'coins': real_coins,
        'bought': bought,
        'earned': earned,
        'spent': spent,
        'bought_coins': bought,
        'earned_coins': earned,
        'referral_code': user.get('referral_code',''),
        'invited_count': invited_count,
        'invited_by': user.get('invited_by',''),
        'business': user.get('business','')
    })

@sannlas_coins_bp.route('/api/coins/buy', methods=['POST'])
def coins_buy():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    coins = int(data.get('coins',0) or 0)
    price = int(data.get('price',0) or 0)
    momo_code = data.get('momo_code','').strip()
    if not coins or coins <=0:
        return jsonify({'success':False,'error':'Invalid coins'}),400
    if not momo_code or len(momo_code) < 5:
        return jsonify({'success':False,'error':'Enter valid MoMo code Boss!'}),400
    users = load_db('users.json', [])
    user = next((u for u in users if (email and str(u.get('email','')).lower()==email) or (phone and str(u.get('phone',''))==phone)), None)
    if not user:
        return jsonify({'success':False,'error':'User not found! Login first!'}),404
    txs = load_db('coin_transactions.json', [])
    if any(t.get('momo_code','').strip().lower()==momo_code.lower() for t in txs):
        return jsonify({'success':False,'error':'This MoMo code already used! Enter new code!'}),400
    coin_cfg = load_db('coin_config.json', {"total":1000000000, "remaining":1000000000, "sold":0, "rate":599})
    if coin_cfg.get('remaining', 1000000000) < coins:
        return jsonify({'success':False,'error':f'Not enough coins remaining! Only {coin_cfg.get("remaining",0)} left!'}),400
    user['bought'] = int(user.get('bought', user.get('bought_coins',0)) or 0) + coins
    user['bought_coins'] = user['bought']
    user['coins'] = int(user.get('bought',0)) + int(user.get('earned', user.get('earned_coins',0)) or 0) - int(user.get('spent',0) or 0)
    coin_cfg['remaining'] = max(0, int(coin_cfg.get('remaining',1000000000)) - coins)
    coin_cfg['sold'] = int(coin_cfg.get('sold',0)) + coins
    coin_cfg['total'] = 1000000000
    if coin_cfg['remaining'] + coin_cfg['sold'] != 1000000000:
        coin_cfg['remaining'] = 1000000000 - coin_cfg['sold']
    txs.append({
        'id': int(time.time()*1000),
        'email': user.get('email'),
        'phone': user.get('phone'),
        'coins': coins,
        'price': price,
        'momo_code': momo_code,
        'reason': f'Bought {coins} coins',
        'time': time.time(),
        'status': 'buy'
    })
    save_db('coin_transactions.json', txs)
    save_db('coin_config.json', coin_cfg)
    save_db('users.json', users)
    return jsonify({'success':True,'message':f'✅ {coins} coins added! New balance: {user["coins"]} 🎉','new_balance': user['coins']})

@sannlas_coins_bp.route('/api/coins/transactions')
def coins_transactions():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    txs = load_db('coin_transactions.json', [])
    filtered = [t for t in txs if (email and str(t.get('email','')).lower()==email) or (phone and str(t.get('phone',''))==phone)]
    filtered = sorted(filtered, key=lambda x: x.get('time',0), reverse=True)[:100]
    return jsonify({'transactions': filtered, 'count': len(filtered)})

@sannlas_coins_bp.route('/api/coins/packs')
def coins_packs():
    packs=[
        {"coins":5, "price":2995, "label":"Starter"},
        {"coins":10, "price":5990, "label":"Popular", "best":True},
        {"coins":20, "price":11980, "label":"Value"},
        {"coins":50, "price":29950, "label":"Business"},
        {"coins":100, "price":59900, "label":"Pro"},
        {"coins":500, "price":299500, "label":"Wholesale"},
    ]
    return jsonify(packs)

@sannlas_coins_bp.route('/api/coins/share', methods=['POST'])
def share_coins():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    receiver_raw = data.get('receiver','').lower().strip()
    amount = int(data.get('amount',0))
    pin = data.get('pin','').strip()
    if not receiver_raw: return jsonify({'success':False,'message':'Enter receiver!'}),400
    if amount < 10: return jsonify({'success':False,'message':'Min 10 coins Boss!'}),400
    users = load_db('users.json', [])
    sender = next((u for u in users if (email and str(u.get('email','')).lower()==email) or (phone and str(u.get('phone',''))==phone)), None)
    if not sender:
        return jsonify({'success':False,'message':'Sender not found - Login again'}),404
    stored_pwd = str(sender.get('password','') or '')
    stored_pin = str(sender.get('coin_pin') or sender.get('pin') or '')
    is_correct = False
    if stored_pwd == hashlib.sha256(pin.encode()).hexdigest():
        is_correct = True
    elif stored_pin and pin == stored_pin:
        is_correct = True
    elif stored_pwd and len(stored_pwd) < 20 and pin == stored_pwd:
        is_correct = True
    if not is_correct:
        return jsonify({'success':False,'message':f'Wrong password Boss! Use YOUR login password!'}),400
    receiver = next((u for u in users if str(u.get('email','')).lower()==receiver_raw or str(u.get('phone','')).strip()==receiver_raw), None)
    if not receiver:
        return jsonify({'success':False,'message':f'Receiver {receiver_raw} not found!'}),404
    if str(sender.get('email','')).lower()==str(receiver.get('email','')).lower():
        return jsonify({'success':False,'message':'Cannot share to yourself!'}),400
    bought = int(sender.get('bought',0))
    earned = int(sender.get('earned',0))
    spent = int(sender.get('spent',0))
    total = bought + earned - spent
    if total < 0: total = 0
    if amount > total:
        return jsonify({'success':False,'message':f'You have {total} coins, cannot send {amount}'}),400
    fee = math.ceil(amount * 0.10)
    if fee < 1 and amount >=10: fee=1
    receiver_gets = amount - fee
    sender['spent'] = spent + amount
    sender['coins'] = int(sender.get('bought',0)) + int(sender.get('earned',0)) - int(sender['spent'])
    if sender['coins'] <0: sender['coins']=0
    receiver['earned'] = int(receiver.get('earned',0)) + receiver_gets
    receiver['earned_coins'] = receiver['earned']
    receiver['coins'] = int(receiver.get('bought',0)) + int(receiver.get('earned',0)) - int(receiver.get('spent',0))
    save_db('users.json', users)
    txs = load_db('coin_transactions.json', [])
    now=time.time()
    txs.append({'id': int(now*1000), 'email': sender.get('email'), 'phone': sender.get('phone'), 'coins': -amount, 'price': 0, 'momo_code': f'SHARE-SENT-{uuid.uuid4().hex[:6].upper()}', 'reason': f'Sent {amount} to {receiver_raw} (fee {fee}, they got {receiver_gets})', 'time': now, 'status': 'share_sent', 'to': receiver_raw, 'fee': fee})
    txs.append({'id': int(now*1000)+1, 'email': receiver.get('email'), 'phone': receiver.get('phone'), 'coins': receiver_gets, 'price': 0, 'momo_code': f'SHARE-RECV-{uuid.uuid4().hex[:6].upper()}', 'reason': f'Received {receiver_gets} from {sender.get("email")}', 'time': now, 'status': 'share_received', 'from': sender.get('email'), 'fee': fee})
    save_db('coin_transactions.json', txs)
    return jsonify({'success':True, 'message':f'Sent {amount}! {receiver_raw} got {receiver_gets}, fee {fee}', 'sent': amount, 'fee': fee, 'receiver_gets': receiver_gets})

@sannlas_coins_bp.route('/api/coins/share/history')
def share_history():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    txs = load_db('coin_transactions.json', [])
    filtered = [t for t in txs if ((email and str(t.get('email','')).lower()==email) or (phone and str(t.get('phone',''))==phone)) and str(t.get('status','')).startswith('share_')]
    history=[]
    for s in filtered:
        if s.get('status')=='share_sent':
            history.append({'type':'sent','amount':abs(s.get('coins',0)),'fee':s.get('fee',0),'to':s.get('to',''),'time':s.get('time',0)})
        else:
            history.append({'type':'received','amount':s.get('coins',0),'from':s.get('from',''),'time':s.get('time',0)})
    return jsonify({'success':True,'history':sorted(history, key=lambda x:x.get('time',0), reverse=True)[:20]})

@sannlas_coins_bp.route('/api/coins/set-pin', methods=['POST'])
def set_coin_pin():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    new_pin = str(data.get('pin','')).strip()
    if len(new_pin) < 4: return jsonify({'success':False,'message':'PIN min 4 digits'}),400
    users = load_db('users.json', [])
    for u in users:
        if (email and str(u.get('email','')).lower()==email) or (phone and str(u.get('phone',''))==phone):
            u['coin_pin'] = new_pin
            u['pin'] = new_pin
            save_db('users.json', users)
            return jsonify({'success':True,'message':f'PIN set to {new_pin}!'})
    return jsonify({'success':False,'message':'User not found'}),404
    
@sannlas_coins_bp.route('/api/coins/deduct', methods=['POST'])
def coins_deduct():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    coins = int(data.get('coins',1))
    reason = data.get('reason','Chat unlock')
    users = load_db('users.json', [])
    user = next((u for u in users if str(u.get('email','')).lower()==email), None)
    if not user:
        return jsonify({'success':False,'error':'User not found'}),404
    real_coins = int(user.get('bought',0)) + int(user.get('earned',0)) - int(user.get('spent',0))
    if real_coins < coins:
        return jsonify({'success':False,'error':'Not enough coins!'}),400
    user['spent'] = int(user.get('spent',0)) + coins
    user['coins'] = int(user.get('bought',0)) + int(user.get('earned',0)) - int(user.get('spent',0))
    txs = load_db('coin_transactions.json', [])
    txs.append({
        'id': int(time.time()*1000),
        'email': user.get('email'),
        'phone': user.get('phone'),
        'coins': -coins,
        'price': 0,
        'momo_code': f'SPENT-{uuid.uuid4().hex[:6].upper()}',
        'reason': reason,
        'time': time.time(),
        'status': 'spent'
    })
    save_db('coin_transactions.json', txs)
    save_db('users.json', users)
    return jsonify({'success':True,'new_balance': user['coins']})

@sannlas_coins_bp.route('/api/coins/admin/add', methods=['POST'])
def coins_admin_add():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    coins = int(data.get('coins',0))
    if not email or not coins:
        return jsonify({'success':False,'error':'Email and coins required'}),400
    users = load_db('users.json', [])
    user = next((u for u in users if str(u.get('email','')).lower()==email), None)
    if not user:
        return jsonify({'success':False,'error':'User not found'}),404
    user['earned'] = int(user.get('earned',0)) + coins
    user['earned_coins'] = user['earned']
    user['coins'] = int(user.get('bought',0)) + int(user.get('earned',0)) - int(user.get('spent',0))
    txs = load_db('coin_transactions.json', [])
    txs.append({
        'id': int(time.time()*1000),
        'email': user.get('email'),
        'phone': user.get('phone'),
        'coins': coins,
        'price': 0,
        'momo_code': f'ADMIN-{uuid.uuid4().hex[:6].upper()}',
        'reason': f'Admin bonus {coins} coins',
        'time': time.time(),
        'status': 'admin_bonus'
    })
    save_db('coin_transactions.json', txs)
    save_db('users.json', users)
    return jsonify({'success':True,'new_balance': user['coins']})
