from flask import Blueprint, request, jsonify, render_template_string
import os, json, time, random
from datetime import datetime

invite_bp = Blueprint('invite_bp', __name__)

# ===== NEON DB STANDALONE =====
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL: raise Exception("No DATABASE_URL")
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def ensure_tables():
    if not DATABASE_URL: return
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, data JSONB NOT NULL);")
        conn.commit(); cur.close(); conn.close()
    except: pass

def load_db(file, default):
    try:
        if DATABASE_URL:
            ensure_tables(); conn = get_conn()
            try:
                from psycopg.rows import dict_row
                cur = conn.cursor(row_factory=dict_row)
                cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
                row = cur.fetchone(); cur.close(); conn.close()
                if not row: return default
                d=row['data']; return d if not isinstance(d,str) else json.loads(d)
            except:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
                row = cur.fetchone(); cur.close(); conn.close()
                if not row: return default
                d=row['data']
                if isinstance(d,str):
                    try: d=json.loads(d)
                    except: pass
                return d
    except: return default

def save_db(file, data):
    if DATABASE_URL:
        try:
            ensure_tables(); conn = get_conn(); cur = conn.cursor()
            try:
                from psycopg.types.json import Jsonb
                cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, Jsonb(data)))
            except ImportError:
                cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, json.dumps(data)))
            conn.commit(); cur.close(); conn.close(); return
        except Exception as e: print("SAVE ERROR", e)
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

def get_referrals(): return load_db('referrals.json', {})
def save_referrals(d): save_db('referrals.json', d)

def get_all_users():
    try:
        users = load_db('users.json', {})
        if isinstance(users, dict): return users
        if isinstance(users, list):
            # convert list to dict
            out={}
            for u in users:
                if isinstance(u, dict) and u.get('email'):
                    out[u['email'].lower()]=u
                elif isinstance(u, dict) and u.get('phone'):
                    out[u['phone']]=u
            return out
        return {}
    except: return {}

COIN_VALUE = 599  # 1 Coin = UGX 599

# ===== API: GET MY REFERRAL LINK & STATS =====
@invite_bp.route('/api/my-referral', methods=['GET'])
def my_referral():
    phone = request.args.get('phone','').strip()
    email = request.args.get('email','').lower().strip()
    
    if not phone and not email:
        return jsonify({"success": False, "message": "Login first Boss!"})

    # Generate referral code from phone or email
    ref_code = ''
    if phone:
        # Clean phone to create code
        clean_phone = ''.join(filter(str.isdigit, phone))
        ref_code = clean_phone[-8:] if len(clean_phone)>=8 else clean_phone
    if not ref_code and email:
        ref_code = email.split('@')[0][:10]

    if not ref_code:
        return jsonify({"success": False, "message": "No phone/email found"})

    # Base URL
    base_url = request.host_url.rstrip('/')
    # If localhost, use real domain
    if 'localhost' in base_url or '127.0.0.1' in base_url:
        base_url = "https://sannlas.com"

    referral_link = f"{base_url}/?ref={ref_code}"
    # Also support /register?ref=
    # referral_link = f"{base_url}/register?ref={ref_code}"

    referrals = get_referrals()
    my_ref_data = referrals.get(ref_code, {"invites": [], "earned_coins": 0})
    
    # Ensure structure
    if isinstance(my_ref_data, list):
        my_ref_data = {"invites": my_ref_data, "earned_coins": len(my_ref_data)}
        referrals[ref_code]=my_ref_data
        save_referrals(referrals)

    invites = my_ref_data.get('invites', [])
    earned_coins = my_ref_data.get('earned_coins', len(invites))
    earned_ugx = earned_coins * COIN_VALUE

    return jsonify({
        "success": True,
        "link": referral_link,
        "ref_code": ref_code,
        "total_invites": len(invites),
        "earned_coins": earned_coins,
        "earned_ugx": earned_ugx,
        "invites": invites[-20:],  # last 20
        "coin_value": COIN_VALUE
    })

# ===== API: TRACK REFERRAL WHEN NEW USER REGISTERS =====
# Call this from your /api/register or /api/signup
@invite_bp.route('/api/referral/track', methods=['POST'])
def track_referral():
    try:
        data = request.get_json() or {}
        ref_code = data.get('ref') or data.get('ref_code') or request.args.get('ref','')
        new_phone = data.get('phone','')
        new_email = (data.get('email','') or '').lower()

        if not ref_code:
            return jsonify({"success": False, "message": "No ref code"}), 400

        ref_code = str(ref_code).strip()
        referrals = get_referrals()
        
        if ref_code not in referrals:
            referrals[ref_code]={"invites":[], "earned_coins":0}

        # Prevent duplicate invite
        existing_phones = [i.get('phone','') for i in referrals[ref_code]['invites']]
        existing_emails = [i.get('email','').lower() for i in referrals[ref_code]['invites']]

        if new_phone and new_phone in existing_phones:
            return jsonify({"success": True, "message": "Already counted"})
        if new_email and new_email.lower() in existing_emails:
            return jsonify({"success": True, "message": "Already counted"})

        invite = {
            "phone": new_phone,
            "email": new_email,
            "timestamp": int(time.time()),
            "created_at": datetime.now().isoformat(),
            "coin_earned": 1
        }
        referrals[ref_code]['invites'].append(invite)
        referrals[ref_code]['earned_coins'] = len(referrals[ref_code]['invites'])

        save_referrals(referrals)

        # Also add coin to referrer's wallet if exists
        try:
            wallets = load_db('wallets.json', {})
            # Find referrer by phone
            referrer_key = None
            for k in wallets.keys():
                if ref_code in k or ref_code[-4:] in k:
                    referrer_key = k
                    break
            # Simple: store by ref_code
            if ref_code not in wallets:
                wallets[ref_code]={"coins":0,"ugx":0}
            wallets[ref_code]['coins'] = referrals[ref_code]['earned_coins']
            wallets[ref_code]['ugx'] = wallets[ref_code]['coins'] * COIN_VALUE
            save_db('wallets.json', wallets)
        except: pass

        return jsonify({"success": True, "earned": 1, "coin_value": COIN_VALUE})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

