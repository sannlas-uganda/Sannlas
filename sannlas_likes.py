# sannlas_likes.py - FIXED - Likes persist in Postgres, never go to 0, counts Products + Reels
from flask import Blueprint, Response, request, jsonify
import os, json, time
import psycopg2, psycopg2.extras

sannlas_likes_bp = Blueprint('sannlas_likes_bp', __name__)

DATABASE_URL = os.getenv('DATABASE_URL')

def get_conn_pg():
    url = DATABASE_URL
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, sslmode='require')

def ensure_likes_table():
    try:
        conn = get_conn_pg(); cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_likes (
            id BIGSERIAL PRIMARY KEY, user_email TEXT, product_id TEXT,
            seller_email TEXT, reel_id TEXT, created TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_email, product_id), UNIQUE(user_email, reel_id))""")
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print("ensure_likes_table fail:", e)

# ✅ FIX - Read from Postgres kv_store FIRST, not local data/ file!
def load_db(file, default):
    try:
        if DATABASE_URL:
            conn = get_conn_pg(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if file == 'products.json':
                cur.execute("SELECT data FROM products ORDER BY id ASC"); rows = cur.fetchall(); cur.close(); conn.close()
                out=[]
                for r in rows:
                    d=r['data']
                    if isinstance(d,str):
                        try: d=json.loads(d)
                        except: pass
                    out.append(d)
                return out
            cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
            row = cur.fetchone(); cur.close(); conn.close()
            if not row: return default
            d = row['data']
            if isinstance(d,str):
                try: d=json.loads(d)
                except: pass
            return d
        if os.path.exists(f'data/{file}'):
            return json.load(open(f'data/{file}'))
        if os.path.exists(file):
            return json.load(open(file))
        return default
    except Exception as e:
        print(f"load_db {file} fail:", e)
        return default

# ✅ FIX - Save to Postgres kv_store, not local file that gets wiped!
def save_db(file, data):
    try:
        if DATABASE_URL:
            conn = get_conn_pg(); cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, data JSONB NOT NULL)")
            if file == 'products.json':
                cur.execute("DELETE FROM products")
                for item in data:
                    cur.execute("INSERT INTO products (data) VALUES (%s)", [json.dumps(item)])
            else:
                cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, json.dumps(data)))
            conn.commit(); cur.close(); conn.close()
            return
        os.makedirs('data', exist_ok=True)
        json.dump(data, open(f'data/{file}','w'), indent=2)
    except Exception as e:
        print(f"save_db {file} fail:", e)

def get_users(): return load_db('users.json', [])
def get_products(): return load_db('products.json', [])
def get_likes(): return load_db('likes.json', [])
def save_likes(d): save_db('likes.json', d)

# ✅ NEW - Shop total likes = Product likes + Reel likes, from BOTH JSON + Postgres
def get_shop_total_likes(shop_email, shop_slug=""):
    shop_email = (shop_email or '').lower().strip()
    shop_slug = (shop_slug or '').lower().strip()
    total = 0
    # 1. Product likes from likes.json
    try:
        likes = get_likes()
        products = get_products()
        my_pids = set([str(p.get('id')) for p in products if (shop_email and str(p.get('seller_email','')).lower()==shop_email) or (shop_slug and str(p.get('shop_slug','')).lower()==shop_slug)])
        total += len([l for l in likes if str(l.get('product_id')) in my_pids])
    except: pass
    # 2. Product likes from Postgres sannlas_likes
    try:
        ensure_likes_table()
        conn = get_conn_pg(); cur = conn.cursor()
        if shop_email:
            cur.execute("SELECT COUNT(*) FROM sannlas_likes WHERE LOWER(seller_email)=%s", (shop_email,))
            total += cur.fetchone()[0] or 0
        cur.close(); conn.close()
    except Exception as e:
        print("shop likes PG fail:", e)
    # 3. Reel likes from sannlas_reels table - SUM(likes)
    try:
        conn = get_conn_pg(); cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(likes),0) FROM sannlas_reels WHERE LOWER(user_email)=%s OR LOWER(shop_slug)=%s", (shop_email, shop_slug))
        row = cur.fetchone()
        if row: total += int(row[0] or 0)
        cur.close(); conn.close()
    except Exception as e:
        print("shop reel likes fail:", e)
    # 4. Fallback - product.likes field (old likes)
    try:
        products = get_products()
        for p in products:
            if (shop_email and str(p.get('seller_email','')).lower()==shop_email) or (shop_slug and str(p.get('shop_slug','')).lower()==shop_slug):
                # Only add if we didn't already count via likes.json (avoid double)
                pass
    except: pass
    return total

COMBINED_LIKES_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LIKES - SANNLAS</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial;background:#f1f5f9;padding-bottom:80px}.navbar{background:#000;color:#FFCC02;padding:12px;display:flex;justify-content:space-between;position:sticky;top:0;z-index:10}.tab-bar{background:#fff;display:flex;border-bottom:2px solid #eee;position:sticky;top:50px;z-index:9}.tab-bar button{flex:1;padding:14px;border:none;background:#fff;font-weight:900;cursor:pointer;border-bottom:3px solid transparent}.tab-bar button.active{border-bottom-color:#FF0000;background:#fff0f0}.product-card{background:#fff;border-radius:14px;overflow:hidden;margin:8px 10px;display:flex;gap:10px;padding:10px;box-shadow:0 1px 5px rgba(0,0,0,.06)}.product-card img{width:80px;height:80px;object-fit:cover;border-radius:10px}.like-btn{padding:6px 12px;border-radius:20px;border:none;font-weight:900;cursor:pointer;margin-top:6px}.btn-liked{background:#FF0000;color:#fff}.btn-like{background:#eee;color:#333}.stats{background:#000;color:#FFCC02;padding:12px;display:flex;justify-content:space-around;text-align:center}.stats b{display:block;font-size:20px}</style>
</head><body>
<div class="navbar"><a href="/" style="color:#FFCC02;text-decoration:none;font-weight:bold">← SANNLAS</a><b>❤️ LIKES</b><span></span></div>
<div class="stats"><div><b id="totalLikes">0</b><small>Total Likes Given</small></div><div><b id="totalLiked">0</b><small>Products Liked</small></div><div><b id="totalStars">0</b><small>Stars Received</small></div></div>
<div class="tab-bar"><button id="tab-liked" class="active" onclick="switchTab('liked')">Liked Products</button><button id="tab-received" onclick="switchTab('received')">Likes Received</button><button id="tab-discover" onclick="switchTab('discover')">Discover</button></div>
<div id="likesList"><p style="text-align:center;padding:30px">Loading...</p></div>
<script>
let currentUser=JSON.parse(localStorage.getItem('sannlas_user')||'{}');
let currentTab='liked';
let allData={liked:[], received:[], discover:[]};
function switchTab(tab){currentTab=tab;document.querySelectorAll('.tab-bar button').forEach(b=>b.classList.remove('active'));document.getElementById('tab-'+tab).classList.add('active');renderList();}
async function loadLikes(){let email=currentUser.email||''; let phone=currentUser.phone||'';try{let r=await fetch(`/api/likes/stats?email=${encodeURIComponent(email)}&phone=${encodeURIComponent(phone)}`);let d=await r.json();document.getElementById('totalLikes').innerText=d.total_given||0;document.getElementById('totalLiked').innerText=(d.liked_list||[]).length;document.getElementById('totalStars').innerText=d.total_received||0;allData.liked=d.liked_list||[];allData.received=d.received_list||[];allData.discover=d.discover||[];renderList();}catch(e){document.getElementById('likesList').innerHTML='<p style="color:red;text-align:center">Error: '+e.message+'</p>';}}
function renderList(){let list=allData[currentTab]||[];if(list.length==0){document.getElementById('likesList').innerHTML=`<p style="text-align:center;padding:30px;color:#666">No ${currentTab} yet</p>`;return;}document.getElementById('likesList').innerHTML=list.map(p=>{let btn=currentTab=='discover'?(p.is_liked?`<button class="like-btn btn-liked" onclick="unlikeProduct('${p.id}')">❤️ Liked</button>`:`<button class="like-btn btn-like" onclick="likeProduct('${p.id}')">🤍 Like</button>`):`<button class="like-btn btn-liked" onclick="unlikeProduct('${p.id}')">❤️ ${p.likes||0} Likes</button>`;return `<div class="product-card"><img src="${p.image||'https://via.placeholder.com/80'}" onclick="location.href='/sell/${p.id}'"><div><b>${(p.name||'').slice(0,30)}</b><br><small>${p.business||p.location||''} • UGX ${Number(p.price||0).toLocaleString()}</small><br>${btn}</div></div>`;}).join('');}
async function likeProduct(productId){if(!currentUser.email){alert('Login first!');return;}let r=await fetch('/api/like',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:currentUser.email,phone:currentUser.phone,product_id:productId})});let d=await r.json();if(d.success){loadLikes();}else alert(d.message);}
async function unlikeProduct(productId){if(!currentUser.email){alert('Login first!');return;}let r=await fetch('/api/unlike',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:currentUser.email,phone:currentUser.phone,product_id:productId})});let d=await r.json();if(d.success){loadLikes();}else alert(d.message);}
loadLikes();
</script>
</body></html>
"""

