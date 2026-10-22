# sannlas_messages.py - ONE FILE = MESSAGES / CHAT SYSTEM - FINAL FIXED
from flask import Blueprint, Response, request, jsonify
import os, json, time

sannlas_messages_bp = Blueprint('sannlas_messages_bp', __name__)

def get_conn():
    try:
        DATABASE_URL = os.environ.get('DATABASE_URL','')
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://","postgresql://",1)
        if not DATABASE_URL:
            return None
        try:
            import psycopg
            return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
        except:
            import psycopg2
            return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except Exception as e:
        print("get_conn error:", e)
        return None

def ensure_chat_tables():
    conn=get_conn()
    if not conn:
        return
    try:
        cur=conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            buyer_email TEXT,
            shop_slug TEXT,
            sender TEXT,
            text TEXT,
            time BIGINT
        );
        CREATE TABLE IF NOT EXISTS chat_unlocks (
            id SERIAL PRIMARY KEY,
            buyer_email TEXT,
            shop_slug TEXT,
            unlock_type TEXT DEFAULT 'chat',
            unlocked_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(buyer_email, shop_slug, unlock_type)
        );
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("ensure_chat_tables error:", e)
        try: conn.close()
        except: pass

COMBINED_MESSAGES_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MESSAGES - SANNLAS</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial;background:#f1f5f9;height:100vh;display:flex;flex-direction:column}.navbar{background:#000;color:#FFCC02;padding:12px;display:flex;justify-content:space-between;position:sticky;top:0;z-index:10}.threads{width:100%;max-width:400px;background:#fff;border-right:1px solid #ddd;overflow-y:auto;flex:1}.thread{padding:12px;border-bottom:1px solid #eee;display:flex;gap:10px;cursor:pointer;align-items:center}.thread:hover{background:#fffde7}.thread.active{background:#FFCC02}.avatar{width:45px;height:45px;border-radius:50%;background:#000;color:#FFCC02;display:flex;align-items:center;justify-content:center;font-weight:900}.chat-area{flex:1;display:flex;flex-direction:column;background:#e5ddd5}.chat-header{background:#075e54;color:#fff;padding:12px;display:flex;align-items:center;gap:10px}.messages{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px}.msg{max-width:70%;padding:8px 12px;border-radius:10px;font-size:14px}.msg-buyer{align-self:flex-end;background:#dcf8c6}.msg-seller{align-self:flex-start;background:#fff}.input-bar{background:#f0f0f0;padding:8px;display:flex;gap:8px}.input-bar input{flex:1;padding:12px;border-radius:25px;border:none}.input-bar button{background:#25D366;color:#fff;border:none;padding:10px 16px;border-radius:50%;cursor:pointer;font-weight:900}.unlock-box{background:#fff;margin:10px;border-radius:12px;padding:20px;text-align:center;border:2px solid #FFCC02}.hidden{display:none}.container{display:flex;flex:1;overflow:hidden}@media(max-width:699px){.threads.hidden-mobile{display:none}.chat-area.hidden-mobile{display:none}.chat-area{position:fixed;top:0;left:0;right:0;bottom:0;z-index:20}}</style>
</head><body>
<div class="navbar"><a href="/" style="color:#FFCC02;text-decoration:none;font-weight:bold">← SANNLAS</a><b>💬 MESSAGES</b><span id="coinBal" style="background:#FFCC02;color:#000;padding:4px 8px;border-radius:10px;font-size:12px">0 coins</span></div>
<div class="container"><div id="threadsPanel" class="threads"><div style="padding:8px"><input id="searchThread" placeholder="Search chats..." oninput="filterThreads()" style="width:100%;padding:10px;border-radius:20px;border:1px solid #ddd"></div><div id="threadsList"><p style="text-align:center;padding:20px;color:#666">Loading threads...</p></div></div>
<div id="chatPanel" class="chat-area hidden-mobile"><div id="chatHeader" class="chat-header hidden"><div class="avatar" id="chatAvatar">S</div><div><b id="chatName">Shop</b><br><small id="chatStatus">Tap to view shop</small></div><button onclick="closeChat()" style="margin-left:auto;background:none;border:none;color:#fff;font-size:20px">✕</button></div>
<div id="unlockBox" class="unlock-box hidden"><h3>🔒 Unlock Chat - 1 Coin</h3><p style="color:#666;margin:8px 0">Pay 1 coin to chat forever!</p><button onclick="unlockChat()" style="background:#000;color:#FFCC02;padding:12px 20px;border-radius:20px;border:none;font-weight:900;cursor:pointer">🔓 Unlock for 1 Coin</button><p id="unlockStatus" style="margin-top:8px;font-weight:bold"></p></div>
<div id="messagesList" class="messages"></div><div id="inputBar" class="input-bar hidden"><input id="msgInput" placeholder="Type a message..." onkeypress="if(event.key==='Enter')sendMsg()"><button onclick="sendMsg()">➤</button></div><div id="noChatSelected" style="flex:1;display:flex;align-items:center;justify-content:center;flex-direction:column;color:#666"><p style="font-size:50px">💬</p><p>Select a chat</p><small>Private and secure</small></div></div></div>
<script>
let currentUser=JSON.parse(localStorage.getItem('sannlas_user')||'{}');
let currentShop=null; let currentBuyer=null; let isUnlocked=false; let threads=[];
async function loadBalance(){try{let r=await fetch(`/api/coins/balance?email=${encodeURIComponent(currentUser.email||'')}&phone=${encodeURIComponent(currentUser.phone||'')}`);let d=await r.json();document.getElementById('coinBal').innerText=(d.coins||0)+' coins';}catch(e){}}
async function loadThreads(){try{let email=currentUser.email||'';let shopSlug=currentUser.business?currentUser.business.toLowerCase().replace(/\s+/g,'-'):'';let url=`/api/chat/threads?shop=${encodeURIComponent(shopSlug)}`;if(!shopSlug)url=`/api/chat/my-threads?buyer=${encodeURIComponent(email)}`;let r=await fetch(url);let data=await r.json();threads=data||[];if(threads.length==0){let r2=await fetch(`/api/chat/my-threads?buyer=${encodeURIComponent(email)}`);let d2=await r2.json();threads=d2||[];}renderThreads();}catch(e){document.getElementById('threadsList').innerHTML='<p style="color:red;text-align:center">Error: '+e.message+'</p>';}}
function renderThreads(){let q=document.getElementById('searchThread').value.toLowerCase();let filtered=threads.filter(t=>(t.buyer_email||'').toLowerCase().includes(q)||(t.shop_slug||'').toLowerCase().includes(q));if(filtered.length==0){document.getElementById('threadsList').innerHTML='<p style="text-align:center;padding:20px;color:#666">No chats yet<br><small>Start from shop page!</small></p>';return;}document.getElementById('threadsList').innerHTML=filtered.map(t=>{let initial=(t.buyer_email||t.shop_slug||'U')[0].toUpperCase();let name=t.buyer_email?t.buyer_email.split('@')[0]:t.shop_slug;let last=t.last_text?t.last_text.slice(0,30):'New chat';return `<div class="thread" onclick="openChat('${t.shop_slug}','${t.buyer_email}')"><div class="avatar">${initial}</div><div style="flex:1"><b>${name}</b><br><small style="color:#666">${last}</small></div><small>${t.last_time?new Date(t.last_time*1000).toLocaleTimeString():''}</small></div>`;}).join('');}
function filterThreads(){renderThreads();}
async function openChat(shopSlug, buyerEmail){currentShop=shopSlug;currentBuyer=buyerEmail||currentUser.email;document.getElementById('noChatSelected').style.display='none';document.getElementById('chatHeader').classList.remove('hidden');document.getElementById('inputBar').classList.remove('hidden');document.getElementById('chatName').innerText=shopSlug||buyerEmail;document.getElementById('chatAvatar').innerText=(shopSlug||buyerEmail||'S')[0].toUpperCase();document.getElementById('threadsPanel').classList.add('hidden-mobile');document.getElementById('chatPanel').classList.remove('hidden-mobile');await checkUnlock();await loadMessages();}
function closeChat(){document.getElementById('threadsPanel').classList.remove('hidden-mobile');document.getElementById('chatPanel').classList.add('hidden-mobile');document.getElementById('noChatSelected').style.display='flex';document.getElementById('chatHeader').classList.add('hidden');document.getElementById('inputBar').classList.add('hidden');document.getElementById('unlockBox').classList.add('hidden');currentShop=null;}
async function checkUnlock(){try{let buyer=currentBuyer||currentUser.email;let r=await fetch(`/api/chat/check-unlock?buyer=${encodeURIComponent(buyer)}&shop=${encodeURIComponent(currentShop)}&type=chat`);let d=await r.json();isUnlocked=d.unlocked;document.getElementById('unlockBox').classList.toggle('hidden',isUnlocked);document.getElementById('messagesList').classList.toggle('hidden',!isUnlocked);document.getElementById('inputBar').classList.toggle('hidden',!isUnlocked);}catch(e){isUnlocked=false;document.getElementById('unlockBox').classList.remove('hidden');}}
async function unlockChat(){if(!currentUser.email){alert('Login first!');return;}document.getElementById('unlockStatus').innerText='Unlocking...';try{let r=await fetch('/api/chat/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({buyer_email:currentBuyer||currentUser.email,shop_slug:currentShop,type:'chat'})});let d=await r.json();document.getElementById('unlockStatus').innerText=d.success?'Unlocked!':'❌ '+d.error;if(d.success){isUnlocked=true;document.getElementById('unlockBox').classList.add('hidden');document.getElementById('messagesList').classList.remove('hidden');document.getElementById('inputBar').classList.remove('hidden');loadBalance();loadMessages();}}catch(e){document.getElementById('unlockStatus').innerText='Error: '+e.message;}}
async function loadMessages(){if(!currentShop||!currentBuyer)return;try{let r=await fetch(`/api/chat/history?buyer=${encodeURIComponent(currentBuyer)}&shop=${encodeURIComponent(currentShop)}`);let msgs=await r.json();document.getElementById('messagesList').innerHTML=msgs.map(m=>`<div class="msg ${m.sender==='buyer'?'msg-buyer':'msg-seller'}">${m.text}<br><small style="font-size:10px;color:#666">${new Date(m.time*1000).toLocaleTimeString()}</small></div>`).join('');document.getElementById('messagesList').scrollTop=document.getElementById('messagesList').scrollHeight;}catch(e){document.getElementById('messagesList').innerHTML='<p style="color:red">Failed</p>';}}
async function sendMsg(){let text=document.getElementById('msgInput').value.trim();if(!text)return;if(!isUnlocked){alert('Unlock chat first - 1 coin!');return;}let sender=(currentUser.email&&currentBuyer&&currentUser.email.toLowerCase()===currentBuyer.toLowerCase())?'buyer':'seller';try{await fetch('/api/chat/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({buyer_email:currentBuyer,shop_slug:currentShop,sender:sender,text:text})});document.getElementById('msgInput').value='';loadMessages();}catch(e){alert('Failed: '+e.message);}}
let params=new URLSearchParams(location.search);let shopParam=params.get('shop'); let buyerParam=params.get('buyer');if(shopParam){openChat(shopParam, buyerParam||currentUser.email);}
loadBalance(); loadThreads(); setInterval(()=>{if(currentShop)loadMessages();},3000);
</script>
</body></html>
"""

@sannlas_messages_bp.route('/messages')
def messages_page():
    return Response(COMBINED_MESSAGES_HTML, mimetype='text/html')

@sannlas_messages_bp.route('/api/chat/check-unlock')
def check_unlock_status():
    buyer = request.args.get('buyer','').lower().strip()
    shop = request.args.get('shop','').lower().strip()
    unlock_type = request.args.get('type','chat').lower().strip()
    conn = get_conn()
    if not conn:
        # Fallback to file if no DB
        try:
            data = json.load(open('data/chat_unlocks.json'))
            unlocked = any(u.get('buyer_email','').lower()==buyer and u.get('shop_slug','').lower()==shop and u.get('unlock_type','chat').lower()==unlock_type for u in data)
            return jsonify({"unlocked": unlocked})
        except:
            return jsonify({"unlocked": False})
    try:
        ensure_chat_tables()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM chat_unlocks WHERE LOWER(buyer_email)=%s AND LOWER(shop_slug)=%s AND LOWER(unlock_type)=%s", (buyer, shop, unlock_type))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({"unlocked": bool(row)})
    except Exception as e:
        print(f"check-unlock error: {e}")
        try: conn.close()
        except: pass
        return jsonify({"unlocked": False})

@sannlas_messages_bp.route('/api/chat/unlock', methods=['POST'])
def unlock_chat():
    try:
        data = request.get_json()
        buyer_email = data.get('buyer_email','').lower().strip()
        shop_slug = data.get('shop_slug','').lower().strip()
        unlock_type = data.get('type','chat').lower().strip()
        if not buyer_email or not shop_slug:
            return jsonify({"success": False, "error": "Missing data"}), 400

        conn = get_conn()
        if not conn:
            # File fallback
            os.makedirs('data', exist_ok=True)
            try: unlocks = json.load(open('data/chat_unlocks.json'))
            except: unlocks=[]
            if any(u.get('buyer_email','').lower()==buyer_email and u.get('shop_slug','').lower()==shop_slug for u in unlocks):
                return jsonify({"success": True, "already_unlocked": True})
            # Check coins from users.json
            try: users = json.load(open('data/users.json'))
            except: users=[]
            user = next((u for u in users if str(u.get('email','')).lower()==buyer_email), None)
            if not user or int(user.get('coins',0)) < 1:
                return jsonify({"success": False, "error": "Not enough coins! Buy coins Boss!"}), 400
            user['coins'] = int(user.get('coins',0)) - 1
            user['spent'] = int(user.get('spent',0)) + 1
            json.dump(users, open('data/users.json','w'), indent=2)
            unlocks.append({"buyer_email": buyer_email, "shop_slug": shop_slug, "unlock_type": unlock_type, "time": time.time()})
            json.dump(unlocks, open('data/chat_unlocks.json','w'), indent=2)
            return jsonify({"success": True, "new_balance": user['coins']})

        ensure_chat_tables()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM chat_unlocks WHERE LOWER(buyer_email)=%s AND LOWER(shop_slug)=%s AND LOWER(unlock_type)=%s", (buyer_email, shop_slug, unlock_type))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"success": True, "already_unlocked": True})
        cur.execute("SELECT coins FROM users WHERE LOWER(email)=%s", (buyer_email,))
        u = cur.fetchone()
        if not u or (u[0] or 0) < 1:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "Not enough coins! Buy coins Boss!"}), 400
        cur.execute("UPDATE users SET coins = coins - 1 WHERE LOWER(email)=%s RETURNING coins", (buyer_email,))
        new_balance = cur.fetchone()[0]
        cur.execute("INSERT INTO chat_unlocks (buyer_email, shop_slug, unlock_type, unlocked_at) VALUES (%s, %s, %s, NOW()) ON CONFLICT DO NOTHING", (buyer_email, shop_slug, unlock_type))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "new_balance": new_balance, "type": unlock_type})
    except Exception as e:
        print(f"unlock error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@sannlas_messages_bp.route('/api/chat/send', methods=['POST'])
def chat_send_new():
    try:
        data = request.get_json()
        buyer_email = data.get('buyer_email','').lower().strip()
        shop_slug = data.get('shop_slug','').lower().strip()
        sender = data.get('sender','buyer')
        text = data.get('text','').strip()
        if not text:
            return jsonify({"success": False}), 400
        conn = get_conn()
        if not conn:
            os.makedirs('data', exist_ok=True)
            try: msgs = json.load(open('data/chat_messages.json'))
            except: msgs=[]
            msgs.append({"buyer_email": buyer_email, "shop_slug": shop_slug, "sender": sender, "text": text, "time": int(time.time())})
            json.dump(msgs, open('data/chat_messages.json','w'), indent=2)
            return jsonify({"success": True})
        ensure_chat_tables()
        cur = conn.cursor()
        cur.execute("INSERT INTO chat_messages (buyer_email, shop_slug, sender, text, time) VALUES (%s, %s, %s, %s, %s)", (buyer_email, shop_slug, sender, text, int(time.time())))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print(f"send error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@sannlas_messages_bp.route('/api/chat/history')
def chat_history_new():
    buyer = request.args.get('buyer','').lower().strip()
    shop = request.args.get('shop','').lower().strip()
    conn = get_conn()
    if not conn:
        try:
            msgs = json.load(open('data/chat_messages.json'))
            filtered = [m for m in msgs if m.get('buyer_email','').lower()==buyer and m.get('shop_slug','').lower()==shop]
            filtered = sorted(filtered, key=lambda x: x.get('time',0))
            return jsonify(filtered)
        except:
            return jsonify([])
    try:
        ensure_chat_tables()
        cur = conn.cursor()
        cur.execute("SELECT sender, text, time FROM chat_messages WHERE LOWER(buyer_email)=%s AND LOWER(shop_slug)=%s ORDER BY time ASC", (buyer, shop))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        msgs = [{"sender": r[0], "text": r[1], "time": r[2]} for r in rows]
        return jsonify(msgs)
    except Exception as e:
        print(f"history error: {e}")
        try: conn.close()
        except: pass
        return jsonify([])

@sannlas_messages_bp.route('/api/chat/threads')
def chat_threads_new():
    shop = request.args.get('shop','').lower().strip()
    conn = get_conn()
    if not conn:
        try:
            msgs = json.load(open('data/chat_messages.json'))
            # Group by buyer
            groups={}
            for m in msgs:
                if shop and m.get('shop_slug','').lower()!=shop: continue
                buyer=m.get('buyer_email')
                if buyer not in groups or m.get('time',0) > groups[buyer].get('time',0):
                    groups[buyer]=m
            result=[{"buyer_email": k, "shop_slug": v.get('shop_slug'), "last_time": v.get('time'), "last_text": v.get('text')} for k,v in groups.items()]
            return jsonify(sorted(result, key=lambda x: x.get('last_time',0), reverse=True))
        except:
            return jsonify([])
    try:
        ensure_chat_tables()
        cur = conn.cursor()
        cur.execute("""
        SELECT DISTINCT ON (buyer_email) buyer_email, shop_slug, text, time 
        FROM chat_messages 
        WHERE LOWER(shop_slug)=%s 
        ORDER BY buyer_email, time DESC
        """, (shop,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        # Need last text per buyer - get max time
        result=[]
        for r in rows:
            result.append({"buyer_email": r[0], "shop_slug": r[1], "last_text": r[2], "last_time": r[3]})
        return jsonify(sorted(result, key=lambda x: x.get('last_time',0), reverse=True))
    except Exception as e:
        print(f"threads error: {e}")
        try: conn.close()
        except: pass
        return jsonify([])

@sannlas_messages_bp.route('/api/chat/my-threads')
def my_threads():
    buyer = request.args.get('buyer','').lower().strip()
    conn = get_conn()
    if not conn:
        try:
            msgs = json.load(open('data/chat_messages.json'))
            groups={}
            for m in msgs:
                if m.get('buyer_email','').lower()!=buyer: continue
                shop=m.get('shop_slug')
                if shop not in groups or m.get('time',0) > groups[shop].get('time',0):
                    groups[shop]=m
            result=[{"buyer_email": v.get('buyer_email'), "shop_slug": k, "last_time": v.get('time'), "last_text": v.get('text')} for k,v in groups.items()]
            return jsonify(sorted(result, key=lambda x: x.get('last_time',0), reverse=True))
        except:
            return jsonify([])
    try:
        ensure_chat_tables()
        cur = conn.cursor()
        cur.execute("""
        SELECT DISTINCT ON (shop_slug) shop_slug, buyer_email, text, time
        FROM chat_messages
        WHERE LOWER(buyer_email)=%s
        ORDER BY shop_slug, time DESC
        """, (buyer,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result=[{"shop_slug": r[0], "buyer_email": r[1], "last_text": r[2], "last_time": r[3]} for r in rows]
        return jsonify(sorted(result, key=lambda x: x.get('last_time',0), reverse=True))
    except Exception as e:
        print(f"my-threads error: {e}")
        try: conn.close()
        except: pass
        return jsonify([])