# ===== PAGE ROUTES =====
@invite_bp.route('/invite')
@invite_bp.route('/invite-and-earn')
@invite_bp.route('/referral')
def invite_page():
    return render_template_string(INVITE_HTML)

INVITE_HTML = """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>Invite & Earn</title>
<style>body{background:#0f0f0f;color:white;font-family:Arial;padding:15px}.card{background:#1e1e1e;padding:20px;border-radius:12px;border:2px solid #FFCC02} input{width:95%;padding:12px;border-radius:8px;border:none;background:#000;color:#FFCC02;margin:8px 0} button{padding:12px;border-radius:8px;border:none;font-weight:bold;margin:3px;cursor:pointer}</style>
</head><body>
<div class="card">
<h2 style="color:#FFCC02">🔗 Invite & Earn 1 Coin = UGX 599!</h2>
<p>Share your link — when friend registers, you get 1 coin instantly!</p>
<input id="myLink" readonly placeholder="Loading link...">
<button onclick="copyLink()" style="background:#FFCC02;color:#000;width:100%">📋 COPY LINK</button>
<div style="display:flex;gap:5px;margin-top:10px">
<button onclick="shareWA()" style="background:#25D366;color:white;flex:1">WhatsApp</button>
<button onclick="shareFB()" style="background:#1877F2;color:white;flex:1">Facebook</button>
</div>
<div id="stats" style="margin-top:20px;background:#000;padding:15px;border-radius:10px;text-align:center">Loading...</div>
<a href="/" style="color:#aaa;display:block;text-align:center;margin-top:15px">← Back to Shop</a>
</div>
<script>
let userPhone = '';
let userEmail = '';
try{
  let u = JSON.parse(localStorage.getItem('sannlas_user')||localStorage.getItem('user')||'{}');
  userPhone = u.phone || '';
  userEmail = u.email || '';
}catch(e){}
if(!userPhone){
  userPhone = localStorage.getItem('user_phone')||'';
  userEmail = localStorage.getItem('user_email')||'';
}
function loadRef(){
 if(!userPhone && !userEmail){
   document.getElementById('stats').innerHTML = '🔒 Please login first Boss!<br><br><a href="/" style="color:#FFCC02">Go Home & Login</a>';
   document.getElementById('myLink').value = 'Login first to get link';
   return;
 }
 fetch(`/api/my-referral?phone=${encodeURIComponent(userPhone)}&email=${encodeURIComponent(userEmail)}`).then(r=>r.json()).then(d=>{
  if(!d.success){
    document.getElementById('stats').innerHTML = d.message + ' — <a href="/" style="color:#FFCC02">Login first</a>';
    document.getElementById('myLink').value = d.message;
    return;
  }
  document.getElementById('myLink').value = d.link;
  document.getElementById('stats').innerHTML = `<h3>👥 Invites: ${d.total_invites}</h3><h3 style="color:#00FF00">🪙 Earned: ${d.earned_coins} coins</h3><h3 style="color:#FFCC02">💵 UGX ${d.earned_ugx.toLocaleString()}</h3><div style="margin-top:10px;text-align:left">${(d.invites||[]).map(i=>`<div style="border-bottom:1px solid #333;padding:5px">📱 ${i.phone||''} - ${i.email||''}</div>`).join('') || '<p style="color:#888">No invites yet - Share now!</p>'}</div>`;
 }).catch(e=>{
   document.getElementById('stats').innerHTML = 'Error: '+e.message;
 });
}
function copyLink(){
  let v = document.getElementById('myLink').value;
  if(!v || v.includes('Login') || v.includes('Loading')){ alert('Login first Boss!'); return; }
  navigator.clipboard.writeText(v).then(()=>alert('Link Copied Boss! ✅')).catch(()=>{
    let input = document.getElementById('myLink'); input.select(); document.execCommand('copy'); alert('Link Copied Boss! ✅');
  });
}
function shareWA(){
  let v = document.getElementById('myLink').value;
  if(!v || v.includes('Login')){ alert('Login first'); return; }
  window.open(`https://wa.me/?text=Join Sannlas! Earn money selling! ${encodeURIComponent(v)}`)
}
function shareFB(){
  let v = document.getElementById('myLink').value;
  if(!v || v.includes('Login')){ alert('Login first'); return; }
  window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(v)}`)
}
loadRef();
</script>
</body></html>"""