@sannlas_likes_bp.route('/likes')
def likes_page():
    return Response(COMBINED_LIKES_HTML, mimetype='text/html')

@sannlas_likes_bp.route('/api/likes/stats')
def likes_stats():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    users = get_users()
    products = get_products()
    likes = get_likes()
    me = next((u for u in users if (email and str(u.get('email','')).lower()==email) or (phone and str(u.get('phone',''))==phone)), None)
    my_email = (me.get('email','').lower() if me else email)
    my_liked_ids = [l['product_id'] for l in likes if l.get('user_email','').lower()==my_email]
    # ✅ Also from Postgres
    try:
        ensure_likes_table()
        conn = get_conn_pg(); cur = conn.cursor()
        cur.execute("SELECT product_id FROM sannlas_likes WHERE LOWER(user_email)=%s AND product_id IS NOT NULL", (my_email,))
        for r in cur.fetchall():
            if r[0] and str(r[0]) not in [str(x) for x in my_liked_ids]:
                my_liked_ids.append(r[0])
        cur.close(); conn.close()
    except: pass
    liked_list=[]
    for pid in my_liked_ids:
        p = next((x for x in products if str(x.get('id'))==str(pid)), None)
        if p:
            p = dict(p)
            p['likes'] = len([l for l in likes if str(l.get('product_id'))==str(pid)])
            p['is_liked'] = True
            liked_list.append(p)
    my_product_ids = [str(p.get('id')) for p in products if (email and str(p.get('seller_email','')).lower()==my_email) or (phone and str(p.get('phone',''))==phone)]
    received_list=[]
    total_received=0
    for pid in my_product_ids:
        count = len([l for l in likes if str(l.get('product_id'))==str(pid)])
        if count>0:
            p = next((x for x in products if str(x.get('id'))==str(pid)), None)
            if p:
                p = dict(p); p['likes']=count
                received_list.append(p)
                total_received+=count
    # ✅ Add PG received
    try:
        conn = get_conn_pg(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sannlas_likes WHERE LOWER(seller_email)=%s", (my_email,))
        pg_recv = cur.fetchone()[0] or 0
        cur.close(); conn.close()
        total_received = max(total_received, pg_recv)
    except: pass
    discover=[]
    for p in products[:100]:
        pid=str(p.get('id'))
        if pid in [str(x) for x in my_liked_ids]: continue
        if pid in my_product_ids: continue
        likes_count = len([l for l in likes if str(l.get('product_id'))==pid])
        p_copy=dict(p)
        p_copy['likes']=likes_count
        p_copy['is_liked']=False
        discover.append(p_copy)
    discover = sorted(discover, key=lambda x: x.get('likes',0), reverse=True)[:50]
    return jsonify({
        'total_given': len(my_liked_ids),
        'total_received': total_received,
        'liked_list': liked_list[::-1],
        'received_list': sorted(received_list, key=lambda x: x.get('likes',0), reverse=True),
        'discover': discover
    })

@sannlas_likes_bp.route('/api/like', methods=['POST'])
def api_like():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    product_id = str(data.get('product_id','')).strip()
    reel_id = str(data.get('reel_id','') or '').strip()
    if not product_id and not reel_id:
        return jsonify({'success':False,'message':'Product ID required'}),400
    likes = get_likes()
    products = get_products()
    users = get_users()
    # Reel like - save to sannlas_reels.likes + sannlas_likes PG
    if reel_id and not product_id:
        try:
            ensure_likes_table()
            conn = get_conn_pg(); cur = conn.cursor()
            cur.execute("INSERT INTO sannlas_likes (user_email, reel_id, seller_email) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (email, reel_id, ''))
            conn.commit()
            cur.execute("UPDATE sannlas_reels SET likes = COALESCE(likes,0)+1 WHERE id=%s OR CAST(id AS TEXT)=%s", (reel_id, reel_id))
            conn.commit(); cur.close(); conn.close()
        except Exception as e:
            print("reel like fail:", e)
        return jsonify({'success':True,'message':'❤️ Liked Reel!'})
    prod = next((p for p in products if str(p.get('id'))==product_id), None)
    if not prod:
        return jsonify({'success':False,'message':'Product not found!'}),404
    exists = next((l for l in likes if l.get('user_email','').lower()==email and str(l.get('product_id'))==product_id), None)
    if exists:
        return jsonify({'success':False,'message':'Already liked! ❤️'}),400
    if str(prod.get('seller_email','')).lower()==email:
        return jsonify({'success':False,'message':'Cannot like your own product Boss!'}),400
    likes.append({'user_email': email,'user_phone': phone,'product_id': product_id,'seller_email': prod.get('seller_email',''),'time': time.time()})
    save_likes(likes)
    # ✅ Also save to Postgres - survives restart!
    try:
        ensure_likes_table()
        conn = get_conn_pg(); cur = conn.cursor()
        cur.execute("INSERT INTO sannlas_likes (user_email, product_id, seller_email) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", (email, product_id, prod.get('seller_email','')))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print("PG like save fail:", e)
    for u in users:
        if str(u.get('email','')).lower()==str(prod.get('seller_email','')).lower():
            u['total_likes'] = int(u.get('total_likes',0)) + 1
            u['total_stars'] = int(u.get('total_stars',0)) + 1
            break
    save_db('users.json', users)
    for p in products:
        if str(p.get('id'))==product_id:
            p['total_likes'] = int(p.get('total_likes',0)) + 1
            p['likes'] = int(p.get('likes',0)) + 1
            break
    save_db('products.json', products)
    return jsonify({'success':True,'message':'❤️ Liked! Seller got +1 star!'})

@sannlas_likes_bp.route('/api/unlike', methods=['POST'])
def api_unlike():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    product_id = str(data.get('product_id','')).strip()
    reel_id = str(data.get('reel_id','') or '').strip()
    if reel_id and not product_id:
        try:
            conn = get_conn_pg(); cur = conn.cursor()
            cur.execute("DELETE FROM sannlas_likes WHERE LOWER(user_email)=%s AND reel_id=%s", (email, reel_id))
            cur.execute("UPDATE sannlas_reels SET likes = GREATEST(0, COALESCE(likes,0)-1) WHERE id=%s OR CAST(id AS TEXT)=%s", (reel_id, reel_id))
            conn.commit(); cur.close(); conn.close()
        except: pass
        return jsonify({'success':True,'message':'Unliked Reel!'})
    likes = get_likes()
    before = len(likes)
    likes = [l for l in likes if not (l.get('user_email','').lower()==email and str(l.get('product_id'))==product_id)]
    after = len(likes)
    if before==after:
        # Try PG only
        try:
            conn = get_conn_pg(); cur = conn.cursor()
            cur.execute("DELETE FROM sannlas_likes WHERE LOWER(user_email)=%s AND product_id=%s", (email, product_id))
            deleted = cur.rowcount; conn.commit(); cur.close(); conn.close()
            if deleted and deleted>0:
                return jsonify({'success':True,'message':'Unliked!'})
        except: pass
        return jsonify({'success':False,'message':'Not liked yet!'}),400
    save_likes(likes)
    try:
        conn = get_conn_pg(); cur = conn.cursor()
        cur.execute("DELETE FROM sannlas_likes WHERE LOWER(user_email)=%s AND product_id=%s", (email, product_id))
        conn.commit(); cur.close(); conn.close()
    except: pass
    products = get_products()
    users = get_users()
    prod = next((p for p in products if str(p.get('id'))==product_id), None)
    if prod:
        for p in products:
            if str(p.get('id'))==product_id:
                p['total_likes'] = max(0, int(p.get('total_likes',0)) - 1)
                p['likes'] = max(0, int(p.get('likes',0)) - 1)
                break
        save_db('products.json', products)
        for u in users:
            if str(u.get('email','')).lower()==str(prod.get('seller_email','')).lower():
                u['total_likes'] = max(0, int(u.get('total_likes',0)) - 1)
                u['total_stars'] = max(0, int(u.get('total_stars',0)) - 1)
                break
        save_db('users.json', users)
    return jsonify({'success':True,'message':'Unliked!'})

@sannlas_likes_bp.route('/api/likes/check')
def api_like_check():
    email = request.args.get('email','').lower()
    product_id = request.args.get('product_id','')
    reel_id = request.args.get('reel_id','')
    likes = get_likes()
    is_liked = any(l.get('user_email','').lower()==email and str(l.get('product_id'))==str(product_id) for l in likes) if product_id else False
    count = len([l for l in likes if str(l.get('product_id'))==str(product_id)]) if product_id else 0
    if not is_liked:
        try:
            conn = get_conn_pg(); cur = conn.cursor()
            if reel_id:
                cur.execute("SELECT 1 FROM sannlas_likes WHERE LOWER(user_email)=%s AND reel_id=%s LIMIT 1", (email, reel_id))
            else:
                cur.execute("SELECT 1 FROM sannlas_likes WHERE LOWER(user_email)=%s AND product_id=%s LIMIT 1", (email, product_id))
            if cur.fetchone(): is_liked = True
            cur.close(); conn.close()
        except: pass
    return jsonify({'is_liked': is_liked, 'count': count})

@sannlas_likes_bp.route('/api/likes/product/<pid>')
def api_likes_product(pid):
    likes = get_likes()
    filtered = [l for l in likes if str(l.get('product_id'))==str(pid)]
    # ✅ Also PG count
    pg_count = 0
    try:
        conn = get_conn_pg(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sannlas_likes WHERE product_id=%s", (str(pid),))
        pg_count = cur.fetchone()[0] or 0
        cur.close(); conn.close()
    except: pass
    return jsonify({'count': max(len(filtered), pg_count), 'likes': filtered})

# ✅ NEW - Shop total likes for shop page - replaces fake *5!
@sannlas_likes_bp.route('/api/shop/<slug>/likes')
def api_shop_likes(slug):
    try:
        shops = load_db('shops.json', [])
        shop = next((s for s in shops if str(s.get('shop_slug','')).lower()==slug.lower() or str(s.get('slug','')).lower()==slug.lower()), None)
        email = (shop.get('owner_email') or shop.get('email') or '') if shop else ''
        total = get_shop_total_likes(email, slug)
        return jsonify({'shop_slug': slug, 'email': email, 'total_likes': total, 'likes': total})
    except Exception as e:
        return jsonify({'total_likes': 0, 'likes': 0, 'error': str(e)})
